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

from app.agents.application.schemas import (
    ApplicationAgentOutput,
    ApplicationCandidate,
)
from app.agents.classification.schemas import ClassificationOutput
from app.agents.extraction.schemas import ExtractionOutput
from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    ArchiveStatus,
    DecisionSource,
    EmailAnalysisStatus,
    EmailCategory,
    EmailDirection,
    EmailParseStatus,
    EmailPriority,
    ExecutionStatus,
    ExecutorType,
    InterviewResult,
    ReminderStatus,
    ReplyDraftStatus,
    ReviewActionType,
    ReviewTaskStatus,
    RiskLevel,
    TaskStatus,
    TaskType,
    TransportSecurity,
    WorkflowRunStatus,
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
    email_address: str
    email_address_masked: str
    imap_host: str
    imap_port: int
    imap_security: TransportSecurity
    smtp_host: str
    smtp_port: int
    smtp_security: TransportSecurity
    is_active: bool
    auto_sync_enabled: bool
    sync_interval_minutes: int
    next_sync_at: datetime | None
    last_auto_sync_at: datetime | None
    inbox_uid_validity: int | None
    last_synced_uid: int | None
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_error: str | None
    created_at: datetime
    updated_at: datetime


class EmailAccountActiveUpdate(ApiSchema):
    is_active: bool


class EmailAccountSyncSettingsUpdate(ApiSchema):
    enabled: bool
    interval_minutes: int = Field(default=10, ge=5, le=60)


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
    created_email_ids: list[int] = Field(default_factory=list)


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
    to_recipients: list[dict[str, Any]]
    direction: EmailDirection
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
    cc_recipients: list[dict[str, Any]]
    sent_at: datetime | None
    plain_body: str | None
    html_sanitized: str | None
    attachment_metadata: list[dict[str, Any]]
    current_analysis: EmailAnalysisRead | None = None


class EmailPage(ApiSchema):
    items: list[EmailListItem]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


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


class JobApplicationStageTransition(ApiSchema):
    version: int = Field(gt=0)
    proposed_stage: ApplicationStage
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("阶段更新原因不能为空")
        return normalized


class JobApplicationInterviewResultUpdate(ApiSchema):
    version: int = Field(gt=0)
    result: InterviewResult
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_result_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("面试结果说明不能为空")
        return normalized


class JobApplicationRead(UtcResponseSchema):
    id: int
    user_id: int
    company_name: str
    company_alias: str | None
    position_name: str
    location: str | None
    current_stage: ApplicationStage
    interview_result: InterviewResult | None
    status: ApplicationStatus
    source: ApplicationSource
    applied_at: datetime | None
    contact_name: str | None
    contact_email: str | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class JobApplicationPage(ApiSchema):
    items: list[JobApplicationRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class ApplicationEventRead(UtcResponseSchema):
    id: int
    application_id: int
    source_email_id: int | None
    workflow_run_id: str | None
    event_type: str
    previous_stage: ApplicationStage | None
    proposed_stage: ApplicationStage | None
    confirmed_stage: ApplicationStage | None
    raw_time_text: str | None
    event_at: datetime | None
    source_timezone: str | None
    details: dict[str, Any] | None
    created_at: datetime


class ApplicationEventPage(ApiSchema):
    items: list[ApplicationEventRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class ApplicationMatchResponse(UtcResponseSchema):
    email_id: int
    analysis_id: int
    candidates: list[ApplicationCandidate]
    suggestion: ApplicationAgentOutput
    review_task_id: str
    requires_human_confirmation: bool = True


class ReviewDecision(ApiSchema):
    version: int = Field(gt=0)
    approve: bool
    reviewed_payload: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=1000)


class ReviewTaskRead(UtcResponseSchema):
    id: str
    user_id: int
    workflow_run_id: str
    source_email_id: int | None
    application_id: int | None
    draft_id: int | None
    action_type: ReviewActionType
    risk_level: RiskLevel
    proposed_payload: dict[str, Any]
    reviewed_payload: dict[str, Any] | None
    status: ReviewTaskStatus
    decision_source: DecisionSource | None
    decision_reason: str | None
    reviewed_at: datetime | None
    resource_version: int
    version: int
    created_at: datetime
    updated_at: datetime


class ReviewTaskPage(ApiSchema):
    items: list[ReviewTaskRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class ActionExecutionRead(UtcResponseSchema):
    id: int
    review_task_id: str
    attempt_no: int
    executor_type: ExecutorType
    status: ExecutionStatus
    external_reference: str | None
    result: dict[str, Any] | None
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None


class ReviewDecisionResponse(ApiSchema):
    review_task: ReviewTaskRead
    execution: ActionExecutionRead | None = None
    follow_up_review_task: ReviewTaskRead | None = None


class WorkflowRunRead(UtcResponseSchema):
    id: str
    thread_id: str
    user_id: int
    email_id: int
    status: WorkflowRunStatus
    current_node: str | None
    graph_version: str
    model_provider: str
    model_name: str
    prompt_versions: dict[str, Any]
    agent_trace: list[dict[str, Any]]
    pending_review_task_id: str | None
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TaskCreate(ApiSchema):
    application_id: int | None = Field(default=None, gt=0)
    source_email_id: int | None = Field(default=None, gt=0)
    task_type: TaskType
    interview_round: int | None = Field(default=None, ge=1, le=20)
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
        if self.task_type is TaskType.INTERVIEW and self.interview_round is None:
            raise ValueError("interview task requires interview_round")
        if self.task_type is not TaskType.INTERVIEW and self.interview_round is not None:
            raise ValueError("only interview task accepts interview_round")
        return self


class TaskUpdate(ApiSchema):
    version: int = Field(gt=0)
    interview_round: int | None = Field(default=None, ge=1, le=20)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    source_timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=500)
    meeting_url: str | None = Field(default=None, max_length=2048)
    status: TaskStatus | None = None


class InterviewTaskWithdrawApplication(ApiSchema):
    version: int = Field(gt=0)
    application_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_withdraw_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("撤回原因不能为空")
        return normalized


class TaskRead(UtcResponseSchema):
    id: int
    user_id: int
    application_id: int | None
    source_email_id: int | None
    task_type: TaskType
    interview_round: int | None
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


class TaskPage(ApiSchema):
    items: list[TaskRead]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class ReminderRead(UtcResponseSchema):
    id: int
    user_id: int
    task_id: int
    title: str
    remind_at: datetime
    event_at: datetime
    status: ReminderStatus
    delivered_at: datetime
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReminderReadUpdate(ApiSchema):
    read: bool = True


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


class ReplyGenerationRequest(ApiSchema):
    workflow_run_id: str | None = Field(default=None, min_length=36, max_length=36)


class ReplyGenerationResponse(ApiSchema):
    should_reply: bool
    confidence: float = Field(ge=0, le=1)
    reason: str
    draft: ReplyDraftRead | None = None
    review_task: ReviewTaskRead | None = None


class ReplySendRequest(ApiSchema):
    draft_version: int = Field(gt=0)
    idempotency_key: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$",
    )


class ReplySendResponse(ApiSchema):
    draft: ReplyDraftRead
    review_task: ReviewTaskRead
    execution: ActionExecutionRead
