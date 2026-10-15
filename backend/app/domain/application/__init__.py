"""求职申请领域状态与命令。"""

from app.domain.application.commands import (
    CommandContext,
    InterviewApplicationOutcome,
    RecordInterviewResultCommand,
    RecordInterviewScheduleCommand,
    RecordOfferDecisionCommand,
    ReopenApplicationCommand,
    ScheduleInterviewRoundCommand,
    TransitionApplicationCommand,
)
from app.domain.application.policy import (
    ApplicationState,
    ApplicationStateChange,
    ApplicationStateError,
    ApplicationStatePolicy,
    StageTransitionStatus,
    StageTransitionValidation,
)

__all__ = [
    "ApplicationState",
    "ApplicationStateChange",
    "ApplicationStateError",
    "ApplicationStatePolicy",
    "CommandContext",
    "InterviewApplicationOutcome",
    "RecordInterviewScheduleCommand",
    "RecordInterviewResultCommand",
    "RecordOfferDecisionCommand",
    "ReopenApplicationCommand",
    "ScheduleInterviewRoundCommand",
    "StageTransitionStatus",
    "StageTransitionValidation",
    "TransitionApplicationCommand",
]
