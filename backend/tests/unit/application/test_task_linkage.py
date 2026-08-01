from types import SimpleNamespace

from app.application.task_linkage import settle_interview_tasks
from app.domain.enums import TaskStatus


class FakeSession:
    def __init__(self, tasks: list[SimpleNamespace], latest_round: int | None) -> None:
        self.tasks = tasks
        self.latest_round = latest_round

    def scalar(self, statement):
        return self.latest_round

    def scalars(self, statement):
        return self.tasks

    def execute(self, statement) -> None:
        return None


def test_settle_current_interview_round_marks_returned_tasks_completed() -> None:
    tasks = [
        SimpleNamespace(id=1, status=TaskStatus.CONFIRMED),
        SimpleNamespace(id=2, status=TaskStatus.PENDING),
    ]
    session = FakeSession(tasks, latest_round=2)

    count = settle_interview_tasks(
        session,  # type: ignore[arg-type]
        application_id=7,
        status=TaskStatus.COMPLETED,
        current_round_only=True,
    )

    assert count == 2
    assert all(task.status is TaskStatus.COMPLETED for task in tasks)


def test_settle_interview_tasks_without_active_round_is_noop() -> None:
    session = FakeSession([], latest_round=None)

    count = settle_interview_tasks(
        session,  # type: ignore[arg-type]
        application_id=7,
        status=TaskStatus.COMPLETED,
        current_round_only=True,
    )

    assert count == 0
