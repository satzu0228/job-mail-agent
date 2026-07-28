from enum import StrEnum
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class AgentSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class EvidenceSource(StrEnum):
    SUBJECT = "SUBJECT"
    SENDER = "SENDER"
    BODY = "BODY"
    ATTACHMENT = "ATTACHMENT"


class Evidence(AgentSchema):
    source: EvidenceSource
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class AttachmentMetadata(AgentSchema):
    filename: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    content_type: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ] | None = None
    size_bytes: Annotated[int, Field(ge=0)] | None = None


class PreparedEmail(AgentSchema):
    email_id: Annotated[int, Field(gt=0)] | None = None
    message_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=998),
    ] | None = None
    subject: Annotated[str, StringConstraints(strip_whitespace=True, max_length=998)]
    sender_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ] | None = None
    sender_address: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=320),
    ]
    sent_at: AwareDatetime | None = None
    received_at: AwareDatetime | None = None
    analysis_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200_000),
    ]
    attachments: list[AttachmentMetadata] = Field(default_factory=list, max_length=50)
    user_timezone: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    ] = "Asia/Shanghai"

    @field_validator("user_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("user_timezone must be a valid IANA timezone") from exc
        return value
