from contextlib import nullcontext

from app.application.email_access import EmailAccessService
from app.infrastructure.db.models.email_account import EmailAccount


class FakeSession:
    def begin(self) -> nullcontext[None]:
        return nullcontext()

    def scalar(self, statement: object) -> object:
        return object()

    def flush(self) -> None:
        return None


class FakeAccountRepository:
    def __init__(self, account: EmailAccount) -> None:
        self.account = account
        self.deactivated_except: int | None | str = "not-called"

    def get(self, account_id: int, *, for_update: bool = False) -> EmailAccount:
        assert account_id == self.account.id
        assert for_update is True
        return self.account

    def deactivate_others(self, *, except_account_id: int | None = None) -> None:
        self.deactivated_except = except_account_id


def test_activating_account_deactivates_other_accounts_in_same_transaction() -> None:
    account = EmailAccount(id=9, user_id=1, is_active=False)
    repository = FakeAccountRepository(account)
    service = EmailAccessService(FakeSession(), 1)  # type: ignore[arg-type]
    service.accounts = repository  # type: ignore[assignment]

    activated = service.set_account_active(9, is_active=True)

    assert activated.is_active is True
    assert repository.deactivated_except == 9


def test_deactivating_account_does_not_change_other_accounts() -> None:
    account = EmailAccount(id=9, user_id=1, is_active=True)
    repository = FakeAccountRepository(account)
    service = EmailAccessService(FakeSession(), 1)  # type: ignore[arg-type]
    service.accounts = repository  # type: ignore[assignment]

    deactivated = service.set_account_active(9, is_active=False)

    assert deactivated.is_active is False
    assert repository.deactivated_except == "not-called"
