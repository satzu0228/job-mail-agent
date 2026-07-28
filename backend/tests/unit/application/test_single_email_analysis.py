from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import Evidence, EvidenceSource
from app.agents.extraction.schemas import ExtractionField, ExtractionOutput
from app.application.email_analysis import (
    EmailModelExecutionError,
    EmailNotReadyForAnalysisError,
    NonJobEmailExtractionError,
    SingleEmailAnalysisService,
    prepare_email,
)
from app.application.schemas import EmailDetail
from app.domain.enums import (
    ArchiveStatus,
    EmailAnalysisStatus,
    EmailCategory,
    EmailParseStatus,
    EmailPriority,
)
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.user import User

EVIDENCE = Evidence(source=EvidenceSource.BODY, quote="邀请您参加线上面试")


def _classification(*, job_related: bool = True) -> ClassificationOutput:
    return ClassificationOutput(
        is_job_related=job_related,
        category=EmailCategory.INTERVIEW if job_related else EmailCategory.NON_JOB,
        priority=EmailPriority.HIGH if job_related else EmailPriority.LOW,
        should_reply=job_related,
        confidence=0.95,
        evidence=[EVIDENCE],
    )


def _extraction() -> ExtractionOutput:
    return ExtractionOutput(
        summary="招聘方邀请候选人参加线上面试。",
        overall_confidence=0.88,
        missing_fields=list(ExtractionField),
    )


def _email() -> Email:
    return Email(
        id=8,
        account_id=2,
        source_folder="INBOX",
        current_folder="INBOX",
        uid_validity=1,
        imap_uid=8,
        message_id="<mail-8@example.com>",
        subject="线上面试邀请",
        from_name="招聘专员",
        from_address="hr@example.com",
        to_recipients=[],
        cc_recipients=[],
        sent_at=datetime(2026, 7, 28, 2, 0),
        received_at=datetime(2026, 7, 28, 2, 1),
        analysis_text="邀请您参加线上面试",
        attachment_metadata=[
            {
                "filename": "岗位说明.pdf",
                "content_type": "application/pdf",
                "size_bytes": 128,
            },
            {
                "filename": None,
                "content_type": "message/rfc822",
                "size_bytes": 1024,
            },
        ],
        parse_status=EmailParseStatus.SUCCEEDED,
    )


class StubEmailRepository:
    def __init__(self, email: Email) -> None:
        self.email = email

    def get(self, email_id: int) -> Email:
        assert email_id == self.email.id
        return self.email


class StubClassificationAgent:
    def __init__(
        self,
        output: ClassificationOutput | Exception,
    ) -> None:
        self.output = output
        self.calls = 0

    def run(self, agent_input: object) -> ClassificationOutput:
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


class StubExtractionAgent:
    def __init__(self, output: ExtractionOutput) -> None:
        self.output = output
        self.calls = 0

    def run(self, agent_input: object) -> ExtractionOutput:
        self.calls += 1
        return self.output


class StubAnalysisRepository:
    def __init__(self) -> None:
        self.saved: EmailAnalysis | None = None

    def add_version(self, analysis: EmailAnalysis) -> EmailAnalysis:
        analysis.id = 11
        analysis.version = 1
        analysis.is_current = True
        self.saved = analysis
        return analysis


def _service(
    classification: ClassificationOutput | Exception,
) -> tuple[
    SingleEmailAnalysisService,
    StubClassificationAgent,
    StubExtractionAgent,
    StubAnalysisRepository,
    MagicMock,
]:
    session = MagicMock(spec=Session)
    session.get.return_value = User(
        id=1,
        display_name="演示用户",
        timezone="Asia/Shanghai",
        reply_preferences={},
    )
    classifier = StubClassificationAgent(classification)
    extractor = StubExtractionAgent(_extraction())
    analyses = StubAnalysisRepository()
    service = SingleEmailAnalysisService(
        session,
        1,
        classifier,
        extractor,
    )
    service._emails = StubEmailRepository(_email())
    service._analyses = analyses
    return service, classifier, extractor, analyses, session


def test_prepare_email_normalizes_database_utc_and_filters_unsafe_metadata() -> None:
    prepared = prepare_email(_email(), user_timezone="Asia/Shanghai")

    assert prepared.email_id == 8
    assert prepared.sent_at == datetime(2026, 7, 28, 2, 0, tzinfo=UTC)
    assert prepared.received_at == datetime(2026, 7, 28, 2, 1, tzinfo=UTC)
    assert prepared.user_timezone == "Asia/Shanghai"
    assert [item.filename for item in prepared.attachments] == ["岗位说明.pdf"]


def test_analyze_job_email_runs_both_agents_and_persists_one_version() -> None:
    service, classifier, extractor, analyses, session = _service(_classification())

    result = service.analyze(8)

    assert classifier.calls == 1
    assert extractor.calls == 1
    assert analyses.saved is result.analysis
    assert result.analysis.version == 1
    assert result.analysis.is_job_related is True
    assert result.extraction is not None
    session.rollback.assert_called_once_with()


def test_analyze_non_job_email_short_circuits_extraction_and_persists() -> None:
    service, classifier, extractor, analyses, _ = _service(_classification(job_related=False))

    result = service.analyze(8)

    assert classifier.calls == 1
    assert extractor.calls == 0
    assert result.extraction is None
    assert analyses.saved is not None
    assert analyses.saved.category is EmailCategory.NON_JOB


def test_extract_rejects_non_job_email_without_calling_extractor() -> None:
    service, _, extractor, _, _ = _service(_classification(job_related=False))

    with pytest.raises(NonJobEmailExtractionError):
        service.extract(8)

    assert extractor.calls == 0


def test_model_failure_is_wrapped_without_exposing_model_exception() -> None:
    service, _, _, _, _ = _service(RuntimeError("raw model response"))

    with pytest.raises(EmailModelExecutionError, match="邮件分类模型执行失败") as info:
        service.classify(8)

    assert "raw model response" not in str(info.value)


def test_failed_mime_parse_never_reaches_model() -> None:
    service, classifier, _, _, _ = _service(_classification())
    failed_email = _email()
    failed_email.parse_status = EmailParseStatus.FAILED
    failed_email.analysis_text = ""
    service._emails = StubEmailRepository(failed_email)

    with pytest.raises(EmailNotReadyForAnalysisError):
        service.classify(8)

    assert classifier.calls == 0


def test_email_detail_exposes_only_current_analysis_version() -> None:
    email = _email()
    email.archive_status = ArchiveStatus.NONE
    old = EmailAnalysis(
        id=10,
        email_id=8,
        version=1,
        is_current=False,
        status=EmailAnalysisStatus.VALID,
        is_job_related=True,
        category=EmailCategory.INTERVIEW,
        priority=EmailPriority.HIGH,
        should_reply=True,
        classification_confidence=Decimal("0.90"),
        extraction_confidence=Decimal("0.80"),
        extraction_json={},
        evidence_json={},
        missing_fields=[],
        schema_version="email-analysis.v1",
        created_at=datetime(2026, 7, 28, 1, 0),
    )
    current = EmailAnalysis(
        id=11,
        email_id=8,
        version=2,
        is_current=True,
        status=EmailAnalysisStatus.VALID,
        is_job_related=True,
        category=EmailCategory.INTERVIEW,
        priority=EmailPriority.HIGH,
        should_reply=True,
        classification_confidence=Decimal("0.95"),
        extraction_confidence=Decimal("0.88"),
        extraction_json={"summary": "current"},
        evidence_json={"classification": []},
        missing_fields=[],
        schema_version="email-analysis.v1",
        created_at=datetime(2026, 7, 28, 2, 0),
    )
    email.analyses = [old, current]

    detail = EmailDetail.model_validate(email)

    assert detail.current_analysis is not None
    assert detail.current_analysis.id == 11
    assert detail.current_analysis.version == 2
    assert detail.current_analysis.classification_confidence == 0.95
