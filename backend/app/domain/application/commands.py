from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.enums import (
    ApplicationStage,
    DecisionSource,
    InterviewResult,
    InterviewRoundSource,
    OfferResult,
)


class InterviewApplicationOutcome(StrEnum):
    """面试结果对申请宏观状态的后续意图。"""

    KEEP_ACTIVE = "KEEP_ACTIVE"
    CLOSE_AS_REJECTED = "CLOSE_AS_REJECTED"


@dataclass(frozen=True)
class CommandContext:
    reason: str
    decision_source: DecisionSource
    source_email_id: int | None = None
    workflow_run_id: str | None = None
    review_task_id: str | None = None


@dataclass(frozen=True)
class TransitionApplicationCommand:
    application_id: int
    expected_version: int
    proposed_stage: ApplicationStage
    context: CommandContext
    interview_result: InterviewResult | None = None
    event_type: str = "STAGE_CHANGED"


@dataclass(frozen=True)
class RecordInterviewResultCommand:
    application_id: int
    expected_version: int
    round_number: int
    result: InterviewResult
    outcome: InterviewApplicationOutcome
    round_source: InterviewRoundSource
    context: CommandContext


@dataclass(frozen=True)
class RecordOfferDecisionCommand:
    application_id: int
    expected_version: int
    result: OfferResult
    context: CommandContext


@dataclass(frozen=True)
class ReopenApplicationCommand:
    application_id: int
    expected_version: int
    target_stage: ApplicationStage
    context: CommandContext


@dataclass(frozen=True)
class ScheduleInterviewRoundCommand:
    application_id: int
    expected_version: int
    title: str
    start_at: datetime
    deadline_at: datetime | None
    raw_time_text: str | None
    source_timezone: str | None
    location: str | None
    meeting_url: str | None
    context: CommandContext


@dataclass(frozen=True)
class RecordInterviewScheduleCommand:
    application_id: int
    expected_version: int
    round_number: int
    interview_date: datetime | None
    location: str | None
    meeting_url: str | None
    round_source: InterviewRoundSource
    source_task_id: int | None
    context: CommandContext
