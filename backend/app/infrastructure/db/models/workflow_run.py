from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import WorkflowRunStatus
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum


class WorkflowRun(TimestampMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_workflow_runs_thread_id"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[str] = mapped_column(mysql.CHAR(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(mysql.CHAR(36), nullable=False)
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("emails.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[WorkflowRunStatus] = mapped_column(
        varchar_enum(WorkflowRunStatus, name="workflow_run_status", length=32),
        nullable=False,
        default=WorkflowRunStatus.PENDING,
        server_default=WorkflowRunStatus.PENDING.value,
    )
    current_node: Mapped[str | None] = mapped_column(String(64), nullable=True)
    graph_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_versions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    agent_trace: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    pending_review_task_id: Mapped[str | None] = mapped_column(
        mysql.CHAR(36),
        ForeignKey(
            "review_tasks.id",
            name="fk_workflow_runs_pending_review_task_id_review_tasks",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
