from typing import Literal

from pydantic import Field, field_validator

from app.agents.common.schemas import AgentSchema, Confidence, PreparedEmail, ShortText
from app.domain.enums import ApplicationStage, EmailCategory


class ReplyApplicationContext(AgentSchema):
    application_id: int = Field(gt=0)
    company_name: str
    position_name: str
    current_stage: ApplicationStage
    contact_name: str | None = None


class ReplyUserContext(AgentSchema):
    display_name: str
    timezone: str
    preferences: dict[str, object] = Field(default_factory=dict)


class ReplyContext(AgentSchema):
    category: EmailCategory
    should_reply_from_classification: bool
    summary: str | None = None
    event_time: str | None = None
    deadline_at: str | None = None
    company_name: str | None = None
    position_name: str | None = None


class ReplyAgentInput(AgentSchema):
    schema_version: Literal["reply-input.v1"] = "reply-input.v1"
    email: PreparedEmail
    analysis: ReplyContext
    application: ReplyApplicationContext | None = None
    user: ReplyUserContext


class ReplyAgentOutput(AgentSchema):
    schema_version: Literal["reply-output.v1"] = "reply-output.v1"
    should_reply: bool
    language: Literal["zh-CN", "en"] = "zh-CN"
    confidence: Confidence
    reason: ShortText
    body: str | None = Field(default=None, max_length=20_000)
    facts_used: list[ShortText] = Field(default_factory=list, max_length=20)
    uncertain_claims: list[ShortText] = Field(default_factory=list, max_length=20)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("facts_used", "uncertain_claims")
    @classmethod
    def unique_items(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("body")
    @classmethod
    def body_must_not_contain_headers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.casefold()
        forbidden = ("\nsubject:", "\nfrom:", "\nto:", "\ncc:")
        if any(item in lowered for item in forbidden):
            raise ValueError("reply body must not contain message headers")
        normalized = value.strip().casefold()
        if normalized.startswith(("您好：", "尊敬的", "dear ")):
            raise ValueError("reply body must not contain salutation")
        if any(
            marker in normalized
            for marker in ("\n此致\n", "\n敬礼", "\nregards,", "\nsincerely,")
        ):
            raise ValueError("reply body must not contain signature")
        return value

    def model_post_init(self, __context: object) -> None:
        if self.should_reply and self.body is None:
            raise ValueError("should_reply=true requires body")
        if not self.should_reply and self.body is not None:
            raise ValueError("should_reply=false cannot include body")
