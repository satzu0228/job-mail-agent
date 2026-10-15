from itertools import product

import pytest

from app.domain.application_state import (
    StageTransitionStatus,
    validate_stage_transition,
)
from app.domain.enums import ApplicationStage

FROZEN_ALLOWED_TRANSITIONS = {
    (ApplicationStage.APPLIED, ApplicationStage.ASSESSMENT),
    (ApplicationStage.APPLIED, ApplicationStage.INTERVIEW),
    (ApplicationStage.APPLIED, ApplicationStage.OFFER),
    (ApplicationStage.APPLIED, ApplicationStage.REJECTED),
    (ApplicationStage.APPLIED, ApplicationStage.WITHDRAWN),
    (ApplicationStage.ASSESSMENT, ApplicationStage.INTERVIEW),
    (ApplicationStage.ASSESSMENT, ApplicationStage.OFFER),
    (ApplicationStage.ASSESSMENT, ApplicationStage.REJECTED),
    (ApplicationStage.ASSESSMENT, ApplicationStage.WITHDRAWN),
    (ApplicationStage.INTERVIEW, ApplicationStage.OFFER),
    (ApplicationStage.INTERVIEW, ApplicationStage.REJECTED),
    (ApplicationStage.INTERVIEW, ApplicationStage.WITHDRAWN),
    (ApplicationStage.OFFER, ApplicationStage.WITHDRAWN),
}


@pytest.mark.parametrize(
    ("current", "proposed"),
    [
        (ApplicationStage.APPLIED, ApplicationStage.ASSESSMENT),
        (ApplicationStage.APPLIED, ApplicationStage.INTERVIEW),
        (ApplicationStage.ASSESSMENT, ApplicationStage.INTERVIEW),
        (ApplicationStage.INTERVIEW, ApplicationStage.OFFER),
        (ApplicationStage.APPLIED, ApplicationStage.REJECTED),
        (ApplicationStage.ASSESSMENT, ApplicationStage.REJECTED),
        (ApplicationStage.INTERVIEW, ApplicationStage.REJECTED),
    ],
)
def test_planned_stage_transitions_are_allowed(
    current: ApplicationStage,
    proposed: ApplicationStage,
) -> None:
    result = validate_stage_transition(current, proposed)

    assert result.status is StageTransitionStatus.ALLOWED
    assert result.can_apply is True


def test_same_stage_is_timeline_event_instead_of_transition() -> None:
    result = validate_stage_transition(
        ApplicationStage.INTERVIEW,
        ApplicationStage.INTERVIEW,
    )

    assert result.status is StageTransitionStatus.NO_CHANGE
    assert result.can_apply is False
    assert "时间线事件" in result.reason


def test_stage_regression_is_rejected() -> None:
    result = validate_stage_transition(
        ApplicationStage.OFFER,
        ApplicationStage.INTERVIEW,
    )

    assert result.status is StageTransitionStatus.REJECTED
    assert result.can_apply is False


@pytest.mark.parametrize(
    ("current", "proposed"),
    list(product(ApplicationStage, repeat=2)),
)
def test_complete_stage_transition_matrix_is_frozen(
    current: ApplicationStage,
    proposed: ApplicationStage,
) -> None:
    result = validate_stage_transition(current, proposed)

    if current is proposed:
        expected = StageTransitionStatus.NO_CHANGE
    elif (current, proposed) in FROZEN_ALLOWED_TRANSITIONS:
        expected = StageTransitionStatus.ALLOWED
    else:
        expected = StageTransitionStatus.REJECTED

    assert result.status is expected
    assert result.can_apply is (expected is StageTransitionStatus.ALLOWED)
