from datetime import datetime
from types import SimpleNamespace

from app.application.application_management import _score_candidate
from app.domain.enums import ApplicationStage


def test_deterministic_candidate_score_combines_business_facts() -> None:
    email = SimpleNamespace(
        from_address="hr@xinghai.example",
        application_id=None,
        received_at=datetime(2026, 7, 28, 10, 0),
    )
    analysis = SimpleNamespace(
        company_name="星海科技",
        position_name="后端开发工程师",
    )
    application = SimpleNamespace(
        id=12,
        company_name="星海科技",
        company_alias=None,
        position_name="后端开发工程师",
        current_stage=ApplicationStage.APPLIED,
        contact_email="hr@xinghai.example",
        updated_at=datetime(2026, 7, 20, 10, 0),
    )

    candidate = _score_candidate(email, analysis, application)

    assert candidate.application_id == 12
    assert candidate.deterministic_score == 0.9
    assert candidate.score_breakdown.company == 1
    assert candidate.score_breakdown.position == 1
    assert candidate.score_breakdown.sender == 1


def test_unrelated_application_stays_below_candidate_threshold() -> None:
    email = SimpleNamespace(
        from_address="hr@xinghai.example",
        application_id=None,
        received_at=datetime(2026, 7, 28, 10, 0),
    )
    analysis = SimpleNamespace(
        company_name="星海科技",
        position_name="后端开发工程师",
    )
    application = SimpleNamespace(
        id=13,
        company_name="远山银行",
        company_alias=None,
        position_name="产品经理",
        current_stage=ApplicationStage.APPLIED,
        contact_email="jobs@yuanshan.example",
        updated_at=datetime(2024, 1, 1, 10, 0),
    )

    candidate = _score_candidate(email, analysis, application)

    assert candidate.deterministic_score == 0
