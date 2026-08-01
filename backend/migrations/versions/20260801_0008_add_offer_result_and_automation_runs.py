"""Add offer result and automation rule run audit.

Revision ID: 20260801_0008
Revises: 20260801_0007
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260801_0008"
down_revision: str | Sequence[str] | None = "20260801_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_applications",
        sa.Column("offer_result", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_job_applications_offer_result",
        "job_applications",
        "offer_result IN ('PENDING', 'ACCEPTED', 'DECLINED')",
    )
    op.execute(
        "UPDATE job_applications SET offer_result = 'PENDING' "
        "WHERE current_stage = 'OFFER'"
    )
    op.create_table(
        "automation_rule_runs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("rule_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("rule_version", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("email_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("analysis_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("analysis_version", mysql.INTEGER(unsigned=True), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("match_reason", sa.JSON(), nullable=False),
        sa.Column("review_task_id", sa.CHAR(length=36), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
        sa.ForeignKeyConstraint(["analysis_id"], ["email_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_task_id"], ["review_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "rule_id",
            "rule_version",
            "email_id",
            "analysis_version",
            name="uq_automation_rule_runs_rule_email_analysis",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index(
        "ix_automation_rule_runs_user_created",
        "automation_rule_runs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_rule_runs_user_created", table_name="automation_rule_runs")
    op.drop_table("automation_rule_runs")
    op.drop_constraint(
        "ck_job_applications_offer_result",
        "job_applications",
        type_="check",
    )
    op.drop_column("job_applications", "offer_result")
