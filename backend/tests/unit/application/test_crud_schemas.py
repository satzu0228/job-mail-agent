from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.application.crud import BusinessCrudService
from app.application.schemas import (
    JobApplicationUpdate,
    TaskCreate,
    TaskRead,
)
from app.domain.enums import TaskStatus, TaskType
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


def test_aware_datetime_is_normalized_to_naive_utc_for_mysql() -> None:
    value = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    normalized = BusinessCrudService._db_values({"start_at": value})

    assert normalized["start_at"] == datetime(2026, 8, 1, 10, 0)
    assert normalized["start_at"].tzinfo is None
