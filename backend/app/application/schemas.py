from datetime import UTC, datetime
from typing import Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    ArchiveStatus,
    EmailParseStatus,
    ReplyDraftStatus,
    TaskStatus,
    TaskType,
)


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class UtcResponseSchema(ApiSchema):
    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_datetime(self, value: Any) -> Any:
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class EmailListItem(UtcResponseSchema):
    id: int
    account_id: int
    application_id: int | None
    subject: str
    from_name: str | None
    from_address: str
    received_at: datetime | None
    parse_status: EmailParseStatus
    archive_status: ArchiveStatus


class EmailDetail(EmailListItem):
    message_id: str | None
    to_recipients: list[dict[str, Any]]
    cc_recipients: list[dict[str, Any]]
    sent_at: datetime | None
    plain_body: str | None
    html_sanitized: str | None
    attachment_metadata: list[dict[str, Any]]


class JobApplicationCreate(ApiSchema):
    company_name: str = Field(min_length=1, max_length=255)
    company_alias: str | None = Field(default=None, max_length=255)
    position_name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    applied_at: AwareDatetime | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=320)
    notes: str | None = None


class JobApplicationUpdate(ApiSchema):
    version: int = Field(gt=0)
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    company_alias: str | None = Field(default=None, max_length=255)
    position_name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    applied_at: AwareDatetime | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=320)
    notes: str | None = None


class JobApplicationRead(UtcResponseSchema):
    id: int
    user_id: int
    company_name: str
    company_alias: str | None
    position_name: str
    location: str | None
    current_stage: ApplicationStage
    status: ApplicationStatus
    source: ApplicationSource
    applied_at: datetime | None
    contact_name: str | None
    contact_email: str | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class TaskCreate(ApiSchema):
    application_id: int | None = Field(default=None, gt=0)
    source_email_id: int | None = Field(default=None, gt=0)
    task_type: TaskType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    raw_time_text: str | None = Field(default=None, max_length=500)
    start_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    source_timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=500)
    meeting_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def require_schedule_time(self) -> "TaskCreate":
        if self.start_at is None and self.deadline_at is None:
            raise ValueError("task requires start_at or deadline_at")
        return self


class TaskUpdate(ApiSchema):
    version: int = Field(gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    source_timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=500)
    meeting_url: str | None = Field(default=None, max_length=2048)
    status: TaskStatus | None = None


class TaskRead(UtcResponseSchema):
    id: int
    user_id: int
    application_id: int | None
    source_email_id: int | None
    task_type: TaskType
    title: str
    description: str | None
    raw_time_text: str | None
    start_at: datetime | None
    deadline_at: datetime | None
    source_timezone: str | None
    location: str | None
    meeting_url: str | None
    status: TaskStatus
    version: int
    created_at: datetime
    updated_at: datetime


class ReplyDraftCreate(ApiSchema):
    email_id: int = Field(gt=0)
    application_id: int | None = Field(default=None, gt=0)
    workflow_run_id: str = Field(min_length=36, max_length=36)
    to_recipients: list[dict[str, Any]]
    cc_recipients: list[dict[str, Any]] = Field(default_factory=list)
    subject: str = Field(min_length=1, max_length=998)
    generated_body: str = Field(min_length=1)
    facts_used: list[dict[str, Any]] = Field(default_factory=list)
    uncertain_claims: list[dict[str, Any]] = Field(default_factory=list)


class ReplyDraftUpdate(ApiSchema):
    reviewed_body: str = Field(min_length=1)


class ReplyDraftRead(UtcResponseSchema):
    id: int
    email_id: int
    application_id: int | None
    workflow_run_id: str
    version: int
    to_recipients: list[dict[str, Any]]
    cc_recipients: list[dict[str, Any]]
    subject: str
    generated_body: str
    reviewed_body: str | None
    facts_used: list[dict[str, Any]]
    uncertain_claims: list[dict[str, Any]]
    status: ReplyDraftStatus
    created_at: datetime
    updated_at: datetime
