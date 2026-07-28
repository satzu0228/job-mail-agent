from pathlib import Path
from typing import Generic, TypeVar

from langchain_core.messages import BaseMessage

from app.agents.classification.agent import ClassificationAgent
from app.agents.classification.schemas import ClassificationInput, ClassificationOutput
from app.agents.common.schemas import Evidence, EvidenceSource, PreparedEmail
from app.agents.extraction.agent import ExtractionAgent
from app.agents.extraction.schemas import (
    ExtractionField,
    ExtractionInput,
    ExtractionOutput,
)
from app.domain.enums import EmailCategory, EmailPriority, RequiredCapability

OutputT = TypeVar("OutputT")


class StubInvoker(Generic[OutputT]):
    def __init__(self, output: OutputT) -> None:
        self.output = output
        self.messages: list[BaseMessage] = []

    def invoke(self, input: list[BaseMessage]) -> OutputT:
        self.messages = input
        return self.output


def test_classification_and_extraction_runners_use_versioned_prompts() -> None:
    email = PreparedEmail.model_validate_json(
        (
            Path(__file__).resolve().parents[4]
            / "tests"
            / "fixtures"
            / "emails"
            / "interview_invitation.json"
        ).read_text(encoding="utf-8")
    )
    evidence = Evidence(source=EvidenceSource.BODY, quote="邀请您于2026年7月31日14:00参加线上一面")
    classification = ClassificationOutput(
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
        evidence=[evidence],
    )
    classification_invoker = StubInvoker(classification)

    actual_classification = ClassificationAgent(classification_invoker).run(
        ClassificationInput(email=email)
    )

    extraction = ExtractionOutput(
        summary="星海科技邀请用户参加后端开发工程师线上一面。",
        overall_confidence=0.9,
        missing_fields=list(ExtractionField),
    )
    extraction_invoker = StubInvoker(extraction)
    actual_extraction = ExtractionAgent(extraction_invoker).run(
        ExtractionInput(email=email, classification=actual_classification)
    )

    assert actual_classification.category is EmailCategory.INTERVIEW
    assert actual_extraction.summary.startswith("星海科技")
    assert "求职邮件分类 Agent" in str(classification_invoker.messages[0].content)
    assert '"classification-output.v1"' in str(classification_invoker.messages[1].content)
    assert "求职邮件信息抽取 Agent" in str(extraction_invoker.messages[0].content)
