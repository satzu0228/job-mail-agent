from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ApplicationStage
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, utc_now, varchar_enum


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    __table_args__ = MYSQL_TABLE_OPTIONS

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    application_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("job_applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_email_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="RESTRICT"),
        nullable=True,
    )
    workflow_run_id: Mapped[str | None] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_stage: Mapped[ApplicationStage | None] = mapped_column(
        varchar_enum(ApplicationStage, name="event_previous_stage", length=32),
        nullable=True,
    )
    proposed_stage: Mapped[ApplicationStage | None] = mapped_column(
        varchar_enum(ApplicationStage, name="event_proposed_stage", length=32),
        nullable=True,
    )
    confirmed_stage: Mapped[ApplicationStage | None] = mapped_column(
        varchar_enum(ApplicationStage, name="event_confirmed_stage", length=32),
        nullable=True,
    )
    raw_time_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    source_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
