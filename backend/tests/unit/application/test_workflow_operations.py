from types import SimpleNamespace

from app.application.workflow import DatabaseWorkflowOperations
from app.domain.enums import ReviewActionType, ReviewTaskStatus


def test_execute_review_captures_task_fields_before_rollback(monkeypatch) -> None:
    class FakeSession:
        expired = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def rollback(self) -> None:
            self.expired = True

    session = FakeSession()

    class ExpiringTask:
        status = ReviewTaskStatus.APPROVED

        @property
        def action_type(self):
            if session.expired:
                raise AssertionError("rollback 后不得再读取 ORM task")
            return ReviewActionType.CREATE_APPLICATION

        @property
        def draft_id(self):
            if session.expired:
                raise AssertionError("rollback 后不得再读取 ORM task")
            return None

    class FakeReviewTaskService:
        def __init__(self, current_session, user_id):
            assert current_session is session

        def get(self, review_task_id):
            return ExpiringTask()

        def execute_decided(self, review_task_id, *, update_workflow):
            return SimpleNamespace(
                follow_up_review_task=None,
                execution=SimpleNamespace(result={"executed": True}),
            )

    monkeypatch.setattr(
        "app.application.workflow.ReviewTaskService",
        FakeReviewTaskService,
    )
    operations = DatabaseWorkflowOperations(
        lambda: session,  # type: ignore[arg-type]
        1,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        model_provider="test",
        model_name="test",
    )

    outcome = operations.execute_review("review-1")

    assert outcome.action_type == ReviewActionType.CREATE_APPLICATION.value
    assert outcome.result == {"executed": True}
