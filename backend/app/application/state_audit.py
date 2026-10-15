from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    OfferResult,
    ReviewActionType,
    ReviewDecisionStatus,
    TaskType,
    WorkflowRunStatus,
)
from app.infrastructure.db.models.action_execution import ActionExecution
from app.infrastructure.db.models.interview_round import InterviewRound
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.models.workflow_run import WorkflowRun

FORMAL_GRAPH_VERSION_PATTERN = "job-mail-workflow.%"
DEFAULT_SAMPLE_LIMIT = 20


@dataclass(frozen=True)
class AuditFinding:
    """一类状态异常的只读统计结果。"""

    code: str
    description: str
    count: int
    sample_ids: list[int | str]


@dataclass(frozen=True)
class SpecialWorkflowVersion:
    """非正式图版本的历史记录及审核引用统计。"""

    graph_version: str
    workflow_run_count: int
    review_task_count: int


@dataclass(frozen=True)
class StateAuditReport:
    """状态重构前的数据一致性审计报告。"""

    generated_at: str
    read_only: bool
    findings: list[AuditFinding]
    special_workflow_versions: list[SpecialWorkflowVersion]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_state_audit_queries() -> dict[str, Select[tuple[Any]]]:
    """构造审计查询；所有语句均为 SELECT，不修改数据库。"""
    illegal_application_state = select(JobApplication.id).where(
        or_(
            and_(
                JobApplication.current_stage == ApplicationStage.REJECTED,
                JobApplication.status != ApplicationStatus.CLOSED,
            ),
            and_(
                JobApplication.current_stage == ApplicationStage.WITHDRAWN,
                JobApplication.status != ApplicationStatus.WITHDRAWN,
            ),
            and_(
                JobApplication.current_stage.in_(
                    [
                        ApplicationStage.APPLIED,
                        ApplicationStage.ASSESSMENT,
                        ApplicationStage.INTERVIEW,
                    ]
                ),
                JobApplication.status != ApplicationStatus.ACTIVE,
            ),
            and_(
                JobApplication.current_stage == ApplicationStage.INTERVIEW,
                ~select(InterviewRound.id)
                .where(InterviewRound.application_id == JobApplication.id)
                .exists(),
            ),
            and_(
                JobApplication.current_stage == ApplicationStage.OFFER,
                or_(
                    JobApplication.offer_result.is_(None),
                    and_(
                        JobApplication.offer_result == OfferResult.PENDING,
                        JobApplication.status != ApplicationStatus.ACTIVE,
                    ),
                    and_(
                        JobApplication.offer_result.in_(
                            [OfferResult.ACCEPTED, OfferResult.DECLINED]
                        ),
                        JobApplication.status != ApplicationStatus.CLOSED,
                    ),
                ),
            ),
            and_(
                JobApplication.current_stage != ApplicationStage.OFFER,
                JobApplication.offer_result.is_not(None),
            ),
        )
    )

    round_for_task = aliased(InterviewRound)
    orphan_interview_task = (
        select(Task.id)
        .outerjoin(
            round_for_task,
            round_for_task.id == Task.interview_round_id,
        )
        .where(
            Task.task_type == TaskType.INTERVIEW,
            or_(
                round_for_task.id.is_(None),
                round_for_task.application_id != Task.application_id,
            ),
        )
    )

    unauthorized_action_execution = (
        select(ActionExecution.id)
        .join(ReviewTask, ReviewTask.id == ActionExecution.review_task_id)
        .where(ReviewTask.decision_status != ReviewDecisionStatus.APPROVED)
    )

    duplicate_active_workflow = (
        select(WorkflowRun.email_id)
        .where(
            WorkflowRun.graph_version.like(FORMAL_GRAPH_VERSION_PATTERN),
            WorkflowRun.status.in_(
                [
                    WorkflowRunStatus.PENDING,
                    WorkflowRunStatus.RUNNING,
                    WorkflowRunStatus.WAITING_REVIEW,
                ]
            ),
        )
        .group_by(WorkflowRun.email_id)
        .having(func.count(WorkflowRun.id) > 1)
    )

    update_task_reviews = select(ReviewTask.id).where(
        ReviewTask.action_type == ReviewActionType.UPDATE_TASK
    )

    return {
        "illegal_application_state": illegal_application_state,
        "orphan_interview_task": orphan_interview_task,
        "unauthorized_action_execution": unauthorized_action_execution,
        "duplicate_active_workflow": duplicate_active_workflow,
        "update_task_review": update_task_reviews,
    }


_FINDING_DESCRIPTIONS = {
    "illegal_application_state": "申请阶段、生命周期状态或 Offer 结果组合违反目标不变量",
    "orphan_interview_task": "面试 Task 缺少权威轮次外键或关联到其他申请的轮次",
    "unauthorized_action_execution": "未批准审核存在动作执行记录",
    "duplicate_active_workflow": "同一邮件存在多个活动正式工作流",
    "update_task_review": "历史 UPDATE_TASK 审核任务",
}


class StateAuditService:
    """执行状态一致性只读审计，不提交事务或修复数据。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def run(self, *, sample_limit: int = DEFAULT_SAMPLE_LIMIT) -> StateAuditReport:
        if sample_limit < 0:
            raise ValueError("sample_limit 不能小于 0")

        queries = build_state_audit_queries()
        findings = [
            self._run_finding(code, statement, sample_limit)
            for code, statement in queries.items()
        ]
        special_versions = self._special_workflow_versions()
        return StateAuditReport(
            generated_at=datetime.now(UTC).isoformat(),
            read_only=True,
            findings=findings,
            special_workflow_versions=special_versions,
        )

    def _run_finding(
        self,
        code: str,
        statement: Select[tuple[Any]],
        sample_limit: int,
    ) -> AuditFinding:
        count = int(
            self._session.scalar(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
            or 0
        )
        sample_ids = (
            list(self._session.scalars(statement.limit(sample_limit)))
            if sample_limit
            else []
        )
        return AuditFinding(
            code=code,
            description=_FINDING_DESCRIPTIONS[code],
            count=count,
            sample_ids=sample_ids,
        )

    def _special_workflow_versions(self) -> list[SpecialWorkflowVersion]:
        rows = self._session.execute(
            select(
                WorkflowRun.graph_version,
                func.count(func.distinct(WorkflowRun.id)),
                func.count(func.distinct(ReviewTask.id)),
            )
            .outerjoin(ReviewTask, ReviewTask.workflow_run_id == WorkflowRun.id)
            .where(~WorkflowRun.graph_version.like(FORMAL_GRAPH_VERSION_PATTERN))
            .group_by(WorkflowRun.graph_version)
            .order_by(WorkflowRun.graph_version)
        )
        return [
            SpecialWorkflowVersion(
                graph_version=graph_version,
                workflow_run_count=int(workflow_count),
                review_task_count=int(review_count),
            )
            for graph_version, workflow_count, review_count in rows
        ]
