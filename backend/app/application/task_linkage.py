from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.enums import ReminderStatus, TaskStatus, TaskType
from app.infrastructure.db.models.reminder import Reminder
from app.infrastructure.db.models.task import Task


def settle_interview_tasks(
    session: Session,
    *,
    application_id: int,
    status: TaskStatus,
    current_round_only: bool,
) -> int:
    """在申请状态确认后，同事务收敛对应的未结束面试日程。"""
    conditions = [
        Task.application_id == application_id,
        Task.task_type == TaskType.INTERVIEW,
        Task.status.in_([TaskStatus.PENDING, TaskStatus.CONFIRMED]),
    ]
    if current_round_only:
        latest_round = session.scalar(
            select(func.max(Task.interview_round)).where(*conditions)
        )
        if latest_round is None:
            return 0
        conditions.append(Task.interview_round == latest_round)

    tasks = list(session.scalars(select(Task).where(*conditions).with_for_update()))
    for task in tasks:
        task.status = status
    if tasks:
        session.execute(
            update(Reminder)
            .where(
                Reminder.task_id.in_([task.id for task in tasks]),
                Reminder.status == ReminderStatus.DELIVERED,
            )
            .values(status=ReminderStatus.CANCELLED)
        )
    return len(tasks)
