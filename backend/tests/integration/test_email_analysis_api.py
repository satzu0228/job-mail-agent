from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import Evidence, EvidenceSource
from app.agents.extraction.schemas import ExtractionField, ExtractionOutput
from app.api.v1.endpoints.analysis import analysis_service
from app.application.email_analysis import (
    CompletedEmailAnalysis,
    NonJobEmailExtractionError,
)
from app.domain.enums import (
    EmailAnalysisStatus,
    EmailCategory,
    EmailPriority,
)
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.main import app


def _classification() -> ClassificationOutput:
    return ClassificationOutput(
        is_job_related=True,
        category=EmailCategory.INTERVIEW,
        priority=EmailPriority.HIGH,
        should_reply=True,
        confidence=0.95,
        evidence=[
            Evidence(
                source=EvidenceSource.BODY,
                quote="邀请您参加线上面试",
            )
        ],
    )


def _extraction() -> ExtractionOutput:
    return ExtractionOutput(
        summary="招聘方邀请候选人参加线上面试。",
        overall_confidence=0.88,
        missing_fields=list(ExtractionField),
    )


class StubAnalysisService:
    def classify(self, email_id: int) -> ClassificationOutput:
        assert email_id == 8
        return _classification()

    def extract(self, email_id: int) -> ExtractionOutput:
        assert email_id == 8
        return _extraction()

    def analyze(self, email_id: int) -> CompletedEmailAnalysis:
        assert email_id == 8
        analysis = EmailAnalysis(
            id=12,
            email_id=email_id,
            version=2,
            is_current=True,
            status=EmailAnalysisStatus.VALID,
            is_job_related=True,
            category=EmailCategory.INTERVIEW,
            priority=EmailPriority.HIGH,
            should_reply=True,
            classification_confidence=0.95,
            extraction_confidence=0.88,
            extraction_json={},
            evidence_json={},
            missing_fields=[],
            schema_version="email-analysis.v1",
            created_at=datetime(2026, 7, 28, 8, 0, tzinfo=UTC),
        )
        return CompletedEmailAnalysis(
            analysis=analysis,
            classification=_classification(),
            extraction=_extraction(),
        )


class NonJobExtractionService(StubAnalysisService):
    def extract(self, email_id: int) -> ExtractionOutput:
        raise NonJobEmailExtractionError("非求职邮件不执行求职信息抽取")


def test_single_email_analysis_endpoints_return_structured_outputs(
    client: TestClient,
) -> None:
    app.dependency_overrides[analysis_service] = StubAnalysisService
    try:
        classification = client.post("/api/v1/emails/8/classify")
        extraction = client.post("/api/v1/emails/8/extract")
        analysis = client.post("/api/v1/emails/8/analyze")
    finally:
        app.dependency_overrides.pop(analysis_service, None)

    assert classification.status_code == 200
    assert classification.json()["category"] == "INTERVIEW"
    assert extraction.status_code == 200
    assert extraction.json()["schema_version"] == "extraction-output.v1"
    assert analysis.status_code == 200
    assert analysis.json()["analysis_id"] == 12
    assert analysis.json()["version"] == 2
    assert analysis.json()["created_at"].endswith("Z")


def test_extract_non_job_email_returns_conflict(client: TestClient) -> None:
    app.dependency_overrides[analysis_service] = NonJobExtractionService
    try:
        response = client.post("/api/v1/emails/8/extract")
    finally:
        app.dependency_overrides.pop(analysis_service, None)

    assert response.status_code == 409
    assert response.json() == {"detail": "非求职邮件不执行求职信息抽取"}
