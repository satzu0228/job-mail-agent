from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    EmailAnalysisStatus,
    EmailCategory,
    EmailPriority,
)
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, utc_now, varchar_enum

if TYPE_CHECKING:
    from app.infrastructure.db.models.email import Email


class EmailAnalysis(Base):
    __tablename__ = "email_analyses"
    __table_args__ = (
        UniqueConstraint(
            "email_id",
            "version",
            name="uq_email_analyses_email_version",
        ),
        UniqueConstraint(
            "workflow_run_id",
            name="uq_email_analyses_workflow_run_id",
        ),
        CheckConstraint(
            "classification_confidence BETWEEN 0 AND 1",
            name="classification_confidence_range",
        ),
        CheckConstraint(
            "extraction_confidence IS NULL OR extraction_confidence BETWEEN 0 AND 1",
            name="extraction_confidence_range",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    email_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_run_id: Mapped[str | None] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    status: Mapped[EmailAnalysisStatus] = mapped_column(
        varchar_enum(
            EmailAnalysisStatus,
            name="email_analysis_status",
            length=32,
        ),
        nullable=False,
    )
    is_job_related: Mapped[bool] = mapped_column(Boolean, nullable=False)
    category: Mapped[EmailCategory] = mapped_column(
        varchar_enum(EmailCategory, name="email_analysis_category", length=32),
        nullable=False,
    )
    priority: Mapped[EmailPriority] = mapped_column(
        varchar_enum(EmailPriority, name="email_analysis_priority", length=16),
        nullable=False,
    )
    should_reply: Mapped[bool] = mapped_column(Boolean, nullable=False)
    classification_confidence: Mapped[Decimal] = mapped_column(
        mysql.DECIMAL(precision=5, scale=4),
        nullable=False,
    )
    extraction_confidence: Mapped[Decimal | None] = mapped_column(
        mysql.DECIMAL(precision=5, scale=4),
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_time: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    source_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    missing_fields: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    email: Mapped[Email] = relationship(back_populates="analyses")
