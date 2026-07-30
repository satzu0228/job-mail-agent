from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ReminderStatus
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum


class Reminder(TimestampMixin, Base):
    __tablename__ = "reminders"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_reminders_task_id"),
        Index("ix_reminders_user_status_remind", "user_id", "status", "remind_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    task_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    event_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    status: Mapped[ReminderStatus] = mapped_column(
        varchar_enum(ReminderStatus, name="reminder_status", length=16),
        nullable=False,
        default=ReminderStatus.DELIVERED,
        server_default=ReminderStatus.DELIVERED.value,
    )
    delivered_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
