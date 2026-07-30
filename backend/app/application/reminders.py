from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import ReminderStatus, TaskStatus
from app.infrastructure.db.models.reminder import Reminder
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.repositories import EntityNotFoundError


class ReminderService:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def generate_due(
        self,
        *,
        now: datetime | None = None,
        lead_minutes: int = 60,
    ) -> list[Reminder]:
        current = now or _utc_now()
        upper_bound = current + timedelta(minutes=lead_minutes)
        event_time = func.coalesce(Task.start_at, Task.deadline_at)
        tasks = list(
            self._session.scalars(
                select(Task)
                .outerjoin(Reminder, Reminder.task_id == Task.id)
                .where(
                    Task.user_id == self._user_id,
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.CONFIRMED]),
                    event_time > current,
                    event_time <= upper_bound,
                    Reminder.id.is_(None),
                )
                .order_by(event_time.asc(), Task.id.asc())
            )
        )
        created: list[Reminder] = []
        for task in tasks:
            target = task.start_at or task.deadline_at
            if target is None:
                continue
            reminder = Reminder(
                user_id=self._user_id,
                task_id=task.id,
                title=task.title,
                remind_at=current,
                event_at=target,
                status=ReminderStatus.DELIVERED,
                delivered_at=current,
            )
            self._session.add(reminder)
            created.append(reminder)
        try:
            self._session.commit()
        except IntegrityError:
            # 多进程同时轮询时由唯一约束收敛为一条提醒。
            self._session.rollback()
            return []
        return created

    def list(
        self,
        *,
        unread_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Reminder]:
        conditions = [Reminder.user_id == self._user_id]
        if unread_only:
            conditions.append(Reminder.status == ReminderStatus.DELIVERED)
        return list(
            self._session.scalars(
                select(Reminder)
                .where(*conditions)
                .order_by(Reminder.event_at.asc(), Reminder.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def set_read(
        self,
        reminder_id: int,
        *,
        read: bool,
        now: datetime | None = None,
    ) -> Reminder:
        with self._session.begin():
            reminder = self._session.scalar(
                select(Reminder)
                .where(
                    Reminder.id == reminder_id,
                    Reminder.user_id == self._user_id,
                )
                .with_for_update()
            )
            if reminder is None:
                raise EntityNotFoundError(f"Reminder {reminder_id} does not exist")
            reminder.status = (
                ReminderStatus.READ if read else ReminderStatus.DELIVERED
            )
            reminder.read_at = (now or _utc_now()) if read else None
            self._session.flush()
            return reminder


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
