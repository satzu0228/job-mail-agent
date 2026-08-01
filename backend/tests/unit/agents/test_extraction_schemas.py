from datetime import datetime

import pytest
from pydantic import ValidationError

from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import Evidence, EvidenceSource, PreparedEmail
from app.agents.extraction.schemas import (
    ExtractedDateTime,
    ExtractedInterviewResult,
    ExtractedStage,
    ExtractedText,
    ExtractedUrl,
    ExtractionField,
    ExtractionInput,
    ExtractionOutput,
)
from app.domain.enums import (
    ApplicationStage,
    EmailCategory,
    EmailPriority,
    InterviewResult,
    RequiredCapability,
)


def body_evidence(quote: str) -> Evidence:
    return Evidence(source=EvidenceSource.BODY, quote=quote)


def job_classification() -> ClassificationOutput:
    return ClassificationOutput(
        is_job_related=True,
        category=EmailCategory.INTERVIEW,
        priority=EmailPriority.HIGH,
        should_reply=True,
        required_capabilities=[RequiredCapability.EXTRACT],
        confidence=0.96,
        evidence=[body_evidence("邀请您参加后端开发工程师面试")],
    )


def prepared_email() -> PreparedEmail:
    return PreparedEmail(
        subject="星海科技面试邀请",
        sender_address="hr@example.com",
        received_at=datetime.fromisoformat("2026-07-28T08:00:00+08:00"),
        analysis_text=(
            "邀请您参加后端开发工程师面试，时间为2026年7月31日14:00，"
            "会议地址为https://meeting.example.com/room/1。"
        ),
    )


def valid_extraction_output() -> ExtractionOutput:
    return ExtractionOutput(
        summary="星海科技邀请候选人参加后端开发工程师线上面试。",
        company=ExtractedText(
            value="星海科技",
            confidence=0.98,
            evidence=[body_evidence("星海科技")],
        ),
        position=ExtractedText(
            value="后端开发工程师",
            confidence=0.96,
            evidence=[body_evidence("后端开发工程师")],
        ),
        proposed_stage=ExtractedStage(
            value=ApplicationStage.INTERVIEW,
            confidence=0.96,
            evidence=[body_evidence("参加面试")],
        ),
        interview_result=ExtractedInterviewResult(
            value=InterviewResult.PENDING,
            confidence=0.98,
            evidence=[body_evidence("邀请您参加后端开发工程师面试")],
        ),
        event_type=ExtractedText(
            value="INTERVIEW_INVITATION",
            confidence=0.95,
            evidence=[body_evidence("邀请您参加面试")],
        ),
        event_time=ExtractedDateTime(
            raw_text="2026年7月31日14:00",
            normalized=datetime.fromisoformat("2026-07-31T14:00:00+08:00"),
            timezone="Asia/Shanghai",
            confidence=0.98,
            evidence=[body_evidence("时间为2026年7月31日14:00")],
            requires_human_confirmation=False,
        ),
        meeting_url=ExtractedUrl(
            value="https://meeting.example.com/room/1",
            confidence=0.99,
            evidence=[body_evidence("https://meeting.example.com/room/1")],
        ),
        overall_confidence=0.95,
        missing_fields=[
            ExtractionField.CONTACT_NAME,
            ExtractionField.CONTACT_EMAIL,
            ExtractionField.DEADLINE,
            ExtractionField.LOCATION,
            ExtractionField.MATERIALS,
        ],
    )


def test_extraction_accepts_evidence_and_aware_datetime() -> None:
    result = valid_extraction_output()
    payload = result.model_dump(mode="json")

    assert payload["proposed_stage"]["value"] == "INTERVIEW"
    assert payload["interview_result"]["value"] == "PENDING"
    assert payload["event_time"]["normalized"] == "2026-07-31T14:00:00+08:00"
    assert payload["meeting_url"]["value"] == "https://meeting.example.com/room/1"
    assert "DEADLINE" in payload["missing_fields"]


def test_extraction_localizes_naive_model_datetime_with_source_timezone() -> None:
    value = ExtractedDateTime.model_validate(
        {
            "raw_text": "2026年7月31日14:00",
            "normalized": "2026-07-31T14:00:00",
            "timezone": "Asia/Shanghai",
            "confidence": 0.98,
            "evidence": [{"source": "BODY", "quote": "2026年7月31日14:00"}],
            "requires_human_confirmation": False,
        }
    )

    assert value.normalized is not None
    assert value.normalized.isoformat() == "2026-07-31T14:00:00+08:00"


def test_extraction_input_rejects_non_job_classification() -> None:
    non_job = ClassificationOutput(
        is_job_related=False,
        category=EmailCategory.NON_JOB,
        priority=EmailPriority.LOW,
        should_reply=False,
        required_capabilities=[RequiredCapability.PROPOSE_ARCHIVE],
        confidence=0.99,
        evidence=[Evidence(source=EvidenceSource.SUBJECT, quote="商城促销")],
    )

    with pytest.raises(ValidationError, match="job-related classification"):
        ExtractionInput(email=prepared_email(), classification=non_job)


def test_unresolved_datetime_requires_confirmation_and_reason() -> None:
    with pytest.raises(ValidationError, match="requires human confirmation"):
        ExtractedDateTime(
            raw_text="本周五下午",
            normalized=None,
            timezone=None,
            confidence=0.5,
            evidence=[body_evidence("本周五下午")],
            requires_human_confirmation=False,
        )


def test_missing_fields_must_match_absent_values() -> None:
    result = valid_extraction_output()
    payload = result.model_dump()
    payload["missing_fields"] = []

    with pytest.raises(ValidationError, match="missing_fields inconsistent"):
        ExtractionOutput.model_validate(payload)


def test_present_field_cannot_also_be_marked_missing() -> None:
    result = valid_extraction_output()
    payload = result.model_dump()
    payload["missing_fields"].append(ExtractionField.COMPANY)

    with pytest.raises(ValidationError, match="COMPANY"):
        ExtractionOutput.model_validate(payload)
