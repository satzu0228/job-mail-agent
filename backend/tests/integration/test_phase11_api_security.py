from datetime import datetime

from fastapi.testclient import TestClient

from app.api.v1.endpoints.business import email_access_service, service
from app.application.email_access import DownloadedAttachment
from app.domain.enums import TransportSecurity
from app.infrastructure.db.models import EmailAccount
from app.main import app


class EmptyRepository:
    def query(self, **kwargs: object) -> tuple[list[object], int]:
        return [], 0


class StubBusinessService:
    emails = EmptyRepository()
    applications = EmptyRepository()
    tasks = EmptyRepository()


class StubSecurityEmailAccess:
    def accounts_list(self) -> list[EmailAccount]:
        return []

    @property
    def accounts(self) -> object:
        class Accounts:
            @staticmethod
            def list() -> list[EmailAccount]:
                now = datetime(2026, 7, 30, 12, 0)
                return [
                    EmailAccount(
                        id=1,
                        user_id=1,
                        provider="fixture",
                        email_address="candidate@example.test",
                        imap_host="imap.example.test",
                        imap_port=993,
                        imap_security=TransportSecurity.SSL,
                        smtp_host="smtp.example.test",
                        smtp_port=465,
                        smtp_security=TransportSecurity.SSL,
                        credential_ciphertext="v1:DO_NOT_ECHO_CIPHERTEXT",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                ]

        return Accounts()

    def download_attachment(
        self,
        email_id: int,
        attachment_index: int,
    ) -> DownloadedAttachment:
        assert (email_id, attachment_index) == (8, 0)
        return DownloadedAttachment(
            filename='面试安排\r\nX-Injected: true".pdf',
            content_type="application/octet-stream",
            content=b"untrusted fixture",
        )


def test_account_read_does_not_echo_credential_ciphertext_or_secret(
    client: TestClient,
) -> None:
    app.dependency_overrides[email_access_service] = StubSecurityEmailAccess
    try:
        response = client.get("/api/v1/email-accounts")
    finally:
        app.dependency_overrides.pop(email_access_service, None)

    assert response.status_code == 200
    body = response.text
    assert "credential_ciphertext" not in body
    assert "DO_NOT_ECHO_CIPHERTEXT" not in body
    assert "authorization" not in body.casefold()


def test_query_pagination_and_enum_inputs_are_rejected_before_business_execution(
    client: TestClient,
) -> None:
    app.dependency_overrides[service] = StubBusinessService
    try:
        responses = [
            client.get("/api/v1/emails/query?limit=101"),
            client.get("/api/v1/emails/query?offset=-1"),
            client.get("/api/v1/emails/query?category=NOT_A_CATEGORY"),
            client.get("/api/v1/job-applications/query?stage=ROOT"),
            client.get("/api/v1/tasks/query?status=ROOT"),
        ]
    finally:
        app.dependency_overrides.pop(service, None)

    assert all(response.status_code == 422 for response in responses)


def test_attachment_response_prevents_header_injection_and_content_sniffing(
    client: TestClient,
) -> None:
    app.dependency_overrides[email_access_service] = StubSecurityEmailAccess
    try:
        response = client.get("/api/v1/emails/8/attachments/0")
    finally:
        app.dependency_overrides.pop(email_access_service, None)

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition
    assert "\n" not in disposition
    assert "X-Injected:" not in disposition
    assert "%0D%0A" in disposition.upper()
    assert response.headers["x-content-type-options"] == "nosniff"
