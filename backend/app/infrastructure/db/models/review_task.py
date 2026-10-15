from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    DecisionSource,
    ReviewActionType,
    ReviewDecisionStatus,
    RiskLevel,
)
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum


class ReviewTask(TimestampMixin, Base):
    __tablename__ = "review_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_review_tasks_idempotency_key"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[str] = mapped_column(mysql.CHAR(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workflow_run_id: Mapped[str | None] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    parent_review_task_id: Mapped[str | None] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("review_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_email_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="RESTRICT"),
        nullable=True,
    )
    application_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("job_applications.id", ondelete="RESTRICT"),
        nullable=True,
    )
    draft_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("reply_drafts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    action_type: Mapped[ReviewActionType] = mapped_column(
        varchar_enum(ReviewActionType, name="review_action_type", length=32),
        nullable=False,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        varchar_enum(RiskLevel, name="review_risk_level", length=16), nullable=False
    )
    proposed_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    reviewed_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    decision_status: Mapped[ReviewDecisionStatus] = mapped_column(
        varchar_enum(
            ReviewDecisionStatus,
            name="review_decision_status",
            length=16,
        ),
        nullable=False,
        default=ReviewDecisionStatus.PENDING,
        server_default=ReviewDecisionStatus.PENDING.value,
    )
    decision_source: Mapped[DecisionSource | None] = mapped_column(
        varchar_enum(DecisionSource, name="review_decision_source", length=16),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_version: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True), nullable=False
    )
    version: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    __mapper_args__ = {"version_id_col": version}
