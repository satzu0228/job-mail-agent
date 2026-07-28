from datetime import datetime

import pytest
from pydantic import ValidationError

from app.agents.classification.schemas import (
    ClassificationInput,
    ClassificationOutput,
)
from app.agents.common.schemas import Evidence, EvidenceSource, PreparedEmail
from app.domain.enums import EmailCategory, EmailPriority, RequiredCapability


def prepared_email() -> PreparedEmail:
    return PreparedEmail(
        email_id=1,
        subject="星海科技后端工程师面试邀请",
        sender_name="招聘专员",
        sender_address="hr@example.com",
        received_at=datetime.fromisoformat("2026-07-28T08:00:00+08:00"),
        analysis_text="邀请您于本周五下午两点参加线上面试。",
        user_timezone="Asia/Shanghai",
    )


def evidence() -> Evidence:
    return Evidence(
        source=EvidenceSource.BODY,
        quote="邀请您于本周五下午两点参加线上面试",
    )


def test_classification_input_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        PreparedEmail(
            subject="面试邀请",
            sender_address="hr@example.com",
            received_at=datetime(2026, 7, 28, 8, 0),
            analysis_text="邀请您参加面试。",
        )


def test_job_related_classification_is_strict_and_serializable() -> None:
    result = ClassificationOutput(
        is_job_related=True,
        category=EmailCategory.INTERVIEW,
        priority=EmailPriority.HIGH,
        should_reply=True,
        required_capabilities=[
            RequiredCapability.EXTRACT,
            RequiredCapability.MATCH_APPLICATION,
            RequiredCapability.DRAFT_REPLY,
        ],
        confidence=0.96,
        evidence=[evidence()],
    )
    payload = result.model_dump(mode="json")

    assert payload["schema_version"] == "classification-output.v1"
    assert payload["category"] == "INTERVIEW"
    assert set(payload["required_capabilities"]) == {
        "EXTRACT",
        "MATCH_APPLICATION",
        "DRAFT_REPLY",
    }
    assert ClassificationInput(email=prepared_email()).email.email_id == 1


def test_non_job_classification_rejects_job_processing_capabilities() -> None:
    with pytest.raises(ValidationError, match="NON_JOB cannot require"):
        ClassificationOutput(
            is_job_related=False,
            category=EmailCategory.NON_JOB,
            priority=EmailPriority.LOW,
            should_reply=False,
            required_capabilities=[RequiredCapability.EXTRACT],
            confidence=0.95,
            evidence=[Evidence(source=EvidenceSource.SUBJECT, quote="商城促销")],
        )


def test_classification_rejects_confidence_outside_unit_interval() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        ClassificationOutput(
            is_job_related=True,
            category=EmailCategory.OFFER,
            priority=EmailPriority.HIGH,
            should_reply=True,
            confidence=1.01,
            evidence=[evidence()],
        )


def test_classification_rejects_unknown_output_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ClassificationOutput.model_validate(
            {
                "is_job_related": True,
                "category": "INTERVIEW",
                "priority": "HIGH",
                "should_reply": True,
                "confidence": 0.9,
                "evidence": [{"source": "BODY", "quote": "面试邀请"}],
                "model_explanation": "free text must not leak into state",
            }
        )
