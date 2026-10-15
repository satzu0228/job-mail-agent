import pytest

from app.domain.application import (
    ApplicationState,
    ApplicationStateError,
    ApplicationStatePolicy,
    InterviewApplicationOutcome,
)
from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    InterviewResult,
    OfferResult,
)


def _state(
    stage: ApplicationStage,
    *,
    status: ApplicationStatus = ApplicationStatus.ACTIVE,
    interview_result: InterviewResult | None = None,
    offer_result: OfferResult | None = None,
) -> ApplicationState:
    return ApplicationState(stage, status, interview_result, offer_result)


@pytest.mark.parametrize(
    ("outcome", "expected_stage", "expected_status"),
    [
        (
            InterviewApplicationOutcome.CLOSE_AS_REJECTED,
            ApplicationStage.REJECTED,
            ApplicationStatus.CLOSED,
        ),
        (
            InterviewApplicationOutcome.KEEP_ACTIVE,
            ApplicationStage.INTERVIEW,
            ApplicationStatus.ACTIVE,
        ),
    ],
)
def test_failed_interview_respects_complete_user_intent(
    outcome: InterviewApplicationOutcome,
    expected_stage: ApplicationStage,
    expected_status: ApplicationStatus,
) -> None:
    change = ApplicationStatePolicy.record_interview_result(
        _state(ApplicationStage.INTERVIEW, interview_result=InterviewResult.PENDING),
        InterviewResult.FAILED,
        outcome,
    )

    assert change.current.current_stage is expected_stage
    assert change.current.status is expected_status
    assert change.current.interview_result is InterviewResult.FAILED


def test_interview_to_offer_requires_a_passed_round() -> None:
    with pytest.raises(ApplicationStateError, match="面试通过"):
        ApplicationStatePolicy.transition_stage(
            _state(ApplicationStage.INTERVIEW, interview_result=InterviewResult.PENDING),
            ApplicationStage.OFFER,
        )

    change = ApplicationStatePolicy.transition_stage(
        _state(ApplicationStage.INTERVIEW, interview_result=InterviewResult.PENDING),
        ApplicationStage.OFFER,
        interview_result=InterviewResult.PASSED,
    )
    assert change.current.interview_result is InterviewResult.PASSED
    assert change.current.offer_result is OfferResult.PENDING
    assert change.current.status is ApplicationStatus.ACTIVE


@pytest.mark.parametrize(
    ("result", "expected_status"),
    [
        (OfferResult.PENDING, ApplicationStatus.ACTIVE),
        (OfferResult.ACCEPTED, ApplicationStatus.CLOSED),
        (OfferResult.DECLINED, ApplicationStatus.CLOSED),
    ],
)
def test_offer_decision_computes_application_status(
    result: OfferResult,
    expected_status: ApplicationStatus,
) -> None:
    change = ApplicationStatePolicy.record_offer_decision(
        _state(ApplicationStage.OFFER, offer_result=OfferResult.PENDING),
        result,
    )

    assert change.current.offer_result is result
    assert change.current.status is expected_status


def test_reopen_restores_a_valid_active_state() -> None:
    change = ApplicationStatePolicy.reopen(
        _state(
            ApplicationStage.REJECTED,
            status=ApplicationStatus.CLOSED,
            interview_result=InterviewResult.FAILED,
        ),
        ApplicationStage.INTERVIEW,
    )

    assert change.current == _state(
        ApplicationStage.INTERVIEW,
        interview_result=InterviewResult.PENDING,
    )


def test_reopen_rejects_active_application() -> None:
    with pytest.raises(ApplicationStateError, match="不能重新打开"):
        ApplicationStatePolicy.reopen(
            _state(ApplicationStage.APPLIED),
            ApplicationStage.INTERVIEW,
        )
