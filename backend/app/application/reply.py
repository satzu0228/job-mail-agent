from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.common.schemas import PreparedEmail
from app.agents.reply.schemas import (
    ReplyAgentInput,
    ReplyAgentOutput,
    ReplyApplicationContext,
    ReplyContext,
    ReplyUserContext,
)
from app.application.email_analysis import prepare_email
from app.application.schemas import (
    ReplyDraftRead,
    ReplyGenerationRequest,
    ReplyGenerationResponse,
    ReplySendRequest,
    ReplySendResponse,
    ReviewTaskRead,
)
from app.domain.enums import (
    ExecutionStatus,
    ExecutorType,
    ReplyDraftStatus,
    ReviewActionType,
    ReviewTaskStatus,
    RiskLevel,
)
from app.infrastructure.db.models.action_execution import ActionExecution
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.reply_draft import ReplyDraft
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.workflow_run import WorkflowRun
from app.infrastructure.db.repositories import (
    EmailRepository,
    EntityNotFoundError,
    ResourceConflictError,
    VersionConflictError,
)
from app.infrastructure.email import (
    SmtpDeliveryFailedError,
    SmtpDeliveryUnknownError,
    SmtpMailer,
    build_message,
    format_reply_body,
    recipient,
    reply_subject,
)
from app.infrastructure.security import EnvironmentCredentialResolver


class ReplyRunner(Protocol):
    prompt_version: str

    def run(self, agent_input: ReplyAgentInput) -> ReplyAgentOutput: ...


class CredentialResolver(Protocol):
    def resolve(self, credential_ref: str) -> str: ...


class Mailer(Protocol):
    def send(self, account: object, credential: str, message: object) -> str | None: ...


class ReplyGenerationUnavailableError(RuntimeError):
    """当前邮件缺少生成回复所需的已验证上下文。"""


class ReplyModelExecutionError(RuntimeError):
    """Reply Agent 调用或结构化输出失败。"""


class ReplyGenerationService:
    def __init__(
        self,
        session: Session,
        user_id: int,
        agent: ReplyRunner,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._agent = agent

    def generate(
        self,
        email_id: int,
        request: ReplyGenerationRequest,
    ) -> ReplyGenerationResponse:
        email = EmailRepository(self._session, self._user_id).get(email_id)
        analysis = self._current_analysis(email.id)
        if not analysis.is_job_related:
            raise ReplyGenerationUnavailableError("非求职邮件不能生成回复草稿")
        workflow = self._workflow(email.id, analysis, request.workflow_run_id)
        user = self._session.get(User, self._user_id)
        if user is None:
            raise EntityNotFoundError(f"User {self._user_id} does not exist")
        prepared = prepare_email(email, user_timezone=user.timezone)
        agent_input = self._agent_input(prepared, email, analysis, user)
        started = perf_counter()
        try:
            result = self._agent.run(agent_input)
        except Exception as exc:
            self._append_trace(
                workflow,
                {
                    "agent": "reply",
                    "node": "generate_reply",
                    "prompt_version": self._agent.prompt_version,
                    "status": "FAILED",
                    "error_code": "MODEL_EXECUTION_ERROR",
                    "error_message": "回复生成模型执行失败",
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            self._session.commit()
            raise ReplyModelExecutionError("回复生成模型执行失败") from exc

        self._append_trace(
            workflow,
            {
                "agent": "reply",
                "node": "generate_reply",
                "prompt_version": self._agent.prompt_version,
                "status": "SUCCEEDED",
                "confidence": result.confidence,
                "input_summary": {
                    "email_id": email.id,
                    "category": analysis.category.value,
                    "application_id": email.application_id,
                },
                "output_summary": {
                    "should_reply": result.should_reply,
                    "facts_used": len(result.facts_used),
                    "uncertain_claims": len(result.uncertain_claims),
                },
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        if not result.should_reply:
            self._session.commit()
            return ReplyGenerationResponse(
                should_reply=False,
                confidence=result.confidence,
                reason=result.reason,
            )

        assert result.body is not None
        self._expire_previous(email.id)
        draft = ReplyDraft(
            email_id=email.id,
            application_id=email.application_id,
            workflow_run_id=workflow.id,
            version=self._next_version(email.id),
            to_recipients=[
                recipient(email.reply_to_address or email.from_address, email.from_name)
            ],
            cc_recipients=[],
            subject=reply_subject(email.subject),
            generated_body=format_reply_body(
                result.body,
                sender_name=email.from_name,
                user_display_name=user.display_name,
                language=result.language,
            ),
            facts_used=[{"fact": fact} for fact in result.facts_used],
            uncertain_claims=[
                {"claim": claim, "requires_confirmation": True}
                for claim in result.uncertain_claims
            ],
            status=ReplyDraftStatus.PENDING,
        )
        self._session.add(draft)
        self._session.flush()
        review = ReviewTask(
            id=str(uuid4()),
            user_id=self._user_id,
            workflow_run_id=workflow.id,
            source_email_id=email.id,
            application_id=email.application_id,
            draft_id=draft.id,
            action_type=ReviewActionType.SEND_REPLY,
            risk_level=RiskLevel.HIGH,
            proposed_payload={
                "schema_version": "send-reply-review.v1",
                "draft_id": draft.id,
                "draft_version": draft.version,
                "to_recipients": draft.to_recipients,
                "cc_recipients": draft.cc_recipients,
                "subject": draft.subject,
                "body": draft.generated_body,
            },
            status=ReviewTaskStatus.PENDING,
            idempotency_key=f"reply-review:{email.id}:{draft.version}",
            resource_version=draft.version,
        )
        self._session.add(review)
        self._session.commit()
        return ReplyGenerationResponse(
            should_reply=True,
            confidence=result.confidence,
            reason=result.reason,
            draft=ReplyDraftRead.model_validate(draft),
            review_task=ReviewTaskRead.model_validate(review),
        )

    def _current_analysis(self, email_id: int) -> EmailAnalysis:
        analysis = self._session.scalar(
            select(EmailAnalysis).where(
                EmailAnalysis.email_id == email_id,
                EmailAnalysis.is_current.is_(True),
            )
        )
        if analysis is None:
            raise ReplyGenerationUnavailableError("邮件缺少当前 AI 分析结果")
        return analysis

    def _workflow(
        self,
        email_id: int,
        analysis: EmailAnalysis,
        requested_id: str | None,
    ) -> WorkflowRun:
        workflow_id = requested_id or analysis.workflow_run_id
        if workflow_id is None:
            raise ReplyGenerationUnavailableError("邮件分析未关联可审计工作流")
        workflow = self._session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.id == workflow_id,
                WorkflowRun.user_id == self._user_id,
                WorkflowRun.email_id == email_id,
            )
        )
        if workflow is None:
            raise ReplyGenerationUnavailableError("回复工作流不存在或不属于当前邮件")
        return workflow

    def _agent_input(
        self,
        prepared: PreparedEmail,
        email: Email,
        analysis: EmailAnalysis,
        user: User,
    ) -> ReplyAgentInput:
        application = email.application
        return ReplyAgentInput(
            email=prepared,
            analysis=ReplyContext(
                category=analysis.category,
                should_reply_from_classification=analysis.should_reply,
                summary=analysis.summary,
                event_time=_iso(analysis.event_time),
                deadline_at=_iso(analysis.deadline_at),
                company_name=analysis.company_name,
                position_name=analysis.position_name,
            ),
            application=(
                ReplyApplicationContext(
                    application_id=application.id,
                    company_name=application.company_name,
                    position_name=application.position_name,
                    current_stage=application.current_stage,
                    contact_name=application.contact_name,
                )
                if application is not None
                else None
            ),
            user=ReplyUserContext(
                display_name=user.display_name,
                timezone=user.timezone,
                preferences=user.reply_preferences,
            ),
        )

    def _expire_previous(self, email_id: int) -> None:
        drafts = list(
            self._session.scalars(
                select(ReplyDraft).where(
                    ReplyDraft.email_id == email_id,
                    ReplyDraft.status == ReplyDraftStatus.PENDING,
                )
            )
        )
        for draft in drafts:
            draft.status = ReplyDraftStatus.EXPIRED
            tasks = self._session.scalars(
                select(ReviewTask).where(
                    ReviewTask.draft_id == draft.id,
                    ReviewTask.status == ReviewTaskStatus.PENDING,
                )
            )
            for task in tasks:
                task.status = ReviewTaskStatus.EXPIRED

    def _next_version(self, email_id: int) -> int:
        latest = self._session.scalar(
            select(func.max(ReplyDraft.version)).where(ReplyDraft.email_id == email_id)
        )
        return int(latest or 0) + 1

    @staticmethod
    def _append_trace(workflow: WorkflowRun, trace: dict[str, object]) -> None:
        workflow.agent_trace = [*(workflow.agent_trace or []), trace]
        versions = dict(workflow.prompt_versions or {})
        versions["reply"] = trace.get("prompt_version", "unknown")
        workflow.prompt_versions = versions


class ReplySendService:
    def __init__(
        self,
        session: Session,
        user_id: int,
        *,
        credential_resolver: CredentialResolver | None = None,
        mailer: Mailer | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self._mailer = mailer or SmtpMailer(timeout_seconds)

    def send(self, draft_id: int, request: ReplySendRequest) -> ReplySendResponse:
        draft, task, email = self._load_command(draft_id, request)
        execution_key = self._execution_key(draft, request)
        repeated = self._execution_by_key(execution_key)
        if repeated is not None:
            return self._response(draft, task, repeated)
        existing = self._latest_execution(task.id)
        if existing is not None:
            if existing.status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.UNKNOWN}:
                return self._response(draft, task, existing)
            if existing.status is ExecutionStatus.RUNNING:
                raise ResourceConflictError("已有 SMTP 发送正在执行，不能并发提交")

        attempt_no = (existing.attempt_no if existing else 0) + 1
        execution = ActionExecution(
            review_task_id=task.id,
            attempt_no=attempt_no,
            idempotency_key=execution_key,
            executor_type=ExecutorType.SMTP,
            status=ExecutionStatus.RUNNING,
            started_at=_utc_now(),
        )
        task.status = ReviewTaskStatus.EXECUTING
        self._session.add(execution)
        self._session.commit()

        account = email.account
        body = draft.reviewed_body or draft.generated_body
        try:
            credential = self._credential_resolver.resolve(account.credential_ref)
            message = build_message(
                from_address=account.email_address,
                from_name=None,
                to_recipients=draft.to_recipients,
                cc_recipients=draft.cc_recipients,
                subject=draft.subject,
                body=body,
                in_reply_to=email.message_id,
            )
            external_reference = self._mailer.send(account, credential, message)
        except SmtpDeliveryUnknownError as exc:
            execution.status = ExecutionStatus.UNKNOWN
            execution.error_code = "SMTP_DELIVERY_UNKNOWN"
            execution.error_message = str(exc)[:500]
            task.status = ReviewTaskStatus.UNKNOWN
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.error_code = (
                "SMTP_DELIVERY_FAILED"
                if isinstance(exc, SmtpDeliveryFailedError)
                else exc.__class__.__name__.upper()
            )
            execution.error_message = (str(exc).strip() or "SMTP 发送失败")[:500]
            task.status = ReviewTaskStatus.FAILED
        else:
            execution.status = ExecutionStatus.SUCCEEDED
            execution.external_reference = external_reference
            execution.result = {
                "draft_id": draft.id,
                "draft_version": draft.version,
                "message_id": external_reference,
                "recipient_count": len(draft.to_recipients)
                + len(draft.cc_recipients),
            }
            task.status = ReviewTaskStatus.SUCCEEDED
        execution.finished_at = _utc_now()
        self._session.commit()
        return self._response(draft, task, execution)

    def _load_command(
        self,
        draft_id: int,
        request: ReplySendRequest,
    ) -> tuple[ReplyDraft, ReviewTask, Email]:
        email = EmailRepository(self._session, self._user_id)
        draft = self._session.scalar(
            select(ReplyDraft)
            .join(Email, ReplyDraft.email_id == Email.id)
            .join(Email.account)
            .where(ReplyDraft.id == draft_id)
            .with_for_update()
        )
        if draft is None:
            raise EntityNotFoundError(f"Reply draft {draft_id} does not exist")
        owned_email = email.get(draft.email_id)
        if draft.version != request.draft_version:
            raise VersionConflictError(
                f"Resource version changed: expected {request.draft_version}, "
                f"actual {draft.version}"
            )
        latest = self._session.scalar(
            select(func.max(ReplyDraft.version)).where(
                ReplyDraft.email_id == draft.email_id
            )
        )
        if latest != draft.version:
            raise ResourceConflictError("旧版本回复草稿不能发送")
        if draft.status not in {
            ReplyDraftStatus.APPROVED,
            ReplyDraftStatus.MODIFIED_AND_APPROVED,
        }:
            raise ResourceConflictError("回复草稿尚未批准或已失效")
        task = self._session.scalar(
            select(ReviewTask).where(
                ReviewTask.draft_id == draft.id,
                ReviewTask.action_type == ReviewActionType.SEND_REPLY,
            )
        )
        if task is None or task.status not in {
            ReviewTaskStatus.APPROVED,
            ReviewTaskStatus.FAILED,
            ReviewTaskStatus.EXECUTING,
            ReviewTaskStatus.SUCCEEDED,
            ReviewTaskStatus.UNKNOWN,
        }:
            raise ResourceConflictError("回复发送审核尚未批准")
        if task.resource_version != draft.version:
            raise VersionConflictError("审核任务引用的草稿版本已变化")
        if not owned_email.account.is_active:
            raise ResourceConflictError("邮箱账户已停用")
        return draft, task, owned_email

    def _latest_execution(self, task_id: str) -> ActionExecution | None:
        return self._session.scalar(
            select(ActionExecution)
            .where(ActionExecution.review_task_id == task_id)
            .order_by(ActionExecution.attempt_no.desc())
            .limit(1)
        )

    def _execution_by_key(self, idempotency_key: str) -> ActionExecution | None:
        return self._session.scalar(
            select(ActionExecution).where(
                ActionExecution.idempotency_key == idempotency_key
            )
        )

    @staticmethod
    def _execution_key(draft: ReplyDraft, request: ReplySendRequest) -> str:
        return f"smtp:{draft.id}:{draft.version}:{request.idempotency_key}"

    @staticmethod
    def _response(
        draft: ReplyDraft,
        task: ReviewTask,
        execution: ActionExecution,
    ) -> ReplySendResponse:
        return ReplySendResponse(
            draft=ReplyDraftRead.model_validate(draft),
            review_task=ReviewTaskRead.model_validate(task),
            execution=execution,
        )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
