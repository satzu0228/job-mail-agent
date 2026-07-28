from typing import Generic, TypeVar

import pytest
from langchain_core.messages import BaseMessage
from pydantic import ValidationError

from app.agents.application.agent import ApplicationAgent
from app.agents.application.schemas import (
    ApplicationAgentInput,
    ApplicationAgentOutput,
    ApplicationAnalysisFacts,
    ApplicationRecommendation,
)
from app.domain.enums import ApplicationStage, EmailCategory

OutputT = TypeVar("OutputT")


class StubInvoker(Generic[OutputT]):
    def __init__(self, output: OutputT) -> None:
        self.output = output
        self.messages: list[BaseMessage] = []

    def invoke(self, input: list[BaseMessage]) -> OutputT:
        self.messages = input
        return self.output


def _agent_input() -> ApplicationAgentInput:
    return ApplicationAgentInput(
        analysis=ApplicationAnalysisFacts(
            email_id=8,
            category=EmailCategory.INTERVIEW,
            sender_address="hr@example.com",
            company_name="星海科技",
            position_name="后端开发工程师",
            proposed_stage=ApplicationStage.INTERVIEW,
        ),
        candidates=[],
        deterministic_conflict=False,
    )


def test_application_agent_uses_versioned_prompt_and_structured_output() -> None:
    output = ApplicationAgentOutput(
        recommendation=ApplicationRecommendation.CREATE_NEW,
        proposed_stage=ApplicationStage.INTERVIEW,
        confidence=0.91,
        reasoning="没有已有候选，且公司和岗位信息完整。",
    )
    invoker = StubInvoker(output)

    actual = ApplicationAgent(invoker).run(_agent_input())

    assert actual.recommendation is ApplicationRecommendation.CREATE_NEW
    assert "Application Agent" in str(invoker.messages[0].content)
    assert '"application-output.v1"' in str(invoker.messages[1].content)


def test_link_recommendation_requires_selected_candidate() -> None:
    with pytest.raises(ValidationError):
        ApplicationAgentOutput(
            recommendation=ApplicationRecommendation.LINK_EXISTING,
            confidence=0.8,
            reasoning="建议关联现有申请。",
        )
