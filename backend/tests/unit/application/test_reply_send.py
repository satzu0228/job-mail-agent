from types import SimpleNamespace

from app.application.reply import ReplySendService
from app.application.schemas import ReplySendRequest
from app.domain.enums import (
    ExecutionStatus,
    ReplyDraftStatus,
    ReviewDecisionStatus,
    TransportSecurity,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def scalar(self, statement: object) -> object | None:
        return None


class FakeMailer:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, account: object, credential: str, message: object) -> str:
        self.calls += 1
        assert credential == "secret"
        return "<sent@example.com>"


class FakeCredentialResolver:
    def resolve(self, credential_ciphertext: str | None) -> str:
        assert credential_ciphertext == "v1:reply-test"
        return "secret"


def _command() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    account = SimpleNamespace(
        id=1,
        email_address="candidate@example.com",
        credential_ciphertext="v1:reply-test",
        smtp_security=TransportSecurity.SSL,
    )
    email = SimpleNamespace(
        message_id="<source@example.com>",
        account=account,
    )
    draft = SimpleNamespace(
        id=3,
        application_id=None,
        version=2,
        status=ReplyDraftStatus.APPROVED,
        to_recipients=[{"address": "hr@example.com"}],
        cc_recipients=[],
        subject="Re: 面试邀请",
        generated_body="已批准正文",
        reviewed_body=None,
    )
    task = SimpleNamespace(
        id="review-reply",
        decision_status=ReviewDecisionStatus.APPROVED,
    )
    return draft, task, email


def test_successful_send_is_reused_without_second_smtp_call() -> None:
    session = FakeSession()
    mailer = FakeMailer()
    service = ReplySendService(
        session,  # type: ignore[arg-type]
        1,
        credential_resolver=FakeCredentialResolver(),
        mailer=mailer,
    )
    draft, task, email = _command()
    request = ReplySendRequest(
        draft_version=2,
        idempotency_key="user-request-1",
    )
    executions: list[object] = []
    service._load_command = lambda draft_id, payload: (  # type: ignore[method-assign]
        draft,
        task,
        email,
    )
    service._latest_execution = lambda task_id: (  # type: ignore[method-assign]
        executions[-1] if executions else None
    )
    service._execution_by_key = lambda key: next(  # type: ignore[method-assign]
        (
            execution
            for execution in executions
            if execution.idempotency_key == key
        ),
        None,
    )
    service._response = lambda d, t, e: e  # type: ignore[method-assign]

    first = service.send(3, request)
    executions.extend(session.added)
    second = service.send(3, request)

    assert first is second
    assert first.status is ExecutionStatus.SUCCEEDED
    assert task.decision_status is ReviewDecisionStatus.APPROVED
    assert mailer.calls == 1


def test_unknown_execution_never_retries_smtp() -> None:
    session = FakeSession()
    mailer = FakeMailer()
    service = ReplySendService(
        session,  # type: ignore[arg-type]
        1,
        credential_resolver=FakeCredentialResolver(),
        mailer=mailer,
    )
    draft, task, email = _command()
    unknown = SimpleNamespace(
        status=ExecutionStatus.UNKNOWN,
        idempotency_key="smtp:3:2:older-request",
    )
    service._load_command = lambda draft_id, payload: (  # type: ignore[method-assign]
        draft,
        task,
        email,
    )
    service._latest_execution = lambda task_id: unknown  # type: ignore[method-assign]
    service._execution_by_key = lambda key: None  # type: ignore[method-assign]
    service._response = lambda d, t, e: e  # type: ignore[method-assign]

    result = service.send(
        3,
        ReplySendRequest(
            draft_version=2,
            idempotency_key="new-request-after-unknown",
        ),
    )

    assert result is unknown
    assert mailer.calls == 0
    assert session.added == []
