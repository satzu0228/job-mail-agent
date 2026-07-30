from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.application.email_access import EmailAccessService, EmailSyncError
from app.application.reminders import ReminderService
from app.infrastructure.db.models.email_account import EmailAccount


@dataclass(frozen=True)
class AutomationCycleResult:
    claimed_account_ids: list[int] = field(default_factory=list)
    synced_account_ids: list[int] = field(default_factory=list)
    created_email_ids: list[int] = field(default_factory=list)
    workflow_email_ids: list[int] = field(default_factory=list)
    failed_accounts: dict[int, str] = field(default_factory=dict)
    failed_workflows: dict[int, str] = field(default_factory=dict)
    reminder_ids: list[int] = field(default_factory=list)


class AutomationService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        user_id: int,
        email_access_factory: Callable[[Session], EmailAccessService],
        workflow_starter: Callable[[int], object],
        *,
        reminder_lead_minutes: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._user_id = user_id
        self._email_access_factory = email_access_factory
        self._workflow_starter = workflow_starter
        self._reminder_lead_minutes = reminder_lead_minutes

    def run_cycle(self, *, now: datetime | None = None) -> AutomationCycleResult:
        current = now or _utc_now()
        reminder_ids = self._generate_reminders(current)
        account_ids = self._claim_due_accounts(current)
        synced: list[int] = []
        created_email_ids: list[int] = []
        workflow_email_ids: list[int] = []
        failed_accounts: dict[int, str] = {}
        failed_workflows: dict[int, str] = {}

        for account_id in account_ids:
            try:
                with self._session_factory() as session:
                    result = self._email_access_factory(session).sync(account_id)
                synced.append(account_id)
                created_email_ids.extend(result.created_email_ids)
                self._record_attempt(account_id, current)
            except EmailSyncError as exc:
                failed_accounts[account_id] = str(exc)
                self._record_attempt(account_id, current)
                continue

            for email_id in result.created_email_ids:
                try:
                    self._workflow_starter(email_id)
                    workflow_email_ids.append(email_id)
                except Exception as exc:
                    # 单封模型失败不阻塞同批其他新邮件，错误详情由工作流自身留痕。
                    failed_workflows[email_id] = str(exc)[:500]

        return AutomationCycleResult(
            claimed_account_ids=account_ids,
            synced_account_ids=synced,
            created_email_ids=created_email_ids,
            workflow_email_ids=workflow_email_ids,
            failed_accounts=failed_accounts,
            failed_workflows=failed_workflows,
            reminder_ids=reminder_ids,
        )

    def _claim_due_accounts(self, now: datetime) -> list[int]:
        with self._session_factory() as session, session.begin():
            accounts = list(
                session.scalars(
                    select(EmailAccount)
                    .where(
                        EmailAccount.user_id == self._user_id,
                        EmailAccount.is_active.is_(True),
                        EmailAccount.auto_sync_enabled.is_(True),
                        or_(
                            EmailAccount.next_sync_at.is_(None),
                            EmailAccount.next_sync_at <= now,
                        ),
                    )
                    .order_by(EmailAccount.id)
                    .with_for_update(skip_locked=True)
                )
            )
            for account in accounts:
                account.next_sync_at = now + timedelta(
                    minutes=account.sync_interval_minutes
                )
            return [account.id for account in accounts]

    def _record_attempt(self, account_id: int, now: datetime) -> None:
        with self._session_factory() as session, session.begin():
            account = session.scalar(
                select(EmailAccount)
                .where(
                    EmailAccount.id == account_id,
                    EmailAccount.user_id == self._user_id,
                )
                .with_for_update()
            )
            if account is not None:
                account.last_auto_sync_at = now

    def _generate_reminders(self, now: datetime) -> list[int]:
        with self._session_factory() as session:
            reminders = ReminderService(session, self._user_id).generate_due(
                now=now,
                lead_minutes=self._reminder_lead_minutes,
            )
            return [item.id for item in reminders]


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
