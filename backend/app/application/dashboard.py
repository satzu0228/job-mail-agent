from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    ReviewTaskStatus,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.review_task import ReviewTask
from app.infrastructure.db.models.task import Task


class DashboardService:
    """聚合仪表盘所需的所有数据。

    在单个 service 中完成多表查询，避免 API 层多次往返。
    """

    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def get_dashboard(self, *, now: datetime | None = None) -> dict:
        current = now or _utc_now()
        today_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_end = today_start + timedelta(days=2)
        deadline_window = current + timedelta(hours=24)

        return {
            "upcoming_interviews": self._upcoming_interviews(today_start, tomorrow_end),
            "urgent_deadlines": self._urgent_deadlines(current, deadline_window),
            "pending_reviews": self._pending_reviews(),
            "stats": self._funnel_stats(),
        }

    # ------------------------------------------------------------------
    # 各分组查询
    # ------------------------------------------------------------------

    def _upcoming_interviews(
        self,
        today_start: datetime,
        tomorrow_end: datetime,
    ) -> list[Task]:
        return list(
            self._session.scalars(
                select(Task)
                .where(
                    Task.user_id == self._user_id,
                    Task.task_type == TaskType.INTERVIEW,
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.CONFIRMED]),
                    Task.start_at >= today_start,
                    Task.start_at < tomorrow_end,
                )
                .order_by(Task.start_at.asc(), Task.id.asc())
                .limit(20)
            )
        )

    def _urgent_deadlines(
        self,
        now: datetime,
        deadline_window: datetime,
    ) -> list[Task]:
        return list(
            self._session.scalars(
                select(Task)
                .where(
                    Task.user_id == self._user_id,
                    Task.task_type.in_(
                        [TaskType.DEADLINE, TaskType.MATERIAL, TaskType.ASSESSMENT]
                    ),
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.CONFIRMED]),
                    Task.deadline_at > now,
                    Task.deadline_at <= deadline_window,
                )
                .order_by(Task.deadline_at.asc(), Task.id.asc())
                .limit(20)
            )
        )

    def _pending_reviews(self) -> list[ReviewTask]:
        return list(
            self._session.scalars(
                select(ReviewTask)
                .where(
                    ReviewTask.user_id == self._user_id,
                    ReviewTask.status == ReviewTaskStatus.PENDING,
                )
                .order_by(ReviewTask.created_at.desc())
                .limit(10)
            )
        )

    # ------------------------------------------------------------------
    # 统计（漏斗）
    # ------------------------------------------------------------------

    def _funnel_stats(self) -> dict:
        rows = list(
            self._session.execute(
                select(
                    JobApplication.current_stage,
                    func.count(JobApplication.id),
                ).where(
                    JobApplication.user_id == self._user_id,
                    JobApplication.status != ApplicationStatus.WITHDRAWN,
                ).group_by(JobApplication.current_stage)
            )
        )
        by_stage: dict[str, int] = {row[0].value: row[1] for row in rows}

        total = sum(by_stage.values())
        in_progress = (
            by_stage.get(ApplicationStage.APPLIED.value, 0)
            + by_stage.get(ApplicationStage.ASSESSMENT.value, 0)
            + by_stage.get(ApplicationStage.INTERVIEW.value, 0)
        )
        offered = by_stage.get(ApplicationStage.OFFER.value, 0)
        rejected = (
            by_stage.get(ApplicationStage.REJECTED.value, 0)
            + by_stage.get(ApplicationStage.WITHDRAWN.value, 0)
        )

        return {
            "applied": total,
            "in_progress": in_progress,
            "offered": offered,
            "rejected": rejected,
        }


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
