from types import SimpleNamespace

from app.application.archive import EmailArchiveService
from app.domain.enums import (
    ArchiveStatus,
    ExecutionStatus,
    ReviewActionType,
    ReviewDecisionStatus,
)
from app.infrastructure.email import ImapMoveResult, ImapMoveUnknownError


class FakeSession:
    def __init__(self, workflow: object) -> None:
        self.workflow = workflow
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def get(self, model: object, value: object) -> object:
        return self.workflow


class FakeCredentialResolver:
    def resolve(self, credential_ciphertext: str | None) -> str:
        assert credential_ciphertext == "v1:archive-test"
        return "secret"


class FakeMover:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def move(self, *args: object, **kwargs: object) -> ImapMoveResult:
        self.calls += 1
        if self.error:
            raise self.error
        assert callable(kwargs.pop("on_copy"))
        assert kwargs == {
            "source_folder": "INBOX",
            "source_uid": 42,
            "target_folder": "JobMailArchive",
            "create_target": True,
        }
        return ImapMoveResult(
            folder="JobMailArchive",
            uid_validity=88,
            uid=99,
        )


def _command() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    account = SimpleNamespace(credential_ciphertext="v1:archive-test")
    email = SimpleNamespace(
        id=8,
        account=account,
        archive_status=ArchiveStatus.PROPOSED,
        archived_at=None,
        source_folder="INBOX",
        current_folder="INBOX",
        previous_folder=None,
        uid_validity=77,
        imap_uid=42,
        current_uid_validity=77,
        current_imap_uid=42,
    )
    task = SimpleNamespace(
        id="archive-review",
        workflow_run_id="archive-run",
        source_email_id=8,
        action_type=ReviewActionType.ARCHIVE_EMAIL,
        decision_status=ReviewDecisionStatus.APPROVED,
        proposed_payload={
            "source_folder": "INBOX",
            "source_uid_validity": 77,
            "source_uid": 42,
            "target_folder": "JobMailArchive",
        },
        reviewed_payload=None,
    )
    workflow = SimpleNamespace(
        status=None,
        pending_review_task_id=task.id,
        current_node="email_move_review",
        finished_at=None,
        error_code=None,
        error_message=None,
    )
    return email, task, workflow


def _service(
    monkeypatch,
    mover: FakeMover,
) -> tuple[EmailArchiveService, FakeSession, SimpleNamespace, SimpleNamespace]:
    email, task, workflow = _command()
    session = FakeSession(workflow)
    service = EmailArchiveService(
        session,  # type: ignore[arg-type]
        1,
        credential_resolver=FakeCredentialResolver(),
        mover=mover,
    )
    service._emails = SimpleNamespace(get=lambda email_id: email)
    executions: list[object] = []
    service._latest_execution = lambda task_id: (  # type: ignore[method-assign]
        executions[-1] if executions else None
    )

    from app.application import archive as archive_module

    monkeypatch.setattr(
        archive_module.ReviewTaskService,
        "get",
        lambda self, task_id: task,
    )
    monkeypatch.setattr(
        archive_module.ReviewTaskService,
        "response_for_task",
        lambda self, task_id: executions[-1],
    )
    original_add = session.add

    def add(value: object) -> None:
        original_add(value)
        if hasattr(value, "executor_type"):
            executions.append(value)

    session.add = add  # type: ignore[method-assign]
    return service, session, email, task


def test_approved_archive_moves_once_and_preserves_original_identity(monkeypatch) -> None:
    mover = FakeMover()
    service, session, email, task = _service(monkeypatch, mover)

    first = service.execute(task.id)
    second = service.execute(task.id)

    assert first is second
    assert first.status is ExecutionStatus.SUCCEEDED
    assert mover.calls == 1
    assert email.uid_validity == 77
    assert email.imap_uid == 42
    assert email.current_folder == "JobMailArchive"
    assert email.current_uid_validity == 88
    assert email.current_imap_uid == 99
    assert email.archive_status is ArchiveStatus.ARCHIVED
    assert session.commits == 2


def test_unknown_archive_result_is_never_retried(monkeypatch) -> None:
    mover = FakeMover(ImapMoveUnknownError("结果未知"))
    service, _, email, task = _service(monkeypatch, mover)

    first = service.execute(task.id)
    second = service.execute(task.id)

    assert first is second
    assert first.status is ExecutionStatus.UNKNOWN
    assert task.decision_status is ReviewDecisionStatus.APPROVED
    assert email.archive_status is ArchiveStatus.PROPOSED
    assert mover.calls == 1
