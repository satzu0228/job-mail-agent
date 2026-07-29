from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.application.schemas import (
    ApplicationAgentOutput,
    ApplicationCandidate,
)
from app.agents.classification.schemas import ClassificationOutput
from app.agents.common.schemas import PreparedEmail
from app.agents.extraction.schemas import ExtractionOutput
from app.domain.enums import WorkflowRunStatus


class WorkflowState(BaseModel):
    """单封邮件工作流的可持久化强类型状态。"""

    model_config = ConfigDict(extra="forbid")

    workflow_run_id: str
    thread_id: str
    user_id: int
    email_id: int
    prepared_email: PreparedEmail | None = None
    classification: ClassificationOutput | None = None
    extraction: ExtractionOutput | None = None
    analysis_id: int | None = None
    application_candidates: list[ApplicationCandidate] = Field(default_factory=list)
    application_suggestion: ApplicationAgentOutput | None = None
    reply_draft_id: int | None = None
    current_review_task_id: str | None = None
    completed_review_task_ids: list[str] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    retry_node: str | None = None
    final_status: WorkflowRunStatus | None = None
    error_code: str | None = None
    error_message: str | None = None
    failure_node: str | None = None


class ReviewResumePayload(BaseModel):
    """从 HTTP 审核接口恢复图时传入的最小可信标识。"""

    model_config = ConfigDict(extra="forbid")

    review_task_id: str


class ReviewExecutionOutcome(BaseModel):
    """确定性审核 Executor 返回给图的结果。"""

    review_task_id: str
    action_type: str = "APPLICATION"
    rejected: bool = False
    follow_up_review_task_id: str | None = None
    result: dict[str, Any] | None = None
