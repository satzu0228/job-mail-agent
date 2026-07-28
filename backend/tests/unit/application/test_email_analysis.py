from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import Evidence, EvidenceSource
from app.agents.extraction.schemas import (
    ExtractedDateTime,
    ExtractedText,
    ExtractionField,
    ExtractionOutput,
)
from app.application.email_analysis import build_email_analysis
from app.domain.enums import EmailAnalysisStatus, EmailCategory, EmailPriority

EVIDENCE = Evidence(source=EvidenceSource.BODY, quote="2026年7月31日14:00线上面试")


def make_classification(*, job_related: bool = True) -> ClassificationOutput:
    return ClassificationOutput(
        is_job_related=job_related,
        category=EmailCategory.INTERVIEW if job_related else EmailCategory.NON_JOB,
        priority=EmailPriority.HIGH if job_related else EmailPriority.LOW,
        should_reply=job_related,
        confidence=0.96,
        evidence=[EVIDENCE],
    )


def make_extraction(*, requires_confirmation: bool = False) -> ExtractionOutput:
    company = ExtractedText(value="星海科技", confidence=0.95, evidence=[EVIDENCE])
    event_time = ExtractedDateTime(
        raw_text="2026年7月31日14:00",
        normalized=datetime(2026, 7, 31, 14, 0, tzinfo=UTC),
        timezone="Asia/Shanghai",
        confidence=0.9,
        evidence=[EVIDENCE],
        requires_human_confirmation=requires_confirmation,
        ambiguity_reason="原文时区需要确认" if requires_confirmation else None,
    )
    present = {ExtractionField.COMPANY, ExtractionField.EVENT_TIME}
    return ExtractionOutput(
        summary="星海科技邀请用户参加线上面试。",
        company=company,
        event_time=event_time,
        overall_confidence=0.9,
        missing_fields=[field for field in ExtractionField if field not in present],
    )


def test_build_email_analysis_preserves_structured_output_and_evidence() -> None:
    analysis = build_email_analysis(
        email_id=42,
        classification=make_classification(),
        extraction=make_extraction(),
        workflow_run_id="61793165-a4ef-4fdd-89b4-0bb53527ac06",
    )

    assert analysis.email_id == 42
    assert analysis.version == 0
    assert analysis.status is EmailAnalysisStatus.VALID
    assert analysis.classification_confidence == Decimal("0.96")
    assert analysis.extraction_confidence == Decimal("0.9")
    assert analysis.company_name == "星海科技"
    assert analysis.event_time == datetime(2026, 7, 31, 14, 0)
    assert analysis.source_timezone == "Asia/Shanghai"
    assert analysis.extraction_json["schema_version"] == "extraction-output.v1"
    assert analysis.evidence_json["classification"][0]["source"] == "BODY"
    assert analysis.evidence_json["extraction"]["company"][0]["quote"].startswith(
        "2026年"
    )


def test_explicit_datetime_uncertainty_requires_confirmation() -> None:
    analysis = build_email_analysis(
        email_id=42,
        classification=make_classification(),
        extraction=make_extraction(requires_confirmation=True),
    )

    assert analysis.status is EmailAnalysisStatus.PENDING_CONFIRMATION


def test_non_job_analysis_has_no_fake_extraction_values() -> None:
    analysis = build_email_analysis(
        email_id=7,
        classification=make_classification(job_related=False),
        extraction=None,
    )

    assert analysis.status is EmailAnalysisStatus.VALID
    assert analysis.extraction_confidence is None
    assert analysis.extraction_json == {}
    assert analysis.missing_fields == []


@pytest.mark.parametrize(
    ("job_related", "include_extraction"),
    [(True, False), (False, True)],
)
def test_classification_and_extraction_must_be_consistent(
    job_related: bool,
    include_extraction: bool,
) -> None:
    with pytest.raises(ValueError):
        build_email_analysis(
            email_id=1,
            classification=make_classification(job_related=job_related),
            extraction=make_extraction() if include_extraction else None,
        )
