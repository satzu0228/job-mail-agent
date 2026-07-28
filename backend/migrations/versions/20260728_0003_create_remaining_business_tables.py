"""创建工作流、时间线、任务、草稿、审核、执行和自动化规则表。

迁移版本：20260728_0003
上一个版本：20260728_0002
创建日期：2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260728_0003"
down_revision: str | Sequence[str] | None = "20260728_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def enum_type(name: str, length: int, *values: str) -> sa.Enum:
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
    )


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", mysql.CHAR(36), nullable=False),
        sa.Column("thread_id", mysql.CHAR(36), nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("email_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "workflow_run_status",
                32,
                "PENDING",
                "RUNNING",
                "WAITING_REVIEW",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
            ),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("current_node", sa.String(64), nullable=True),
        sa.Column("graph_version", sa.String(32), nullable=False),
        sa.Column("model_provider", sa.String(32), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt_versions", sa.JSON(), nullable=False),
        sa.Column("agent_trace", sa.JSON(), nullable=False),
        sa.Column("pending_review_task_id", mysql.CHAR(36), nullable=True),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=False),
        *timestamps(),
        sa.Column("finished_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["email_id"], ["emails.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", name="uq_workflow_runs_thread_id"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "application_events",
        sa.Column(
            "id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False
        ),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("source_email_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("workflow_run_id", mysql.CHAR(36), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "previous_stage",
            enum_type(
                "event_previous_stage",
                32,
                "APPLIED",
                "ASSESSMENT",
                "INTERVIEW",
                "OFFER",
                "REJECTED",
                "WITHDRAWN",
            ),
            nullable=True,
        ),
        sa.Column(
            "proposed_stage",
            enum_type(
                "event_proposed_stage",
                32,
                "APPLIED",
                "ASSESSMENT",
                "INTERVIEW",
                "OFFER",
                "REJECTED",
                "WITHDRAWN",
            ),
            nullable=True,
        ),
        sa.Column(
            "confirmed_stage",
            enum_type(
                "event_confirmed_stage",
                32,
                "APPLIED",
                "ASSESSMENT",
                "INTERVIEW",
                "OFFER",
                "REJECTED",
                "WITHDRAWN",
            ),
            nullable=True,
        ),
        sa.Column("raw_time_text", sa.String(500), nullable=True),
        sa.Column("event_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("source_timezone", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["job_applications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_email_id"], ["emails.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"], ["workflow_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "tasks",
        sa.Column(
            "id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False
        ),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("source_email_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("source_review_task_id", mysql.CHAR(36), nullable=True),
        sa.Column(
            "task_type",
            enum_type(
                "task_type",
                32,
                "INTERVIEW",
                "ASSESSMENT",
                "MATERIAL",
                "DEADLINE",
                "OTHER",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw_time_text", sa.String(500), nullable=True),
        sa.Column("start_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("deadline_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("source_timezone", sa.String(64), nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("meeting_url", sa.String(2048), nullable=True),
        sa.Column(
            "status",
            enum_type(
                "task_status",
                32,
                "PENDING",
                "CONFIRMED",
                "COMPLETED",
                "CANCELLED",
            ),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "version",
            mysql.INTEGER(unsigned=True),
            server_default=sa.text("1"),
            nullable=False,
        ),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["job_applications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_email_id"], ["emails.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_review_task_id", name="uq_tasks_source_review_task_id"
        ),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "reply_drafts",
        sa.Column(
            "id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False
        ),
        sa.Column("email_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("workflow_run_id", mysql.CHAR(36), nullable=False),
        sa.Column("version", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("to_recipients", sa.JSON(), nullable=False),
        sa.Column("cc_recipients", sa.JSON(), nullable=False),
        sa.Column("subject", sa.String(998), nullable=False),
        sa.Column("generated_body", mysql.LONGTEXT(), nullable=False),
        sa.Column("reviewed_body", mysql.LONGTEXT(), nullable=True),
        sa.Column("facts_used", sa.JSON(), nullable=False),
        sa.Column("uncertain_claims", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "reply_draft_status",
                32,
                "PENDING",
                "APPROVED",
                "MODIFIED_AND_APPROVED",
                "REJECTED",
                "EXPIRED",
            ),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["email_id"], ["emails.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["job_applications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"], ["workflow_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "email_id", "version", name="uq_reply_drafts_email_version"
        ),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "review_tasks",
        sa.Column("id", mysql.CHAR(36), nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("workflow_run_id", mysql.CHAR(36), nullable=False),
        sa.Column("source_email_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("draft_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "action_type",
            enum_type(
                "review_action_type",
                32,
                "CREATE_APPLICATION",
                "LINK_APPLICATION",
                "UPDATE_APPLICATION_STAGE",
                "CREATE_TASK",
                "UPDATE_TASK",
                "SEND_REPLY",
                "ARCHIVE_EMAIL",
                "RESTORE_EMAIL",
            ),
            nullable=False,
        ),
        sa.Column(
            "risk_level",
            enum_type("review_risk_level", 16, "LOW", "MEDIUM", "HIGH"),
            nullable=False,
        ),
        sa.Column("proposed_payload", sa.JSON(), nullable=False),
        sa.Column("reviewed_payload", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            enum_type(
                "review_task_status",
                32,
                "PENDING",
                "APPROVED",
                "REJECTED",
                "CANCELLED",
                "EXPIRED",
                "EXECUTING",
                "SUCCEEDED",
                "FAILED",
                "UNKNOWN",
            ),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "decision_source",
            enum_type("review_decision_source", 16, "USER", "RULE"),
            nullable=True,
        ),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("resource_version", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column(
            "version",
            mysql.INTEGER(unsigned=True),
            server_default=sa.text("1"),
            nullable=False,
        ),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"], ["workflow_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_email_id"], ["emails.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["job_applications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"], ["reply_drafts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_review_tasks_idempotency_key"
        ),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "action_executions",
        sa.Column(
            "id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False
        ),
        sa.Column("review_task_id", mysql.CHAR(36), nullable=False),
        sa.Column("attempt_no", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "executor_type",
            enum_type("executor_type", 32, "APPLICATION", "TASK", "SMTP", "IMAP"),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum_type(
                "execution_status",
                32,
                "PENDING",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "UNKNOWN",
            ),
            nullable=False,
        ),
        sa.Column("external_reference", sa.String(998), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("finished_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_task_id"], ["review_tasks.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_task_id",
            "attempt_no",
            name="uq_action_executions_review_attempt",
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_action_executions_idempotency_key"
        ),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "automation_rules",
        sa.Column(
            "id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False
        ),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("account_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "rule_type",
            enum_type(
                "automation_rule_type", 32, "LOW_PRIORITY_ARCHIVE"
            ),
            server_default=sa.text("'LOW_PRIORITY_ARCHIVE'"),
            nullable=False,
        ),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("action_config", sa.JSON(), nullable=False),
        sa.Column(
            "requires_confirmation",
            sa.Boolean(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "version",
            mysql.INTEGER(unsigned=True),
            server_default=sa.text("1"),
            nullable=False,
        ),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["email_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        **TABLE_OPTIONS,
    )

    op.create_foreign_key(
        "fk_email_analyses_workflow_run_id_workflow_runs",
        "email_analyses",
        "workflow_runs",
        ["workflow_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_tasks_source_review_task_id_review_tasks",
        "tasks",
        "review_tasks",
        ["source_review_task_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_workflow_runs_pending_review_task_id_review_tasks",
        "workflow_runs",
        "review_tasks",
        ["pending_review_task_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_workflow_runs_pending_review_task_id_review_tasks",
        "workflow_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tasks_source_review_task_id_review_tasks",
        "tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_email_analyses_workflow_run_id_workflow_runs",
        "email_analyses",
        type_="foreignkey",
    )
    op.drop_table("automation_rules")
    op.drop_table("action_executions")
    op.drop_table("review_tasks")
    op.drop_table("reply_drafts")
    op.drop_table("tasks")
    op.drop_table("application_events")
    op.drop_table("workflow_runs")
