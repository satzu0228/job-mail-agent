from datetime import UTC, datetime
from typing import Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.agents.classification.schemas import ClassificationOutput
from app.agents.extraction.schemas import ExtractionOutput
from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    ArchiveStatus,
    EmailAnalysisStatus,
    EmailCategory,
    EmailParseStatus,
    EmailPriority,
    ReplyDraftStatus,
    TaskStatus,
    TaskType,
    TransportSecurity,
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


class EmailAccountCreate(ApiSchema):
    provider: str = Field(min_length=1, max_length=32)
    email_address: str = Field(min_length=3, max_length=320)
    imap_host: str = Field(min_length=1, max_length=255)
    imap_port: int = Field(gt=0, le=65535)
    imap_security: TransportSecurity
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(gt=0, le=65535)
    smtp_security: TransportSecurity
    credential_ref: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    is_active: bool = True

    @field_validator("provider", "imap_host", "smtp_host", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email_address")
    @classmethod
    def normalize_email_address(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.rpartition("@")
        if not separator or not local or "." not in domain:
            raise ValueError("email_address must be a valid mailbox address")
        return normalized


class EmailAccountRead(UtcResponseSchema):
    id: int
    provider: str
    email_address_masked: str
    imap_host: str
    imap_port: int
    imap_security: TransportSecurity
    smtp_host: str
    smtp_port: int
    smtp_security: TransportSecurity
    is_active: bool
    inbox_uid_validity: int | None
    last_synced_uid: int | None
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_error: str | None
    created_at: datetime
    updated_at: datetime


class ConnectionCheck(ApiSchema):
    success: bool
    message: str


class EmailConnectionTestResult(ApiSchema):
    imap: ConnectionCheck
    smtp: ConnectionCheck


class EmailSyncRequest(ApiSchema):
    limit: int | None = Field(default=None, ge=1, le=200)


class EmailSyncResult(ApiSchema):
    account_id: int
    folder: str
    uid_validity: int
    examined: int
    created: int
    skipped: int
    failed: int


class EmailAnalyzeResponse(UtcResponseSchema):
    analysis_id: int
    email_id: int
    version: int
    status: EmailAnalysisStatus
    is_current: bool
    created_at: datetime
    classification: ClassificationOutput
    extraction: ExtractionOutput | None


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


class EmailAnalysisRead(UtcResponseSchema):
    id: int
    email_id: int
    version: int
    is_current: bool
    status: EmailAnalysisStatus
    is_job_related: bool
    category: EmailCategory
    priority: EmailPriority
    should_reply: bool
    classification_confidence: float
    extraction_confidence: float | None
    summary: str | None
    company_name: str | None
    position_name: str | None
    event_type: str | None
    event_time: datetime | None
    deadline_at: datetime | None
    source_timezone: str | None
    extraction_json: dict[str, Any]
    evidence_json: dict[str, Any]
    missing_fields: list[str]
    schema_version: str
    created_at: datetime


class EmailDetail(EmailListItem):
    message_id: str | None
    to_recipients: list[dict[str, Any]]
    cc_recipients: list[dict[str, Any]]
    sent_at: datetime | None
    plain_body: str | None
    html_sanitized: str | None
    attachment_metadata: list[dict[str, Any]]
    current_analysis: EmailAnalysisRead | None = None


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
