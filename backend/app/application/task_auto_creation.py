from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    EmailAnalysisStatus,
    EmailCategory,
    ReviewActionType,
    ReviewTaskStatus,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.task import Task


class TaskAutoCreationService:
    """从已分析邮件中自动创建日程任务。

    扫描 extraction_confidence 足够高的 EmailAnalysis 记录，
    根据提取出的 event_time / deadline_at 创建 Task，
    使后续 ReminderService.generate_due() 能为其生成提醒。

    设计上放在自动化轮询周期中而非 workflow graph 内，
    以避免 workflow 在 human_review 处长时间暂停导致
    Task 创建被不必要地推迟。
    """

    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def create_tasks_from_analyses(
        self,
        *,
        confidence_threshold: float = 0.7,
        high_confidence_threshold: float = 0.8,
    ) -> list[Task]:
        """扫描可自动创建 Task 的分析记录并创建 Task。"""
        analyses = list(self._find_candidate_analyses(confidence_threshold))
        if not analyses:
            return []

        # 收集已处理过的 source_email_id，避免同轮创建同邮件的新查询二次处理。
        created: list[Task] = []
        seen_email_ids: set[int] = set()

        for analysis in analyses:
            if analysis.email_id in seen_email_ids:
                continue

            task_type = _derive_task_type(analysis)
            if task_type is None:
                seen_email_ids.add(analysis.email_id)
                continue

            # 去重：同一 source_email 的同类型 Task 只创建一次。
            if self._task_exists(analysis.email_id, task_type):
                seen_email_ids.add(analysis.email_id)
                continue

            # 如果已有待审核任务，交给审核流程处理。
            if self._has_pending_review(analysis.email_id):
                seen_email_ids.add(analysis.email_id)
                continue

            # 面试时间调整/改期邮件不自动创建日程——更新已有日程的逻辑在审核流中处理
            if _is_reschedule_event(analysis):
                seen_email_ids.add(analysis.email_id)
                continue

            title = _build_title(analysis, task_type)
            status = (
                TaskStatus.CONFIRMED
                if (analysis.extraction_confidence or 0) >= high_confidence_threshold
                else TaskStatus.PENDING
            )

            task = Task(
                user_id=self._user_id,
                application_id=self._resolve_application_id(analysis.email_id),
                source_email_id=analysis.email_id,
                source_review_task_id=None,
                task_type=task_type,
                interview_round=None,
                title=title,
                description=analysis.summary,
                raw_time_text=self._raw_time_text(analysis),
                start_at=self._event_start(analysis, task_type),
                deadline_at=analysis.deadline_at,
                source_timezone=analysis.source_timezone,
                location=None,
                meeting_url=self._meeting_url(analysis),
                status=status,
            )
            self._session.add(task)
            created.append(task)
            seen_email_ids.add(analysis.email_id)

        if created:
            self._session.commit()
        return created

    # ------------------------------------------------------------------
    # 内部查询
    # ------------------------------------------------------------------

    def _find_candidate_analyses(
        self,
        confidence_threshold: float,
    ) -> list[EmailAnalysis]:
        """查找用户拥有的、置信度足够且有可调度时间的分析记录。"""
        return list(
            self._session.scalars(
                select(EmailAnalysis)
                .join(Email, Email.id == EmailAnalysis.email_id)
                .join(EmailAccount, EmailAccount.id == Email.account_id)
                .where(
                    EmailAccount.user_id == self._user_id,
                    EmailAnalysis.is_current.is_(True),
                    EmailAnalysis.is_job_related.is_(True),
                    EmailAnalysis.status.in_(
                        [EmailAnalysisStatus.VALID, EmailAnalysisStatus.PENDING_CONFIRMATION]
                    ),
                    EmailAnalysis.extraction_confidence >= confidence_threshold,
                    or_(
                        EmailAnalysis.event_time.is_not(None),
                        EmailAnalysis.deadline_at.is_not(None),
                    ),
                )
                .order_by(EmailAnalysis.extraction_confidence.desc(), EmailAnalysis.id.asc())
            )
        )

    def _task_exists(self, source_email_id: int, task_type: TaskType) -> bool:
        return (
            self._session.scalar(
                select(Task.id).where(
                    Task.source_email_id == source_email_id,
                    Task.task_type == task_type,
                ).limit(1)
            )
            is not None
        )

    def _has_pending_review(self, source_email_id: int) -> bool:
        """同邮件存在未完成的审核任务时跳过自动创建，避免：
        - 邮件尚未关联申请（application_id 为空）
        - 与审核流程中的 _create_task_follow_up 重复创建"""
        return (
            self._session.scalar(
                select(ReviewTask.id).where(
                    ReviewTask.source_email_id == source_email_id,
                    ReviewTask.status == ReviewTaskStatus.PENDING,
                ).limit(1)
            )
            is not None
        )

    def _resolve_application_id(self, email_id: int) -> int | None:
        email = self._session.get(Email, email_id)
        return email.application_id if email is not None else None

    @staticmethod
    def _raw_time_text(analysis: EmailAnalysis) -> str | None:
        extraction = analysis.extraction_json or {}
        event_time = extraction.get("event_time") or {}
        deadline = extraction.get("deadline") or {}
        raw = event_time.get("raw_text") or deadline.get("raw_text")
        return raw if isinstance(raw, str) and raw.strip() else None

    @staticmethod
    def _event_start(analysis: EmailAnalysis, task_type: TaskType) -> datetime | None:
        """面试/笔试等有明确开始时间的任务用 event_time；截止类用 deadline_at 兜底。"""
        if task_type in (TaskType.INTERVIEW, TaskType.ASSESSMENT):
            return analysis.event_time or analysis.deadline_at
        return analysis.event_time

    @staticmethod
    def _meeting_url(analysis: EmailAnalysis) -> str | None:
        extraction = analysis.extraction_json or {}
        meeting_url = extraction.get("meeting_url") or {}
        value = meeting_url.get("value") if isinstance(meeting_url, dict) else None
        return value if isinstance(value, str) and value.strip() else None


# ------------------------------------------------------------------
# 分类映射
# ------------------------------------------------------------------

_CATEGORY_TASK_TYPE: dict[EmailCategory, TaskType | None] = {
    EmailCategory.INTERVIEW: TaskType.INTERVIEW,
    EmailCategory.ASSESSMENT: TaskType.ASSESSMENT,
    EmailCategory.OFFER: TaskType.DEADLINE,
    EmailCategory.MATERIAL_REQUEST: TaskType.MATERIAL,
    EmailCategory.REJECTION: None,
    EmailCategory.APPLICATION_UPDATE: None,
    EmailCategory.RECRUITER_COMMUNICATION: None,
    EmailCategory.JOB_RELATED_OTHER: None,
    EmailCategory.NON_JOB: None,
}


def _derive_task_type(analysis: EmailAnalysis) -> TaskType | None:
    """根据邮件类别和字段存在性推导 TaskType。"""
    direct = _CATEGORY_TASK_TYPE.get(analysis.category)
    if direct is not None:
        return direct

    # 兜底：有 deadline 用 DEADLINE，仅有 event_time 用 OTHER。
    if analysis.deadline_at is not None:
        return TaskType.DEADLINE
    if analysis.event_time is not None:
        return TaskType.OTHER
    return None


def _build_title(analysis: EmailAnalysis, task_type: TaskType) -> str:
    company = (analysis.company_name or "").strip()
    position = (analysis.position_name or "").strip()
    event_type = (analysis.event_type or "").strip()

    if task_type is TaskType.INTERVIEW:
        if company and position:
            return f"{company} 面试 - {position}"
        if company:
            return f"{company} 面试"
        return event_type or "面试安排"

    if task_type is TaskType.ASSESSMENT:
        if company:
            return f"{company} 笔试测评"
        return event_type or "笔试测评"

    if task_type is TaskType.DEADLINE:
        if company and analysis.category is EmailCategory.OFFER:
            return f"{company} Offer 确认截止"
        if company and analysis.category is EmailCategory.MATERIAL_REQUEST:
            return f"材料补充截止 - {company}"
        if company:
            return f"{company} 截止日期"
        return event_type or "截止日期"

    if task_type is TaskType.MATERIAL:
        if company:
            return f"材料补充截止 - {company}"
        return "材料补充截止"

    # OTHER
    if event_type and company:
        return f"{event_type} - {company}"
    if event_type:
        return event_type
    if company:
        return f"{company} 日程提醒"
    return "日程提醒"


# ------------------------------------------------------------------
# 改期检测（与 application_management._is_reschedule 保持一致）
# ------------------------------------------------------------------

import re as _re  # noqa: E402

_RESCHEDULE_RE = _re.compile(
    r"面试时间调整|面试改期|面试时间变更|面试延期|面试提前|"
    r"reschedule|时间调整|时间变更|面试时间更新",
    _re.IGNORECASE,
)


def _is_reschedule_event(analysis: EmailAnalysis) -> bool:
    """判断分析记录是否描述面试时间调整/改期而非新增面试。"""
    text = " ".join(
        value
        for value in (analysis.event_type, analysis.summary)
        if value
    )
    return bool(_RESCHEDULE_RE.search(text))
