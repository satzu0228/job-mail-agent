from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ExecutionStatus, ExecutorType
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, varchar_enum


class ActionExecution(Base):
    __tablename__ = "action_executions"
    __table_args__ = (
        UniqueConstraint(
            "review_task_id",
            "attempt_no",
            name="uq_action_executions_review_attempt",
        ),
        UniqueConstraint(
            "idempotency_key", name="uq_action_executions_idempotency_key"
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    review_task_id: Mapped[str] = mapped_column(
        mysql.CHAR(36),
        ForeignKey("review_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(mysql.SMALLINT(unsigned=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    executor_type: Mapped[ExecutorType] = mapped_column(
        varchar_enum(ExecutorType, name="executor_type", length=32), nullable=False
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        varchar_enum(ExecutionStatus, name="execution_status", length=32),
        nullable=False,
    )
    external_reference: Mapped[str | None] = mapped_column(String(998), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
