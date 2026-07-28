from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import TaskStatus, TaskType
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint(
            "source_review_task_id", name="uq_tasks_source_review_task_id"
        ),
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
    application_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("job_applications.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_email_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_review_task_id: Mapped[str | None] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("review_tasks.id", ondelete="RESTRICT"),
        nullable=True,
    )
    task_type: Mapped[TaskType] = mapped_column(
        varchar_enum(TaskType, name="task_type", length=32), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_time_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6), nullable=True
    )
    source_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        varchar_enum(TaskStatus, name="task_status", length=32),
        nullable=False,
        default=TaskStatus.PENDING,
        server_default=TaskStatus.PENDING.value,
    )
    version: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    __mapper_args__ = {"version_id_col": version}
