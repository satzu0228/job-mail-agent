"""创建邮件分析版本表。

迁移版本：20260728_0002
上一个版本：20260727_0001
创建日期：2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260728_0002"
down_revision: str | Sequence[str] | None = "20260727_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_analyses",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("email_id", mysql.BIGINT(unsigned=True), nullable=False),
        # workflow_runs 在后续迁移创建，届时为该字段补加外键。
        sa.Column("workflow_run_id", mysql.CHAR(length=36), nullable=True),
        sa.Column("version", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_job_related", sa.Boolean(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("should_reply", sa.Boolean(), nullable=False),
        sa.Column(
            "classification_confidence",
            mysql.DECIMAL(precision=5, scale=4),
            nullable=False,
        ),
        sa.Column(
            "extraction_confidence",
            mysql.DECIMAL(precision=5, scale=4),
            nullable=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("position_name", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=True),
        sa.Column("event_time", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("deadline_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("source_timezone", sa.String(length=64), nullable=True),
        sa.Column("extraction_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('VALID', 'PENDING_CONFIRMATION', 'INVALID')",
            name=op.f("ck_email_analyses_email_analysis_status"),
        ),
        sa.CheckConstraint(
            "category IN "
            "('INTERVIEW', 'ASSESSMENT', 'OFFER', 'REJECTION', 'MATERIAL_REQUEST', "
            "'APPLICATION_UPDATE', 'RECRUITER_COMMUNICATION', 'JOB_RELATED_OTHER', "
            "'NON_JOB')",
            name=op.f("ck_email_analyses_email_analysis_category"),
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name=op.f("ck_email_analyses_email_analysis_priority"),
        ),
        sa.CheckConstraint(
            "classification_confidence BETWEEN 0 AND 1",
            name=op.f("ck_email_analyses_classification_confidence_range"),
        ),
        sa.CheckConstraint(
            "extraction_confidence IS NULL OR extraction_confidence BETWEEN 0 AND 1",
            name=op.f("ck_email_analyses_extraction_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["emails.id"],
            name="fk_email_analyses_email_id_emails",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_analyses")),
        sa.UniqueConstraint(
            "email_id",
            "version",
            name="uq_email_analyses_email_version",
        ),
        sa.UniqueConstraint(
            "workflow_run_id",
            name="uq_email_analyses_workflow_run_id",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )


def downgrade() -> None:
    op.drop_table("email_analyses")
