from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.enums import ReminderStatus, TaskStatus, TaskType
from app.infrastructure.db.models.interview_round import InterviewRound
from app.infrastructure.db.models.reminder import Reminder
from app.infrastructure.db.models.task import Task


def settle_interview_tasks(
    session: Session,
    *,
    application_id: int,
    status: TaskStatus,
    current_round_only: bool,
    round_number: int | None = None,
) -> int:
    """在申请状态确认后，同事务收敛对应的未结束面试日程。"""
    conditions = [
        Task.application_id == application_id,
        Task.task_type == TaskType.INTERVIEW,
        Task.status.in_([TaskStatus.PENDING, TaskStatus.CONFIRMED]),
    ]
    if round_number is not None:
        round_id = session.scalar(
            select(InterviewRound.id).where(
                InterviewRound.application_id == application_id,
                InterviewRound.round_number == round_number,
            )
        )
        if round_id is None:
            return 0
        conditions.append(Task.interview_round_id == round_id)
    elif current_round_only:
        latest_round_id = session.scalar(
            select(InterviewRound.id)
            .where(InterviewRound.application_id == application_id)
            .order_by(InterviewRound.round_number.desc())
            .limit(1)
        )
        if latest_round_id is None:
            return 0
        conditions.append(Task.interview_round_id == latest_round_id)

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
