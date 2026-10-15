from app.domain.application.policy import (
    ApplicationStatePolicy,
    StageTransitionStatus,
    StageTransitionValidation,
)
from app.domain.enums import ApplicationStage

__all__ = [
    "StageTransitionStatus",
    "StageTransitionValidation",
    "validate_stage_transition",
]


def validate_stage_transition(
    current_stage: ApplicationStage,
    proposed_stage: ApplicationStage,
) -> StageTransitionValidation:
    """校验用户确认前的申请阶段迁移，不执行任何数据库写入。"""
    return ApplicationStatePolicy.validate_stage_transition(
        current_stage,
        proposed_stage,
    )
