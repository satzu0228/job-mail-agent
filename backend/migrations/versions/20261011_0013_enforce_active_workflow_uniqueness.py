"""enforce active workflow uniqueness

Revision ID: 20261011_0013
Revises: 20261011_0012
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20261011_0013"
down_revision: str | Sequence[str] | None = "20261011_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column("active_email_id", mysql.BIGINT(unsigned=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_runs_active_email_id_emails",
        "workflow_runs",
        "emails",
        ["active_email_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_workflow_runs_active_email_id",
        "workflow_runs",
        ["active_email_id"],
    )
    op.execute(
        """
        UPDATE workflow_runs
        SET active_email_id = email_id
        WHERE graph_version LIKE 'job-mail-workflow.%'
          AND status IN ('PENDING', 'RUNNING', 'WAITING_REVIEW')
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_workflow_runs_active_email_id", "workflow_runs", type_="unique"
    )
    op.drop_constraint(
        "fk_workflow_runs_active_email_id_emails",
        "workflow_runs",
        type_="foreignkey",
    )
    op.drop_column("workflow_runs", "active_email_id")
