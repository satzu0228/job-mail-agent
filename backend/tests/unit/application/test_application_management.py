from datetime import datetime
from types import SimpleNamespace

from app.agents.application.schemas import (
    ApplicationAgentOutput,
    ApplicationRecommendation,
)
from app.application.application_management import (
    ReviewTaskService,
    _application_review_action,
    _interview_round_label,
    _is_candidate_eligible,
    _parse_interview_round,
    _review_datetime,
    _score_candidate,
)
from app.domain.enums import (
    ApplicationStage,
    EmailCategory,
    ReviewActionType,
    TaskType,
)


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


def test_explicit_company_conflict_excludes_historical_sender_candidate() -> None:
    email = SimpleNamespace(
        from_address="same-test-sender@example.com",
        application_id=None,
        received_at=datetime(2026, 8, 1, 10, 0),
    )
    analysis = SimpleNamespace(
        company_name="启明智联",
        position_name="前端研发实习生",
    )
    application = SimpleNamespace(
        id=106,
        company_name="远大科技",
        company_alias=None,
        position_name="前端开发实习生",
        current_stage=ApplicationStage.INTERVIEW,
        contact_email=None,
        updated_at=datetime(2026, 8, 1, 9, 0),
    )

    candidate = _score_candidate(
        email,
        analysis,
        application,
        linked_sender_match=True,
    )

    assert candidate.deterministic_score >= 0.15
    assert not _is_candidate_eligible(email, analysis, application, candidate)


def test_no_candidates_turns_uncertain_model_result_into_create_review() -> None:
    suggestion = ApplicationAgentOutput(
        recommendation=ApplicationRecommendation.NEEDS_CONFIRMATION,
        confidence=0.4,
        reasoning="没有候选申请，需要人工确认是否新建。",
    )

    assert (
        _application_review_action(suggestion, [])
        is ReviewActionType.CREATE_APPLICATION
    )


def test_interview_round_parser_uses_explicit_round_and_generic_label() -> None:
    assert _parse_interview_round("邀请参加前端岗位二面") == 2
    assert _parse_interview_round("请参加第 3 轮面试") == 3
    assert _parse_interview_round("8月1日早上10点参加线上面试") is None
    assert _interview_round_label(1) == "一面"


def test_review_datetime_normalizes_aware_value_to_utc_naive() -> None:
    assert _review_datetime("2026-08-01T10:00:00+08:00") == datetime(
        2026, 8, 1, 2, 0
    )


def test_interview_analysis_creates_readable_first_round_task_review() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.results = iter(
                [
                    SimpleNamespace(
                        id=18,
                        category=EmailCategory.INTERVIEW,
                        event_time=datetime(2026, 8, 1, 2, 0),
                        event_type="INTERVIEW_INVITATION",
                        summary="邀请参加线上面试。",
                        source_timezone="Asia/Shanghai",
                        extraction_json={
                            "event_time": {"raw_text": "8月1日早上10点"},
                            "location": {"value": "线上"},
                        },
                    ),
                    None,
                    None,
                ]
            )
            self.added: list[object] = []

        def scalar(self, _statement: object) -> object:
            return next(self.results)

        def add(self, value: object) -> None:
            self.added.append(value)

        def flush(self) -> None:
            return None

    session = FakeSession()
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]
    review = service._create_task_follow_up(
        SimpleNamespace(
            id="stage-review",
            action_type=ReviewActionType.UPDATE_APPLICATION_STAGE,
            source_email_id=27,
            workflow_run_id="run-1",
        ),
        SimpleNamespace(id=105, company_name="远大科技", position_name="前端开发实习生"),
    )

    assert review is not None
    assert review.action_type is ReviewActionType.CREATE_TASK
    assert review.proposed_payload["task_type"] == TaskType.INTERVIEW.value
    assert review.proposed_payload["interview_round"] == 1
    assert review.proposed_payload["title"] == "远大科技一面"
    assert review.proposed_payload["start_at"] == "2026-08-01T02:00:00Z"
    assert review.proposed_payload["location"] == "线上"
