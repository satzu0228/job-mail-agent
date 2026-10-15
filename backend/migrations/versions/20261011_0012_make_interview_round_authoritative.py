"""make interview round authoritative

Revision ID: 20261011_0012
Revises: 20261010_0011
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20261011_0012"
down_revision: str | Sequence[str] | None = "20261010_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_interview_rounds_status", "interview_rounds", type_="check")
    op.alter_column(
        "interview_rounds",
        "status",
        existing_type=sa.String(length=16),
        nullable=False,
        server_default="PLANNED",
    )
    op.create_check_constraint(
        "ck_interview_rounds_status",
        "interview_rounds",
        "status IN ('PLANNED', 'SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')",
    )
    op.add_column(
        "tasks",
        sa.Column("interview_round_id", mysql.BIGINT(unsigned=True), nullable=True),
    )
    op.create_index(
        "ix_tasks_interview_round_id",
        "tasks",
        ["interview_round_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_tasks_interview_round_id_interview_rounds",
        "tasks",
        "interview_rounds",
        ["interview_round_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        INSERT INTO interview_rounds
            (application_id, round_number, status, result, interview_date,
             location, meeting_url, source, source_task_id, notes,
             created_at, updated_at)
        SELECT
            t.application_id,
            t.interview_round,
            CASE
                WHEN MAX(t.status = 'COMPLETED') = 1 THEN 'COMPLETED'
                WHEN MAX(t.status = 'CANCELLED') = 1 THEN 'CANCELLED'
                WHEN MAX(t.start_at IS NOT NULL) = 1 THEN 'SCHEDULED'
                ELSE 'PLANNED'
            END,
            CASE
                WHEN t.interview_round = (
                    SELECT MAX(t2.interview_round)
                    FROM tasks t2
                    WHERE t2.application_id = t.application_id
                      AND t2.task_type = 'INTERVIEW'
                ) AND MAX(ja.interview_result) IS NOT NULL
                THEN MAX(ja.interview_result)
                ELSE 'PENDING'
            END,
            MAX(t.start_at),
            MAX(t.location),
            MAX(t.meeting_url),
            'EMAIL',
            MIN(t.id),
            'M2_BACKFILL_MISSING_ROUND',
            MIN(t.created_at),
            MAX(t.updated_at)
        FROM tasks t
        JOIN job_applications ja ON ja.id = t.application_id
        LEFT JOIN interview_rounds ir
          ON ir.application_id = t.application_id
         AND ir.round_number = t.interview_round
        WHERE t.task_type = 'INTERVIEW'
          AND t.application_id IS NOT NULL
          AND t.interview_round IS NOT NULL
          AND ir.id IS NULL
        GROUP BY t.application_id, t.interview_round
        """
    )
    op.execute(
        """
        INSERT INTO interview_rounds
            (application_id, round_number, status, result, interview_date,
             location, meeting_url, source, source_task_id, notes,
             created_at, updated_at)
        SELECT
            t.application_id,
            COALESCE((
                SELECT MAX(ir2.round_number)
                FROM interview_rounds ir2
                WHERE ir2.application_id = t.application_id
            ), 0) + 1,
            CASE
                WHEN MAX(t.status = 'COMPLETED') = 1 THEN 'COMPLETED'
                WHEN MAX(t.status = 'CANCELLED') = 1 THEN 'CANCELLED'
                WHEN MAX(t.start_at IS NOT NULL) = 1 THEN 'SCHEDULED'
                ELSE 'PLANNED'
            END,
            COALESCE(MAX(ja.interview_result), 'PENDING'),
            MAX(t.start_at),
            MAX(t.location),
            MAX(t.meeting_url),
            'EMAIL',
            MIN(t.id),
            'M2_COMPATIBILITY_NULL_ROUND',
            MIN(t.created_at),
            MAX(t.updated_at)
        FROM tasks t
        JOIN job_applications ja ON ja.id = t.application_id
        WHERE t.task_type = 'INTERVIEW'
          AND t.application_id IS NOT NULL
          AND t.interview_round IS NULL
        GROUP BY t.application_id
        """
    )
    op.execute(
        """
        UPDATE tasks t
        JOIN interview_rounds ir
          ON ir.application_id = t.application_id
         AND (
              ir.round_number = t.interview_round
              OR (
                  t.interview_round IS NULL
                  AND ir.notes = 'M2_COMPATIBILITY_NULL_ROUND'
              )
         )
        SET t.interview_round = ir.round_number,
            t.interview_round_id = ir.id
        WHERE t.task_type = 'INTERVIEW'
          AND t.application_id IS NOT NULL
          AND t.interview_round_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE interview_rounds ir
        SET ir.status = CASE
            WHEN ir.status = 'NO_SHOW' THEN 'NO_SHOW'
            WHEN ir.result IN ('PASSED', 'FAILED') THEN 'COMPLETED'
            WHEN EXISTS (
                SELECT 1 FROM tasks t
                WHERE t.interview_round_id = ir.id AND t.status = 'CANCELLED'
            ) THEN 'CANCELLED'
            WHEN ir.interview_date IS NOT NULL OR EXISTS (
                SELECT 1 FROM tasks t
                WHERE t.interview_round_id = ir.id AND t.start_at IS NOT NULL
            ) THEN 'SCHEDULED'
            ELSE 'PLANNED'
        END
        """
    )
    op.execute(
        """
        UPDATE job_applications ja
        JOIN interview_rounds ir
          ON ir.application_id = ja.id
         AND ir.round_number = (
             SELECT MAX(ir2.round_number)
             FROM interview_rounds ir2
             WHERE ir2.application_id = ja.id
         )
        SET ja.interview_result = ir.result
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tasks_interview_round_id_interview_rounds",
        "tasks",
        type_="foreignkey",
    )
    op.drop_index("ix_tasks_interview_round_id", table_name="tasks")
    op.drop_column("tasks", "interview_round_id")
    op.execute(
        "UPDATE interview_rounds SET status = 'SCHEDULED' WHERE status = 'PLANNED'"
    )
    op.drop_constraint("ck_interview_rounds_status", "interview_rounds", type_="check")
    op.alter_column(
        "interview_rounds",
        "status",
        existing_type=sa.String(length=16),
        nullable=False,
        server_default="SCHEDULED",
    )
    op.create_check_constraint(
        "ck_interview_rounds_status",
        "interview_rounds",
        "status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')",
    )
