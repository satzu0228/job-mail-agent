from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin


class AutomationRuleRun(TimestampMixin, Base):
    __tablename__ = "automation_rule_runs"
    __table_args__ = (
        UniqueConstraint(
            "rule_id",
            "rule_version",
            "email_id",
            "analysis_version",
            name="uq_automation_rule_runs_rule_email_analysis",
        ),
        Index("ix_automation_rule_runs_user_created", "user_id", "created_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    rule_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("email_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    analysis_version: Mapped[int | None] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=True,
    )
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    match_reason: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    review_task_id: Mapped[str | None] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("review_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
