from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.agents.application.schemas import (
    ApplicationAgentOutput,
    ApplicationAnalysisFacts,
    ApplicationCandidate,
    ApplicationRecommendation,
    CandidateRanking,
    CandidateScoreBreakdown,
)
from app.application.application_management import (
    ApplicationAnalysisUnavailableError,
    ApplicationManagementService,
    ApplicationModelExecutionError,
    ReviewTaskService,
    _application_review_action,
    _application_stage,
    _extracted_interview_result,
    _extracted_value,
    _infer_round_from_extraction,
    _interview_result,
    _interview_round_label,
    _is_candidate_eligible,
    _is_reschedule,
    _json_datetime,
    _normalize_text,
    _optional_text,
    _parse_interview_round,
    _parse_interview_round_max,
    _recency_score,
    _review_datetime,
    _same_domain,
    _score_candidate,
    _task_review_snapshot,
    _text_score,
)
from app.domain.enums import (
    ApplicationStage,
    EmailCategory,
    InterviewResult,
    ReviewActionType,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.repositories import ResourceConflictError


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


def test_review_datetime_rejects_invalid_or_naive_values() -> None:
    assert _review_datetime(None) is None
    assert _review_datetime("") is None
    with pytest.raises(ResourceConflictError, match="格式无效"):
        _review_datetime(42)
    with pytest.raises(ResourceConflictError, match="格式无效"):
        _review_datetime("not-a-date")
    with pytest.raises(ResourceConflictError, match="必须包含时区"):
        _review_datetime("2026-08-01T10:00:00")


def test_round_parsing_and_reschedule_helpers_cover_edge_cases() -> None:
    assert _parse_interview_round("初面通知") == 1
    assert _parse_interview_round("第十轮面试") == 10
    assert _parse_interview_round("第21轮面试") is None
    assert _parse_interview_round_max("先初面，再进行第三轮面试和第 2 轮面试") == 3
    assert _parse_interview_round_max("第21轮面试") is None
    assert _is_reschedule("原面试时间调整到周五")
    assert not _is_reschedule("邀请参加新一轮面试")
    assert _interview_round_label(11) == "第 11 轮面试"


def test_text_and_time_score_helpers_cover_matching_levels() -> None:
    assert _normalize_text(" 星海_科技！") == "星海科技"
    assert _normalize_text(None) == ""
    assert _text_score(None, "星海") == 0
    assert _text_score("星海", None, "星海科技") == 0.85
    assert _text_score("abc", "xyz") == 0
    assert _same_domain("hr@example.com", "jobs@example.com") == 0.5
    assert _same_domain("invalid", "jobs@example.com") == 0
    now = datetime(2026, 8, 1, tzinfo=UTC)
    assert _recency_score(None, now) == 0
    assert _recency_score(now, now - timedelta(days=20)) == 1
    assert _recency_score(now, now - timedelta(days=100)) == 0.6
    assert _recency_score(now, now - timedelta(days=300)) == 0.2
    assert _recency_score(now, now - timedelta(days=500)) == 0


def test_payload_conversion_helpers_are_strict_and_serializable() -> None:
    assert _extracted_value({"value": " 线上 "}) == "线上"
    assert _extracted_value("线上") is None
    assert _optional_text("  ") is None
    assert _json_datetime(None) is None
    assert _json_datetime(datetime(2026, 8, 1, 2, 0)) == "2026-08-01T02:00:00Z"
    assert _application_stage("INTERVIEW") is ApplicationStage.INTERVIEW
    assert _interview_result(None) is None
    assert _interview_result("PASSED") is InterviewResult.PASSED
    with pytest.raises(ResourceConflictError, match="proposed_stage"):
        _application_stage("UNKNOWN")
    with pytest.raises(ResourceConflictError, match="interview_result"):
        _interview_result("UNKNOWN")


def test_extraction_round_and_result_helpers_use_structured_then_text_fallback() -> None:
    assert _infer_round_from_extraction(
        {"interview_result": {"round_number": 4}}, None
    ) == 4
    assert _infer_round_from_extraction(
        {"summary": {"value": "请参加二面"}}, None
    ) == 2
    assert _infer_round_from_extraction({}, None) is None
    assert _extracted_interview_result({}) is None
    assert _extracted_interview_result(
        {"interview_result": {"value": "FAILED"}}
    ) == "FAILED"


def test_task_snapshot_uses_stable_wire_values() -> None:
    task = SimpleNamespace(
        title="星海科技一面",
        description=None,
        start_at=datetime(2026, 8, 1, 2, 0),
        deadline_at=None,
        source_timezone="Asia/Shanghai",
        location="线上",
        meeting_url="https://meeting.example/1",
        status=TaskStatus.PENDING,
    )

    assert _task_review_snapshot(task) == {
        "title": "星海科技一面",
        "description": None,
        "start_at": "2026-08-01T02:00:00Z",
        "deadline_at": None,
        "source_timezone": "Asia/Shanghai",
        "location": "线上",
        "meeting_url": "https://meeting.example/1",
        "status": "PENDING",
    }


def _candidate(application_id: int = 12) -> ApplicationCandidate:
    return ApplicationCandidate(
        application_id=application_id,
        company_name="星海科技",
        position_name="后端开发工程师",
        current_stage=ApplicationStage.APPLIED,
        deterministic_score=0.9,
        score_breakdown=CandidateScoreBreakdown(
            company=1,
            position=1,
            sender=1,
            linked_email=0,
            recency=1,
        ),
    )


def test_agent_output_validation_rejects_out_of_scope_changes() -> None:
    facts = ApplicationAnalysisFacts(
        email_id=1,
        email_subject="面试通知",
        category=EmailCategory.INTERVIEW,
        sender_address="hr@example.com",
        proposed_stage=ApplicationStage.INTERVIEW,
    )
    candidate = _candidate()
    valid = ApplicationAgentOutput(
        recommendation=ApplicationRecommendation.LINK_EXISTING,
        selected_application_id=12,
        proposed_stage=ApplicationStage.INTERVIEW,
        confidence=0.9,
        reasoning="候选一致",
    )
    ApplicationManagementService._validate_agent_output(valid, [candidate], facts)

    outside = valid.model_copy(update={"selected_application_id": 99})
    with pytest.raises(ApplicationModelExecutionError, match="候选列表外"):
        ApplicationManagementService._validate_agent_output(outside, [candidate], facts)
    bad_ranking = valid.model_copy(
        update={
            "candidate_rankings": [
                CandidateRanking(
                    application_id=99, rank=1, confidence=0.8, reason="错误候选"
                )
            ]
        }
    )
    with pytest.raises(ApplicationModelExecutionError, match="排序了候选列表外"):
        ApplicationManagementService._validate_agent_output(
            bad_ranking, [candidate], facts
        )
    bad_stage = valid.model_copy(update={"proposed_stage": ApplicationStage.OFFER})
    with pytest.raises(ApplicationModelExecutionError, match="改写了抽取阶段"):
        ApplicationManagementService._validate_agent_output(
            bad_stage, [candidate], facts
        )


class _RecordingSession:
    def __init__(self, scalar_values: list[object] | None = None) -> None:
        self.scalar_values = iter(scalar_values or [])
        self.added: list[object] = []
        self.flush_count = 0

    def scalar(self, _statement: object) -> object:
        return next(self.scalar_values)

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1


def _source_review(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": "source-review",
        "action_type": ReviewActionType.LINK_APPLICATION,
        "source_email_id": 27,
        "workflow_run_id": "run-1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _application(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 105,
        "company_name": "远大科技",
        "position_name": "前端开发实习生",
        "current_stage": ApplicationStage.APPLIED,
        "interview_result": None,
        "version": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_stage_follow_up_records_no_change_event() -> None:
    session = _RecordingSession()
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]

    result = service._create_stage_follow_up(
        _source_review(),
        _application(),
        {
            "proposed_stage": "APPLIED",
            "event_type": "APPLICATION_UPDATE",
            "summary": "申请已收到",
        },
    )

    assert result is None
    assert len(session.added) == 1
    event = session.added[0]
    assert event.event_type == "APPLICATION_UPDATE"
    assert event.confirmed_stage is ApplicationStage.APPLIED
    assert event.details["stage_changed"] is False


def test_stage_follow_up_separates_interview_result_review() -> None:
    session = _RecordingSession()
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]

    follow_up = service._create_stage_follow_up(
        _source_review(),
        _application(
            current_stage=ApplicationStage.INTERVIEW,
            interview_result=InterviewResult.PENDING,
        ),
        {
            "proposed_stage": "INTERVIEW",
            "interview_result": "PASSED",
            "interview_round": 2,
            "summary": "二面通过",
        },
    )

    assert follow_up is not None
    assert follow_up.action_type is ReviewActionType.UPDATE_INTERVIEW_RESULT
    assert follow_up.proposed_payload["round_number"] == 2
    assert follow_up.proposed_payload["result"] == "PASSED"
    assert session.flush_count == 1


def test_stage_follow_up_creates_transition_review_and_rejects_invalid_transition() -> None:
    session = _RecordingSession()
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]
    application = _application()

    follow_up = service._create_stage_follow_up(
        _source_review(),
        application,
        {
            "proposed_stage": "INTERVIEW",
            "interview_result": "PENDING",
        },
    )

    assert follow_up is not None
    assert follow_up.action_type is ReviewActionType.UPDATE_APPLICATION_STAGE
    assert follow_up.proposed_payload["previous_stage"] == "APPLIED"
    assert follow_up.proposed_payload["proposed_stage"] == "INTERVIEW"

    assert (
        service._create_stage_follow_up(
            _source_review(action_type=ReviewActionType.UPDATE_APPLICATION_STAGE),
            application,
            {"proposed_stage": "OFFER"},
        )
        is None
    )


def test_deadline_follow_up_creates_material_review() -> None:
    session = _RecordingSession([None, None])
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]
    analysis = SimpleNamespace(
        id=18,
        category=EmailCategory.MATERIAL_REQUEST,
        deadline_at=datetime(2026, 8, 8, 10, 0),
        source_timezone="Asia/Shanghai",
        summary="请按时补充材料",
        extraction_json={"deadline": {"raw_text": "8月8日18点前"}},
    )

    follow_up = service._create_deadline_task_review(
        _source_review(), _application(), analysis
    )

    assert follow_up is not None
    assert follow_up.action_type is ReviewActionType.CREATE_TASK
    assert follow_up.proposed_payload["task_type"] == TaskType.MATERIAL.value
    assert follow_up.proposed_payload["title"] == "远大科技 材料补充截止"
    assert follow_up.proposed_payload["deadline_at"] == "2026-08-08T10:00:00Z"


def test_deadline_follow_up_reuses_review_and_links_existing_task() -> None:
    existing_review = SimpleNamespace(id="existing")
    service = ReviewTaskService(  # type: ignore[arg-type]
        _RecordingSession([existing_review]), user_id=1
    )
    analysis = SimpleNamespace(
        id=18,
        category=EmailCategory.OFFER,
        deadline_at=datetime(2026, 8, 8, 10, 0),
        source_timezone="Asia/Shanghai",
        summary="请确认 Offer",
        extraction_json={},
    )
    assert (
        service._create_deadline_task_review(
            _source_review(), _application(), analysis
        )
        is existing_review
    )

    duplicate = SimpleNamespace(application_id=None)
    duplicate_session = _RecordingSession([None, duplicate])
    duplicate_service = ReviewTaskService(  # type: ignore[arg-type]
        duplicate_session, user_id=1
    )
    assert (
        duplicate_service._create_deadline_task_review(
            _source_review(), _application(), analysis
        )
        is None
    )
    assert duplicate.application_id == 105
    assert duplicate_session.flush_count == 1


def test_infer_next_round_reuses_reschedule_and_increments_new_invite() -> None:
    reschedule_service = ReviewTaskService(  # type: ignore[arg-type]
        _RecordingSession([2]), user_id=1
    )
    assert (
        reschedule_service._infer_next_interview_round(105, "面试时间变更") == 2
    )
    new_service = ReviewTaskService(  # type: ignore[arg-type]
        _RecordingSession([2]), user_id=1
    )
    assert new_service._infer_next_interview_round(105, "新的面试邀请") == 3
    explicit_service = ReviewTaskService(  # type: ignore[arg-type]
        _RecordingSession(), user_id=1
    )
    assert explicit_service._infer_next_interview_round(105, "第三轮面试") == 3


def test_task_follow_up_short_circuits_recursive_and_missing_analysis() -> None:
    service = ReviewTaskService(_RecordingSession(), user_id=1)  # type: ignore[arg-type]
    assert (
        service._create_task_follow_up(
            _source_review(action_type=ReviewActionType.CREATE_TASK), _application()
        )
        is None
    )
    missing_service = ReviewTaskService(  # type: ignore[arg-type]
        _RecordingSession([None]), user_id=1
    )
    assert (
        missing_service._create_task_follow_up(_source_review(), _application())
        is None
    )


def test_changed_interview_schedule_creates_task_update_review() -> None:
    duplicate = SimpleNamespace(
        id=88,
        application_id=None,
        version=4,
        title="远大科技二面",
        description="原安排",
        start_at=datetime(2026, 8, 1, 2, 0),
        deadline_at=None,
        source_timezone="Asia/Shanghai",
        location="原会议室",
        meeting_url="https://meeting.example/old",
        status=TaskStatus.PENDING,
    )
    session = _RecordingSession([None, duplicate])
    service = ReviewTaskService(session, user_id=1)  # type: ignore[arg-type]
    analysis = SimpleNamespace(
        id=18,
        category=EmailCategory.INTERVIEW,
        event_time=datetime(2026, 8, 2, 2, 0, tzinfo=UTC),
        event_type="SECOND_INTERVIEW",
        summary="二面时间调整",
        source_timezone="Asia/Shanghai",
        extraction_json={
            "event_time": {"raw_text": "二面调整到8月2日10点"},
            "location": {"value": "新会议室"},
            "meeting_url": {"value": "https://meeting.example/new"},
        },
    )

    follow_up = service._create_interview_task_review(
        _source_review(), _application(), analysis
    )

    assert follow_up is not None
    assert duplicate.application_id == 105
    assert follow_up.action_type is ReviewActionType.UPDATE_TASK
    assert follow_up.resource_version == 4
    assert follow_up.proposed_payload["start_at"] == "2026-08-02T02:00:00Z"
    assert follow_up.proposed_payload["location"] == "新会议室"
    assert follow_up.proposed_payload["meeting_url"] == "https://meeting.example/new"
    assert follow_up.proposed_payload["before"]["location"] == "原会议室"


def test_unchanged_interview_schedule_does_not_repeat_review() -> None:
    duplicate = SimpleNamespace(
        id=88,
        application_id=105,
        version=4,
        title="远大科技二面",
        description="二面安排",
        start_at=datetime(2026, 8, 2, 2, 0),
        deadline_at=None,
        source_timezone="Asia/Shanghai",
        location="新会议室",
        meeting_url=None,
        status=TaskStatus.PENDING,
    )
    service = ReviewTaskService(  # type: ignore[arg-type]
        _RecordingSession([None, duplicate]), user_id=1
    )
    analysis = SimpleNamespace(
        id=18,
        category=EmailCategory.INTERVIEW,
        event_time=datetime(2026, 8, 2, 2, 0, tzinfo=UTC),
        event_type="SECOND_INTERVIEW",
        summary="二面安排",
        source_timezone="Asia/Shanghai",
        extraction_json={
            "event_time": {"raw_text": "二面8月2日10点"},
            "location": {"value": "新会议室"},
        },
    )

    assert (
        service._create_interview_task_review(
            _source_review(), _application(), analysis
        )
        is None
    )


class _CandidateSession(_RecordingSession):
    def __init__(self, scalar_lists: list[list[object]]) -> None:
        super().__init__()
        self.scalar_lists = iter(scalar_lists)

    def scalars(self, _statement: object) -> object:
        return iter(next(self.scalar_lists))


def _management_service(session: object) -> ApplicationManagementService:
    agent = SimpleNamespace(prompt_version="test-v1")
    return ApplicationManagementService(
        session, 1, agent, model_provider="stub", model_name="stub"  # type: ignore[arg-type]
    )


def test_current_analysis_and_job_relevance_validation_fail_closed() -> None:
    service = _management_service(_RecordingSession([None]))
    with pytest.raises(ApplicationAnalysisUnavailableError, match="尚无当前分析"):
        service._current_analysis(27)
    with pytest.raises(ApplicationAnalysisUnavailableError, match="非求职邮件"):
        service._validate_analysis(SimpleNamespace(is_job_related=False))
    service._validate_analysis(SimpleNamespace(is_job_related=True))


def test_analysis_facts_preserve_only_extracted_stage() -> None:
    facts = ApplicationManagementService._analysis_facts(
        SimpleNamespace(
            id=27,
            subject="面试通知",
            from_address="hr@example.com",
        ),
        SimpleNamespace(
            category=EmailCategory.INTERVIEW,
            company_name="星海科技",
            position_name="后端开发工程师",
            event_type="INTERVIEW_INVITATION",
            summary="邀请参加面试",
            extraction_json={"proposed_stage": {"value": "INTERVIEW"}},
        ),
    )
    assert facts.email_id == 27
    assert facts.proposed_stage is ApplicationStage.INTERVIEW

    no_stage = ApplicationManagementService._analysis_facts(
        SimpleNamespace(id=28, subject="进度通知", from_address="hr@example.com"),
        SimpleNamespace(
            category=EmailCategory.APPLICATION_UPDATE,
            company_name=None,
            position_name=None,
            event_type=None,
            summary=None,
            extraction_json={},
        ),
    )
    assert no_stage.proposed_stage is None


def test_find_candidates_sorts_and_reports_ambiguous_same_company_matches() -> None:
    applications = [
        SimpleNamespace(
            id=12,
            company_name="星海科技",
            company_alias=None,
            position_name="后端开发工程师",
            current_stage=ApplicationStage.APPLIED,
            contact_email=None,
            updated_at=datetime(2026, 7, 20),
        ),
        SimpleNamespace(
            id=13,
            company_name="星海科技",
            company_alias=None,
            position_name="平台开发工程师",
            current_stage=ApplicationStage.APPLIED,
            contact_email=None,
            updated_at=datetime(2026, 7, 19),
        ),
    ]
    service = _management_service(_CandidateSession([applications, []]))
    candidates, reasons = service._find_candidates(
        SimpleNamespace(
            from_address="hr@example.com",
            application_id=None,
            received_at=datetime(2026, 7, 28),
        ),
        SimpleNamespace(company_name="星海科技", position_name=None),
    )

    assert [candidate.application_id for candidate in candidates] == [12, 13]
    assert "排名前两位候选分数接近" in reasons
    assert "邮件缺少岗位且同公司存在多个候选申请" in reasons


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
                    None,  # Task table dedup check
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
