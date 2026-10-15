from contextlib import nullcontext
from types import SimpleNamespace

from app.application.mailbox_processing import SyncAndProcessMailbox
from app.application.schemas import EmailSyncResult


class StubEmailAccess:
    def sync(self, account_id: int, *, limit: int | None = None) -> EmailSyncResult:
        assert account_id == 7
        assert limit == 20
        return EmailSyncResult(
            account_id=account_id,
            folder="INBOX",
            uid_validity=9,
            examined=2,
            created=2,
            skipped=0,
            failed=0,
            created_email_ids=[11, 12],
        )


def test_sync_and_process_mailbox_isolates_single_workflow_failure() -> None:
    started: list[int] = []

    def start(email_id: int) -> object:
        started.append(email_id)
        if email_id == 12:
            raise RuntimeError("模型暂不可用")
        return SimpleNamespace(id="run-11")

    use_case = SyncAndProcessMailbox(
        lambda: nullcontext(object()),
        lambda _session: StubEmailAccess(),
        start,
    )

    result = use_case.execute(7, limit=20)

    assert started == [11, 12]
    assert result.created_email_ids == [11, 12]
    assert result.workflow_run_ids == ["run-11"]
    assert result.failed_workflows == {12: "模型暂不可用"}
