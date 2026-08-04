from __future__ import annotations

from typing import Any, Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.application.schemas import ApplicationAgentOutput, ApplicationCandidate
from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import PreparedEmail
from app.agents.extraction.schemas import ExtractionOutput
from app.domain.enums import RequiredCapability, WorkflowRunStatus
from app.workflows.state import (
    ReviewExecutionOutcome,
    ReviewResumePayload,
    WorkflowState,
)

GRAPH_VERSION = "job-mail-workflow.v2"


class WorkflowOperations(Protocol):
    def load_email(self, email_id: int) -> PreparedEmail: ...

    def classify(
        self,
        prepared: PreparedEmail,
        workflow_run_id: str,
    ) -> ClassificationOutput: ...

    def extract(
        self,
        prepared: PreparedEmail,
        classification: ClassificationOutput,
        workflow_run_id: str,
    ) -> ExtractionOutput: ...

    def persist_analysis(
        self,
        *,
        email_id: int,
        workflow_run_id: str,
        classification: ClassificationOutput,
        extraction: ExtractionOutput | None,
    ) -> int: ...

    def match_application(
        self,
        *,
        email_id: int,
        workflow_run_id: str,
    ) -> tuple[int, list[ApplicationCandidate], ApplicationAgentOutput, str]: ...

    def generate_reply(
        self,
        *,
        email_id: int,
        workflow_run_id: str,
    ) -> tuple[int | None, str | None]: ...

    def execute_review(self, review_task_id: str) -> ReviewExecutionOutcome: ...

    def mark_waiting(self, workflow_run_id: str, review_task_id: str) -> None: ...

    def finalize(self, workflow_run_id: str, status: WorkflowRunStatus) -> None: ...

    def fail(
        self,
        workflow_run_id: str,
        *,
        node: str,
        error_code: str,
        error_message: str,
    ) -> None: ...


class JobMailGraph:
    def __init__(self, operations: WorkflowOperations) -> None:
        self._operations = operations

    def compile(self, *, checkpointer: Any) -> Any:
        builder = StateGraph(WorkflowState)
        builder.add_node("load_email", self._load_email)
        builder.add_node("classify_email", self._classify_email)
        builder.add_node("extract_information", self._extract_information)
        builder.add_node("validate_results", self._validate_results)
        builder.add_node("persist_analysis", self._persist_analysis)
        builder.add_node("match_application", self._match_application)
        builder.add_node("generate_reply", self._generate_reply)
        builder.add_node("human_review", self._human_review)
        builder.add_node("execute_review", self._execute_review)
        builder.add_node("finalize", self._finalize)
        builder.add_node("fail", self._fail)

        builder.add_edge(START, "load_email")
        builder.add_conditional_edges(
            "load_email",
            self._route_failure,
            {"continue": "classify_email", "fail": "fail"},
        )
        builder.add_conditional_edges(
            "classify_email",
            self._route_after_classification,
            {
                "retry": "classify_email",
                "extract": "extract_information",
                "persist": "persist_analysis",
                "fail": "fail",
            },
        )
        builder.add_conditional_edges(
            "extract_information",
            self._route_after_extraction,
            {
                "retry": "extract_information",
                "continue": "validate_results",
                "fail": "fail",
            },
        )
        builder.add_conditional_edges(
            "validate_results",
            self._route_failure,
            {"continue": "persist_analysis", "fail": "fail"},
        )
        builder.add_conditional_edges(
            "persist_analysis",
            self._route_after_persist,
            {"match": "match_application", "finalize": "finalize", "fail": "fail"},
        )
        builder.add_conditional_edges(
            "match_application",
            self._route_after_application,
            {
                "retry": "match_application",
                "continue": "human_review",
                "fail": "fail",
            },
        )
        builder.add_edge("human_review", "execute_review")
        builder.add_conditional_edges(
            "execute_review",
            self._route_after_review,
            {
                "review": "human_review",
                "reply": "generate_reply",
                "finalize": "finalize",
                "fail": "fail",
            },
        )
        builder.add_conditional_edges(
            "generate_reply",
            self._route_after_reply,
            {
                "retry": "generate_reply",
                "review": "human_review",
                "finalize": "finalize",
                "fail": "fail",
            },
        )
        builder.add_edge("finalize", END)
        builder.add_edge("fail", END)
        return builder.compile(checkpointer=checkpointer)

    def _load_email(self, state: WorkflowState) -> dict[str, Any]:
        try:
            prepared = self._operations.load_email(state.email_id)
            return {"prepared_email": prepared.model_dump(mode="json")}
        except Exception as exc:
            return self._failure("load_email", exc)

    def _classify_email(self, state: WorkflowState) -> dict[str, Any]:
        if state.prepared_email is None:
            return self._failure("classify_email", ValueError("缺少邮件分析输入"))
        try:
            classification = self._operations.classify(
                state.prepared_email,
                state.workflow_run_id,
            )
            return {
                "classification": classification.model_dump(mode="json"),
                "retry_node": None,
            }
        except Exception as exc:
            return self._retry_or_failure(
                state,
                retry_key="classification",
                node="classify_email",
                exc=exc,
            )

    def _extract_information(self, state: WorkflowState) -> dict[str, Any]:
        if state.prepared_email is None or state.classification is None:
            return self._failure("extract_information", ValueError("缺少分类结果"))
        try:
            extraction = self._operations.extract(
                state.prepared_email,
                state.classification,
                state.workflow_run_id,
            )
            return {
                "extraction": extraction.model_dump(mode="json"),
                "retry_node": None,
            }
        except Exception as exc:
            return self._retry_or_failure(
                state,
                retry_key="extraction",
                node="extract_information",
                exc=exc,
            )

    def _validate_results(self, state: WorkflowState) -> dict[str, Any]:
        if state.classification is None:
            return self._failure("validate_results", ValueError("缺少分类结果"))
        extraction_required = (
            RequiredCapability.EXTRACT
            in state.classification.required_capabilities
        )
        if extraction_required and state.extraction is None:
            return self._failure("validate_results", ValueError("求职邮件缺少抽取结果"))
        if not state.classification.is_job_related and state.extraction is not None:
            return self._failure("validate_results", ValueError("非求职邮件存在抽取结果"))
        return {}

    def _persist_analysis(self, state: WorkflowState) -> dict[str, Any]:
        if state.classification is None:
            return self._failure("persist_analysis", ValueError("缺少分类结果"))
        try:
            analysis_id = self._operations.persist_analysis(
                email_id=state.email_id,
                workflow_run_id=state.workflow_run_id,
                classification=state.classification,
                extraction=state.extraction,
            )
            updates: dict[str, Any] = {"analysis_id": analysis_id}
            if not state.classification.is_job_related:
                updates["final_status"] = WorkflowRunStatus.SUCCEEDED.value
            return updates
        except Exception as exc:
            return self._failure("persist_analysis", exc)

    def _match_application(self, state: WorkflowState) -> dict[str, Any]:
        try:
            analysis_id, candidates, suggestion, review_task_id = (
                self._operations.match_application(
                    email_id=state.email_id,
                    workflow_run_id=state.workflow_run_id,
                )
            )
            return {
                "analysis_id": analysis_id,
                "application_candidates": [
                    candidate.model_dump(mode="json") for candidate in candidates
                ],
                "application_suggestion": suggestion.model_dump(mode="json"),
                "current_review_task_id": review_task_id,
                "retry_node": None,
            }
        except Exception as exc:
            return self._retry_or_failure(
                state,
                retry_key="application",
                node="match_application",
                exc=exc,
            )

    def _human_review(self, state: WorkflowState) -> dict[str, Any]:
        task_id = state.current_review_task_id
        if not task_id:
            return self._failure("human_review", ValueError("缺少待审核任务"))
        try:
            self._operations.mark_waiting(state.workflow_run_id, task_id)
            payload = ReviewResumePayload.model_validate(
                interrupt(
                    {
                        "workflow_run_id": state.workflow_run_id,
                        "review_task_id": task_id,
                    }
                )
            )
            if payload.review_task_id != task_id:
                raise ValueError("恢复审核任务与当前中断任务不一致")
            return {}
        except Exception as exc:
            # GraphInterrupt 必须继续向上传递，不能转换为业务失败。
            if exc.__class__.__name__ == "GraphInterrupt":
                raise
            return self._failure("human_review", exc)

    def _generate_reply(self, state: WorkflowState) -> dict[str, Any]:
        try:
            draft_id, review_task_id = self._operations.generate_reply(
                email_id=state.email_id,
                workflow_run_id=state.workflow_run_id,
            )
            if draft_id is None or review_task_id is None:
                return {
                    "reply_draft_id": None,
                    "current_review_task_id": None,
                    "final_status": WorkflowRunStatus.SUCCEEDED.value,
                    "retry_node": None,
                }
            return {
                "reply_draft_id": draft_id,
                "current_review_task_id": review_task_id,
                "retry_node": None,
            }
        except Exception as exc:
            return self._retry_or_failure(
                state,
                retry_key="reply",
                node="generate_reply",
                exc=exc,
            )

    def _execute_review(self, state: WorkflowState) -> dict[str, Any]:
        task_id = state.current_review_task_id
        if not task_id:
            return self._failure("execute_review", ValueError("缺少审核任务"))
        try:
            outcome = self._operations.execute_review(task_id)
            completed = [*state.completed_review_task_ids, task_id]
            if outcome.follow_up_review_task_id:
                return {
                    "completed_review_task_ids": completed,
                    "current_review_task_id": outcome.follow_up_review_task_id,
                }
            if outcome.rejected:
                return {
                    "completed_review_task_ids": completed,
                    "current_review_task_id": None,
                    "final_status": WorkflowRunStatus.CANCELLED.value,
                }
            if outcome.action_type == "SEND_REPLY":
                return {
                    "completed_review_task_ids": completed,
                    "current_review_task_id": None,
                    "final_status": WorkflowRunStatus.SUCCEEDED.value,
                }
            return {
                "completed_review_task_ids": completed,
                "current_review_task_id": None,
            }
        except Exception as exc:
            return self._failure("execute_review", exc)

    def _finalize(self, state: WorkflowState) -> dict[str, Any]:
        status = state.final_status or WorkflowRunStatus.SUCCEEDED
        self._operations.finalize(state.workflow_run_id, status)
        return {"final_status": status.value}

    def _fail(self, state: WorkflowState) -> dict[str, Any]:
        self._operations.fail(
            state.workflow_run_id,
            node=state.failure_node or "unknown",
            error_code=state.error_code or "WORKFLOW_ERROR",
            error_message=state.error_message or "工作流执行失败",
        )
        return {"final_status": WorkflowRunStatus.FAILED.value}

    @staticmethod
    def _route_failure(state: WorkflowState) -> str:
        return "fail" if state.error_code else "continue"

    @staticmethod
    def _route_after_classification(state: WorkflowState) -> str:
        if state.retry_node == "classify_email":
            return "retry"
        if state.error_code:
            return "fail"
        if state.classification and state.classification.is_job_related:
            if (
                RequiredCapability.EXTRACT
                in state.classification.required_capabilities
            ):
                return "extract"
            return "persist"
        return "persist"

    @staticmethod
    def _route_after_extraction(state: WorkflowState) -> str:
        if state.retry_node == "extract_information":
            return "retry"
        return "fail" if state.error_code else "continue"

    @staticmethod
    def _route_after_application(state: WorkflowState) -> str:
        if state.retry_node == "match_application":
            return "retry"
        return "fail" if state.error_code else "continue"

    @staticmethod
    def _route_after_persist(state: WorkflowState) -> str:
        if state.error_code:
            return "fail"
        if state.classification and state.classification.is_job_related:
            return "match"
        return "finalize"

    @staticmethod
    def _route_after_review(state: WorkflowState) -> str:
        if state.error_code:
            return "fail"
        if state.current_review_task_id:
            return "review"
        if state.final_status:
            return "finalize"
        if state.classification and not state.classification.should_reply:
            return "finalize"
        return "reply"

    @staticmethod
    def _route_after_reply(state: WorkflowState) -> str:
        if state.retry_node == "generate_reply":
            return "retry"
        if state.error_code:
            return "fail"
        if state.current_review_task_id:
            return "review"
        return "finalize"

    @staticmethod
    def _failure(node: str, exc: Exception) -> dict[str, Any]:
        message = str(exc).strip() or exc.__class__.__name__
        return {
            "failure_node": node,
            "error_code": exc.__class__.__name__.upper(),
            "error_message": message[:500],
        }

    @classmethod
    def _retry_or_failure(
        cls,
        state: WorkflowState,
        *,
        retry_key: str,
        node: str,
        exc: Exception,
    ) -> dict[str, Any]:
        attempts = state.retry_counts.get(retry_key, 0)
        if attempts < 1:
            return {
                "retry_counts": {
                    **state.retry_counts,
                    retry_key: attempts + 1,
                },
                "retry_node": node,
            }
        return {
            **cls._failure(node, exc),
            "retry_node": None,
        }
