from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.agents.common.schemas import AgentSchema, Confidence, ShortText
from app.domain.enums import ApplicationStage, EmailCategory


class ApplicationRecommendation(StrEnum):
    LINK_EXISTING = "LINK_EXISTING"
    CREATE_NEW = "CREATE_NEW"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


class CandidateScoreBreakdown(AgentSchema):
    company: float = Field(ge=0, le=1)
    position: float = Field(ge=0, le=1)
    sender: float = Field(ge=0, le=1)
    linked_email: float = Field(ge=0, le=1)
    recency: float = Field(ge=0, le=1)


class ApplicationCandidate(AgentSchema):
    application_id: int = Field(gt=0)
    company_name: str
    position_name: str
    current_stage: ApplicationStage
    contact_email: str | None = None
    deterministic_score: float = Field(ge=0, le=1)
    score_breakdown: CandidateScoreBreakdown
    match_reasons: list[ShortText] = Field(default_factory=list, max_length=10)


class ApplicationAnalysisFacts(AgentSchema):
    email_id: int = Field(gt=0)
    category: EmailCategory
    sender_address: str
    company_name: str | None = None
    position_name: str | None = None
    proposed_stage: ApplicationStage | None = None
    event_type: str | None = None
    summary: str | None = None


class ApplicationAgentInput(AgentSchema):
    schema_version: Literal["application-input.v1"] = "application-input.v1"
    analysis: ApplicationAnalysisFacts
    candidates: list[ApplicationCandidate] = Field(default_factory=list, max_length=10)
    deterministic_conflict: bool
    conflict_reasons: list[ShortText] = Field(default_factory=list, max_length=10)


class CandidateRanking(AgentSchema):
    application_id: int = Field(gt=0)
    rank: int = Field(gt=0, le=10)
    confidence: Confidence
    reason: ShortText


class ApplicationAgentOutput(AgentSchema):
    schema_version: Literal["application-output.v1"] = "application-output.v1"
    recommendation: ApplicationRecommendation
    selected_application_id: int | None = Field(default=None, gt=0)
    proposed_stage: ApplicationStage | None = None
    confidence: Confidence
    reasoning: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ]
    candidate_rankings: list[CandidateRanking] = Field(default_factory=list, max_length=10)
    uncertainties: list[ShortText] = Field(default_factory=list, max_length=20)

    @field_validator("candidate_rankings")
    @classmethod
    def validate_rankings(cls, value: list[CandidateRanking]) -> list[CandidateRanking]:
        ids = [item.application_id for item in value]
        ranks = [item.rank for item in value]
        if len(ids) != len(set(ids)) or len(ranks) != len(set(ranks)):
            raise ValueError("candidate rankings must have unique ids and ranks")
        return value

    @model_validator(mode="after")
    def validate_recommendation(self) -> "ApplicationAgentOutput":
        if (
            self.recommendation is ApplicationRecommendation.LINK_EXISTING
            and self.selected_application_id is None
        ):
            raise ValueError("LINK_EXISTING requires selected_application_id")
        if (
            self.recommendation is ApplicationRecommendation.CREATE_NEW
            and self.selected_application_id is not None
        ):
            raise ValueError("CREATE_NEW cannot select an existing application")
        return self
