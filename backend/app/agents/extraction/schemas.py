from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import (
    AgentSchema,
    Confidence,
    Evidence,
    PreparedEmail,
    ShortText,
)
from app.domain.enums import ApplicationStage, EmailCategory, InterviewResult


class ExtractionField(StrEnum):
    COMPANY = "COMPANY"
    POSITION = "POSITION"
    PROPOSED_STAGE = "PROPOSED_STAGE"
    INTERVIEW_RESULT = "INTERVIEW_RESULT"
    EVENT_TYPE = "EVENT_TYPE"
    CONTACT_NAME = "CONTACT_NAME"
    CONTACT_EMAIL = "CONTACT_EMAIL"
    EVENT_TIME = "EVENT_TIME"
    DEADLINE = "DEADLINE"
    LOCATION = "LOCATION"
    MEETING_URL = "MEETING_URL"
    MATERIALS = "MATERIALS"


class ExtractedText(AgentSchema):
    value: ShortText
    confidence: Confidence
    evidence: list[Evidence] = Field(min_length=1, max_length=10)


class ExtractedStage(AgentSchema):
    value: ApplicationStage
    confidence: Confidence
    evidence: list[Evidence] = Field(min_length=1, max_length=10)


class ExtractedInterviewResult(AgentSchema):
    value: InterviewResult
    round_number: int | None = None
    confidence: Confidence
    evidence: list[Evidence] = Field(min_length=1, max_length=10)


class ExtractedUrl(AgentSchema):
    value: AnyHttpUrl
    confidence: Confidence
    evidence: list[Evidence] = Field(min_length=1, max_length=10)


class ExtractedDateTime(AgentSchema):
    raw_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    normalized: AwareDatetime | None
    timezone: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    ] | None
    confidence: Confidence
    evidence: list[Evidence] = Field(min_length=1, max_length=10)
    requires_human_confirmation: bool
    ambiguity_reason: ShortText | None = None

    @model_validator(mode="before")
    @classmethod
    def attach_unambiguous_source_timezone(cls, data: Any) -> Any:
        """模型同时给出有效时区时，为无偏移 ISO 时间补充确定的时区信息。"""
        if not isinstance(data, dict):
            return data

        normalized = data.get("normalized")
        timezone = data.get("timezone")
        if normalized is None or not timezone:
            return data

        try:
            parsed = (
                normalized
                if isinstance(normalized, datetime)
                else datetime.fromisoformat(str(normalized).replace("Z", "+00:00"))
            )
            zone = ZoneInfo(str(timezone))
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            return data

        if parsed.tzinfo is not None:
            return data

        fold_zero = parsed.replace(tzinfo=zone, fold=0)
        fold_one = parsed.replace(tzinfo=zone, fold=1)
        if fold_zero.utcoffset() != fold_one.utcoffset():
            return data

        normalized_data = dict(data)
        normalized_data["normalized"] = fold_zero
        return normalized_data

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_normalization_state(self) -> "ExtractedDateTime":
        if self.normalized is None:
            if not self.requires_human_confirmation:
                raise ValueError("unresolved datetime requires human confirmation")
            if self.ambiguity_reason is None:
                raise ValueError("unresolved datetime requires ambiguity_reason")
        elif self.timezone is None:
            raise ValueError("normalized datetime requires source timezone")

        return self


class ExtractionInput(AgentSchema):
    schema_version: Literal["extraction-input.v1"] = "extraction-input.v1"
    email: PreparedEmail
    classification: ClassificationOutput

    @model_validator(mode="after")
    def reject_non_job_email(self) -> "ExtractionInput":
        if (
            not self.classification.is_job_related
            or self.classification.category is EmailCategory.NON_JOB
        ):
            raise ValueError("ExtractionInput requires a job-related classification")
        return self


class ExtractionOutput(AgentSchema):
    schema_version: Literal["extraction-output.v1"] = "extraction-output.v1"
    summary: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ]
    company: ExtractedText | None = None
    position: ExtractedText | None = None
    proposed_stage: ExtractedStage | None = None
    interview_result: ExtractedInterviewResult | None = None
    event_type: ExtractedText | None = None
    contact_name: ExtractedText | None = None
    contact_email: ExtractedText | None = None
    event_time: ExtractedDateTime | None = None
    deadline: ExtractedDateTime | None = None
    location: ExtractedText | None = None
    meeting_url: ExtractedUrl | None = None
    materials: list[ExtractedText] = Field(default_factory=list, max_length=20)
    overall_confidence: Confidence
    missing_fields: list[ExtractionField] = Field(default_factory=list, max_length=12)
    uncertainties: list[ShortText] = Field(default_factory=list, max_length=20)

    @field_validator("missing_fields")
    @classmethod
    def reject_duplicate_missing_fields(
        cls,
        value: list[ExtractionField],
    ) -> list[ExtractionField]:
        if len(value) != len(set(value)):
            raise ValueError("missing_fields cannot contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_missing_fields(self) -> "ExtractionOutput":
        values_by_field = {
            ExtractionField.COMPANY: self.company,
            ExtractionField.POSITION: self.position,
            ExtractionField.PROPOSED_STAGE: self.proposed_stage,
            ExtractionField.INTERVIEW_RESULT: self.interview_result,
            ExtractionField.EVENT_TYPE: self.event_type,
            ExtractionField.CONTACT_NAME: self.contact_name,
            ExtractionField.CONTACT_EMAIL: self.contact_email,
            ExtractionField.EVENT_TIME: self.event_time,
            ExtractionField.DEADLINE: self.deadline,
            ExtractionField.LOCATION: self.location,
            ExtractionField.MEETING_URL: self.meeting_url,
            ExtractionField.MATERIALS: self.materials,
        }

        # Only check that fields listed in missing_fields are actually null/empty.
        # The reverse (all null fields must be in missing_fields) is too strict:
        # different email categories expect different fields (e.g. INTERVIEW_RESULT
        # and DEADLINE are not expected for interview invitations, so they should
        # not be listed in missing_fields even though they are null).
        claimed_missing_but_present = [
            field
            for field in self.missing_fields
            if values_by_field.get(field)
        ]
        if claimed_missing_but_present:
            names = ", ".join(field.value for field in claimed_missing_but_present)
            raise ValueError(
                f"missing_fields lists fields that are actually present: {names}"
            )

        return self
