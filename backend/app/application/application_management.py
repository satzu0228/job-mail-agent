from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.application.schemas import (
    ApplicationAgentInput,
    ApplicationAgentOutput,
    ApplicationAnalysisFacts,
    ApplicationCandidate,
    ApplicationRecommendation,
    CandidateScoreBreakdown,
)
from app.application.schemas import (
    ApplicationMatchResponse,
    ReviewDecision,
    ReviewDecisionResponse,
)
from app.application.task_linkage import settle_interview_tasks
from app.domain.application_state import StageTransitionStatus, validate_stage_transition
from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    DecisionSource,
    EmailCategory,
    ExecutionStatus,
    ExecutorType,
    InterviewResult,
    InterviewRoundSource,
    ReplyDraftStatus,
    ReviewActionType,
    ReviewTaskStatus,
    RiskLevel,
    TaskStatus,
    TaskType,
    WorkflowRunStatus,
)
from app.infrastructure.db.models.action_execution import ActionExecution
from app.infrastructure.db.models.application_event import ApplicationEvent
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.interview_round import InterviewRound
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.reply_draft import ReplyDraft
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.models.workflow_run import WorkflowRun
from app.infrastructure.db.repositories import (
    EmailRepository,
    EntityNotFoundError,
    ResourceConflictError,
    VersionConflictError,
)


class ApplicationRunner(Protocol):
    prompt_version: str

    def run(self, agent_input: ApplicationAgentInput) -> ApplicationAgentOutput: ...


class ApplicationAnalysisUnavailableError(RuntimeError):
    """邮件没有可用于申请匹配的当前求职分析。"""


class ApplicationModelExecutionError(RuntimeError):
    """Application Agent 执行或输出校验失败。"""


@dataclass(frozen=True, slots=True)
class RecordedReviewDecision:
    task: ReviewTask
    should_resume: bool


class ApplicationManagementService:
    def __init__(
        self,
        session: Session,
        user_id: int,
        application_agent: ApplicationRunner,
        *,
        model_provider: str,
        model_name: str,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._agent = application_agent
        self._model_provider = model_provider
        self._model_name = model_name
        self._emails = EmailRepository(session, user_id)

    def match_email(
        self,
        email_id: int,
        *,
        workflow_run_id: str | None = None,
    ) -> ApplicationMatchResponse:
        email = self._emails.get(email_id)
        analysis = self._current_analysis(email_id)
        self._validate_analysis(analysis)

        idempotency_key = (
            f"match-application:{email_id}:{analysis.id}"
            if workflow_run_id is None
            else f"workflow-match:{workflow_run_id}:{analysis.id}"
        )
        existing = self._session.scalar(
            select(ReviewTask).where(ReviewTask.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return self._response_from_task(existing)

        candidates, conflict_reasons = self._find_candidates(email, analysis)
        facts = self._analysis_facts(email, analysis)
        agent_input = ApplicationAgentInput(
            analysis=facts,
            candidates=candidates,
            deterministic_conflict=bool(conflict_reasons),
            conflict_reasons=conflict_reasons,
        )

        # 模型调用期间不持有数据库事务或行锁。
        self._session.rollback()
        model_started = perf_counter()
        try:
            suggestion = self._agent.run(agent_input)
        except Exception as exc:
            if workflow_run_id is not None:
                model_duration_ms = round((perf_counter() - model_started) * 1000, 2)
                with self._session.begin():
                    workflow = self._session.get(WorkflowRun, workflow_run_id)
                    if workflow is not None:
                        workflow.agent_trace = [
                            *workflow.agent_trace,
                            {
                                "agent": "application",
                                "node": "match_application",
                                "prompt_version": self._agent.prompt_version,
                                "status": "FAILED",
                                "error_code": "MODEL_EXECUTION_ERROR",
                                "error_message": "申请匹配模型执行失败",
                                "duration_ms": model_duration_ms,
                                "recorded_at": _utc_now().isoformat(),
                            },
                        ]
            raise ApplicationModelExecutionError("申请匹配模型执行失败") from exc
        model_duration_ms = round((perf_counter() - model_started) * 1000, 2)
        self._validate_agent_output(suggestion, candidates, facts)

        with self._session.begin():
            # 模型返回后重新读取当前分析，避免对过期版本创建审核任务。
            current = self._current_analysis(email_id)
            if current.id != analysis.id:
                raise ResourceConflictError("邮件当前分析已变化，请重新执行申请匹配")
            review_task = self._create_match_review(
                email=email,
                analysis=current,
                candidates=candidates,
                suggestion=suggestion,
                idempotency_key=idempotency_key,
                workflow_run_id=workflow_run_id,
                model_duration_ms=model_duration_ms,
            )
        return ApplicationMatchResponse(
            email_id=email_id,
            analysis_id=analysis.id,
            candidates=candidates,
            suggestion=suggestion,
            review_task_id=review_task.id,
        )

    def _current_analysis(self, email_id: int) -> EmailAnalysis:
        analysis = self._session.scalar(
            select(EmailAnalysis).where(
                EmailAnalysis.email_id == email_id,
                EmailAnalysis.is_current.is_(True),
            )
        )
        if analysis is None:
            raise ApplicationAnalysisUnavailableError("邮件尚无当前分析结果")
        return analysis

    @staticmethod
    def _validate_analysis(analysis: EmailAnalysis) -> None:
        if not analysis.is_job_related:
            raise ApplicationAnalysisUnavailableError("非求职邮件不能匹配求职申请")

    def _find_candidates(
        self,
        email: Email,
        analysis: EmailAnalysis,
    ) -> tuple[list[ApplicationCandidate], list[str]]:
        applications = list(
            self._session.scalars(
                select(JobApplication)
                .where(JobApplication.user_id == self._user_id)
                .order_by(JobApplication.updated_at.desc(), JobApplication.id.desc())
                .limit(100)
            )
        )
        application_ids = [application.id for application in applications]
        linked_sender_ids = (
            set(
                self._session.scalars(
                    select(Email.application_id).where(
                        Email.application_id.in_(application_ids),
                        func.lower(Email.from_address)
                        == email.from_address.strip().casefold(),
                    )
                )
            )
            if application_ids
            else set()
        )
        candidate_values: list[ApplicationCandidate] = []
        for application in applications:
            candidate = _score_candidate(
                email,
                analysis,
                application,
                linked_sender_match=application.id in linked_sender_ids,
            )
            if _is_candidate_eligible(email, analysis, application, candidate):
                candidate_values.append(candidate)
        candidate_values.sort(
            key=lambda item: (-item.deterministic_score, item.application_id)
        )
        candidates = candidate_values[:10]

        reasons: list[str] = []
        if len(candidates) >= 2:
            if candidates[0].deterministic_score - candidates[1].deterministic_score < 0.12:
                reasons.append("排名前两位候选分数接近")
            if analysis.position_name is None and (
                candidates[0].score_breakdown.company > 0
                and candidates[1].score_breakdown.company > 0
            ):
                reasons.append("邮件缺少岗位且同公司存在多个候选申请")
        if candidates and candidates[0].deterministic_score < 0.5:
            reasons.append("最高候选的确定性匹配分数不足")
        return candidates, reasons

    @staticmethod
    def _analysis_facts(
        email: Email,
        analysis: EmailAnalysis,
    ) -> ApplicationAnalysisFacts:
        extraction = analysis.extraction_json
        stage_payload = extraction.get("proposed_stage")
        proposed_stage = (
            ApplicationStage(stage_payload["value"])
            if isinstance(stage_payload, dict) and stage_payload.get("value")
            else None
        )
        return ApplicationAnalysisFacts(
            email_id=email.id,
            category=analysis.category,
            sender_address=email.from_address,
            company_name=analysis.company_name,
            position_name=analysis.position_name,
            proposed_stage=proposed_stage,
            event_type=analysis.event_type,
            summary=analysis.summary,
        )

    @staticmethod
    def _validate_agent_output(
        suggestion: ApplicationAgentOutput,
        candidates: list[ApplicationCandidate],
        facts: ApplicationAnalysisFacts,
    ) -> None:
        candidate_ids = {candidate.application_id for candidate in candidates}
        selected = suggestion.selected_application_id
        if selected is not None and selected not in candidate_ids:
            raise ApplicationModelExecutionError("申请匹配模型选择了候选列表外的申请")
        ranked_ids = {item.application_id for item in suggestion.candidate_rankings}
        if not ranked_ids <= candidate_ids:
            raise ApplicationModelExecutionError("申请匹配模型排序了候选列表外的申请")
        if suggestion.proposed_stage not in {None, facts.proposed_stage}:
            raise ApplicationModelExecutionError("申请匹配模型改写了抽取阶段建议")

    def _create_match_review(
        self,
        *,
        email: Email,
        analysis: EmailAnalysis,
        candidates: list[ApplicationCandidate],
        suggestion: ApplicationAgentOutput,
        idempotency_key: str,
        workflow_run_id: str | None,
        model_duration_ms: float,
    ) -> ReviewTask:
        now = _utc_now()
        if workflow_run_id is None:
            run_id = str(uuid4())
            workflow = WorkflowRun(
                id=run_id,
                thread_id=str(uuid4()),
                user_id=self._user_id,
                email_id=email.id,
                status=WorkflowRunStatus.WAITING_REVIEW,
                current_node="application_review",
                graph_version="phase-6-standalone.v1",
                model_provider=self._model_provider,
                model_name=self._model_name,
                prompt_versions={"application": self._agent.prompt_version},
                agent_trace=[],
                started_at=now,
            )
            self._session.add(workflow)
            # 两表存在 pending_review_task_id 循环外键，先落库工作流再创建审核任务。
            self._session.flush()
        else:
            run_id = workflow_run_id
            workflow = self._session.get(WorkflowRun, run_id)
            if (
                workflow is None
                or workflow.user_id != self._user_id
                or workflow.email_id != email.id
            ):
                raise ResourceConflictError("工作流与当前邮件不匹配")
            workflow.status = WorkflowRunStatus.WAITING_REVIEW
            workflow.current_node = "human_review"
            workflow.prompt_versions = {
                **workflow.prompt_versions,
                "application": self._agent.prompt_version,
            }
        workflow.agent_trace = [
            *workflow.agent_trace,
            {
                "agent": "application",
                "node": "match_application",
                "prompt_version": self._agent.prompt_version,
                "confidence": suggestion.confidence,
                "recommendation": suggestion.recommendation.value,
                "output": suggestion.model_dump(mode="json"),
                "status": "SUCCEEDED",
                "duration_ms": model_duration_ms,
                "recorded_at": now.isoformat(),
            },
        ]
        selected = suggestion.selected_application_id
        selected_application = (
            self._session.get(JobApplication, selected) if selected is not None else None
        )
        action_type = _application_review_action(suggestion, candidates)

        # 新建申请时忽略 LLM 选中的低分候选，确保 payload 一致性
        if action_type is ReviewActionType.CREATE_APPLICATION:
            selected = None
            selected_application = None

        # 关键：如果推荐新建申请，但已存在同一公司/发件人的待审核新建申请，
        # 则改为关联申请以推迟解析，避免重复创建。
        deferred_source: str | None = None
        if action_type is ReviewActionType.CREATE_APPLICATION:
            deferred_source = self._find_pending_create_review(
                sender_address=email.from_address,
                company_name=analysis.company_name,
                exclude_email_id=email.id,
            )
            if deferred_source is not None:
                action_type = ReviewActionType.LINK_APPLICATION

        payload = {
            "schema_version": "application-review.v1",
            "analysis_id": analysis.id,
            "recommendation": suggestion.recommendation.value,
            "application_id": selected,
            "application_version": (
                selected_application.version if selected_application is not None else None
            ),
            "company_name": analysis.company_name,
            "position_name": analysis.position_name,
            "proposed_stage": (
                suggestion.proposed_stage.value if suggestion.proposed_stage else None
            ),
            "event_type": analysis.event_type,
            "summary": analysis.summary,
            "interview_result": _extracted_interview_result(
                analysis.extraction_json
            ),
            "interview_round": _infer_round_from_extraction(
                analysis.extraction_json,
                selected,
            ),
            "deferred_source_review_task_id": deferred_source,
            "agent_output": suggestion.model_dump(mode="json"),
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        }
        if selected_application is not None and suggestion.proposed_stage is not None:
            validation = validate_stage_transition(
                selected_application.current_stage,
                suggestion.proposed_stage,
            )
            payload["stage_validation"] = {
                "status": validation.status.value,
                "reason": validation.reason,
            }
        task = ReviewTask(
            id=str(uuid4()),
            user_id=self._user_id,
            workflow_run_id=run_id,
            source_email_id=email.id,
            application_id=selected,
            action_type=action_type,
            risk_level=RiskLevel.HIGH,
            proposed_payload=payload,
            status=ReviewTaskStatus.PENDING,
            idempotency_key=idempotency_key,
            resource_version=selected_application.version if selected_application else 0,
        )
        self._session.add(task)
        self._session.flush()
        workflow.pending_review_task_id = task.id
        return task

    def _find_pending_create_review(
        self,
        *,
        sender_address: str,
        company_name: str | None,
        exclude_email_id: int | None = None,
    ) -> str | None:
        """查找同一发件人或公司的待审核新建申请，用于推迟关联。"""
        conditions = [
            ReviewTask.user_id == self._user_id,
            ReviewTask.action_type == ReviewActionType.CREATE_APPLICATION,
            ReviewTask.status == ReviewTaskStatus.PENDING,
        ]
        if exclude_email_id is not None:
            conditions.append(ReviewTask.source_email_id != exclude_email_id)

        pending_tasks = list(
            self._session.scalars(
                select(ReviewTask).where(*conditions).order_by(ReviewTask.created_at.asc())
            )
        )
        if not pending_tasks:
            return None

        normalized_sender = sender_address.strip().casefold()
        for task in pending_tasks:
            payload = task.proposed_payload
            task_company = (payload.get("company_name") or "").strip().casefold()
            if company_name and task_company:
                # 使用模糊匹配，去除标点后比较
                import re as _re
                norm_payload_company = _re.sub(r"[\W_]+", "", task_company)
                norm_analysis_company = _re.sub(r"[\W_]+", "", (company_name or "").casefold())
                if norm_payload_company and norm_payload_company == norm_analysis_company:
                    return task.id
            # 同一发件人的也视为候选（同公司多岗位场景）
            if normalized_sender:
                task_sender = self._email_sender(task.source_email_id)
                if task_sender and task_sender.casefold() == normalized_sender:
                    return task.id
        return None

    def _email_sender(self, email_id: int | None) -> str | None:
        if email_id is None:
            return None
        email = self._session.get(Email, email_id)
        return email.from_address if email else None

    def _resolve_deferred_application(self, source_review_task_id: str) -> JobApplication | None:
        """从源审核任务的执行结果中解析已创建的申请。"""
        execution = self._session.scalar(
            select(ActionExecution)
            .where(ActionExecution.review_task_id == source_review_task_id)
            .order_by(ActionExecution.attempt_no.desc())
            .limit(1)
        )
        if execution is None or execution.result is None:
            return None
        application_id = execution.result.get("application_id")
        if not isinstance(application_id, int):
            return None
        return self._session.get(JobApplication, application_id)

    @staticmethod
    def _response_from_task(task: ReviewTask) -> ApplicationMatchResponse:
        payload = task.proposed_payload
        return ApplicationMatchResponse(
            email_id=task.source_email_id,
            analysis_id=payload["analysis_id"],
            candidates=[
                ApplicationCandidate.model_validate(item)
                for item in payload.get("candidates", [])
            ],
            suggestion=ApplicationAgentOutput.model_validate(payload["agent_output"]),
            review_task_id=task.id,
        )


class ReviewTaskService:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def list(self, *, offset: int, limit: int) -> list[ReviewTask]:
        return list(
            self._session.scalars(
                select(ReviewTask)
                .where(ReviewTask.user_id == self._user_id)
                .order_by(ReviewTask.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def query(
        self,
        *,
        offset: int,
        limit: int,
        status: ReviewTaskStatus | None = None,
        action_type: ReviewActionType | None = None,
    ) -> tuple[list[ReviewTask], int]:
        conditions = [ReviewTask.user_id == self._user_id]
        if status is not None:
            conditions.append(ReviewTask.status == status)
        if action_type is not None:
            conditions.append(ReviewTask.action_type == action_type)
        total = int(
            self._session.scalar(
                select(func.count(ReviewTask.id)).where(*conditions)
            )
            or 0
        )
        statement = (
            select(ReviewTask)
            .where(*conditions)
            .order_by(ReviewTask.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement)), total

    def get(self, task_id: str, *, for_update: bool = False) -> ReviewTask:
        statement = select(ReviewTask).where(
            ReviewTask.id == task_id,
            ReviewTask.user_id == self._user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        task = self._session.scalar(statement)
        if task is None:
            raise EntityNotFoundError(f"Review task {task_id} does not exist")
        return task

    def decide(
        self,
        task_id: str,
        decision: ReviewDecision,
    ) -> ReviewDecisionResponse:
        recorded = self.record_decision(task_id, decision, update_workflow=True)
        if not recorded.should_resume:
            return self._existing_response(recorded.task)
        if recorded.task.status is ReviewTaskStatus.REJECTED:
            return ReviewDecisionResponse(review_task=recorded.task)
        if recorded.task.action_type is ReviewActionType.SEND_REPLY:
            return self._existing_response(recorded.task)
        return self.execute_decided(task_id, update_workflow=True)

    def record_decision(
        self,
        task_id: str,
        decision: ReviewDecision,
        *,
        update_workflow: bool,
    ) -> RecordedReviewDecision:
        with self._session.begin():
            task = self.get(task_id, for_update=True)
            if task.status is ReviewTaskStatus.SUCCEEDED:
                return RecordedReviewDecision(task=task, should_resume=False)
            if task.status is ReviewTaskStatus.REJECTED and not decision.approve:
                return RecordedReviewDecision(task=task, should_resume=False)
            if task.status is not ReviewTaskStatus.PENDING:
                raise ResourceConflictError(
                    f"审核任务当前状态 {task.status.value} 不允许提交决策"
                )
            if task.version != decision.version:
                raise VersionConflictError(
                    f"Resource version changed: expected {decision.version}, actual {task.version}"
                )

            now = _utc_now()
            task.reviewed_payload = decision.reviewed_payload
            task.decision_source = DecisionSource.USER
            task.decision_reason = decision.reason
            task.reviewed_at = now
            if not decision.approve:
                task.status = ReviewTaskStatus.REJECTED
                self._update_reply_draft_after_decision(task, approved=False)
                if update_workflow:
                    self._update_workflow_after_decision(task, follow_up=None)
                self._session.flush()
                return RecordedReviewDecision(task=task, should_resume=True)

            payload = dict(task.proposed_payload)
            if decision.reviewed_payload:
                payload.update(decision.reviewed_payload)
            self._validate_approved_payload(task, payload)
            task.status = ReviewTaskStatus.APPROVED
            self._update_reply_draft_after_decision(task, approved=True)
            self._session.flush()
            return RecordedReviewDecision(task=task, should_resume=True)

    def execute_decided(
        self,
        task_id: str,
        *,
        update_workflow: bool,
    ) -> ReviewDecisionResponse:
        with self._session.begin():
            task = self.get(task_id, for_update=True)
            if task.status is ReviewTaskStatus.SUCCEEDED:
                return self._existing_response(task)
            if task.status is ReviewTaskStatus.REJECTED:
                return ReviewDecisionResponse(review_task=task)
            if task.status is not ReviewTaskStatus.APPROVED:
                raise ResourceConflictError(
                    f"审核任务当前状态 {task.status.value} 不允许执行"
                )

            payload = dict(task.proposed_payload)
            if task.reviewed_payload:
                payload.update(task.reviewed_payload)
            self._validate_approved_payload(task, payload)
            now = _utc_now()
            task.status = ReviewTaskStatus.EXECUTING
            is_task_action = task.action_type is ReviewActionType.CREATE_TASK
            execution = ActionExecution(
                review_task_id=task.id,
                attempt_no=1,
                idempotency_key=f"execute:{task.id}:1",
                executor_type=(ExecutorType.TASK if is_task_action else ExecutorType.APPLICATION),
                status=ExecutionStatus.RUNNING,
                started_at=now,
            )
            self._session.add(execution)
            self._session.flush()

            if is_task_action:
                scheduled_task = self._execute_task(task, payload)
                application = self._owned_application(scheduled_task.application_id)
                follow_up = None
                external_reference = f"task:{scheduled_task.id}"
                result = {
                    "task_id": scheduled_task.id,
                    "application_id": application.id,
                    "email_id": task.source_email_id,
                    "follow_up_review_task_id": None,
                }
            else:
                application = self._execute(task, payload)
                follow_up = self._create_stage_follow_up(task, application, payload)
                if follow_up is None:
                    follow_up = self._create_task_follow_up(task, application)
                external_reference = f"job_application:{application.id}"
                result = {
                    "application_id": application.id,
                    "email_id": task.source_email_id,
                    "follow_up_review_task_id": follow_up.id if follow_up else None,
                }
            execution.status = ExecutionStatus.SUCCEEDED
            execution.external_reference = external_reference
            execution.result = result
            execution.finished_at = _utc_now()
            task.status = ReviewTaskStatus.SUCCEEDED
            if update_workflow:
                self._update_workflow_after_decision(task, follow_up=follow_up)
            self._session.flush()
            return ReviewDecisionResponse(
                review_task=task,
                execution=execution,
                follow_up_review_task=follow_up,
            )

    def _validate_approved_payload(
        self,
        task: ReviewTask,
        payload: dict[str, Any],
    ) -> None:
        if task.action_type is ReviewActionType.LINK_APPLICATION:
            application_id = payload.get("application_id")
            deferred_source = payload.get("deferred_source_review_task_id")
            # 支持推迟关联：有 deferred_source 时不需要在载荷中直接提供 application_id
            if not isinstance(application_id, int) or application_id <= 0:
                if not isinstance(deferred_source, str) or not deferred_source:
                    raise ResourceConflictError("批准关联申请时必须明确 application_id 或推迟关联源")
                # 验证推迟源存在且已执行成功
                source_task = self._session.get(ReviewTask, deferred_source)
                if source_task is None or source_task.user_id != self._user_id:
                    raise ResourceConflictError("推迟关联引用的审核任务不存在")
                return
            application = self._owned_application(application_id)
            expected_version = payload.get("application_version")
            if expected_version is not None and application.version != expected_version:
                raise VersionConflictError(
                    f"Resource version changed: expected {expected_version}, "
                    f"actual {application.version}"
                )
            email = self._owned_email(task.source_email_id)
            if email.application_id not in {None, application_id}:
                raise ResourceConflictError("邮件已关联到其他求职申请")
        elif task.action_type is ReviewActionType.CREATE_APPLICATION:
            for field_name in ("company_name", "position_name"):
                value = payload.get(field_name)
                if not isinstance(value, str) or not value.strip():
                    raise ResourceConflictError(f"批准新建申请时必须明确 {field_name}")
        elif task.action_type is ReviewActionType.UPDATE_APPLICATION_STAGE:
            application = self._owned_application(task.application_id)
            if application.version != task.resource_version:
                raise VersionConflictError(
                    f"Resource version changed: expected {task.resource_version}, "
                    f"actual {application.version}"
                )
            proposed = _application_stage(payload.get("proposed_stage"))
            validation = validate_stage_transition(application.current_stage, proposed)
            result = _interview_result(payload.get("interview_result"))
            result_change = (
                proposed is ApplicationStage.INTERVIEW
                and result is not None
                and result is not application.interview_result
            )
            if not validation.can_apply and not result_change:
                raise ResourceConflictError(validation.reason)
        elif task.action_type is ReviewActionType.CREATE_TASK:
            application = self._owned_application(task.application_id)
            self._owned_email(task.source_email_id)
            if payload.get("application_id") != application.id:
                raise ResourceConflictError("日程审核引用的求职申请无效")
            if payload.get("source_email_id") != task.source_email_id:
                raise ResourceConflictError("日程审核引用的来源邮件无效")
            if payload.get("task_type") != TaskType.INTERVIEW.value:
                raise ResourceConflictError("当前智能工作流只支持创建面试日程")
            round_value = payload.get("interview_round")
            if not isinstance(round_value, int) or not 1 <= round_value <= 20:
                raise ResourceConflictError("面试日程必须包含 1～20 的面试轮次")
            if _review_datetime(payload.get("start_at")) is None:
                raise ResourceConflictError("面试日程必须包含明确的开始时间")
            if not _optional_text(payload.get("title")):
                raise ResourceConflictError("面试日程必须包含标题")
            text_limits = (
                ("title", 255),
                ("raw_time_text", 500),
                ("source_timezone", 64),
                ("location", 500),
                ("meeting_url", 2048),
            )
            for field_name, limit in text_limits:
                value = payload.get(field_name)
                if value is not None and (not isinstance(value, str) or len(value) > limit):
                    raise ResourceConflictError(f"日程字段 {field_name} 无效")
        elif task.action_type is ReviewActionType.SEND_REPLY:
            unexpected = set(task.reviewed_payload or {}) - {"body"}
            if unexpected:
                raise ResourceConflictError("回复审核只允许修改正文")
            if task.draft_id is None:
                raise ResourceConflictError("发送审核任务缺少回复草稿")
            draft = self._session.get(ReplyDraft, task.draft_id)
            if draft is None or draft.email_id != task.source_email_id:
                raise ResourceConflictError("发送审核任务引用的回复草稿无效")
            latest = self._session.scalar(
                select(func.max(ReplyDraft.version)).where(
                    ReplyDraft.email_id == draft.email_id
                )
            )
            if latest != draft.version or task.resource_version != draft.version:
                raise VersionConflictError("旧版本回复草稿不能批准")
            if draft.status is not ReplyDraftStatus.PENDING:
                raise ResourceConflictError(
                    f"回复草稿当前状态 {draft.status.value} 不允许批准"
                )
            body = payload.get("body")
            if not isinstance(body, str) or not body.strip():
                raise ResourceConflictError("批准回复时正文不能为空")
            if len(body) > 20_000:
                raise ResourceConflictError("回复正文超过长度限制")
        elif task.action_type is ReviewActionType.UPDATE_INTERVIEW_RESULT:
            application = self._owned_application(task.application_id)
            if application.version != task.resource_version:
                raise VersionConflictError(
                    f"Resource version changed: expected {task.resource_version}, "
                    f"actual {application.version}"
                )
            round_number = payload.get("round_number")
            if not isinstance(round_number, int) or not 1 <= round_number <= 20:
                raise ResourceConflictError("面试结果审核必须包含有效的面试轮次")
            result = _interview_result(payload.get("result"))
            if result is None:
                raise ResourceConflictError("面试结果审核必须包含有效的结果值")
            source_email_id = payload.get("source_email_id")
            if source_email_id is not None:
                self._owned_email(source_email_id)
        elif task.action_type in {
            ReviewActionType.ARCHIVE_EMAIL,
            ReviewActionType.RESTORE_EMAIL,
        }:
            email = self._owned_email(task.source_email_id)
            proposed = task.proposed_payload
            protected = {
                "source_folder",
                "source_uid_validity",
                "source_uid",
                "target_folder",
            }
            if any(payload.get(key) != proposed.get(key) for key in protected):
                raise ResourceConflictError("邮件移动审核不允许修改文件夹或 UID")
            current_uid = email.current_imap_uid or email.imap_uid
            current_uid_validity = email.current_uid_validity or email.uid_validity
            if (
                email.current_folder != proposed.get("source_folder")
                or current_uid != proposed.get("source_uid")
                or current_uid_validity != proposed.get("source_uid_validity")
            ):
                raise ResourceConflictError("邮件当前位置已变化，请重新发起审核")
        else:
            raise ResourceConflictError("当前阶段不支持执行该审核动作")

    def _update_reply_draft_after_decision(
        self,
        task: ReviewTask,
        *,
        approved: bool,
    ) -> None:
        if task.action_type is not ReviewActionType.SEND_REPLY or task.draft_id is None:
            return
        draft = self._session.get(ReplyDraft, task.draft_id)
        if draft is None:
            raise ResourceConflictError("发送审核任务引用的回复草稿不存在")
        if not approved:
            draft.status = ReplyDraftStatus.REJECTED
            return
        body = draft.reviewed_body or draft.generated_body
        if task.reviewed_payload and "body" in task.reviewed_payload:
            reviewed = task.reviewed_payload["body"]
            if not isinstance(reviewed, str) or not reviewed.strip():
                raise ResourceConflictError("人工修改后的回复正文不能为空")
            body = reviewed.strip()
        if body != draft.generated_body:
            draft.reviewed_body = body
            draft.status = ReplyDraftStatus.MODIFIED_AND_APPROVED
        else:
            draft.reviewed_body = None
            draft.status = ReplyDraftStatus.APPROVED

    def _execute(
        self,
        task: ReviewTask,
        payload: dict[str, Any],
    ) -> JobApplication:
        if task.action_type is ReviewActionType.CREATE_APPLICATION:
            application = JobApplication(
                user_id=self._user_id,
                company_name=payload["company_name"].strip(),
                position_name=payload["position_name"].strip(),
                source=ApplicationSource.EMAIL,
                current_stage=ApplicationStage.APPLIED,
                status=ApplicationStatus.ACTIVE,
            )
            self._session.add(application)
            self._session.flush()
            self._session.add(
                ApplicationEvent(
                    application_id=application.id,
                    source_email_id=task.source_email_id,
                    workflow_run_id=task.workflow_run_id,
                    event_type="APPLICATION_CREATED",
                    proposed_stage=ApplicationStage.APPLIED,
                    confirmed_stage=ApplicationStage.APPLIED,
                    details={"review_task_id": task.id},
                )
            )
        else:
            # 推迟关联的审核载荷中没有直接的 application_id
            deferred = payload.get("deferred_source_review_task_id")
            if deferred and payload.get("application_id") is None:
                application = None  # 稍后由 _resolve_deferred_application 解析
            else:
                application = self._owned_application(payload["application_id"])

        if task.action_type in {
            ReviewActionType.CREATE_APPLICATION,
            ReviewActionType.LINK_APPLICATION,
        }:
            # 支持推迟关联：如果 application_id 为空但有 deferred_source，
            # 从源审核任务的执行结果中解析已创建的申请
            effective_application = application
            deferred_source = payload.get("deferred_source_review_task_id")
            if deferred_source and application is None:
                effective_application = self._resolve_deferred_application(deferred_source)
            if effective_application is None:
                raise ResourceConflictError("无法解析推迟关联的目标申请，请先批准对应的新建申请审核")

            email = self._owned_email(task.source_email_id)
            email.application_id = effective_application.id
            task.application_id = effective_application.id
            self._session.add(
                ApplicationEvent(
                    application_id=effective_application.id,
                    source_email_id=email.id,
                    workflow_run_id=task.workflow_run_id,
                    event_type="EMAIL_LINKED",
                    details={
                        "review_task_id": task.id,
                        "analysis_id": payload.get("analysis_id"),
                    },
                )
            )
            return effective_application

        if task.action_type is ReviewActionType.UPDATE_INTERVIEW_RESULT:
            round_number = int(payload["round_number"])
            result = _interview_result(payload["result"])
            previous_result = application.interview_result
            source_email_id = payload.get("source_email_id") or task.source_email_id
            self._upsert_interview_round(
                application_id=application.id,
                round_number=round_number,
                result=result,
                source=(
                    InterviewRoundSource.EMAIL
                    if source_email_id
                    else InterviewRoundSource.MANUAL
                ),
                source_email_id=source_email_id,
                notes=payload.get("reason"),
            )
            # 根据本轮结果收敛关联的面试日程
            if result in {InterviewResult.PASSED, InterviewResult.FAILED}:
                settle_interview_tasks(
                    self._session,
                    application_id=application.id,
                    status=TaskStatus.COMPLETED,
                    current_round_only=True,
                )
            self._session.add(
                ApplicationEvent(
                    application_id=application.id,
                    source_email_id=source_email_id,
                    workflow_run_id=task.workflow_run_id,
                    event_type="INTERVIEW_RESULT_CHANGED",
                    previous_stage=application.current_stage,
                    confirmed_stage=application.current_stage,
                    details={
                        "review_task_id": task.id,
                        "round_number": round_number,
                        "previous_result": (
                            previous_result.value if previous_result else None
                        ),
                        "interview_result": result.value,
                    },
                )
            )
            return application

        proposed = _application_stage(payload.get("proposed_stage"))
        previous = application.current_stage
        previous_result = application.interview_result
        application.current_stage = proposed
        extracted_result = _interview_result(payload.get("interview_result"))
        if proposed is ApplicationStage.INTERVIEW and extracted_result is not None:
            # 仅在首次进入面试阶段（非 INTERVIEW→INTERVIEW），或结果为通过/未通过时更新
            if previous is not ApplicationStage.INTERVIEW:
                application.interview_result = extracted_result
            elif extracted_result in (InterviewResult.PASSED, InterviewResult.FAILED):
                application.interview_result = extracted_result
            # 同一面试阶段内 PENDING 不覆盖已确认的结果
        elif proposed is ApplicationStage.REJECTED and previous is ApplicationStage.INTERVIEW:
            application.interview_result = InterviewResult.FAILED
        elif proposed is ApplicationStage.OFFER and previous is ApplicationStage.INTERVIEW:
            application.interview_result = InterviewResult.PASSED

        # 将阶段变更中隐含的面试结果同步到 interview_rounds 表
        if previous is ApplicationStage.INTERVIEW or proposed is ApplicationStage.INTERVIEW:
            self._sync_stage_result_to_rounds(
                application,
                previous=previous,
                proposed=proposed,
                extracted_result=extracted_result,
                source_review_task_id=task.id,
                source_email_id=task.source_email_id,
            )

        if application.interview_result is InterviewResult.FAILED:
            application.status = ApplicationStatus.CLOSED
        elif proposed is ApplicationStage.WITHDRAWN:
            application.status = ApplicationStatus.WITHDRAWN
        else:
            application.status = ApplicationStatus.ACTIVE
        if previous is ApplicationStage.INTERVIEW:
            if proposed is ApplicationStage.WITHDRAWN:
                settle_interview_tasks(
                    self._session,
                    application_id=application.id,
                    status=TaskStatus.CANCELLED,
                    current_round_only=False,
                )
            elif proposed is not ApplicationStage.INTERVIEW:
                settle_interview_tasks(
                    self._session,
                    application_id=application.id,
                    status=TaskStatus.COMPLETED,
                    current_round_only=False,
                )
            elif application.interview_result in {
                InterviewResult.PASSED,
                InterviewResult.FAILED,
            }:
                settle_interview_tasks(
                    self._session,
                    application_id=application.id,
                    status=TaskStatus.COMPLETED,
                    current_round_only=True,
                )
        self._session.add(
            ApplicationEvent(
                application_id=application.id,
                source_email_id=task.source_email_id,
                workflow_run_id=task.workflow_run_id,
                event_type=(
                    "INTERVIEW_RESULT_CHANGED"
                    if previous is proposed and previous_result != application.interview_result
                    else "STAGE_CHANGED"
                ),
                previous_stage=previous,
                proposed_stage=proposed,
                confirmed_stage=proposed,
                details={
                    "review_task_id": task.id,
                    "previous_result": (
                        previous_result.value if previous_result else None
                    ),
                    "interview_result": (
                        application.interview_result.value
                        if application.interview_result
                        else None
                    ),
                },
            )
        )
        return application

    def _create_stage_follow_up(
        self,
        source_task: ReviewTask,
        application: JobApplication,
        payload: dict[str, Any],
    ) -> ReviewTask | None:
        proposed_value = payload.get("proposed_stage")
        if (
            not proposed_value
            or source_task.action_type in {
                ReviewActionType.UPDATE_APPLICATION_STAGE,
                ReviewActionType.UPDATE_INTERVIEW_RESULT,
            }
        ):
            return None
        proposed = _application_stage(proposed_value)
        validation = validate_stage_transition(application.current_stage, proposed)
        result = _interview_result(payload.get("interview_result"))
        result_change = (
            proposed is ApplicationStage.INTERVIEW
            and result is not None
            and result is not application.interview_result
        )
        if validation.status is StageTransitionStatus.NO_CHANGE:
            if result_change:
                # 仅面试结果变化，创建专门的面试结果更新审核
                round_number = payload.get("interview_round")
                if not isinstance(round_number, int) or not 1 <= round_number <= 20:
                    round_number = self._session.scalar(
                        select(func.max(InterviewRound.round_number)).where(
                            InterviewRound.application_id == application.id,
                        )
                    ) or 0
                    if round_number < 1:
                        round_number = 1
                follow_up = ReviewTask(
                    id=str(uuid4()),
                    user_id=self._user_id,
                    workflow_run_id=source_task.workflow_run_id,
                    source_email_id=source_task.source_email_id,
                    application_id=application.id,
                    action_type=ReviewActionType.UPDATE_INTERVIEW_RESULT,
                    risk_level=RiskLevel.HIGH,
                    proposed_payload={
                        "schema_version": "interview-result-review.v1",
                        "application_id": application.id,
                        "company_name": application.company_name,
                        "position_name": application.position_name,
                        "round_number": round_number,
                        "result": result.value,
                        "summary": payload.get("summary"),
                        "source_email_id": source_task.source_email_id,
                        "source_review_task_id": source_task.id,
                    },
                    status=ReviewTaskStatus.PENDING,
                    idempotency_key=(
                        f"interview-result:{source_task.id}:{application.id}:"
                        f"{round_number}:{result.value}"
                    ),
                    resource_version=application.version,
                )
                self._session.add(follow_up)
                self._session.flush()
                return follow_up
            else:
                self._session.add(
                    ApplicationEvent(
                        application_id=application.id,
                        source_email_id=source_task.source_email_id,
                        workflow_run_id=source_task.workflow_run_id,
                        event_type=payload.get("event_type") or "EMAIL_EVENT",
                        previous_stage=application.current_stage,
                        proposed_stage=proposed,
                        confirmed_stage=application.current_stage,
                        details={
                            "review_task_id": source_task.id,
                            "stage_changed": False,
                            "summary": payload.get("summary"),
                        },
                    )
                )
                return None
        if validation.status is StageTransitionStatus.REJECTED:
            return None

        follow_up = ReviewTask(
            id=str(uuid4()),
            user_id=self._user_id,
            workflow_run_id=source_task.workflow_run_id,
            source_email_id=source_task.source_email_id,
            application_id=application.id,
            action_type=ReviewActionType.UPDATE_APPLICATION_STAGE,
            risk_level=RiskLevel.HIGH,
            proposed_payload={
                "schema_version": "stage-review.v1",
                "application_id": application.id,
                "company_name": application.company_name,
                "position_name": application.position_name,
                "previous_stage": application.current_stage.value,
                "proposed_stage": proposed.value,
                "interview_result": result.value if result else None,
                "validation": {
                    "status": validation.status.value,
                    "reason": validation.reason,
                },
                "source_review_task_id": source_task.id,
            },
            status=ReviewTaskStatus.PENDING,
            idempotency_key=(
                f"stage:{source_task.id}:{application.id}:{proposed.value}:"
                f"{result.value if result else 'NONE'}"
            ),
            resource_version=application.version,
        )
        self._session.add(follow_up)
        self._session.flush()
        return follow_up

    def _create_task_follow_up(
        self,
        source_task: ReviewTask,
        application: JobApplication,
    ) -> ReviewTask | None:
        """将已确认关联的面试时间转换为独立日程审核，避免模型直接写业务表。"""
        if source_task.action_type is ReviewActionType.CREATE_TASK:
            return None
        analysis = self._session.scalar(
            select(EmailAnalysis).where(
                EmailAnalysis.email_id == source_task.source_email_id,
                EmailAnalysis.workflow_run_id == source_task.workflow_run_id,
            )
        )
        if (
            analysis is None
            or analysis.category is not EmailCategory.INTERVIEW
            or analysis.event_time is None
        ):
            return None

        extraction = analysis.extraction_json or {}
        event_time = extraction.get("event_time")
        raw_time_text = (
            event_time.get("raw_text")
            if isinstance(event_time, dict) and isinstance(event_time.get("raw_text"), str)
            else None
        )
        location = _extracted_value(extraction.get("location"))
        meeting_url = _extracted_value(extraction.get("meeting_url"))
        interview_round = self._infer_next_interview_round(
            application.id,
            " ".join(
                value
                for value in (raw_time_text, analysis.event_type, analysis.summary)
                if value
            ),
        )
        round_label = _interview_round_label(interview_round)
        idempotency_key = f"interview-task:{analysis.id}:{application.id}"
        existing = self._session.scalar(
            select(ReviewTask).where(ReviewTask.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        follow_up = ReviewTask(
            id=str(uuid4()),
            user_id=self._user_id,
            workflow_run_id=source_task.workflow_run_id,
            source_email_id=source_task.source_email_id,
            application_id=application.id,
            action_type=ReviewActionType.CREATE_TASK,
            risk_level=RiskLevel.HIGH,
            proposed_payload={
                "schema_version": "task-review.v1",
                "application_id": application.id,
                "company_name": application.company_name,
                "position_name": application.position_name,
                "source_email_id": source_task.source_email_id,
                "task_type": TaskType.INTERVIEW.value,
                "interview_round": interview_round,
                "title": f"{application.company_name}{round_label}",
                "description": analysis.summary,
                "raw_time_text": raw_time_text,
                "start_at": (
                    analysis.event_time.replace(tzinfo=UTC)
                    .isoformat()
                    .replace("+00:00", "Z")
                ),
                "deadline_at": None,
                "source_timezone": analysis.source_timezone,
                "location": location,
                "meeting_url": meeting_url,
                "source_review_task_id": source_task.id,
            },
            status=ReviewTaskStatus.PENDING,
            idempotency_key=idempotency_key,
            resource_version=0,
        )
        self._session.add(follow_up)
        self._session.flush()
        return follow_up

    def _infer_interview_round(self, application_id: int, text: str) -> int:
        explicit = _parse_interview_round(text)
        if explicit is not None:
            return explicit
        latest = self._session.scalar(
            select(func.max(Task.interview_round)).where(
                Task.application_id == application_id,
                Task.task_type == TaskType.INTERVIEW,
            )
        )
        return int(latest or 0) + 1

    def _infer_next_interview_round(self, application_id: int, text: str) -> int:
        """推断新面试的轮次。从文本中取最大轮次号（因为新面试总是最后提及的），
        如果解析不到，则用已有最大轮次+1。"""
        max_parsed = _parse_interview_round_max(text)
        if max_parsed is not None:
            return max_parsed
        latest = self._session.scalar(
            select(func.max(Task.interview_round)).where(
                Task.application_id == application_id,
                Task.task_type == TaskType.INTERVIEW,
            )
        )
        return int(latest or 0) + 1

    def _execute_task(self, review_task: ReviewTask, payload: dict[str, Any]) -> Task:
        task = Task(
            user_id=self._user_id,
            application_id=review_task.application_id,
            source_email_id=review_task.source_email_id,
            source_review_task_id=review_task.id,
            task_type=TaskType.INTERVIEW,
            interview_round=int(payload["interview_round"]),
            title=str(payload["title"]).strip(),
            description=_optional_text(payload.get("description")),
            raw_time_text=_optional_text(payload.get("raw_time_text")),
            start_at=_review_datetime(payload.get("start_at")),
            deadline_at=_review_datetime(payload.get("deadline_at")),
            source_timezone=_optional_text(payload.get("source_timezone")),
            location=_optional_text(payload.get("location")),
            meeting_url=_optional_text(payload.get("meeting_url")),
            status=TaskStatus.CONFIRMED,
        )
        self._session.add(task)
        application = self._owned_application(review_task.application_id)
        # 更新或新建对应轮次的 interview_rounds 记录
        # 注意：不覆盖已有的确定结果（PASSED/FAILED），仅填补缺失或更新日程信息
        existing_round = self._session.scalar(
            select(InterviewRound).where(
                InterviewRound.application_id == application.id,
                InterviewRound.round_number == int(payload["interview_round"]),
            )
        )
        result_for_round = (
            existing_round.result
            if existing_round is not None and existing_round.result is not InterviewResult.PENDING
            else InterviewResult.PENDING
        )
        self._upsert_interview_round(
            application_id=application.id,
            round_number=int(payload["interview_round"]),
            result=result_for_round,
            interview_date=_review_datetime(payload.get("start_at")),
            location=_optional_text(payload.get("location")),
            meeting_url=_optional_text(payload.get("meeting_url")),
            source=(
                InterviewRoundSource.EMAIL
                if review_task.source_email_id
                else InterviewRoundSource.MANUAL
            ),
            source_email_id=review_task.source_email_id,
            source_task_id=task.id,
        )
        application.status = ApplicationStatus.ACTIVE
        self._session.flush()
        return task

    def _upsert_interview_round(
        self,
        *,
        application_id: int,
        round_number: int,
        result: InterviewResult = InterviewResult.PENDING,
        interview_date: datetime | None = None,
        location: str | None = None,
        meeting_url: str | None = None,
        source: InterviewRoundSource = InterviewRoundSource.MANUAL,
        source_email_id: int | None = None,
        source_task_id: int | None = None,
        notes: str | None = None,
    ) -> InterviewRound:
        """创建或更新面试轮次记录，并同步 JobApplication.interview_result 缓存。"""
        existing = self._session.scalar(
            select(InterviewRound).where(
                InterviewRound.application_id == application_id,
                InterviewRound.round_number == round_number,
            )
        )
        if existing is not None:
            existing.result = result
            if interview_date is not None:
                existing.interview_date = interview_date
            if location is not None:
                existing.location = location
            if meeting_url is not None:
                existing.meeting_url = meeting_url
            if source_email_id is not None:
                existing.source_email_id = source_email_id
            if source_task_id is not None:
                existing.source_task_id = source_task_id
            if notes is not None:
                existing.notes = notes
            existing.source = source
            self._session.flush()
            self._sync_application_interview_result(application_id)
            return existing

        round_record = InterviewRound(
            application_id=application_id,
            round_number=round_number,
            result=result,
            interview_date=interview_date,
            location=location,
            meeting_url=meeting_url,
            source=source,
            source_email_id=source_email_id,
            source_task_id=source_task_id,
            notes=notes,
        )
        self._session.add(round_record)
        self._session.flush()
        self._sync_application_interview_result(application_id)
        return round_record

    def _sync_application_interview_result(self, application_id: int) -> None:
        """将最新轮次的结果同步到 JobApplication.interview_result 缓存字段。"""
        latest = self._session.scalar(
            select(InterviewRound)
            .where(InterviewRound.application_id == application_id)
            .order_by(InterviewRound.round_number.desc())
            .limit(1)
        )
        application = self._owned_application(application_id)
        application.interview_result = latest.result if latest else None
        self._session.flush()

    def _sync_stage_result_to_rounds(
        self,
        application: JobApplication,
        *,
        previous: ApplicationStage,
        proposed: ApplicationStage,
        extracted_result: InterviewResult | None,
        source_review_task_id: str,
        source_email_id: int | None,
    ) -> None:
        """阶段变更中隐含的面试结果同步到 interview_rounds 的最新轮次。"""
        # 确定本轮面试的轮次号
        latest_round = self._session.scalar(
            select(func.max(InterviewRound.round_number)).where(
                InterviewRound.application_id == application.id,
            )
        )
        # 仅在首次进入面试阶段时创建新轮次，同一阶段内只更新最新轮次
        if proposed is ApplicationStage.INTERVIEW and previous is not ApplicationStage.INTERVIEW:
            round_number = (latest_round or 0) + 1
        else:
            round_number = max(latest_round or 0, 1)

        # 确定当前阶段对应的结果
        if proposed is ApplicationStage.REJECTED and previous is ApplicationStage.INTERVIEW:
            result = InterviewResult.FAILED
        elif proposed is ApplicationStage.OFFER and previous is ApplicationStage.INTERVIEW:
            result = InterviewResult.PASSED
        elif extracted_result is not None:
            # 同一面试阶段内，仅接受明确的通过/未通过结果，PENDING 不覆盖已有确定结果
            if previous is ApplicationStage.INTERVIEW and proposed is ApplicationStage.INTERVIEW:
                if extracted_result not in (InterviewResult.PASSED, InterviewResult.FAILED):
                    return
            result = extracted_result
        else:
            return

        self._upsert_interview_round(
            application_id=application.id,
            round_number=round_number,
            result=result,
            source=(
                InterviewRoundSource.EMAIL
                if source_email_id
                else InterviewRoundSource.MANUAL
            ),
            source_email_id=source_email_id,
            notes=f"审核任务 {source_review_task_id} 阶段从 {previous.value} 迁移到 {proposed.value}",
        )

    def _existing_response(self, task: ReviewTask) -> ReviewDecisionResponse:
        execution = self._session.scalar(
            select(ActionExecution)
            .where(ActionExecution.review_task_id == task.id)
            .order_by(ActionExecution.attempt_no.desc())
            .limit(1)
        )
        follow_up = None
        if execution and execution.result:
            follow_up_id = execution.result.get("follow_up_review_task_id")
            if follow_up_id:
                follow_up = self.get(follow_up_id)
        return ReviewDecisionResponse(
            review_task=task,
            execution=execution,
            follow_up_review_task=follow_up,
        )

    def response_for_task(self, task_id: str) -> ReviewDecisionResponse:
        return self._existing_response(self.get(task_id))

    def _owned_email(self, email_id: int | None) -> Email:
        if email_id is None:
            raise ResourceConflictError("审核任务缺少来源邮件")
        return EmailRepository(self._session, self._user_id).get(email_id)

    def _owned_application(self, application_id: int | None) -> JobApplication:
        if application_id is None:
            raise ResourceConflictError("审核任务缺少求职申请")
        application = self._session.scalar(
            select(JobApplication).where(
                JobApplication.id == application_id,
                JobApplication.user_id == self._user_id,
            )
        )
        if application is None:
            raise EntityNotFoundError(
                f"Job application {application_id} does not exist"
            )
        return application

    def _update_workflow_after_decision(
        self,
        task: ReviewTask,
        *,
        follow_up: ReviewTask | None,
    ) -> None:
        workflow = self._session.get(WorkflowRun, task.workflow_run_id)
        if workflow is None:
            return
        if follow_up is not None:
            workflow.status = WorkflowRunStatus.WAITING_REVIEW
            workflow.current_node = (
                "task_review"
                if follow_up.action_type is ReviewActionType.CREATE_TASK
                else "stage_review"
            )
            workflow.pending_review_task_id = follow_up.id
            return
        workflow.pending_review_task_id = None
        workflow.current_node = None
        workflow.status = (
            WorkflowRunStatus.SUCCEEDED
            if task.status in {
                ReviewTaskStatus.APPROVED,
                ReviewTaskStatus.SUCCEEDED,
            }
            else WorkflowRunStatus.CANCELLED
        )
        workflow.finished_at = _utc_now()


_CHINESE_ROUND_VALUES = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _parse_interview_round(text: str) -> int | None:
    if re.search(r"(?:初面|首面|首轮面试|第一轮面试)", text, re.IGNORECASE):
        return 1
    match = re.search(
        r"(?:第\s*)?(?P<round>\d{1,2}|[一二三四五六七八九十])\s*(?:轮\s*)?面",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    raw_value = match.group("round")
    value = int(raw_value) if raw_value.isdigit() else _CHINESE_ROUND_VALUES[raw_value]
    return value if 1 <= value <= 20 else None


def _parse_interview_round_max(text: str) -> int | None:
    """查找文本中提到的所有面试轮次，返回最大值。用于新面试日程创建。"""
    if re.search(r"(?:初面|首面|首轮面试|第一轮面试)", text, re.IGNORECASE):
        pass  # Still scan all matches, don't short-circuit
    matches = re.finditer(
        r"(?:第\s*)?(?P<round>\d{1,2}|[一二三四五六七八九十])\s*(?:轮\s*)?面",
        text,
        re.IGNORECASE,
    )
    max_value: int | None = None
    for m in matches:
        raw = m.group("round")
        value = int(raw) if raw.isdigit() else _CHINESE_ROUND_VALUES.get(raw)
        if value is not None and 1 <= value <= 20:
            if max_value is None or value > max_value:
                max_value = value
    if re.search(r"(?:初面|首面|首轮面试|第一轮面试)", text, re.IGNORECASE):
        if max_value is None or 1 > max_value:
            max_value = 1
    return max_value


def _interview_round_label(round_value: int) -> str:
    chinese = next(
        (label for label, value in _CHINESE_ROUND_VALUES.items() if value == round_value),
        None,
    )
    return f"{chinese}面" if chinese else f"第 {round_value} 轮面试"


def _extracted_value(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    return _optional_text(payload.get("value"))


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _review_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, (str, datetime)):
        raise ResourceConflictError("日程时间格式无效")
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(value.replace("Z", "+00:00"))
        )
    except ValueError as exc:
        raise ResourceConflictError("日程时间格式无效") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResourceConflictError("日程时间必须包含时区")
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _score_candidate(
    email: Email,
    analysis: EmailAnalysis,
    application: JobApplication,
    *,
    linked_sender_match: bool = False,
) -> ApplicationCandidate:
    company_score = _text_score(
        analysis.company_name,
        application.company_name,
        application.company_alias,
    )
    position_score = _text_score(analysis.position_name, application.position_name)
    sender = email.from_address.strip().casefold()
    contact = (application.contact_email or "").strip().casefold()
    sender_score = 1.0 if sender and sender == contact else _same_domain(sender, contact)
    linked_email_score = (
        1.0
        if email.application_id == application.id or linked_sender_match
        else 0.0
    )
    recency_score = _recency_score(email.received_at, application.updated_at)
    total = (
        company_score * 0.35
        + position_score * 0.30
        + sender_score * 0.20
        + linked_email_score * 0.10
        + recency_score * 0.05
    )
    reasons: list[str] = []
    if company_score >= 0.8:
        reasons.append("公司名称高度一致")
    if position_score >= 0.8:
        reasons.append("岗位名称高度一致")
    if sender_score >= 0.8:
        reasons.append("发件邮箱与申请联系人一致")
    if linked_email_score:
        reasons.append("邮件已关联该申请")
    return ApplicationCandidate(
        application_id=application.id,
        company_name=application.company_name,
        position_name=application.position_name,
        current_stage=application.current_stage,
        contact_email=application.contact_email,
        deterministic_score=round(min(total, 1.0), 4),
        score_breakdown=CandidateScoreBreakdown(
            company=round(company_score, 4),
            position=round(position_score, 4),
            sender=round(sender_score, 4),
            linked_email=linked_email_score,
            recency=round(recency_score, 4),
        ),
        match_reasons=reasons,
    )


def _is_candidate_eligible(
    email: Email,
    analysis: EmailAnalysis,
    application: JobApplication,
    candidate: ApplicationCandidate,
) -> bool:
    if candidate.deterministic_score < 0.15:
        return False
    explicit_company_conflict = bool(
        analysis.company_name
        and application.company_name
        and candidate.score_breakdown.company == 0
    )
    # 同一测试发件人或招聘代理可能联系多家公司，历史发件人关联不能覆盖明确的公司冲突。
    if explicit_company_conflict and email.application_id != application.id:
        return False
    return True


def _application_review_action(
    suggestion: ApplicationAgentOutput,
    candidates: list[ApplicationCandidate],
) -> ReviewActionType:
    if suggestion.recommendation is ApplicationRecommendation.CREATE_NEW:
        return ReviewActionType.CREATE_APPLICATION
    if suggestion.recommendation is ApplicationRecommendation.NEEDS_CONFIRMATION:
        # 检查候选列表是否包含有意义的高分匹配（≥0.5）
        good_candidates = [
            c for c in candidates if c.deterministic_score >= 0.5
        ]
        if not good_candidates:
            # 没有高分候选 → 新建申请，等用户确认公司/岗位
            return ReviewActionType.CREATE_APPLICATION
    return ReviewActionType.LINK_APPLICATION


def _text_score(source: str | None, *targets: str | None) -> float:
    normalized_source = _normalize_text(source)
    if not normalized_source:
        return 0.0
    best = 0.0
    for target in targets:
        normalized_target = _normalize_text(target)
        if not normalized_target:
            continue
        if normalized_source == normalized_target:
            score = 1.0
        elif normalized_source in normalized_target or normalized_target in normalized_source:
            score = 0.85
        else:
            score = SequenceMatcher(None, normalized_source, normalized_target).ratio()
            score = score if score >= 0.55 else 0.0
        best = max(best, score)
    return best


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)


def _same_domain(first: str, second: str) -> float:
    first_domain = first.rpartition("@")[2]
    second_domain = second.rpartition("@")[2]
    return 0.5 if first_domain and first_domain == second_domain else 0.0


def _recency_score(
    email_time: datetime | None,
    application_time: datetime | None,
) -> float:
    if email_time is None or application_time is None:
        return 0.0
    if email_time.tzinfo is not None:
        email_time = email_time.astimezone(UTC).replace(tzinfo=None)
    if application_time.tzinfo is not None:
        application_time = application_time.astimezone(UTC).replace(tzinfo=None)
    days = abs((email_time - application_time).days)
    if days <= 30:
        return 1.0
    if days <= 180:
        return 0.6
    if days <= 365:
        return 0.2
    return 0.0


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _application_stage(value: Any) -> ApplicationStage:
    try:
        return ApplicationStage(value)
    except (TypeError, ValueError) as exc:
        raise ResourceConflictError("审核载荷中的 proposed_stage 无效") from exc


def _interview_result(value: Any) -> InterviewResult | None:
    if value is None:
        return None
    try:
        return InterviewResult(value)
    except (TypeError, ValueError) as exc:
        raise ResourceConflictError("审核载荷中的 interview_result 无效") from exc


def _infer_round_from_extraction(
    extraction: dict[str, Any],
    application: JobApplication | None,
) -> int | None:
    """从抽取结果推断面试轮次，优先使用模型输出的 round_number。"""
    result_payload = extraction.get("interview_result")
    if isinstance(result_payload, dict):
        round_num = result_payload.get("round_number")
        if isinstance(round_num, int) and 1 <= round_num <= 20:
            return round_num
    # 回退到从摘要和事件类型文本中解析
    text_parts = []
    for key in ("event_type", "summary"):
        value = extraction.get(key)
        if isinstance(value, dict) and isinstance(value.get("value"), str):
            text_parts.append(value["value"])
    combined = " ".join(text_parts)
    parsed = _parse_interview_round(combined)
    if parsed is not None:
        return parsed
    return None


def _extracted_interview_result(extraction: dict[str, Any]) -> str | None:
    payload = extraction.get("interview_result")
    if not isinstance(payload, dict) or not payload.get("value"):
        return None
    return _interview_result(payload["value"]).value
