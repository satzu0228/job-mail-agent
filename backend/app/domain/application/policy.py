from dataclasses import dataclass
from enum import StrEnum

from app.domain.application.commands import InterviewApplicationOutcome
from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    InterviewResult,
    OfferResult,
)


class ApplicationStateError(ValueError):
    """领域状态或命令前置条件不合法。"""


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


@dataclass(frozen=True)
class ApplicationState:
    current_stage: ApplicationStage
    status: ApplicationStatus
    interview_result: InterviewResult | None
    offer_result: OfferResult | None


@dataclass(frozen=True)
class ApplicationStateChange:
    previous: ApplicationState
    current: ApplicationState

    @property
    def changed_fields(self) -> frozenset[str]:
        return frozenset(
            field_name
            for field_name in (
                "current_stage",
                "status",
                "interview_result",
                "offer_result",
            )
            if getattr(self.previous, field_name) != getattr(self.current, field_name)
        )


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


class ApplicationStatePolicy:
    """不依赖 ORM 或框架的申请状态计算内核。"""

    @staticmethod
    def validate_stage_transition(
        current_stage: ApplicationStage,
        proposed_stage: ApplicationStage,
    ) -> StageTransitionValidation:
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

    @classmethod
    def transition_stage(
        cls,
        state: ApplicationState,
        proposed_stage: ApplicationStage,
        *,
        interview_result: InterviewResult | None = None,
        has_passed_interview: bool = False,
    ) -> ApplicationStateChange:
        validation = cls.validate_stage_transition(state.current_stage, proposed_stage)
        if not validation.can_apply:
            raise ApplicationStateError(validation.reason)
        if (
            state.current_stage is ApplicationStage.INTERVIEW
            and proposed_stage is ApplicationStage.OFFER
            and interview_result is not InterviewResult.PASSED
            and not has_passed_interview
        ):
            raise ApplicationStateError("至少需要一轮面试通过才能进入录用阶段")

        next_interview_result = state.interview_result
        next_offer_result: OfferResult | None = None
        if proposed_stage in {ApplicationStage.APPLIED, ApplicationStage.ASSESSMENT}:
            next_interview_result = None
        elif proposed_stage is ApplicationStage.INTERVIEW:
            next_interview_result = interview_result or InterviewResult.PENDING
        elif proposed_stage is ApplicationStage.OFFER:
            if state.current_stage is ApplicationStage.INTERVIEW:
                next_interview_result = InterviewResult.PASSED
            next_offer_result = OfferResult.PENDING
        elif proposed_stage is ApplicationStage.REJECTED:
            if state.current_stage is ApplicationStage.INTERVIEW:
                next_interview_result = InterviewResult.FAILED

        if proposed_stage is ApplicationStage.REJECTED:
            next_status = ApplicationStatus.CLOSED
        elif proposed_stage is ApplicationStage.WITHDRAWN:
            next_status = ApplicationStatus.WITHDRAWN
        else:
            next_status = ApplicationStatus.ACTIVE

        return ApplicationStateChange(
            previous=state,
            current=ApplicationState(
                current_stage=proposed_stage,
                status=next_status,
                interview_result=next_interview_result,
                offer_result=next_offer_result,
            ),
        )

    @staticmethod
    def record_interview_result(
        state: ApplicationState,
        result: InterviewResult,
        outcome: InterviewApplicationOutcome,
    ) -> ApplicationStateChange:
        if state.current_stage is not ApplicationStage.INTERVIEW:
            raise ApplicationStateError("只有面试阶段的申请可以记录面试结果")
        if (
            result is not InterviewResult.FAILED
            and outcome is not InterviewApplicationOutcome.KEEP_ACTIVE
        ):
            raise ApplicationStateError("只有面试未通过可以同时结束申请")
        if (
            result is InterviewResult.FAILED
            and outcome is InterviewApplicationOutcome.CLOSE_AS_REJECTED
        ):
            stage = ApplicationStage.REJECTED
            status = ApplicationStatus.CLOSED
        else:
            stage = ApplicationStage.INTERVIEW
            status = ApplicationStatus.ACTIVE
        return ApplicationStateChange(
            previous=state,
            current=ApplicationState(
                current_stage=stage,
                status=status,
                interview_result=result,
                offer_result=None,
            ),
        )

    @staticmethod
    def record_offer_decision(
        state: ApplicationState,
        result: OfferResult,
    ) -> ApplicationStateChange:
        if state.current_stage is not ApplicationStage.OFFER:
            raise ApplicationStateError("只有录用阶段的申请可以记录 Offer 结果")
        return ApplicationStateChange(
            previous=state,
            current=ApplicationState(
                current_stage=ApplicationStage.OFFER,
                status=(
                    ApplicationStatus.ACTIVE
                    if result is OfferResult.PENDING
                    else ApplicationStatus.CLOSED
                ),
                interview_result=state.interview_result,
                offer_result=result,
            ),
        )

    @staticmethod
    def reopen(
        state: ApplicationState,
        target_stage: ApplicationStage,
    ) -> ApplicationStateChange:
        if state.status is ApplicationStatus.ACTIVE:
            raise ApplicationStateError("进行中的申请不能重新打开")
        if target_stage in {ApplicationStage.REJECTED, ApplicationStage.WITHDRAWN}:
            raise ApplicationStateError("重新打开的目标必须是非终态阶段")
        return ApplicationStateChange(
            previous=state,
            current=ApplicationState(
                current_stage=target_stage,
                status=ApplicationStatus.ACTIVE,
                interview_result=(
                    InterviewResult.PENDING
                    if target_stage is ApplicationStage.INTERVIEW
                    else state.interview_result
                    if target_stage is ApplicationStage.OFFER
                    else None
                ),
                offer_result=(
                    OfferResult.PENDING if target_stage is ApplicationStage.OFFER else None
                ),
            ),
        )
