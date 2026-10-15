from __future__ import annotations

from datetime import datetime

from app.domain.enums import DecisionSource, ReviewDecisionStatus
from app.infrastructure.db.models.review_task import ReviewTask


def review_decision_status(task: ReviewTask) -> ReviewDecisionStatus:
    """读取审核决定唯一真相。"""
    return ReviewDecisionStatus(task.decision_status)


def set_review_decision(
    task: ReviewTask,
    status: ReviewDecisionStatus,
    *,
    source: DecisionSource | None = None,
    reason: str | None = None,
    reviewed_at: datetime | None = None,
) -> None:
    """写入审核决定真相。"""
    task.decision_status = status
    if source is not None:
        task.decision_source = source
    if reason is not None:
        task.decision_reason = reason
    if reviewed_at is not None:
        task.reviewed_at = reviewed_at
