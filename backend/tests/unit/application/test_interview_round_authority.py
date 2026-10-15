from datetime import UTC, datetime
from types import SimpleNamespace

from app.application.application_commands import ApplicationCommandHandler
from app.application.task_auto_creation import TaskAutoCreationService
from app.domain.application import (
    CommandContext,
    InterviewApplicationOutcome,
    RecordInterviewResultCommand,
)
from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    DecisionSource,
    EmailCategory,
    InterviewResult,
    InterviewRoundSource,
    InterviewRoundStatus,
    ReviewActionType,
)
from app.infrastructure.db.models.application_event import ApplicationEvent
from app.infrastructure.db.models.interview_round import InterviewRound
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.task import Task


class _Session:
    def __init__(self, scalar_values: list[object]) -> None:
        self.scalar_values = iter(scalar_values)
        self.added: list[object] = []

    def scalar(self, statement):
        return next(self.scalar_values)

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None


def _application() -> SimpleNamespace:
    return SimpleNamespace(
        id=9,
        version=2,
        current_stage=ApplicationStage.INTERVIEW,
        interview_result=InterviewResult.PENDING,
        offer_result=None,
        status=ApplicationStatus.ACTIVE,
    )


def test_task_has_authoritative_interview_round_foreign_key() -> None:
    foreign_keys = {item.target_fullname for item in Task.interview_round_id.foreign_keys}

    assert foreign_keys == {"interview_rounds.id"}
    assert "interview_round" not in Task.__table__.columns
    assert "interview_result" not in JobApplication.__table__.columns


def test_unscheduled_round_defaults_to_planned() -> None:
    session = _Session([None])
    handler = ApplicationCommandHandler(session, user_id=1)  # type: ignore[arg-type]

    record = handler._upsert_round(
        application_id=9,
        round_number=2,
        result=InterviewResult.PENDING,
        source=InterviewRoundSource.MANUAL,
    )

    assert record.status is InterviewRoundStatus.PLANNED


def test_historical_round_result_does_not_replace_latest_application_projection(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.application.application_commands.settle_interview_tasks",
        lambda *args, **kwargs: 1,
    )
    old_round = InterviewRound(
        id=3,
        application_id=9,
        round_number=1,
        status=InterviewRoundStatus.SCHEDULED,
        result=InterviewResult.PENDING,
        source=InterviewRoundSource.EMAIL,
    )
    session = _Session([old_round, 4])
    handler = ApplicationCommandHandler(session, user_id=1)  # type: ignore[arg-type]
    application = _application()

    change, updated_round = handler.record_interview_result(
        application,
        RecordInterviewResultCommand(
            application_id=9,
            expected_version=2,
            round_number=1,
            result=InterviewResult.PASSED,
            outcome=InterviewApplicationOutcome.KEEP_ACTIVE,
            round_source=InterviewRoundSource.EMAIL,
            context=CommandContext(
                reason="补录历史一面结果",
                decision_source=DecisionSource.USER,
            ),
        ),
    )

    assert updated_round.result is InterviewResult.PASSED
    assert updated_round.status is InterviewRoundStatus.COMPLETED
    assert application.interview_result is InterviewResult.PENDING
    assert change.previous == change.current
    assert any(isinstance(item, ApplicationEvent) for item in session.added)


def test_scheduled_round_uses_explicit_scheduled_status() -> None:
    session = _Session([None])
    handler = ApplicationCommandHandler(session, user_id=1)  # type: ignore[arg-type]

    record = handler._upsert_round(
        application_id=9,
        round_number=2,
        result=InterviewResult.PENDING,
        source=InterviewRoundSource.MANUAL,
        interview_date=datetime(2026, 10, 20, 2, 0, tzinfo=UTC),
    )

    assert record.status is InterviewRoundStatus.SCHEDULED


def test_automatic_schedule_scan_creates_review_instead_of_task() -> None:
    analysis = SimpleNamespace(
        id=18,
        email_id=27,
        category=EmailCategory.MATERIAL_REQUEST,
        extraction_confidence=0.95,
        company_name="星河科技",
        position_name="后端工程师",
        event_type="MATERIAL_DEADLINE",
        summary="请在截止时间前补充成绩单。",
        event_time=None,
        deadline_at=datetime(2026, 10, 20, 2, 0),
        source_timezone="Asia/Shanghai",
        extraction_json={"deadline": {"raw_text": "10 月 20 日 10:00"}},
    )

    class _AutomationSession:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.commits = 0

        def add(self, value: object) -> None:
            self.added.append(value)

        def commit(self) -> None:
            self.commits += 1

    session = _AutomationSession()
    service = TaskAutoCreationService(session, user_id=1)  # type: ignore[arg-type]
    service._find_candidate_analyses = lambda threshold: [analysis]  # type: ignore[method-assign]
    service._task_exists = lambda email_id, task_type: False  # type: ignore[method-assign]
    service._has_task_review = lambda email_id: False  # type: ignore[method-assign]
    service._resolve_application_id = lambda email_id: 8  # type: ignore[method-assign]
    service._application_version = lambda application_id: 2  # type: ignore[method-assign]

    created = service.create_task_reviews_from_analyses()

    assert len(created) == 1
    assert isinstance(created[0], ReviewTask)
    assert created[0].action_type is ReviewActionType.CREATE_TASK
    assert created[0].proposed_payload["task_type"] == "MATERIAL"
    assert not any(isinstance(item, Task) for item in session.added)
    assert session.commits == 1
