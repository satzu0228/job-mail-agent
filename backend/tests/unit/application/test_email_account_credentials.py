from contextlib import nullcontext

from app.application.email_access import EmailAccessService
from app.application.schemas import EmailAccountCreate
from app.domain.enums import TransportSecurity
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.security import EncryptedCredentialResolver

TEST_KEY = "33" * 32


class FakeSession:
    def begin(self):  # noqa: ANN201
        return nullcontext()

    def get(self, model: object, entity_id: int) -> object:
        return object()

    def flush(self) -> None:
        pass


class FakeAccounts:
    def __init__(self, existing: EmailAccount | None = None) -> None:
        self.existing = existing
        self.created: EmailAccount | None = None

    def add(self, account: EmailAccount) -> EmailAccount:
        self.created = account
        return account

    def get(self, account_id: int, *, for_update: bool = False) -> EmailAccount:
        assert account_id == 7
        assert self.existing is not None
        return self.existing


def _service(accounts: FakeAccounts) -> EmailAccessService:
    resolver = EncryptedCredentialResolver(TEST_KEY)
    service = EmailAccessService(
        FakeSession(),  # type: ignore[arg-type]
        1,
        credential_resolver=resolver,
    )
    service.accounts = accounts  # type: ignore[assignment]
    return service


def test_create_account_encrypts_authorization_code_before_persistence() -> None:
    accounts = FakeAccounts()
    service = _service(accounts)

    account = service.create_account(
        EmailAccountCreate(
            provider="163",
            email_address="candidate@163.com",
            imap_host="imap.163.com",
            imap_port=993,
            imap_security=TransportSecurity.SSL,
            smtp_host="smtp.163.com",
            smtp_port=465,
            smtp_security=TransportSecurity.SSL,
            authorization_code="fixture-authorization-code",
            is_active=False,
        )
    )

    assert account.credential_ciphertext is not None
    assert "fixture-authorization-code" not in account.credential_ciphertext
    assert (
        EncryptedCredentialResolver(TEST_KEY).resolve(account.credential_ciphertext)
        == "fixture-authorization-code"
    )


def test_reauthorization_replaces_ciphertext_and_clears_stale_error() -> None:
    account = EmailAccount(
        id=7,
        user_id=1,
        credential_ciphertext=None,
        last_sync_status="FAILED",
        last_sync_error="邮箱需要重新授权",
    )
    service = _service(FakeAccounts(account))

    updated = service.update_authorization_code(
        7,
        authorization_code="new-authorization-code",
    )

    assert updated.last_sync_error is None
    assert updated.last_sync_status is None
    assert (
        EncryptedCredentialResolver(TEST_KEY).resolve(updated.credential_ciphertext)
        == "new-authorization-code"
    )


class SuccessfulConnectionClient:
    def __init__(self) -> None:
        self.calls = 0

    def test_connection(self, account: EmailAccount, credential: str) -> None:
        assert account.id == 7
        assert credential == "qq-authorization-code"
        self.calls += 1


def test_inactive_account_can_run_read_only_connection_test() -> None:
    resolver = EncryptedCredentialResolver(TEST_KEY)
    account = EmailAccount(
        id=7,
        user_id=1,
        is_active=False,
        credential_ciphertext=resolver.protect("qq-authorization-code"),
    )
    service = _service(FakeAccounts(account))
    imap = SuccessfulConnectionClient()
    smtp = SuccessfulConnectionClient()
    service._imap_client = imap  # type: ignore[assignment]
    service._smtp_tester = smtp  # type: ignore[assignment]

    result = service.test_connection(7)

    assert result.imap.success is True
    assert result.smtp.success is True
    assert imap.calls == 1
    assert smtp.calls == 1
