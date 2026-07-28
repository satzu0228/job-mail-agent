from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.agents.common.schemas import (
    AgentSchema,
    Confidence,
    Evidence,
    PreparedEmail,
    ShortText,
)
from app.domain.enums import EmailCategory, EmailPriority, RequiredCapability


class ClassificationInput(AgentSchema):
    schema_version: Literal["classification-input.v1"] = "classification-input.v1"
    email: PreparedEmail


class ClassificationOutput(AgentSchema):
    schema_version: Literal["classification-output.v1"] = "classification-output.v1"
    is_job_related: bool
    category: EmailCategory
    priority: EmailPriority
    should_reply: bool
    required_capabilities: list[RequiredCapability] = Field(default_factory=list, max_length=4)
    confidence: Confidence
    evidence: list[Evidence] = Field(min_length=1, max_length=10)
    uncertainties: list[ShortText] = Field(default_factory=list, max_length=10)

    @field_validator("required_capabilities")
    @classmethod
    def reject_duplicate_capabilities(
        cls,
        value: list[RequiredCapability],
    ) -> list[RequiredCapability]:
        if len(value) != len(set(value)):
            raise ValueError("required_capabilities cannot contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_category_consistency(self) -> "ClassificationOutput":
        if self.category is EmailCategory.NON_JOB:
            if self.is_job_related:
                raise ValueError("NON_JOB category requires is_job_related=false")
            disallowed = {
                RequiredCapability.EXTRACT,
                RequiredCapability.MATCH_APPLICATION,
                RequiredCapability.DRAFT_REPLY,
            }
            if set(self.required_capabilities) & disallowed:
                raise ValueError("NON_JOB cannot require job-processing capabilities")
            if self.should_reply:
                raise ValueError("NON_JOB cannot request a job-email reply")
        elif not self.is_job_related:
            raise ValueError("job-related categories require is_job_related=true")

        return self
