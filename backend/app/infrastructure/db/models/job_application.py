from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    InterviewResult,
)
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum

if TYPE_CHECKING:
    from app.infrastructure.db.models.email import Email
    from app.infrastructure.db.models.user import User


class JobApplication(TimestampMixin, Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        Index(
            "ix_job_applications_user_stage_updated",
            "user_id",
            "current_stage",
            "updated_at",
        ),
        Index(
            "ix_job_applications_user_company_position",
            "user_id",
            "company_name",
            "position_name",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_stage: Mapped[ApplicationStage] = mapped_column(
        varchar_enum(ApplicationStage, name="application_stage", length=32),
        nullable=False,
        default=ApplicationStage.APPLIED,
        server_default=ApplicationStage.APPLIED.value,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        varchar_enum(ApplicationStatus, name="application_status", length=32),
        nullable=False,
        default=ApplicationStatus.ACTIVE,
        server_default=ApplicationStatus.ACTIVE.value,
    )
    interview_result: Mapped[InterviewResult | None] = mapped_column(
        varchar_enum(InterviewResult, name="interview_result", length=16),
        nullable=True,
    )
    source: Mapped[ApplicationSource] = mapped_column(
        varchar_enum(ApplicationSource, name="application_source", length=32),
        nullable=False,
        default=ApplicationSource.MANUAL,
        server_default=ApplicationSource.MANUAL.value,
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    user: Mapped[User] = relationship(back_populates="job_applications")
    emails: Mapped[list[Email]] = relationship(back_populates="application")

    __mapper_args__ = {"version_id_col": version}
