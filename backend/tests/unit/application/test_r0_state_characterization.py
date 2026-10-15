from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import mysql

from app.application.application_management import ReviewTaskService
from app.application.crud import BusinessCrudService
from app.application.schemas import (
    JobApplicationInterviewResultUpdate,
    JobApplicationNextInterviewCreate,
)
from app.application.task_auto_creation import TaskAutoCreationService
from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    InterviewResult,
    InterviewRoundStatus,
    OfferResult,
    ReviewActionType,
    TaskType,
)
from app.infrastructure.db.models.interview_round import InterviewRound


class _RecordingSession:
    def __init__(
        self,
        *,
        scalar_value: object = 1,
        scalar_values: list[object] | None = None,
    ) -> None:
        self.scalar_value = scalar_value
        self.scalar_values = iter(scalar_values) if scalar_values is not None else None
        self.scalar_statements: list[object] = []
        self.added: list[object] = []

    def begin(self):
        return nullcontext()

    def scalar(self, statement):
        self.scalar_statements.append(statement)
        if self.scalar_values is not None:
            return next(self.scalar_values)
        return self.scalar_value

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None


def _manual_interview_result_service():
    application = SimpleNamespace(
        id=9,
        version=2,
        current_stage=ApplicationStage.INTERVIEW,
        interview_result=InterviewResult.PENDING,
        offer_result=None,
        status=ApplicationStatus.ACTIVE,
    )
    session = _RecordingSession(scalar_value=None)
    service = BusinessCrudService.__new__(BusinessCrudService)
    service._session = session  # type: ignore[assignment]
    service._user_id = 1
    service.applications = SimpleNamespace(
        get=lambda application_id, for_update: application
    )
    return service, session, application


def test_failed_interview_never_leaves_interview_application_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.application.application_commands.settle_interview_tasks",
        lambda *args, **kwargs: 1,
    )
    service, _, application = _manual_interview_result_service()

    service.update_interview_result(
        9,
        JobApplicationInterviewResultUpdate(
            version=2,
            result=InterviewResult.FAILED,
            reason="一面未通过",
        ),
    )

    assert not (
        application.current_stage is ApplicationStage.INTERVIEW
        and application.status is ApplicationStatus.CLOSED
    )


def test_manual_interview_result_writes_interview_round_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.application.application_commands.settle_interview_tasks",
        lambda *args, **kwargs: 1,
    )
    service, session, _ = _manual_interview_result_service()

    service.update_interview_result(
        9,
        JobApplicationInterviewResultUpdate(
            version=2,
            result=InterviewResult.PASSED,
            reason="用户确认一面通过",
        ),
    )

    assert any(isinstance(value, InterviewRound) for value in session.added)


def test_next_interview_number_is_derived_from_interview_rounds() -> None:
    application = SimpleNamespace(
        id=9,
        version=3,
        current_stage=ApplicationStage.INTERVIEW,
        interview_result=InterviewResult.PASSED,
        offer_result=None,
        status=ApplicationStatus.ACTIVE,
    )
    session = _RecordingSession(scalar_values=[2, None])

    class _Tasks:
        def add(self, task):
            task.id = 31
            return task

    service = BusinessCrudService.__new__(BusinessCrudService)
    service._session = session  # type: ignore[assignment]
    service._user_id = 1
    service.applications = SimpleNamespace(
        get=lambda application_id, for_update: application
    )
    service.tasks = _Tasks()  # type: ignore[assignment]

    service.schedule_next_interview(
        9,
        JobApplicationNextInterviewCreate(
            version=3,
            title="三面",
            start_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
            source_timezone="Asia/Shanghai",
            reason="招聘人员通知",
        ),
    )

    sql = str(
        session.scalar_statements[0].compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "interview_rounds" in sql
    assert "tasks.interview_round" not in sql


def test_review_transition_to_offer_initializes_pending_offer_result() -> None:
    application = SimpleNamespace(
        id=8,
        version=1,
        current_stage=ApplicationStage.APPLIED,
        interview_result=None,
        offer_result=None,
        status=ApplicationStatus.ACTIVE,
    )
    session = _RecordingSession()
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]
    service._owned_application = lambda application_id: application  # type: ignore[method-assign]
    task = SimpleNamespace(
        id="offer-review",
        action_type=ReviewActionType.UPDATE_APPLICATION_STAGE,
        source_email_id=17,
        workflow_run_id="run-1",
    )

    service._execute(
        task,
        {
            "application_id": application.id,
            "proposed_stage": ApplicationStage.OFFER.value,
        },
    )

    assert application.offer_result is OfferResult.PENDING
    assert application.status is ApplicationStatus.ACTIVE


@pytest.mark.parametrize("task_type", [TaskType.MATERIAL, TaskType.DEADLINE])
def test_review_executor_accepts_non_interview_deadline_tasks(
    task_type: TaskType,
) -> None:
    session = _RecordingSession()
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]
    service._owned_application = lambda application_id: SimpleNamespace(id=8)  # type: ignore[method-assign]
    service._owned_email = lambda email_id: SimpleNamespace(id=17)  # type: ignore[method-assign]
    task = SimpleNamespace(
        action_type=ReviewActionType.CREATE_TASK,
        application_id=8,
        source_email_id=17,
        reviewed_payload=None,
    )

    service._validate_approved_payload(
        task,
        {
            "application_id": 8,
            "source_email_id": 17,
            "task_type": task_type.value,
            "title": "提交截止提醒",
            "deadline_at": "2026-09-03T10:00:00Z",
        },
    )


def test_rejected_task_review_blocks_automatic_task_creation() -> None:
    session = _RecordingSession(scalar_value=None)
    service = TaskAutoCreationService(session, user_id=1)  # type: ignore[arg-type]

    service._has_task_review(source_email_id=17)

    sql = str(
        session.scalar_statements[0].compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "REJECTED" in sql


def test_interview_round_supports_planned_status() -> None:
    assert getattr(InterviewRoundStatus, "PLANNED", None) is not None
