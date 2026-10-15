from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.application_commands import ApplicationCommandHandler
from app.application.review_actions import (
    CreateTaskReviewCommand,
    UpdateTaskReviewCommand,
)
from app.domain.application import CommandContext, RecordInterviewScheduleCommand
from app.domain.enums import DecisionSource, InterviewRoundSource, TaskStatus, TaskType
from app.infrastructure.db.models.interview_round import InterviewRound
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.reminder import Reminder
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.repositories import (
    EntityNotFoundError,
    ResourceConflictError,
    VersionConflictError,
)


@dataclass(frozen=True)
class TaskCommandResult:
    task: Task
    before: dict[str, Any] | None
    after: dict[str, Any]


class TaskCommandHandler:
    """执行经审核的日程创建和更新命令。"""

    EDITABLE_FIELDS = (
        "title",
        "description",
        "start_at",
        "deadline_at",
        "source_timezone",
        "location",
        "meeting_url",
    )

    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def create(
        self,
        review_task: ReviewTask,
        command: CreateTaskReviewCommand,
    ) -> TaskCommandResult:
        existing = self._session.scalar(
            select(Task).where(Task.source_review_task_id == review_task.id).limit(1)
        )
        if existing is not None:
            return TaskCommandResult(existing, None, self._snapshot(existing))
        application = self._owned_application(command.application_id)
        if review_task.application_id != application.id:
            raise ResourceConflictError("日程审核引用的求职申请无效")
        if review_task.source_email_id != command.source_email_id:
            raise ResourceConflictError("日程审核引用的来源邮件无效")
        interview_round = command.interview_round
        task = Task(
            user_id=self._user_id,
            application_id=application.id,
            source_email_id=command.source_email_id,
            source_review_task_id=review_task.id,
            task_type=command.task_type,
            title=command.title.strip(),
            description=command.description,
            raw_time_text=command.raw_time_text,
            start_at=self._db_datetime(command.start_at),
            deadline_at=self._db_datetime(command.deadline_at),
            source_timezone=command.source_timezone,
            location=command.location,
            meeting_url=command.meeting_url,
            status=TaskStatus.CONFIRMED,
        )
        self._session.add(task)
        self._session.flush()
        if task.task_type is TaskType.INTERVIEW:
            round_record = self._sync_interview(
                application,
                task,
                round_number=int(interview_round),
                reason="批准创建面试日程",
            )
            task.round_record = round_record
        return TaskCommandResult(task, None, self._snapshot(task))

    def update(
        self,
        review_task: ReviewTask,
        command: UpdateTaskReviewCommand,
    ) -> TaskCommandResult:
        task = self._session.scalar(
            select(Task)
            .where(Task.id == command.task_id, Task.user_id == self._user_id)
            .with_for_update()
        )
        if task is None:
            raise EntityNotFoundError(f"Task {command.task_id} does not exist")
        if task.version != command.task_version:
            raise VersionConflictError(
                f"Resource version changed: expected {command.task_version}, "
                f"actual {task.version}"
            )
        if review_task.application_id != task.application_id:
            raise ResourceConflictError("日程更新审核引用的求职申请无效")
        before = self._snapshot(task)
        changed = False
        for field_name in self.EDITABLE_FIELDS:
            if field_name not in command.model_fields_set:
                continue
            value = getattr(command, field_name)
            if field_name in {"start_at", "deadline_at"}:
                value = self._db_datetime(value)
            if getattr(task, field_name) != value:
                setattr(task, field_name, value)
                changed = True
        if not changed:
            raise ResourceConflictError("日程审核没有产生实际修改")
        if {"start_at", "deadline_at"} & command.model_fields_set:
            self._session.execute(delete(Reminder).where(Reminder.task_id == task.id))
        self._session.flush()
        if task.task_type is TaskType.INTERVIEW:
            if task.application_id is None or task.interview_round is None:
                raise ResourceConflictError("面试日程缺少申请或轮次关联")
            round_record = self._sync_interview(
                self._owned_application(task.application_id),
                task,
                round_number=task.interview_round,
                reason=command.reason,
            )
            task.round_record = round_record
        return TaskCommandResult(task, before, self._snapshot(task))

    def _sync_interview(
        self,
        application: JobApplication,
        task: Task,
        *,
        round_number: int,
        reason: str,
    ) -> InterviewRound:
        return ApplicationCommandHandler(
            self._session, self._user_id
        ).record_interview_schedule(
            application,
            RecordInterviewScheduleCommand(
                application_id=application.id,
                expected_version=application.version,
                round_number=round_number,
                interview_date=task.start_at,
                location=task.location,
                meeting_url=task.meeting_url,
                round_source=(
                    InterviewRoundSource.EMAIL
                    if task.source_email_id is not None
                    else InterviewRoundSource.MANUAL
                ),
                source_task_id=task.id,
                context=CommandContext(
                    reason=reason,
                    decision_source=DecisionSource.USER,
                    source_email_id=task.source_email_id,
                    review_task_id=task.source_review_task_id,
                ),
            ),
        )

    def _owned_application(self, application_id: int) -> JobApplication:
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

    @staticmethod
    def _db_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def _snapshot(cls, task: Task) -> dict[str, Any]:
        return {
            field_name: getattr(task, field_name)
            for field_name in (*cls.EDITABLE_FIELDS, "status")
        }
