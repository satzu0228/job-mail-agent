from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.application.schemas import ApplicationAgentOutput, ApplicationCandidate
from app.agents.classification.schemas import ClassificationInput, ClassificationOutput
from app.agents.common.schemas import PreparedEmail
from app.agents.extraction.schemas import ExtractionInput, ExtractionOutput
from app.application.application_management import (
    ApplicationManagementService,
    ApplicationRunner,
    ReviewTaskService,
)
from app.application.email_analysis import (
    ClassificationRunner,
    EmailModelExecutionError,
    EmailNotReadyForAnalysisError,
    ExtractionRunner,
    PersistEmailAnalysis,
    prepare_email,
)
from app.application.reply import ReplyGenerationService, ReplyRunner
from app.application.schemas import (
    ReplyGenerationRequest,
    ReviewDecision,
    ReviewDecisionResponse,
    WorkflowRunRead,
)
from app.domain.enums import EmailParseStatus, ReviewTaskStatus, WorkflowRunStatus
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.workflow_run import WorkflowRun
from app.infrastructure.db.repositories import (
    EmailRepository,
    EntityNotFoundError,
    ResourceConflictError,
)
from app.workflows import (
    GRAPH_VERSION,
    JobMailGraph,
    ReviewExecutionOutcome,
    WorkflowState,
)


class Checkpointer(Protocol):
    pass


class WorkflowCheckpointUnavailableError(RuntimeError):
    """工作流 checkpoint 缺失、损坏或无法恢复。"""


class DatabaseWorkflowOperations:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        user_id: int,
        classification_agent: ClassificationRunner,
        extraction_agent: ExtractionRunner,
        application_agent: ApplicationRunner,
        reply_agent: ReplyRunner,
        *,
        model_provider: str,
        model_name: str,
    ) -> None:
        self._session_factory = session_factory
        self._user_id = user_id
        self._classification_agent = classification_agent
        self._extraction_agent = extraction_agent
        self._application_agent = application_agent
        self._reply_agent = reply_agent
        self._model_provider = model_provider
        self._model_name = model_name

    def load_email(self, email_id: int) -> PreparedEmail:
        with self._session_factory() as session:
            email = EmailRepository(session, self._user_id).get(email_id)
            if (
                email.parse_status
                not in {EmailParseStatus.SUCCEEDED, EmailParseStatus.PARTIAL}
                or not email.analysis_text.strip()
            ):
                raise EmailNotReadyForAnalysisError(
                    "邮件尚未成功解析，不能启动 AI 工作流"
                )
            user = session.get(User, self._user_id)
            timezone = user.timezone if user is not None else "Asia/Shanghai"
            return prepare_email(email, user_timezone=timezone)

    def classify(
        self,
        prepared: PreparedEmail,
        workflow_run_id: str,
    ) -> ClassificationOutput:
        started = perf_counter()
        try:
            result = self._classification_agent.run(
                ClassificationInput(email=prepared)
            )
        except Exception as exc:
            self._append_trace(
                workflow_run_id=workflow_run_id,
                email_id=prepared.email_id,
                trace={
                    "agent": "classification",
                    "node": "classify_email",
                    "prompt_version": getattr(
                        self._classification_agent, "prompt_version", "unknown"
                    ),
                    "status": "FAILED",
                    "error_code": "MODEL_EXECUTION_ERROR",
                    "error_message": "邮件分类模型执行失败",
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            raise EmailModelExecutionError("邮件分类模型执行失败") from exc
        duration_ms = round((perf_counter() - started) * 1000, 2)
        self._append_trace(
            workflow_run_id=workflow_run_id,
            email_id=prepared.email_id,
            trace={
                "agent": "classification",
                "node": "classify_email",
                "prompt_version": getattr(
                    self._classification_agent, "prompt_version", "unknown"
                ),
                "confidence": result.confidence,
                "input_summary": {
                    "email_id": prepared.email_id,
                    "analysis_text_chars": len(prepared.analysis_text),
                    "attachment_count": len(prepared.attachments),
                },
                "output": result.model_dump(mode="json"),
                "status": "SUCCEEDED",
                "duration_ms": duration_ms,
            },
        )
        return result

    def extract(
        self,
        prepared: PreparedEmail,
        classification: ClassificationOutput,
        workflow_run_id: str,
    ) -> ExtractionOutput:
        started = perf_counter()
        try:
            result = self._extraction_agent.run(
                ExtractionInput(email=prepared, classification=classification)
            )
        except Exception as exc:
            self._append_trace(
                workflow_run_id=workflow_run_id,
                email_id=prepared.email_id,
                trace={
                    "agent": "extraction",
                    "node": "extract_information",
                    "prompt_version": getattr(
                        self._extraction_agent, "prompt_version", "unknown"
                    ),
                    "status": "FAILED",
                    "error_code": "MODEL_EXECUTION_ERROR",
                    "error_message": "邮件抽取模型执行失败",
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            raise EmailModelExecutionError("邮件抽取模型执行失败") from exc
        duration_ms = round((perf_counter() - started) * 1000, 2)
        self._append_trace(
            workflow_run_id=workflow_run_id,
            email_id=prepared.email_id,
            trace={
                "agent": "extraction",
                "node": "extract_information",
                "prompt_version": getattr(
                    self._extraction_agent, "prompt_version", "unknown"
                ),
                "confidence": result.overall_confidence,
                "input_summary": {
                    "email_id": prepared.email_id,
                    "category": classification.category.value,
                },
                "output": result.model_dump(mode="json", exclude_none=True),
                "status": "SUCCEEDED",
                "duration_ms": duration_ms,
            },
        )
        return result

    def persist_analysis(
        self,
        *,
        email_id: int,
        workflow_run_id: str,
        classification: ClassificationOutput,
        extraction: ExtractionOutput | None,
    ) -> int:
        with self._session_factory() as session:
            existing = session.scalar(
                select(EmailAnalysis).where(
                    EmailAnalysis.workflow_run_id == workflow_run_id
                )
            )
            if existing is not None:
                return existing.id
        persisted = PersistEmailAnalysis(self._session_factory).execute(
            email_id=email_id,
            classification=classification,
            extraction=extraction,
            workflow_run_id=workflow_run_id,
        )
        return persisted.id

    def match_application(
        self,
        *,
        email_id: int,
        workflow_run_id: str,
    ) -> tuple[int, list[ApplicationCandidate], ApplicationAgentOutput, str]:
        with self._session_factory() as session:
            result = ApplicationManagementService(
                session,
                self._user_id,
                self._application_agent,
                model_provider=self._model_provider,
                model_name=self._model_name,
            ).match_email(email_id, workflow_run_id=workflow_run_id)
        return (
            result.analysis_id,
            result.candidates,
            result.suggestion,
            result.review_task_id,
        )

    def execute_review(self, review_task_id: str) -> ReviewExecutionOutcome:
        with self._session_factory() as session:
            service = ReviewTaskService(session, self._user_id)
            task = service.get(review_task_id)
            status = task.status
            action_type = task.action_type
            draft_id = task.draft_id
            session.rollback()
            if status is ReviewTaskStatus.REJECTED:
                return ReviewExecutionOutcome(
                    review_task_id=review_task_id,
                    action_type=action_type.value,
                    rejected=True,
                )
            if action_type.value == "SEND_REPLY":
                return ReviewExecutionOutcome(
                    review_task_id=review_task_id,
                    action_type=action_type.value,
                    result={"draft_id": draft_id},
                )
            response = service.execute_decided(
                review_task_id,
                update_workflow=False,
            )
            return ReviewExecutionOutcome(
                review_task_id=review_task_id,
                action_type=action_type.value,
                follow_up_review_task_id=(
                    response.follow_up_review_task.id
                    if response.follow_up_review_task
                    else None
                ),
                result=response.execution.result if response.execution else None,
            )

    def generate_reply(
        self,
        *,
        email_id: int,
        workflow_run_id: str,
    ) -> tuple[int | None, str | None]:
        with self._session_factory() as session:
            response = ReplyGenerationService(
                session,
                self._user_id,
                self._reply_agent,
            ).generate(
                email_id,
                ReplyGenerationRequest(workflow_run_id=workflow_run_id),
            )
        if response.draft is None or response.review_task is None:
            return None, None
        return response.draft.id, response.review_task.id

    def mark_waiting(self, workflow_run_id: str, review_task_id: str) -> None:
        with self._session_factory() as session, session.begin():
            workflow = self._owned_workflow(session, workflow_run_id)
            task = session.get(ReviewTask, review_task_id)
            if task is None or task.workflow_run_id != workflow.id:
                raise ResourceConflictError("待审核任务不属于当前工作流")
            workflow.status = WorkflowRunStatus.WAITING_REVIEW
            workflow.current_node = "human_review"
            workflow.pending_review_task_id = task.id

    def finalize(self, workflow_run_id: str, status: WorkflowRunStatus) -> None:
        with self._session_factory() as session, session.begin():
            workflow = self._owned_workflow(session, workflow_run_id)
            workflow.status = status
            workflow.current_node = None
            workflow.pending_review_task_id = None
            workflow.finished_at = _utc_now()

    def fail(
        self,
        workflow_run_id: str,
        *,
        node: str,
        error_code: str,
        error_message: str,
    ) -> None:
        with self._session_factory() as session, session.begin():
            workflow = self._owned_workflow(session, workflow_run_id)
            workflow.status = WorkflowRunStatus.FAILED
            workflow.current_node = node
            workflow.pending_review_task_id = None
            workflow.error_code = error_code[:64]
            workflow.error_message = error_message[:500]
            workflow.agent_trace = [
                *workflow.agent_trace,
                {
                    "node": node,
                    "status": "FAILED",
                    "error_code": error_code[:64],
                    "error_message": error_message[:500],
                    "recorded_at": _utc_now().isoformat(),
                },
            ]
            workflow.finished_at = _utc_now()

    def _append_trace(
        self,
        *,
        workflow_run_id: str | None,
        email_id: int,
        trace: dict[str, Any],
    ) -> None:
        with self._session_factory() as session, session.begin():
            workflow = (
                session.get(WorkflowRun, workflow_run_id)
                if workflow_run_id
                else session.scalar(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.user_id == self._user_id,
                        WorkflowRun.email_id == email_id,
                        WorkflowRun.graph_version == GRAPH_VERSION,
                        WorkflowRun.status == WorkflowRunStatus.RUNNING,
                    )
                    .order_by(WorkflowRun.started_at.desc())
                    .limit(1)
                )
            )
            if workflow is None:
                return
            workflow.current_node = trace["node"]
            workflow.agent_trace = [
                *workflow.agent_trace,
                {**trace, "recorded_at": _utc_now().isoformat()},
            ]

    def _owned_workflow(self, session: Session, workflow_run_id: str) -> WorkflowRun:
        workflow = session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.id == workflow_run_id,
                WorkflowRun.user_id == self._user_id,
            )
        )
        if workflow is None:
            raise EntityNotFoundError(
                f"Workflow run {workflow_run_id} does not exist"
            )
        return workflow


class JobMailWorkflowService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        user_id: int,
        operations: DatabaseWorkflowOperations,
        checkpointer: Checkpointer,
        *,
        model_provider: str,
        model_name: str,
        prompt_versions: dict[str, str],
    ) -> None:
        self._session_factory = session_factory
        self._user_id = user_id
        self._operations = operations
        self._graph = JobMailGraph(operations).compile(checkpointer=checkpointer)
        self._model_provider = model_provider
        self._model_name = model_name
        self._prompt_versions = prompt_versions

    def start(self, email_id: int) -> WorkflowRunRead:
        existing = self._active_run_for_email(email_id)
        if existing is not None:
            return WorkflowRunRead.model_validate(existing)

        run_id = str(uuid4())
        thread_id = str(uuid4())
        now = _utc_now()
        with self._session_factory() as session, session.begin():
            EmailRepository(session, self._user_id).get(email_id)
            workflow = WorkflowRun(
                id=run_id,
                thread_id=thread_id,
                user_id=self._user_id,
                email_id=email_id,
                status=WorkflowRunStatus.RUNNING,
                current_node="load_email",
                graph_version=GRAPH_VERSION,
                model_provider=self._model_provider,
                model_name=self._model_name,
                prompt_versions=self._prompt_versions,
                agent_trace=[],
                started_at=now,
            )
            session.add(workflow)

        initial = WorkflowState(
            workflow_run_id=run_id,
            thread_id=thread_id,
            user_id=self._user_id,
            email_id=email_id,
        )
        self._graph.invoke(
            initial.model_dump(mode="json"),
            config={"configurable": {"thread_id": thread_id}},
        )
        return self.get(run_id)

    def get(self, workflow_run_id: str) -> WorkflowRunRead:
        with self._session_factory() as session:
            workflow = self._owned_workflow(session, workflow_run_id)
            return WorkflowRunRead.model_validate(workflow)

    def decide_review(
        self,
        task_id: str,
        decision: ReviewDecision,
    ) -> ReviewDecisionResponse:
        with self._session_factory() as session:
            task = ReviewTaskService(session, self._user_id).get(task_id)
            workflow = self._owned_workflow(session, task.workflow_run_id)
            if workflow.graph_version != GRAPH_VERSION:
                session.rollback()
                return ReviewTaskService(session, self._user_id).decide(
                    task_id,
                    decision,
                )
            should_resume = (
                workflow.status is WorkflowRunStatus.WAITING_REVIEW
                and workflow.pending_review_task_id == task.id
            )
            thread_id = workflow.thread_id
            task_status = task.status

        if task_status is ReviewTaskStatus.PENDING:
            with self._session_factory() as session:
                recorded = ReviewTaskService(
                    session,
                    self._user_id,
                ).record_decision(
                    task_id,
                    decision,
                    update_workflow=False,
                )
                should_resume = should_resume and recorded.should_resume
        elif task_status not in {
            ReviewTaskStatus.APPROVED,
            ReviewTaskStatus.REJECTED,
            ReviewTaskStatus.SUCCEEDED,
        }:
            raise ResourceConflictError(
                f"审核任务当前状态 {task_status.value} 不允许恢复"
            )

        if should_resume and task_status is not ReviewTaskStatus.SUCCEEDED:
            snapshot = self._graph.get_state(
                {"configurable": {"thread_id": thread_id}}
            )
            if not snapshot.tasks:
                raise WorkflowCheckpointUnavailableError(
                    "工作流没有可恢复的 checkpoint 中断"
                )
            self._graph.invoke(
                Command(resume={"review_task_id": task_id}),
                config={"configurable": {"thread_id": thread_id}},
            )

        with self._session_factory() as session:
            return ReviewTaskService(
                session,
                self._user_id,
            ).response_for_task(task_id)

    def _active_run_for_email(self, email_id: int) -> WorkflowRun | None:
        with self._session_factory() as session:
            EmailRepository(session, self._user_id).get(email_id)
            return session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.user_id == self._user_id,
                    WorkflowRun.email_id == email_id,
                    WorkflowRun.graph_version == GRAPH_VERSION,
                    WorkflowRun.status.in_(
                        (
                            WorkflowRunStatus.PENDING,
                            WorkflowRunStatus.RUNNING,
                            WorkflowRunStatus.WAITING_REVIEW,
                        )
                    ),
                )
                .order_by(WorkflowRun.started_at.desc())
                .limit(1)
            )

    def _owned_workflow(self, session: Session, workflow_run_id: str) -> WorkflowRun:
        workflow = session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.id == workflow_run_id,
                WorkflowRun.user_id == self._user_id,
            )
        )
        if workflow is None:
            raise EntityNotFoundError(
                f"Workflow run {workflow_run_id} does not exist"
            )
        return workflow


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
