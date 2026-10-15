from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    ApplicationStage,
    ExecutorType,
    InterviewResult,
    ReviewActionType,
    RiskLevel,
    TaskStatus,
    TaskType,
)


class ReviewCommand(BaseModel):
    model_config = ConfigDict(extra="allow")


class CreateApplicationReviewCommand(ReviewCommand):
    company_name: str = Field(min_length=1, max_length=255)
    position_name: str = Field(min_length=1, max_length=255)


class LinkApplicationReviewCommand(ReviewCommand):
    application_id: int | None = Field(default=None, gt=0)
    application_version: int | None = Field(default=None, gt=0)
    deferred_source_review_task_id: str | None = None

    @model_validator(mode="after")
    def require_target(self) -> LinkApplicationReviewCommand:
        if self.application_id is None and not self.deferred_source_review_task_id:
            raise ValueError("关联申请必须包含目标申请或推迟关联源")
        return self


class TransitionApplicationReviewCommand(ReviewCommand):
    application_id: int = Field(gt=0)
    proposed_stage: ApplicationStage
    interview_result: InterviewResult | None = None


class RecordInterviewResultReviewCommand(ReviewCommand):
    application_id: int = Field(gt=0)
    round_number: int = Field(ge=1, le=20)
    result: InterviewResult
    close_application: bool = True
    source_email_id: int | None = Field(default=None, gt=0)


class CreateTaskReviewCommand(ReviewCommand):
    application_id: int = Field(gt=0)
    source_email_id: int = Field(gt=0)
    task_type: TaskType
    interview_round: int | None = Field(default=None, ge=1, le=20)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    raw_time_text: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = None
    deadline_at: datetime | None = None
    source_timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=500)
    meeting_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_schedule(self) -> CreateTaskReviewCommand:
        if self.start_at is None and self.deadline_at is None:
            raise ValueError("日程必须包含开始时间或截止时间")
        if self.task_type is TaskType.INTERVIEW and self.interview_round is None:
            raise ValueError("面试日程必须包含轮次")
        if self.task_type is not TaskType.INTERVIEW and self.interview_round is not None:
            raise ValueError("非面试日程不能包含面试轮次")
        return self


class TaskReviewSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None
    start_at: datetime | None
    deadline_at: datetime | None
    source_timezone: str | None
    location: str | None
    meeting_url: str | None
    status: TaskStatus


class UpdateTaskReviewCommand(ReviewCommand):
    task_id: int = Field(gt=0)
    task_version: int = Field(gt=0)
    before: TaskReviewSnapshot
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_at: datetime | None = None
    deadline_at: datetime | None = None
    source_timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=500)
    meeting_url: str | None = Field(default=None, max_length=2048)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_change(self) -> UpdateTaskReviewCommand:
        editable = {
            "title",
            "description",
            "start_at",
            "deadline_at",
            "source_timezone",
            "location",
            "meeting_url",
        }
        if not (self.model_fields_set & editable):
            raise ValueError("日程更新必须包含至少一个业务字段")
        return self


class SendReplyReviewCommand(ReviewCommand):
    body: str = Field(min_length=1, max_length=20_000)


class EmailMoveReviewCommand(ReviewCommand):
    source_folder: str = Field(min_length=1, max_length=255)
    source_uid_validity: int = Field(gt=0)
    source_uid: int = Field(gt=0)
    target_folder: str = Field(min_length=1, max_length=255)


class ReviewHandlerKey(StrEnum):
    APPLICATION = "APPLICATION"
    TASK = "TASK"
    SMTP = "SMTP"
    IMAP = "IMAP"


@dataclass(frozen=True)
class ReviewActionSpec:
    action_type: ReviewActionType
    command_schema: type[ReviewCommand]
    editable_fields: frozenset[str]
    risk_level: RiskLevel
    handler_key: ReviewHandlerKey
    executor_type: ExecutorType

    def idempotency_key(self, review_task_id: str, attempt_no: int = 1) -> str:
        return f"execute:{review_task_id}:{attempt_no}"


class ReviewActionHandlerRegistry:
    def __init__(self, specs: list[ReviewActionSpec]) -> None:
        self._specs = {spec.action_type: spec for spec in specs}
        missing = set(ReviewActionType) - set(self._specs)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise RuntimeError(f"审核动作缺少注册项：{names}")

    def get(self, action_type: ReviewActionType) -> ReviewActionSpec:
        return self._specs[action_type]

    def parse(
        self,
        action_type: ReviewActionType,
        proposed_payload: dict[str, Any],
        reviewed_payload: dict[str, Any] | None,
    ) -> ReviewCommand:
        spec = self.get(action_type)
        reviewed = reviewed_payload or {}
        unexpected = set(reviewed) - spec.editable_fields
        if unexpected:
            fields = "、".join(sorted(unexpected))
            raise ValueError(f"审核动作不允许修改字段：{fields}")
        payload = dict(proposed_payload)
        payload.update(reviewed)
        return spec.command_schema.model_validate(payload)


REVIEW_ACTION_REGISTRY = ReviewActionHandlerRegistry(
    [
        ReviewActionSpec(
            ReviewActionType.CREATE_APPLICATION,
            CreateApplicationReviewCommand,
            frozenset({"company_name", "position_name"}),
            RiskLevel.HIGH,
            ReviewHandlerKey.APPLICATION,
            ExecutorType.APPLICATION,
        ),
        ReviewActionSpec(
            ReviewActionType.LINK_APPLICATION,
            LinkApplicationReviewCommand,
            frozenset({"application_id"}),
            RiskLevel.HIGH,
            ReviewHandlerKey.APPLICATION,
            ExecutorType.APPLICATION,
        ),
        ReviewActionSpec(
            ReviewActionType.UPDATE_APPLICATION_STAGE,
            TransitionApplicationReviewCommand,
            frozenset({"proposed_stage", "interview_result"}),
            RiskLevel.HIGH,
            ReviewHandlerKey.APPLICATION,
            ExecutorType.APPLICATION,
        ),
        ReviewActionSpec(
            ReviewActionType.UPDATE_INTERVIEW_RESULT,
            RecordInterviewResultReviewCommand,
            frozenset({"result", "close_application"}),
            RiskLevel.HIGH,
            ReviewHandlerKey.APPLICATION,
            ExecutorType.APPLICATION,
        ),
        ReviewActionSpec(
            ReviewActionType.CREATE_TASK,
            CreateTaskReviewCommand,
            frozenset(
                {
                    "title",
                    "description",
                    "start_at",
                    "deadline_at",
                    "source_timezone",
                    "location",
                    "meeting_url",
                }
            ),
            RiskLevel.HIGH,
            ReviewHandlerKey.TASK,
            ExecutorType.TASK,
        ),
        ReviewActionSpec(
            ReviewActionType.UPDATE_TASK,
            UpdateTaskReviewCommand,
            frozenset(
                {
                    "title",
                    "description",
                    "start_at",
                    "deadline_at",
                    "source_timezone",
                    "location",
                    "meeting_url",
                    "reason",
                }
            ),
            RiskLevel.HIGH,
            ReviewHandlerKey.TASK,
            ExecutorType.TASK,
        ),
        ReviewActionSpec(
            ReviewActionType.SEND_REPLY,
            SendReplyReviewCommand,
            frozenset({"body"}),
            RiskLevel.HIGH,
            ReviewHandlerKey.SMTP,
            ExecutorType.SMTP,
        ),
        ReviewActionSpec(
            ReviewActionType.ARCHIVE_EMAIL,
            EmailMoveReviewCommand,
            frozenset(),
            RiskLevel.MEDIUM,
            ReviewHandlerKey.IMAP,
            ExecutorType.IMAP,
        ),
        ReviewActionSpec(
            ReviewActionType.RESTORE_EMAIL,
            EmailMoveReviewCommand,
            frozenset(),
            RiskLevel.MEDIUM,
            ReviewHandlerKey.IMAP,
            ExecutorType.IMAP,
        ),
    ]
)
