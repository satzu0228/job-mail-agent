from email.message import EmailMessage

import pytest

from app.domain.enums import TransportSecurity
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.email.client import (
    ImapMailboxClient,
    SmtpDeliveryUnknownError,
    SmtpMailer,
)


class FakeImap:
    def __init__(self) -> None:
        self.readonly = False
        self.fetch_queries: list[tuple[str, str]] = []
        self.client_identified = False

    def login(self, email_address: str, credential: str) -> tuple[str, list[bytes]]:
        return "OK", [b"logged in"]

    def select(
        self,
        folder: str,
        readonly: bool = False,
    ) -> tuple[str, list[bytes]]:
        self.readonly = readonly
        return "OK", [b"3"]

    def response(self, name: str) -> tuple[str, list[bytes]]:
        return "UIDVALIDITY", [b"42"]

    def _simple_command(
        self,
        command: str,
        arguments: str,
    ) -> tuple[str, list[bytes]]:
        assert command == "ID"
        assert "JobMailAgent" in arguments
        self.client_identified = True
        return "OK", [b"ID accepted"]

    def uid(
        self,
        command: str,
        *args: str | None,
    ) -> tuple[str, list[bytes | tuple[bytes, bytes]]]:
        if command == "search":
            return "OK", [b"1 2 3"]
        uid, query = str(args[0]), str(args[1])
        self.fetch_queries.append((uid, query))
        if query == "(RFC822.SIZE)":
            return "OK", [f"1 (UID {uid} RFC822.SIZE 128)".encode()]
        raw = b"Subject: Test\r\nFrom: sender@example.com\r\nTo: candidate@example.com\r\n\r\nBody"
        metadata = f'1 (UID {uid} INTERNALDATE "28-Jul-2026 10:00:00 +0800"'.encode()
        return "OK", [(metadata, raw), b")"]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"logout"]


def _account() -> EmailAccount:
    return EmailAccount(
        id=1,
        user_id=1,
        provider="163",
        email_address="candidate@example.com",
        imap_host="imap.163.com",
        imap_port=993,
        imap_security=TransportSecurity.SSL,
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security=TransportSecurity.SSL,
        credential_ref="JOB_MAIL_EMAIL_CREDENTIAL_TEST",
    )


def test_uidvalidity_change_resets_cursor_and_fetch_is_read_only() -> None:
    fake = FakeImap()
    client = ImapMailboxClient(timeout_seconds=5)
    client._connect = lambda account: fake  # type: ignore[method-assign]

    uid_validity, messages = client.fetch_recent(
        _account(),
        "secret-not-logged",
        previous_uid_validity=41,
        last_synced_uid=999,
        limit=2,
        max_message_bytes=1024,
    )

    assert uid_validity == 42
    assert [message.uid for message in messages] == [2, 3]
    assert fake.client_identified is True
    assert fake.readonly is True
    assert ("2", "(BODY.PEEK[] INTERNALDATE)") in fake.fetch_queries
    assert messages[0].received_at.isoformat() == "2026-07-28T02:00:00"


def test_fetch_raw_message_uses_read_only_folder_and_size_limit() -> None:
    fake = FakeImap()
    client = ImapMailboxClient(timeout_seconds=5)
    client._connect = lambda account: fake  # type: ignore[method-assign]

    raw_message = client.fetch_raw_message(
        _account(),
        "secret-not-logged",
        folder="INBOX",
        uid=2,
        max_message_bytes=1024,
    )

    assert fake.readonly is True
    assert raw_message.startswith(b"Subject: Test")
    assert ("2", "(RFC822.SIZE)") in fake.fetch_queries
    assert ("2", "(BODY.PEEK[] INTERNALDATE)") in fake.fetch_queries


class FakeSmtp:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent = 0

    def login(self, email_address: str, credential: str) -> None:
        assert credential == "secret-not-logged"

    def send_message(self, message: EmailMessage) -> dict[str, object]:
        self.sent += 1
        if self.error:
            raise self.error
        return {}

    def quit(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_smtp_mailer_transports_message_without_reformatting() -> None:
    fake = FakeSmtp()
    mailer = SmtpMailer(timeout_seconds=5)
    mailer._connect = lambda account: fake  # type: ignore[method-assign]
    message = EmailMessage()
    message["From"] = "candidate@example.com"
    message["To"] = "hr@example.com"
    message["Subject"] = "Re: 面试邀请"
    message["Message-ID"] = "<fixed@example.com>"
    message.set_content("已经确定格式的正文")

    reference = mailer.send(
        _account(),
        "secret-not-logged",
        message,
    )

    assert reference == "<fixed@example.com>"
    assert fake.sent == 1
    assert message.get_content().strip() == "已经确定格式的正文"


def test_smtp_disconnect_during_submission_is_unknown() -> None:
    import smtplib

    fake = FakeSmtp(smtplib.SMTPServerDisconnected("connection lost"))
    mailer = SmtpMailer(timeout_seconds=5)
    mailer._connect = lambda account: fake  # type: ignore[method-assign]
    message = EmailMessage()
    message["From"] = "candidate@example.com"
    message["To"] = "hr@example.com"
    message.set_content("正文")

    with pytest.raises(SmtpDeliveryUnknownError):
        mailer.send(_account(), "secret-not-logged", message)
