from datetime import datetime

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agents.application.schemas import (
    ApplicationAgentOutput,
    ApplicationRecommendation,
)
from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import Evidence, EvidenceSource, PreparedEmail
from app.agents.extraction.schemas import ExtractionField, ExtractionOutput
from app.domain.enums import EmailCategory, EmailPriority, WorkflowRunStatus
from app.infrastructure.checkpoint import sqlite_checkpointer
from app.workflows import JobMailGraph, ReviewExecutionOutcome, WorkflowState


def _prepared() -> PreparedEmail:
    return PreparedEmail(
        email_id=8,
        subject="面试邀请",
        sender_address="hr@example.com",
        received_at=datetime.fromisoformat("2026-07-29T08:00:00+08:00"),
        analysis_text="邀请您参加后端开发工程师面试。",
    )


def _classification(*, job_related: bool) -> ClassificationOutput:
    return ClassificationOutput(
        is_job_related=job_related,
        category=EmailCategory.INTERVIEW if job_related else EmailCategory.NON_JOB,
        priority=EmailPriority.HIGH if job_related else EmailPriority.LOW,
        should_reply=job_related,
        confidence=0.95,
        evidence=[
            Evidence(
                source=EvidenceSource.BODY,
                quote="邀请您参加后端开发工程师面试",
            )
        ],
    )


def _extraction() -> ExtractionOutput:
    return ExtractionOutput(
        summary="招聘方邀请候选人参加面试。",
        overall_confidence=0.9,
        missing_fields=list(ExtractionField),
    )


class FakeOperations:
    def __init__(self, *, job_related: bool = True) -> None:
        self.job_related = job_related
        self.calls: list[str] = []
        self.waiting: list[str] = []
        self.final_status: WorkflowRunStatus | None = None
        self.review_outcomes = [
            ReviewExecutionOutcome(
                review_task_id="review-1",
                follow_up_review_task_id="review-2",
            ),
            ReviewExecutionOutcome(review_task_id="review-2"),
        ]

    def load_email(self, email_id: int) -> PreparedEmail:
        self.calls.append("load")
        assert email_id == 8
        return _prepared()

    def classify(
        self,
        prepared: PreparedEmail,
        workflow_run_id: str,
    ) -> ClassificationOutput:
        self.calls.append("classify")
        return _classification(job_related=self.job_related)

    def extract(
        self,
        prepared: PreparedEmail,
        classification: ClassificationOutput,
        workflow_run_id: str,
    ) -> ExtractionOutput:
        self.calls.append("extract")
        return _extraction()

    def persist_analysis(self, **kwargs: object) -> int:
        self.calls.append("persist")
        return 15

    def match_application(
        self,
        **kwargs: object,
    ) -> tuple[int, list, ApplicationAgentOutput, str]:
        self.calls.append("match")
        return (
            15,
            [],
            ApplicationAgentOutput(
                recommendation=ApplicationRecommendation.CREATE_NEW,
                confidence=0.92,
                reasoning="没有候选申请，需要人工确认新建。",
            ),
            "review-1",
        )

    def execute_review(self, review_task_id: str) -> ReviewExecutionOutcome:
        self.calls.append(f"execute:{review_task_id}")
        outcome = self.review_outcomes.pop(0)
        assert outcome.review_task_id == review_task_id
        return outcome

    def mark_waiting(self, workflow_run_id: str, review_task_id: str) -> None:
        self.waiting.append(review_task_id)

    def finalize(self, workflow_run_id: str, status: WorkflowRunStatus) -> None:
        self.final_status = status

    def fail(self, workflow_run_id: str, **kwargs: object) -> None:
        self.final_status = WorkflowRunStatus.FAILED


def _initial() -> WorkflowState:
    return WorkflowState(
        workflow_run_id="run-1",
        thread_id="thread-1",
        user_id=1,
        email_id=8,
    )


def test_non_job_email_persists_and_finishes_without_application_agent() -> None:
    operations = FakeOperations(job_related=False)
    graph = JobMailGraph(operations).compile(checkpointer=InMemorySaver())

    graph.invoke(
        _initial().model_dump(mode="json"),
        config={"configurable": {"thread_id": "thread-1"}},
    )

    assert operations.calls == ["load", "classify", "persist"]
    assert operations.final_status is WorkflowRunStatus.SUCCEEDED
    assert operations.waiting == []


def test_job_email_interrupts_twice_and_resumes_from_same_thread() -> None:
    operations = FakeOperations()
    graph = JobMailGraph(operations).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "thread-1"}}

    first = graph.invoke(_initial().model_dump(mode="json"), config=config)
    assert first["current_review_task_id"] == "review-1"
    assert operations.waiting == ["review-1"]

    second = graph.invoke(
        Command(resume={"review_task_id": "review-1"}),
        config=config,
    )
    assert second["current_review_task_id"] == "review-2"
    # interrupt 所在节点恢复时从节点开头重放，写入必须保持幂等。
    assert operations.waiting == ["review-1", "review-1", "review-2"]

    final = graph.invoke(
        Command(resume={"review_task_id": "review-2"}),
        config=config,
    )
    assert final["final_status"] == WorkflowRunStatus.SUCCEEDED.value
    assert operations.calls[-2:] == ["execute:review-1", "execute:review-2"]
    assert operations.final_status is WorkflowRunStatus.SUCCEEDED


def test_sqlite_checkpoint_resumes_after_graph_is_recreated(tmp_path) -> None:
    path = tmp_path / "workflow.sqlite"
    config = {"configurable": {"thread_id": "restart-thread"}}

    first_operations = FakeOperations()
    with sqlite_checkpointer(path, "02" * 32) as checkpointer:
        graph = JobMailGraph(first_operations).compile(checkpointer=checkpointer)
        first = graph.invoke(
            _initial().model_dump(mode="json"),
            config=config,
        )
    assert first["current_review_task_id"] == "review-1"

    second_operations = FakeOperations()
    with sqlite_checkpointer(path, "02" * 32) as checkpointer:
        graph = JobMailGraph(second_operations).compile(checkpointer=checkpointer)
        second = graph.invoke(
            Command(resume={"review_task_id": "review-1"}),
            config=config,
        )
    assert second["current_review_task_id"] == "review-2"
    assert "execute:review-1" in second_operations.calls

    third_operations = FakeOperations()
    third_operations.review_outcomes = [
        ReviewExecutionOutcome(review_task_id="review-2")
    ]
    with sqlite_checkpointer(path, "02" * 32) as checkpointer:
        graph = JobMailGraph(third_operations).compile(checkpointer=checkpointer)
        final = graph.invoke(
            Command(resume={"review_task_id": "review-2"}),
            config=config,
        )
    assert final["final_status"] == WorkflowRunStatus.SUCCEEDED.value


def test_classification_failure_retries_once_before_continuing() -> None:
    class RetryOperations(FakeOperations):
        classification_attempts = 0

        def classify(
            self,
            prepared: PreparedEmail,
            workflow_run_id: str,
        ) -> ClassificationOutput:
            self.classification_attempts += 1
            self.calls.append("classify")
            if self.classification_attempts == 1:
                raise RuntimeError("temporary structured output error")
            return _classification(job_related=False)

    operations = RetryOperations(job_related=False)
    graph = JobMailGraph(operations).compile(checkpointer=InMemorySaver())

    result = graph.invoke(
        _initial().model_dump(mode="json"),
        config={"configurable": {"thread_id": "retry-thread"}},
    )

    assert operations.classification_attempts == 2
    assert result["retry_counts"] == {"classification": 1}
    assert result["final_status"] == WorkflowRunStatus.SUCCEEDED.value


def test_rejected_review_cancels_workflow_without_executor_follow_up() -> None:
    operations = FakeOperations()
    operations.review_outcomes = [
        ReviewExecutionOutcome(review_task_id="review-1", rejected=True)
    ]
    graph = JobMailGraph(operations).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "reject-thread"}}

    graph.invoke(_initial().model_dump(mode="json"), config=config)
    final = graph.invoke(
        Command(resume={"review_task_id": "review-1"}),
        config=config,
    )

    assert final["final_status"] == WorkflowRunStatus.CANCELLED.value
    assert operations.final_status is WorkflowRunStatus.CANCELLED
