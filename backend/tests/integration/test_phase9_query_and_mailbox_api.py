from datetime import datetime

from fastapi.testclient import TestClient

from app.api.v1.endpoints.application_management import review_service
from app.api.v1.endpoints.business import email_access_service, service
from app.application.email_access import DownloadedAttachment
from app.domain.enums import TransportSecurity
from app.infrastructure.db.models.email_account import EmailAccount
from app.main import app


class EmptyQueryRepository:
    def query(self, **kwargs: object) -> tuple[list[object], int]:
        assert kwargs["offset"] == 0
        assert kwargs["limit"] == 25
        return [], 0


class ApplicationQueryRepository(EmptyQueryRepository):
    def list_events(
        self,
        application_id: int,
        **kwargs: object,
    ) -> tuple[list[object], int]:
        assert application_id == 7
        assert kwargs == {"offset": 0, "limit": 25}
        return [], 0


class StubBusinessService:
    emails = EmptyQueryRepository()
    applications = ApplicationQueryRepository()
    tasks = EmptyQueryRepository()


class StubReviewService:
    def query(self, **kwargs: object) -> tuple[list[object], int]:
        assert kwargs["offset"] == 0
        assert kwargs["limit"] == 25
        return [], 0


class StubEmailAccessService:
    def set_account_active(self, account_id: int, *, is_active: bool) -> EmailAccount:
        assert account_id == 3
        assert is_active is True
        now = datetime(2026, 7, 29, 12, 0)
        return EmailAccount(
            id=3,
            user_id=1,
            provider="gmail",
            email_address="candidate@gmail.com",
            imap_host="imap.gmail.com",
            imap_port=993,
            imap_security=TransportSecurity.SSL,
            smtp_host="smtp.gmail.com",
            smtp_port=465,
            smtp_security=TransportSecurity.SSL,
            credential_ref="JOB_MAIL_GMAIL_AUTH_CODE",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def download_attachment(
        self,
        email_id: int,
        attachment_index: int,
    ) -> DownloadedAttachment:
        assert (email_id, attachment_index) == (8, 0)
        return DownloadedAttachment(
            filename="面试说明.pdf",
            content_type="application/pdf",
            content=b"%PDF-test",
        )


def test_paginated_query_routes_return_metadata(client: TestClient) -> None:
    app.dependency_overrides[service] = StubBusinessService
    app.dependency_overrides[review_service] = StubReviewService
    try:
        paths = [
            "/api/v1/emails/query?limit=25",
            "/api/v1/job-applications/query?limit=25",
            "/api/v1/job-applications/7/events?limit=25",
            "/api/v1/tasks/query?limit=25",
            "/api/v1/review-tasks/query?limit=25",
        ]
        responses = [client.get(path) for path in paths]
    finally:
        app.dependency_overrides.pop(service, None)
        app.dependency_overrides.pop(review_service, None)

    assert all(response.status_code == 200 for response in responses)
    assert all(
        response.json() == {"items": [], "total": 0, "offset": 0, "limit": 25}
        for response in responses
    )


def test_account_activation_and_attachment_download_routes(
    client: TestClient,
) -> None:
    app.dependency_overrides[email_access_service] = StubEmailAccessService
    try:
        activation = client.patch(
            "/api/v1/email-accounts/3/active",
            json={"is_active": True},
        )
        attachment = client.get("/api/v1/emails/8/attachments/0")
    finally:
        app.dependency_overrides.pop(email_access_service, None)

    assert activation.status_code == 200
    assert activation.json()["is_active"] is True
    assert activation.json()["email_address_masked"] == "c***@gmail.com"
    assert attachment.status_code == 200
    assert attachment.content == b"%PDF-test"
    assert attachment.headers["x-content-type-options"] == "nosniff"
    assert "filename*=UTF-8''" in attachment.headers["content-disposition"]
