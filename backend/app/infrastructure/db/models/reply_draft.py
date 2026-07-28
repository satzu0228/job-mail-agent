from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ReplyDraftStatus
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum


class ReplyDraft(TimestampMixin, Base):
    __tablename__ = "reply_drafts"
    __table_args__ = (
        UniqueConstraint(
            "email_id", "version", name="uq_reply_drafts_email_version"
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    email_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("job_applications.id", ondelete="RESTRICT"),
        nullable=True,
    )
    workflow_run_id: Mapped[str] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    to_recipients: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    cc_recipients: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    generated_body: Mapped[str] = mapped_column(mysql.LONGTEXT, nullable=False)
    reviewed_body: Mapped[str | None] = mapped_column(mysql.LONGTEXT, nullable=True)
    facts_used: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    uncertain_claims: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    status: Mapped[ReplyDraftStatus] = mapped_column(
        varchar_enum(ReplyDraftStatus, name="reply_draft_status", length=32),
        nullable=False,
        default=ReplyDraftStatus.PENDING,
        server_default=ReplyDraftStatus.PENDING.value,
    )
