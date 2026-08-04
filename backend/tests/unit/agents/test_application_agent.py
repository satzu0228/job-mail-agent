import pytest
from pydantic import ValidationError

from app.agents.application.agent import ApplicationAgent
from app.agents.application.schemas import (
    ApplicationAgentInput,
    ApplicationAgentOutput,
    ApplicationAnalysisFacts,
    ApplicationRecommendation,
)
from app.domain.enums import ApplicationStage, EmailCategory


def _agent_input() -> ApplicationAgentInput:
    return ApplicationAgentInput(
        analysis=ApplicationAnalysisFacts(
            email_id=8,
            email_subject="面试邀请",
            category=EmailCategory.INTERVIEW,
            sender_address="hr@example.com",
            company_name="星海科技",
            position_name="后端开发工程师",
            proposed_stage=ApplicationStage.INTERVIEW,
        ),
        candidates=[],
        deterministic_conflict=False,
    )


def test_application_agent_run_delegates_to_stub_runner() -> None:
    output = ApplicationAgentOutput(
        recommendation=ApplicationRecommendation.CREATE_NEW,
        proposed_stage=ApplicationStage.INTERVIEW,
        confidence=0.91,
        reasoning="没有已有候选，且公司和岗位信息完整。",
    )
    captured_input = None
    captured_config = None

    def stub_run(agent_input, *, config=None):
        nonlocal captured_input, captured_config
        captured_input = agent_input
        captured_config = config
        return output

    actual = ApplicationAgent(stub_run).run(_agent_input())

    assert actual.recommendation is ApplicationRecommendation.CREATE_NEW
    assert captured_input is not None


def test_application_agent_run_passes_config_through() -> None:
    output = ApplicationAgentOutput(
        recommendation=ApplicationRecommendation.CREATE_NEW,
        proposed_stage=ApplicationStage.INTERVIEW,
        confidence=0.91,
        reasoning="测试。",
    )

    def stub_run(agent_input, *, config=None):
        return output

    config = {"configurable": {"user_id": 42}}
    actual = ApplicationAgent(stub_run).run(_agent_input(), config=config)

    assert actual.recommendation is ApplicationRecommendation.CREATE_NEW


def test_link_recommendation_requires_selected_candidate() -> None:
    with pytest.raises(ValidationError):
        ApplicationAgentOutput(
            recommendation=ApplicationRecommendation.LINK_EXISTING,
            confidence=0.8,
            reasoning="建议关联现有申请。",
        )
