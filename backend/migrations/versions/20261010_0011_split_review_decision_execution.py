"""split review decision and execution state

Revision ID: 20261010_0011
Revises: e08e5060a4f5
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20261010_0011"
down_revision: str | Sequence[str] | None = "e08e5060a4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_tasks",
        sa.Column(
            "decision_status",
            sa.String(length=16),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE review_tasks
        SET decision_status = CASE
            WHEN status = 'PENDING' THEN 'PENDING'
            WHEN status = 'REJECTED' THEN 'REJECTED'
            WHEN status = 'CANCELLED' THEN 'CANCELLED'
            WHEN status = 'EXPIRED' THEN 'EXPIRED'
            ELSE 'APPROVED'
        END
        """
    )
    op.alter_column(
        "review_tasks",
        "decision_status",
        existing_type=sa.String(length=16),
        nullable=False,
        server_default="PENDING",
    )
    op.add_column(
        "review_tasks",
        sa.Column("parent_review_task_id", mysql.CHAR(length=36), nullable=True),
    )
    op.create_index(
        "ix_review_tasks_parent_review_task_id",
        "review_tasks",
        ["parent_review_task_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_review_tasks_parent_review_task_id_review_tasks",
        "review_tasks",
        "review_tasks",
        ["parent_review_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "review_tasks",
        "workflow_run_id",
        existing_type=mysql.CHAR(length=36),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "review_tasks",
        "workflow_run_id",
        existing_type=mysql.CHAR(length=36),
        nullable=False,
    )
    op.drop_constraint(
        "fk_review_tasks_parent_review_task_id_review_tasks",
        "review_tasks",
        type_="foreignkey",
    )
    op.drop_index("ix_review_tasks_parent_review_task_id", table_name="review_tasks")
    op.drop_column("review_tasks", "parent_review_task_id")
    op.drop_column("review_tasks", "decision_status")
