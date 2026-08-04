from dataclasses import dataclass
from enum import StrEnum

from app.domain.enums import ApplicationStage


class StageTransitionStatus(StrEnum):
    ALLOWED = "ALLOWED"
    NO_CHANGE = "NO_CHANGE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class StageTransitionValidation:
    current_stage: ApplicationStage
    proposed_stage: ApplicationStage
    status: StageTransitionStatus
    reason: str

    @property
    def can_apply(self) -> bool:
        return self.status is StageTransitionStatus.ALLOWED


_ALLOWED_TRANSITIONS: frozenset[tuple[ApplicationStage, ApplicationStage]] = frozenset(
    {
        (ApplicationStage.APPLIED, ApplicationStage.ASSESSMENT),
        (ApplicationStage.APPLIED, ApplicationStage.INTERVIEW),
        (ApplicationStage.APPLIED, ApplicationStage.OFFER),
        (ApplicationStage.ASSESSMENT, ApplicationStage.INTERVIEW),
        (ApplicationStage.ASSESSMENT, ApplicationStage.OFFER),
        (ApplicationStage.INTERVIEW, ApplicationStage.OFFER),
        (ApplicationStage.APPLIED, ApplicationStage.REJECTED),
        (ApplicationStage.ASSESSMENT, ApplicationStage.REJECTED),
        (ApplicationStage.INTERVIEW, ApplicationStage.REJECTED),
        (ApplicationStage.APPLIED, ApplicationStage.WITHDRAWN),
        (ApplicationStage.ASSESSMENT, ApplicationStage.WITHDRAWN),
        (ApplicationStage.INTERVIEW, ApplicationStage.WITHDRAWN),
        (ApplicationStage.OFFER, ApplicationStage.WITHDRAWN),
    }
)


def validate_stage_transition(
    current_stage: ApplicationStage,
    proposed_stage: ApplicationStage,
) -> StageTransitionValidation:
    """校验用户确认前的申请阶段迁移，不执行任何数据库写入。"""
    if current_stage is proposed_stage:
        return StageTransitionValidation(
            current_stage=current_stage,
            proposed_stage=proposed_stage,
            status=StageTransitionStatus.NO_CHANGE,
            reason="建议阶段与当前阶段相同，应记录邮件时间线事件而不是阶段迁移",
        )
    if (current_stage, proposed_stage) in _ALLOWED_TRANSITIONS:
        return StageTransitionValidation(
            current_stage=current_stage,
            proposed_stage=proposed_stage,
            status=StageTransitionStatus.ALLOWED,
            reason="阶段迁移符合求职状态机",
        )
    return StageTransitionValidation(
        current_stage=current_stage,
        proposed_stage=proposed_stage,
        status=StageTransitionStatus.REJECTED,
        reason=f"不允许从 {current_stage.value} 迁移到 {proposed_stage.value}",
    )
