from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import InterviewResult, InterviewRoundSource, InterviewRoundStatus
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum

if TYPE_CHECKING:
    from app.infrastructure.db.models.email import Email
    from app.infrastructure.db.models.job_application import JobApplication
    from app.infrastructure.db.models.task import Task


class InterviewRound(TimestampMixin, Base):
    """每次面试的独立轮次记录，支持一面/二面/三面各自的结果追踪。"""

    __tablename__ = "interview_rounds"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "round_number",
            name="uq_interview_rounds_application_round",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    application_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("job_applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(
        mysql.SMALLINT(unsigned=True),
        nullable=False,
    )
    status: Mapped[InterviewRoundStatus] = mapped_column(
        varchar_enum(InterviewRoundStatus, name="interview_round_status", length=16),
        nullable=False,
        default=InterviewRoundStatus.PLANNED,
        server_default=InterviewRoundStatus.PLANNED.value,
    )
    result: Mapped[InterviewResult] = mapped_column(
        varchar_enum(InterviewResult, name="interview_round_result", length=16),
        nullable=False,
        default=InterviewResult.PENDING,
        server_default=InterviewResult.PENDING.value,
    )
    interview_date: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source: Mapped[InterviewRoundSource] = mapped_column(
        varchar_enum(InterviewRoundSource, name="interview_round_source", length=16),
        nullable=False,
        default=InterviewRoundSource.MANUAL,
        server_default=InterviewRoundSource.MANUAL.value,
    )
    source_email_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_task_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    application: Mapped[JobApplication] = relationship(back_populates="interview_rounds")
    source_email: Mapped[Email | None] = relationship()
    source_task: Mapped[Task | None] = relationship(foreign_keys=[source_task_id])

    __mapper_args__ = {"version_id_col": version}
