from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.schemas import (
    ConnectionCheck,
    EmailAccountCreate,
    EmailConnectionTestResult,
    EmailSyncResult,
)
from app.domain.enums import EmailParseStatus
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories import (
    EmailAccountRepository,
    EmailRepository,
    EntityNotFoundError,
    ResourceConflictError,
)
from app.infrastructure.email import (
    EmailConnectionError,
    ImapMailboxClient,
    ParsedEmail,
    RemoteEmail,
    SmtpConnectionTester,
    parse_email,
)
from app.infrastructure.security import (
    CredentialNotConfiguredError,
    EnvironmentCredentialResolver,
)

INBOX = "INBOX"


class CredentialResolver(Protocol):
    def resolve(self, credential_ref: str) -> str: ...


class ImapClient(Protocol):
    def test_connection(self, account: EmailAccount, credential: str) -> None: ...

    def fetch_recent(
        self,
        account: EmailAccount,
        credential: str,
        *,
        previous_uid_validity: int | None,
        last_synced_uid: int | None,
        limit: int,
        max_message_bytes: int,
    ) -> tuple[int, list[RemoteEmail]]: ...

    def fetch_raw_message(
        self,
        account: EmailAccount,
        credential: str,
        *,
        folder: str,
        uid: int,
        max_message_bytes: int,
    ) -> bytes: ...


class SmtpTester(Protocol):
    def test_connection(self, account: EmailAccount, credential: str) -> None: ...


class EmailSyncError(RuntimeError):
    """同步整体失败；单封解析失败不抛出该异常。"""


@dataclass(frozen=True)
class DownloadedAttachment:
    filename: str
    content_type: str
    content: bytes


class EmailAccessService:
    def __init__(
        self,
        session: Session,
        user_id: int,
        *,
        credential_resolver: CredentialResolver | None = None,
        imap_client: ImapClient | None = None,
        smtp_tester: SmtpTester | None = None,
        timeout_seconds: float = 15.0,
        default_sync_limit: int = 50,
        max_message_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self.accounts = EmailAccountRepository(session, user_id)
        self.emails = EmailRepository(session, user_id)
        self._credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self._imap_client = imap_client or ImapMailboxClient(timeout_seconds)
        self._smtp_tester = smtp_tester or SmtpConnectionTester(timeout_seconds)
        self._default_sync_limit = default_sync_limit
        self._max_message_bytes = max_message_bytes

    def create_account(self, data: EmailAccountCreate) -> EmailAccount:
        try:
            with self._session.begin():
                self._ensure_demo_user()
                if data.is_active:
                    self._lock_user()
                    self.accounts.deactivate_others()
                account = EmailAccount(
                    user_id=self._user_id,
                    **data.model_dump(),
                )
                return self.accounts.add(account)
        except IntegrityError as exc:
            raise ResourceConflictError("该邮箱账户已存在") from exc

    def set_account_active(self, account_id: int, *, is_active: bool) -> EmailAccount:
        with self._session.begin():
            self._lock_user()
            account = self.accounts.get(account_id, for_update=True)
            if is_active:
                self.accounts.deactivate_others(except_account_id=account.id)
            account.is_active = is_active
            self._session.flush()
            return account

    def download_attachment(
        self,
        email_id: int,
        attachment_index: int,
    ) -> DownloadedAttachment:
        email = self.emails.get(email_id)
        if attachment_index < 0 or attachment_index >= len(email.attachment_metadata):
            raise EntityNotFoundError("附件不存在")
        metadata = email.attachment_metadata[attachment_index]
        if metadata.get("download_skipped"):
            raise ResourceConflictError("原邮件超过安全下载上限，附件不可下载")
        account = self.accounts.get(email.account_id)
        try:
            credential = self._credential_resolver.resolve(account.credential_ref)
            raw_message = self._imap_client.fetch_raw_message(
                account,
                credential,
                folder=email.current_folder,
                uid=email.imap_uid,
                max_message_bytes=self._max_message_bytes,
            )
        except CredentialNotConfiguredError as exc:
            raise ResourceConflictError("邮箱凭据尚未配置") from exc
        except EmailConnectionError as exc:
            raise EmailSyncError("附件读取失败") from exc
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        attachments = list(message.iter_attachments())
        if attachment_index >= len(attachments):
            raise EntityNotFoundError("远程邮件中的附件已发生变化")
        part = attachments[attachment_index]
        payload = part.get_payload(decode=True)
        content = payload if payload is not None else part.as_bytes(policy=policy.default)
        if len(content) > self._max_message_bytes:
            raise ResourceConflictError("附件超过安全下载上限")
        filename = (part.get_filename() or f"attachment-{attachment_index + 1}").strip()
        filename = filename.replace("\r", "").replace("\n", "")[:255]
        return DownloadedAttachment(
            filename=filename or f"attachment-{attachment_index + 1}",
            content_type=part.get_content_type() or "application/octet-stream",
            content=content,
        )

    def test_connection(self, account_id: int) -> EmailConnectionTestResult:
        account = self.accounts.get(account_id)
        if not account.is_active:
            raise ResourceConflictError("邮箱账户已停用")
        try:
            credential = self._credential_resolver.resolve(account.credential_ref)
        except CredentialNotConfiguredError:
            failure = ConnectionCheck(success=False, message="邮箱凭据尚未配置")
            return EmailConnectionTestResult(imap=failure, smtp=failure)
        return EmailConnectionTestResult(
            imap=self._check_connection(
                self._imap_client.test_connection,
                account,
                credential,
                protocol="IMAP",
            ),
            smtp=self._check_connection(
                self._smtp_tester.test_connection,
                account,
                credential,
                protocol="SMTP",
            ),
        )

    def sync(self, account_id: int, *, limit: int | None = None) -> EmailSyncResult:
        account = self.accounts.get(account_id)
        if not account.is_active:
            raise ResourceConflictError("邮箱账户已停用")
        sync_limit = limit or self._default_sync_limit
        try:
            credential = self._credential_resolver.resolve(account.credential_ref)
            uid_validity, remote_messages = self._imap_client.fetch_recent(
                account,
                credential,
                previous_uid_validity=account.inbox_uid_validity,
                last_synced_uid=account.last_synced_uid,
                limit=sync_limit,
                max_message_bytes=self._max_message_bytes,
            )
        except (CredentialNotConfiguredError, EmailConnectionError) as exc:
            self._record_sync_failure(account, str(exc))
            raise EmailSyncError(str(exc)) from exc

        created = skipped = failed = 0
        for remote in remote_messages:
            outcome = self._persist_remote(account, uid_validity, remote)
            created += outcome == "created"
            skipped += outcome == "skipped"
            failed += outcome == "failed"

        account.inbox_uid_validity = uid_validity
        if remote_messages:
            account.last_synced_uid = max(message.uid for message in remote_messages)
        account.last_sync_at = _utc_now()
        account.last_sync_status = "PARTIAL" if failed else "SUCCEEDED"
        account.last_sync_error = f"{failed} 封邮件解析失败" if failed else None
        self._session.commit()
        return EmailSyncResult(
            account_id=account.id,
            folder=INBOX,
            uid_validity=uid_validity,
            examined=len(remote_messages),
            created=created,
            skipped=skipped,
            failed=failed,
        )

    def _persist_remote(
        self,
        account: EmailAccount,
        uid_validity: int,
        remote: RemoteEmail,
    ) -> str:
        if self.emails.find_by_imap_identity(
            account_id=account.id,
            source_folder=INBOX,
            uid_validity=uid_validity,
            imap_uid=remote.uid,
        ):
            return "skipped"
        try:
            parsed = parse_email(
                remote.raw_message,
                received_at=remote.received_at,
                truncated=remote.truncated,
                message_size=remote.message_size,
            )
            if parsed.message_id and self.emails.find_by_message_id(
                account_id=account.id,
                message_id=parsed.message_id,
            ):
                return "skipped"
            email = self._email_model(account.id, uid_validity, remote.uid, parsed)
            self.emails.add(email)
            self._session.commit()
            return "failed" if parsed.parse_status == EmailParseStatus.FAILED else "created"
        except Exception:
            self._session.rollback()
            try:
                self.emails.add(
                    Email(
                        account_id=account.id,
                        source_folder=INBOX,
                        current_folder=INBOX,
                        uid_validity=uid_validity,
                        imap_uid=remote.uid,
                        subject="(解析失败)",
                        from_address="unknown@invalid.local",
                        to_recipients=[],
                        cc_recipients=[],
                        received_at=remote.received_at,
                        analysis_text="",
                        attachment_metadata=[],
                        parse_status=EmailParseStatus.FAILED,
                    )
                )
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                return "skipped"
            return "failed"

    @staticmethod
    def _email_model(
        account_id: int,
        uid_validity: int,
        imap_uid: int,
        parsed: ParsedEmail,
    ) -> Email:
        return Email(
            account_id=account_id,
            source_folder=INBOX,
            current_folder=INBOX,
            uid_validity=uid_validity,
            imap_uid=imap_uid,
            **parsed.__dict__,
        )

    def _record_sync_failure(self, account: EmailAccount, message: str) -> None:
        account.last_sync_at = _utc_now()
        account.last_sync_status = "FAILED"
        account.last_sync_error = message[:500]
        self._session.commit()

    @staticmethod
    def _check_connection(
        check: object,
        account: EmailAccount,
        credential: str,
        *,
        protocol: str,
    ) -> ConnectionCheck:
        try:
            check(account, credential)  # type: ignore[operator]
            return ConnectionCheck(success=True, message=f"{protocol} 连接成功")
        except EmailConnectionError:
            return ConnectionCheck(
                success=False,
                message=f"{protocol} 连接或认证失败",
            )

    def _ensure_demo_user(self) -> None:
        if self._session.get(User, self._user_id) is None:
            self._session.add(
                User(
                    id=self._user_id,
                    display_name="演示用户",
                    timezone="Asia/Shanghai",
                    reply_preferences={},
                )
            )
            self._session.flush()

    def _lock_user(self) -> None:
        user = self._session.scalar(
            select(User).where(User.id == self._user_id).with_for_update()
        )
        if user is None:
            self._ensure_demo_user()
            self._session.scalar(
                select(User).where(User.id == self._user_id).with_for_update()
            )


def mask_email_address(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    visible = local[:1]
    return f"{visible}***@{domain}"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
