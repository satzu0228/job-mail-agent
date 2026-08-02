from email.message import EmailMessage

from app.application.email_access import EmailAccessService
from app.domain.enums import EmailParseStatus, TransportSecurity
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_account import EmailAccount


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def refresh(self, instance: object) -> None:
        return None


class FakeRepository:
    def __init__(self, value: object) -> None:
        self.value = value

    def get(self, object_id: int) -> object:
        assert object_id == self.value.id  # type: ignore[attr-defined]
        return self.value


class FakeCredentialResolver:
    def resolve(self, credential_ciphertext: str | None) -> str:
        assert credential_ciphertext == "v1:mail-token"
        return "secret"


class FakeImapClient:
    def __init__(self, raw_message: bytes) -> None:
        self.raw_message = raw_message

    def fetch_raw_message(
        self,
        account: EmailAccount,
        credential: str,
        *,
        folder: str,
        uid: int,
        max_message_bytes: int,
    ) -> bytes:
        assert account.id == 3
        assert credential == "secret"
        assert (folder, uid) == ("INBOX", 21)
        assert max_message_bytes == 10 * 1024 * 1024
        return self.raw_message


def test_refresh_content_reparses_safe_image_metadata_without_creating_email() -> None:
    message = EmailMessage()
    message["From"] = "safe@example.com"
    message["To"] = "candidate@example.com"
    message.set_content("安全提醒")
    message.add_alternative(
        '<p>安全提醒</p><img src="https://img.example.com/logo.png">',
        subtype="html",
    )
    account = EmailAccount(
        id=3,
        user_id=1,
        provider="custom",
        email_address="candidate@example.com",
        imap_host="imap.example.com",
        imap_port=993,
        imap_security=TransportSecurity.SSL,
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security=TransportSecurity.SSL,
        credential_ciphertext="v1:mail-token",
        is_active=True,
    )
    email = Email(
        id=8,
        account_id=3,
        source_folder="INBOX",
        current_folder="INBOX",
        uid_validity=1,
        imap_uid=21,
        subject="安全提醒",
        from_address="safe@example.com",
        to_recipients=[],
        cc_recipients=[],
        analysis_text="旧正文",
        attachment_metadata=[],
        parse_status=EmailParseStatus.SUCCEEDED,
    )
    session = FakeSession()
    service = EmailAccessService(
        session,  # type: ignore[arg-type]
        1,
        credential_resolver=FakeCredentialResolver(),
        imap_client=FakeImapClient(message.as_bytes()),  # type: ignore[arg-type]
    )
    service.accounts = FakeRepository(account)  # type: ignore[assignment]
    service.emails = FakeRepository(email)  # type: ignore[assignment]

    refreshed = service.refresh_content(8)

    assert refreshed is email
    assert (
        'data-jm-remote-src="https://img.example.com/logo.png"'
        in refreshed.html_sanitized
    )
    assert refreshed.analysis_text == "安全提醒"
    assert session.committed is True
