from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.application_management import ReviewTaskService
from app.application.schemas import ReviewDecision, ReviewDecisionResponse
from app.domain.enums import (
    ArchiveStatus,
    ExecutionStatus,
    ExecutorType,
    ReviewActionType,
    ReviewTaskStatus,
    RiskLevel,
    WorkflowRunStatus,
)
from app.infrastructure.db.models import (
    ActionExecution,
    Email,
    ReviewTask,
    WorkflowRun,
)
from app.infrastructure.db.repositories import (
    EmailRepository,
    ResourceConflictError,
)
from app.infrastructure.email import (
    EmailConnectionError,
    ImapMailboxClient,
    ImapMoveResult,
    ImapMoveUnknownError,
)
from app.infrastructure.security import (
    CredentialNotConfiguredError,
    EnvironmentCredentialResolver,
)

ARCHIVE_FOLDER = "JobMailArchive"
ARCHIVE_GRAPH_VERSION = "phase-11-archive.v1"


class CredentialResolver(Protocol):
    def resolve(self, credential_ref: str) -> str: ...


class ImapMover(Protocol):
    def move(
        self,
        account: object,
        credential: str,
        *,
        source_folder: str,
        source_uid: int,
        target_folder: str,
        create_target: bool,
        on_copy: Callable[[ImapMoveResult], None] | None = None,
    ) -> ImapMoveResult: ...


class EmailArchiveService:
    """创建人工审核任务，并在批准后通过幂等 IMAP Executor 移动邮件。"""

    def __init__(
        self,
        session: Session,
        user_id: int,
        *,
        credential_resolver: CredentialResolver | None = None,
        mover: ImapMover | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._emails = EmailRepository(session, user_id)
        self._credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self._mover = mover or ImapMailboxClient(timeout_seconds)

    def propose_archive(self, email_id: int) -> ReviewTask:
        return self._propose(email_id, ReviewActionType.ARCHIVE_EMAIL)

    def propose_restore(self, email_id: int) -> ReviewTask:
        return self._propose(email_id, ReviewActionType.RESTORE_EMAIL)

    def _propose(
        self,
        email_id: int,
        action_type: ReviewActionType,
    ) -> ReviewTask:
        with self._session.begin():
            email = self._emails.get(email_id)
            if not email.account.is_active:
                raise ResourceConflictError("停用邮箱中的邮件不能移动")
            source_uid = email.current_imap_uid or email.imap_uid
            source_uid_validity = email.current_uid_validity or email.uid_validity
            key = (
                f"email-move:{email.id}:{action_type.value}:"
                f"{email.current_folder}:{source_uid}"
            )
            existing = self._session.scalar(
                select(ReviewTask).where(ReviewTask.idempotency_key == key)
            )
            if existing is not None and existing.status not in {
                ReviewTaskStatus.REJECTED,
                ReviewTaskStatus.CANCELLED,
                ReviewTaskStatus.EXPIRED,
                ReviewTaskStatus.FAILED,
            }:
                return existing
            if existing is not None:
                key = f"{key}:{uuid4()}"
            if action_type is ReviewActionType.ARCHIVE_EMAIL:
                if email.archive_status in {
                    ArchiveStatus.ARCHIVED,
                    ArchiveStatus.PROPOSED,
                }:
                    raise ResourceConflictError("邮件已归档或已有待审核归档任务")
                target_folder = ARCHIVE_FOLDER
            else:
                if email.archive_status is not ArchiveStatus.ARCHIVED:
                    raise ResourceConflictError("只有已归档邮件可以恢复")
                target_folder = email.previous_folder or "INBOX"

            now = _utc_now()
            run_id = str(uuid4())
            workflow = WorkflowRun(
                id=run_id,
                thread_id=str(uuid4()),
                user_id=self._user_id,
                email_id=email.id,
                status=WorkflowRunStatus.WAITING_REVIEW,
                current_node="email_move_review",
                graph_version=ARCHIVE_GRAPH_VERSION,
                model_provider="deterministic",
                model_name="imap-move",
                prompt_versions={},
                agent_trace=[],
                started_at=now,
            )
            self._session.add(workflow)
            self._session.flush()
            task = ReviewTask(
                id=str(uuid4()),
                user_id=self._user_id,
                workflow_run_id=run_id,
                source_email_id=email.id,
                application_id=email.application_id,
                action_type=action_type,
                risk_level=RiskLevel.MEDIUM,
                proposed_payload={
                    "schema_version": "email-move-review.v1",
                    "source_folder": email.current_folder,
                    "source_uid_validity": source_uid_validity,
                    "source_uid": source_uid,
                    "target_folder": target_folder,
                },
                status=ReviewTaskStatus.PENDING,
                idempotency_key=key,
                resource_version=source_uid,
            )
            self._session.add(task)
            self._session.flush()
            workflow.pending_review_task_id = task.id
            if action_type is ReviewActionType.ARCHIVE_EMAIL:
                email.archive_status = ArchiveStatus.PROPOSED
            return task

    def decide(
        self,
        task_id: str,
        decision: ReviewDecision,
    ) -> ReviewDecisionResponse:
        service = ReviewTaskService(self._session, self._user_id)
        recorded = service.record_decision(
            task_id,
            decision,
            update_workflow=True,
        )
        if not recorded.should_resume:
            return service.response_for_task(task_id)
        if recorded.task.status is ReviewTaskStatus.REJECTED:
            self._reset_after_rejection(recorded.task)
            return service.response_for_task(task_id)
        return self.execute(task_id)

    def execute(self, task_id: str) -> ReviewDecisionResponse:
        service = ReviewTaskService(self._session, self._user_id)
        task = service.get(task_id)
        if task.action_type not in {
            ReviewActionType.ARCHIVE_EMAIL,
            ReviewActionType.RESTORE_EMAIL,
        }:
            raise ResourceConflictError("审核任务不是邮件移动动作")
        existing = self._latest_execution(task.id)
        if existing is not None:
            if existing.status in {
                ExecutionStatus.SUCCEEDED,
                ExecutionStatus.UNKNOWN,
                ExecutionStatus.RUNNING,
            }:
                return service.response_for_task(task_id)
        if task.status is not ReviewTaskStatus.APPROVED:
            raise ResourceConflictError(
                f"审核任务当前状态 {task.status.value} 不允许执行"
            )

        email = self._emails.get(task.source_email_id or 0)
        payload = dict(task.proposed_payload)
        if task.reviewed_payload:
            payload.update(task.reviewed_payload)
        self._validate_command(task, email, payload)
        attempt_no = (existing.attempt_no if existing else 0) + 1
        execution = ActionExecution(
            review_task_id=task.id,
            attempt_no=attempt_no,
            idempotency_key=f"imap-move:{task.id}:{attempt_no}",
            executor_type=ExecutorType.IMAP,
            status=ExecutionStatus.RUNNING,
            started_at=_utc_now(),
        )
        task.status = ReviewTaskStatus.EXECUTING
        self._session.add(execution)
        self._session.commit()

        try:
            credential = self._credential_resolver.resolve(email.account.credential_ref)
            result = self._mover.move(
                email.account,
                credential,
                source_folder=str(payload["source_folder"]),
                source_uid=int(payload["source_uid"]),
                target_folder=str(payload["target_folder"]),
                create_target=task.action_type is ReviewActionType.ARCHIVE_EMAIL,
                on_copy=lambda copied: self._checkpoint_copy(execution, copied),
            )
        except ImapMoveUnknownError as exc:
            execution.status = ExecutionStatus.UNKNOWN
            execution.error_code = "IMAP_MOVE_UNKNOWN"
            execution.error_message = str(exc)[:500]
            task.status = ReviewTaskStatus.UNKNOWN
        except (EmailConnectionError, CredentialNotConfiguredError) as exc:
            execution.status = ExecutionStatus.FAILED
            execution.error_code = "IMAP_MOVE_FAILED"
            execution.error_message = str(exc)[:500]
            task.status = ReviewTaskStatus.FAILED
            if task.action_type is ReviewActionType.ARCHIVE_EMAIL:
                email.archive_status = ArchiveStatus.FAILED
        else:
            self._apply_success(email, task, result)
            execution.status = ExecutionStatus.SUCCEEDED
            execution.external_reference = (
                f"imap:{result.folder}:{result.uid_validity}:{result.uid}"
            )
            execution.result = {
                "email_id": email.id,
                "folder": result.folder,
                "uid_validity": result.uid_validity,
                "uid": result.uid,
            }
            task.status = ReviewTaskStatus.SUCCEEDED
        execution.finished_at = _utc_now()
        self._update_workflow(task, execution)
        self._session.commit()
        return service.response_for_task(task_id)

    def _reset_after_rejection(self, task: ReviewTask) -> None:
        email = self._emails.get(task.source_email_id or 0)
        email.archive_status = (
            ArchiveStatus.NONE
            if task.action_type is ReviewActionType.ARCHIVE_EMAIL
            else ArchiveStatus.ARCHIVED
        )
        self._session.commit()

    def _validate_command(
        self,
        task: ReviewTask,
        email: Email,
        payload: dict[str, object],
    ) -> None:
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
            email.current_folder != payload.get("source_folder")
            or current_uid != payload.get("source_uid")
            or current_uid_validity != payload.get("source_uid_validity")
        ):
            raise ResourceConflictError("邮件当前位置已变化，请重新发起审核")

    def _apply_success(
        self,
        email: Email,
        task: ReviewTask,
        result: ImapMoveResult,
    ) -> None:
        source_folder = email.current_folder
        email.previous_folder = source_folder
        email.current_folder = result.folder
        email.current_uid_validity = result.uid_validity
        email.current_imap_uid = result.uid
        if task.action_type is ReviewActionType.ARCHIVE_EMAIL:
            email.archive_status = ArchiveStatus.ARCHIVED
            email.archived_at = _utc_now()
        else:
            email.archive_status = ArchiveStatus.RESTORED
            email.archived_at = None

    def _checkpoint_copy(
        self,
        execution: ActionExecution,
        result: ImapMoveResult,
    ) -> None:
        execution.external_reference = (
            f"imap-copy:{result.folder}:{result.uid_validity}:{result.uid}"
        )
        execution.result = {
            "phase": "COPIED",
            "folder": result.folder,
            "uid_validity": result.uid_validity,
            "uid": result.uid,
        }
        self._session.commit()

    def _update_workflow(
        self,
        task: ReviewTask,
        execution: ActionExecution,
    ) -> None:
        workflow = self._session.get(WorkflowRun, task.workflow_run_id)
        if workflow is None:
            return
        workflow.pending_review_task_id = None
        workflow.current_node = None
        workflow.finished_at = _utc_now()
        if execution.status is ExecutionStatus.SUCCEEDED:
            workflow.status = WorkflowRunStatus.SUCCEEDED
        elif execution.status is ExecutionStatus.UNKNOWN:
            workflow.status = WorkflowRunStatus.FAILED
            workflow.error_code = "IMAP_MOVE_UNKNOWN"
            workflow.error_message = execution.error_message
        else:
            workflow.status = WorkflowRunStatus.FAILED
            workflow.error_code = "IMAP_MOVE_FAILED"
            workflow.error_message = execution.error_message

    def _latest_execution(self, task_id: str) -> ActionExecution | None:
        return self._session.scalar(
            select(ActionExecution)
            .where(ActionExecution.review_task_id == task_id)
            .order_by(ActionExecution.attempt_no.desc())
            .limit(1)
        )


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
