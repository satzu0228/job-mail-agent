from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.application.crud import BusinessCrudService
from app.application.schemas import (
    JobApplicationInterviewResultUpdate,
    JobApplicationStageTransition,
    JobApplicationUpdate,
    TaskCreate,
    TaskRead,
)
from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    InterviewResult,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.repositories import VersionConflictError


def test_task_input_requires_timezone_and_a_schedule_value() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(
            task_type=TaskType.INTERVIEW,
            title="线上面试",
            start_at=datetime(2026, 8, 1, 10, 0),
        )

    with pytest.raises(ValidationError):
        TaskCreate(task_type=TaskType.INTERVIEW, title="线上面试")

    interview = TaskCreate(
        task_type=TaskType.INTERVIEW,
        interview_round=2,
        title="二面",
        start_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
    )

    assert interview.interview_round == 2


def test_response_serializes_database_utc_as_aware_iso_value() -> None:
    response = TaskRead(
        id=1,
        user_id=1,
        application_id=None,
        source_email_id=None,
        task_type=TaskType.DEADLINE,
        interview_round=None,
        title="提交材料",
        description=None,
        raw_time_text=None,
        start_at=None,
        deadline_at=datetime(2026, 8, 1, 2, 0),
        source_timezone="Asia/Shanghai",
        location=None,
        meeting_url=None,
        status=TaskStatus.PENDING,
        version=1,
        created_at=datetime(2026, 7, 28, 10, 0),
        updated_at=datetime(2026, 7, 28, 10, 0),
    )

    payload = response.model_dump(mode="json")
    assert payload["deadline_at"] == "2026-08-01T02:00:00Z"
    assert payload["created_at"].endswith("Z")


def test_application_update_has_no_critical_stage_field_and_checks_version() -> None:
    assert "current_stage" not in JobApplicationUpdate.model_fields
    with pytest.raises(VersionConflictError):
        BusinessCrudService._check_version(actual=3, expected=2)


def test_manual_stage_transition_rejects_blank_reason() -> None:
    with pytest.raises(ValidationError):
        JobApplicationStageTransition(
            version=1,
            proposed_stage=ApplicationStage.INTERVIEW,
            reason="   ",
        )


def test_manual_stage_transition_updates_status_and_writes_user_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.application.crud.settle_interview_tasks", lambda *args, **kwargs: 1
    )
    application = SimpleNamespace(
        id=8,
        version=3,
        current_stage=ApplicationStage.INTERVIEW,
        status=ApplicationStatus.ACTIVE,
    )

    class FakeSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def begin(self):
            return nullcontext()

        def scalar(self, statement):
            return 1

        def add(self, value: object) -> None:
            self.added.append(value)

        def flush(self) -> None:
            return None

    session = FakeSession()
    service = BusinessCrudService.__new__(BusinessCrudService)
    service._session = session  # type: ignore[assignment]
    service.applications = SimpleNamespace(
        get=lambda application_id, for_update: application
    )

    updated = service.transition_application_stage(
        8,
        JobApplicationStageTransition(
            version=3,
            proposed_stage=ApplicationStage.REJECTED,
            reason="招聘网站显示未通过",
        ),
    )

    assert updated.current_stage is ApplicationStage.REJECTED
    assert updated.status is ApplicationStatus.CLOSED
    event = session.added[0]
    assert event.event_type == "MANUAL_STAGE_CHANGED"
    assert event.previous_stage is ApplicationStage.INTERVIEW
    assert event.confirmed_stage is ApplicationStage.REJECTED
    assert event.details == {
        "decision_source": "USER",
        "reason": "招聘网站显示未通过",
    }


def test_manual_interview_result_closes_failed_application_and_writes_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.application.crud.settle_interview_tasks", lambda *args, **kwargs: 1
    )
    application = SimpleNamespace(
        id=9,
        version=2,
        current_stage=ApplicationStage.INTERVIEW,
        interview_result=InterviewResult.PENDING,
        status=ApplicationStatus.ACTIVE,
    )

    class FakeSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def begin(self):
            return nullcontext()

        def scalar(self, statement):
            return 1

        def add(self, value: object) -> None:
            self.added.append(value)

        def flush(self) -> None:
            return None

    session = FakeSession()
    service = BusinessCrudService.__new__(BusinessCrudService)
    service._session = session  # type: ignore[assignment]
    service.applications = SimpleNamespace(
        get=lambda application_id, for_update: application
    )

    updated = service.update_interview_result(
        9,
        JobApplicationInterviewResultUpdate(
            version=2,
            result=InterviewResult.FAILED,
            reason="招聘网站显示一面未通过",
        ),
    )

    assert updated.current_stage is ApplicationStage.INTERVIEW
    assert updated.interview_result is InterviewResult.FAILED
    assert updated.status is ApplicationStatus.CLOSED
    event = session.added[0]
    assert event.event_type == "INTERVIEW_RESULT_CHANGED"
    assert event.details["previous_result"] == "PENDING"
    assert event.details["interview_result"] == "FAILED"


def test_aware_datetime_is_normalized_to_naive_utc_for_mysql() -> None:
    value = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    normalized = BusinessCrudService._db_values({"start_at": value})

    assert normalized["start_at"] == datetime(2026, 8, 1, 10, 0)
    assert normalized["start_at"].tzinfo is None
