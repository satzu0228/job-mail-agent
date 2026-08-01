"""Add interview_rounds table for per-round interview tracking.

Revision ID: 20260802_0009
Revises: 20260801_0008
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260802_0009"
down_revision: str | Sequence[str] | None = "20260801_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_rounds",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column(
            "application_id",
            mysql.BIGINT(unsigned=True),
            sa.ForeignKey("job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round_number", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="SCHEDULED",
        ),
        sa.Column(
            "result",
            sa.String(length=16),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("interview_date", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("meeting_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default="MANUAL",
        ),
        sa.Column(
            "source_email_id",
            mysql.BIGINT(unsigned=True),
            sa.ForeignKey("emails.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "source_task_id",
            mysql.BIGINT(unsigned=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "version",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.UniqueConstraint(
            "application_id",
            "round_number",
            name="uq_interview_rounds_application_round",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_check_constraint(
        "ck_interview_rounds_status",
        "interview_rounds",
        "status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')",
    )
    op.create_check_constraint(
        "ck_interview_rounds_result",
        "interview_rounds",
        "result IN ('PENDING', 'PASSED', 'FAILED')",
    )
    op.create_check_constraint(
        "ck_interview_rounds_source",
        "interview_rounds",
        "source IN ('MANUAL', 'EMAIL')",
    )

    # 从存量 interview tasks 迁移数据
    op.execute(
        """
        INSERT INTO interview_rounds
            (application_id, round_number, status, result, interview_date,
             location, meeting_url, source, source_task_id, created_at, updated_at)
        SELECT
            t.application_id,
            t.interview_round,
            CASE t.status
                WHEN 'COMPLETED' THEN 'COMPLETED'
                WHEN 'CANCELLED' THEN 'CANCELLED'
                ELSE 'SCHEDULED'
            END,
            CASE
                WHEN ja.interview_result IS NOT NULL
                     AND t.interview_round = (
                         SELECT MAX(t2.interview_round)
                         FROM tasks t2
                         WHERE t2.application_id = t.application_id
                           AND t2.task_type = 'INTERVIEW'
                     )
                THEN ja.interview_result
                ELSE 'PENDING'
            END,
            t.start_at,
            t.location,
            t.meeting_url,
            'EMAIL',
            t.id,
            t.created_at,
            t.updated_at
        FROM tasks t
        JOIN job_applications ja ON ja.id = t.application_id
        WHERE t.task_type = 'INTERVIEW'
          AND t.interview_round IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM interview_rounds ir
              WHERE ir.application_id = t.application_id
                AND ir.round_number = t.interview_round
          )
        """
    )


def downgrade() -> None:
    op.drop_table("interview_rounds")
