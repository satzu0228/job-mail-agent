from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.application.review_actions import REVIEW_ACTION_REGISTRY
from app.application.review_decisions import (
    review_decision_status,
    set_review_decision,
)
from app.application.schemas import ReviewTaskRead
from app.application.task_commands import TaskCommandHandler
from app.domain.enums import (
    DecisionSource,
    ExecutionStatus,
    ReviewActionType,
    ReviewDecisionStatus,
    ReviewDisplayStatus,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.repositories import EntityNotFoundError


def _payload(action_type: ReviewActionType) -> dict[str, object]:
    common_task = {
        "application_id": 8,
        "source_email_id": 17,
        "title": "材料提交截止提醒",
        "task_type": "MATERIAL",
        "deadline_at": "2026-10-20T10:00:00+08:00",
    }
    payloads: dict[ReviewActionType, dict[str, object]] = {
        ReviewActionType.CREATE_APPLICATION: {
            "company_name": "星河科技",
            "position_name": "后端工程师",
        },
        ReviewActionType.LINK_APPLICATION: {"application_id": 8},
        ReviewActionType.UPDATE_APPLICATION_STAGE: {
            "application_id": 8,
            "proposed_stage": "INTERVIEW",
        },
        ReviewActionType.UPDATE_INTERVIEW_RESULT: {
            "application_id": 8,
            "round_number": 1,
            "result": "PASSED",
        },
        ReviewActionType.CREATE_TASK: common_task,
        ReviewActionType.UPDATE_TASK: {
            "task_id": 31,
            "task_version": 2,
            "before": {
                "title": "一面",
                "description": None,
                "start_at": "2026-10-20T10:00:00+08:00",
                "deadline_at": None,
                "source_timezone": "Asia/Shanghai",
                "location": "线上",
                "meeting_url": None,
                "status": "CONFIRMED",
            },
            "start_at": "2026-10-21T10:00:00+08:00",
            "reason": "招聘方通知改期",
        },
        ReviewActionType.SEND_REPLY: {"body": "感谢邀请，我会准时参加。"},
        ReviewActionType.ARCHIVE_EMAIL: {
            "source_folder": "INBOX",
            "source_uid_validity": 11,
            "source_uid": 12,
            "target_folder": "JobMailArchive",
        },
        ReviewActionType.RESTORE_EMAIL: {
            "source_folder": "JobMailArchive",
            "source_uid_validity": 11,
            "source_uid": 12,
            "target_folder": "INBOX",
        },
    }
    return payloads[action_type]


@pytest.mark.parametrize("action_type", list(ReviewActionType))
def test_every_review_action_has_a_validated_handler_contract(
    action_type: ReviewActionType,
) -> None:
    spec = REVIEW_ACTION_REGISTRY.get(action_type)

    command = REVIEW_ACTION_REGISTRY.parse(action_type, _payload(action_type), None)

    assert command is not None
    assert spec.idempotency_key("review-1") == "execute:review-1:1"
    assert spec.handler_key.value
    assert spec.executor_type.value


@pytest.mark.parametrize("action_type", list(ReviewActionType))
def test_reviewed_payload_cannot_modify_unregistered_internal_fields(
    action_type: ReviewActionType,
) -> None:
    with pytest.raises(ValueError, match="不允许修改字段"):
        REVIEW_ACTION_REGISTRY.parse(
            action_type,
            _payload(action_type),
            {"workflow_run_id": "forged-run"},
        )


@pytest.mark.parametrize("task_type", ["MATERIAL", "DEADLINE"])
def test_create_task_contract_accepts_non_interview_deadlines(task_type: str) -> None:
    payload = _payload(ReviewActionType.CREATE_TASK)
    payload["task_type"] = task_type

    command = REVIEW_ACTION_REGISTRY.parse(
        ReviewActionType.CREATE_TASK,
        payload,
        None,
    )

    assert command.task_type.value == task_type


@pytest.mark.parametrize(
    ("execution_status", "display_status"),
    [
        (None, ReviewDisplayStatus.APPROVED),
        (ExecutionStatus.RUNNING, ReviewDisplayStatus.APPROVED_EXECUTING),
        (ExecutionStatus.SUCCEEDED, ReviewDisplayStatus.APPROVED_SUCCEEDED),
        (ExecutionStatus.FAILED, ReviewDisplayStatus.APPROVED_FAILED),
        (ExecutionStatus.UNKNOWN, ReviewDisplayStatus.APPROVED_UNKNOWN),
    ],
)
def test_review_read_model_combines_decision_and_execution_status(
    execution_status: ExecutionStatus | None,
    display_status: ReviewDisplayStatus,
) -> None:
    now = datetime.now(UTC)
    task = ReviewTaskRead.model_validate(
        {
            "id": "review-1",
            "user_id": 1,
            "workflow_run_id": None,
            "source_email_id": 17,
            "application_id": 8,
            "draft_id": None,
            "action_type": "CREATE_TASK",
            "risk_level": "HIGH",
            "proposed_payload": _payload(ReviewActionType.CREATE_TASK),
            "reviewed_payload": None,
            "decision_status": "APPROVED",
            "execution_status": execution_status,
            "decision_source": "USER",
            "decision_reason": None,
            "reviewed_at": now,
            "resource_version": 0,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )

    assert task.display_status is display_status


def test_decision_writer_updates_only_decision_axis() -> None:
    task = SimpleNamespace(
        decision_status=ReviewDecisionStatus.APPROVED,
        decision_source=None,
        decision_reason=None,
        reviewed_at=None,
    )

    assert review_decision_status(task) is ReviewDecisionStatus.APPROVED
    set_review_decision(
        task,
        ReviewDecisionStatus.REJECTED,
        source=DecisionSource.USER,
        reason="用户拒绝",
        reviewed_at=datetime.now(UTC),
    )

    assert task.decision_status is ReviewDecisionStatus.REJECTED


class _TaskSession:
    def __init__(self, scalar_values: list[object]) -> None:
        self.scalar_values = iter(scalar_values)
        self.added: list[object] = []
        self.executed: list[object] = []

    def scalar(self, statement):
        return next(self.scalar_values)

    def add(self, value: object) -> None:
        if getattr(value, "id", None) is None:
            value.id = 31
        self.added.append(value)

    def flush(self) -> None:
        return None

    def execute(self, statement) -> None:
        self.executed.append(statement)


def test_task_command_handler_creates_material_task_idempotently() -> None:
    application = SimpleNamespace(id=8)
    session = _TaskSession([None, application])
    handler = TaskCommandHandler(session, user_id=1)  # type: ignore[arg-type]
    review = SimpleNamespace(id="review-1", application_id=8, source_email_id=17)
    command = REVIEW_ACTION_REGISTRY.parse(
        ReviewActionType.CREATE_TASK,
        _payload(ReviewActionType.CREATE_TASK),
        None,
    )

    first = handler.create(review, command)
    session.scalar_values = iter([first.task])
    second = handler.create(review, command)

    assert first.task.task_type is TaskType.MATERIAL
    assert first.task.status is TaskStatus.CONFIRMED
    assert second.task is first.task
    assert len(session.added) == 1


def test_task_command_handler_returns_update_before_and_after() -> None:
    task = SimpleNamespace(
        id=31,
        user_id=1,
        application_id=8,
        source_email_id=17,
        source_review_task_id="old-review",
        task_type=TaskType.MATERIAL,
        interview_round=None,
        title="提交材料",
        description=None,
        start_at=None,
        deadline_at=datetime(2026, 10, 20, 2, 0),
        source_timezone="Asia/Shanghai",
        location=None,
        meeting_url=None,
        status=TaskStatus.CONFIRMED,
        version=2,
    )
    session = _TaskSession([task])
    handler = TaskCommandHandler(session, user_id=1)  # type: ignore[arg-type]
    review = SimpleNamespace(id="review-2", application_id=8, source_email_id=17)
    payload = _payload(ReviewActionType.UPDATE_TASK)
    command = REVIEW_ACTION_REGISTRY.parse(
        ReviewActionType.UPDATE_TASK,
        payload,
        None,
    )

    result = handler.update(review, command)

    assert result.before is not None
    assert result.before["start_at"] != result.after["start_at"]
    assert result.after["start_at"] == datetime(2026, 10, 21, 2, 0)
    assert len(session.executed) == 1


def test_task_command_handler_rejects_cross_user_update() -> None:
    session = _TaskSession([None])
    handler = TaskCommandHandler(session, user_id=1)  # type: ignore[arg-type]
    command = REVIEW_ACTION_REGISTRY.parse(
        ReviewActionType.UPDATE_TASK,
        _payload(ReviewActionType.UPDATE_TASK),
        None,
    )

    with pytest.raises(EntityNotFoundError):
        handler.update(
            SimpleNamespace(id="review-2", application_id=8, source_email_id=17),
            command,
        )
