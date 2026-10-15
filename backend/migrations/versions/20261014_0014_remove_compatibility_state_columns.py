"""remove compatibility state columns

Revision ID: 20261014_0014
Revises: 20261011_0013
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import mysql

revision: str = "20261014_0014"
down_revision: str | Sequence[str] | None = "20261011_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    if context.is_offline_mode():
        return True
    return column_name in {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _has_index(
    table_name: str,
    index_name: str,
    *,
    offline_default: bool = True,
) -> bool:
    if context.is_offline_mode():
        return offline_default
    return index_name in {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    }


def _has_check(table_name: str, constraint_name: str) -> bool:
    if context.is_offline_mode():
        return True
    return constraint_name in {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints(table_name)
    }


def upgrade() -> None:
    # OFFER/ACTIVE 且结果为空是 R0 已记录的历史非法组合；PENDING 只表示尚待确认，
    # 不推断接受或拒绝，因此可在删除其他兼容列前确定性修复。
    op.execute(
        "UPDATE job_applications SET offer_result = 'PENDING' "
        "WHERE current_stage = 'OFFER' AND status = 'ACTIVE' "
        "AND offer_result IS NULL"
    )
    job_result_check = "ck_job_applications_ck_job_applications_interview_result"
    if _has_check("job_applications", job_result_check):
        op.drop_constraint(op.f(job_result_check), "job_applications", type_="check")
    if _has_column("job_applications", "interview_result"):
        op.drop_column("job_applications", "interview_result")

    if not _has_index("tasks", "ix_tasks_application_id", offline_default=False):
        op.create_index(
            "ix_tasks_application_id",
            "tasks",
            ["application_id"],
            unique=False,
        )
    if _has_index("tasks", "ix_tasks_application_type_round"):
        op.drop_index("ix_tasks_application_type_round", table_name="tasks")
    if _has_column("tasks", "interview_round"):
        op.drop_column("tasks", "interview_round")

    review_status_check = "ck_review_tasks_review_task_status"
    if _has_check("review_tasks", review_status_check):
        op.drop_constraint(op.f(review_status_check), "review_tasks", type_="check")
    if _has_column("review_tasks", "status"):
        op.drop_column("review_tasks", "status")


def downgrade() -> None:
    op.add_column(
        "review_tasks",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.create_check_constraint(
        op.f("ck_review_tasks_review_task_status"),
        "review_tasks",
        "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED', "
        "'EXECUTING', 'SUCCEEDED', 'FAILED', 'UNKNOWN')",
    )
    op.execute("UPDATE review_tasks SET status = decision_status")

    op.add_column(
        "tasks",
        sa.Column("interview_round", mysql.SMALLINT(unsigned=True), nullable=True),
    )
    op.execute(
        """
        UPDATE tasks t
        JOIN interview_rounds ir ON ir.id = t.interview_round_id
        SET t.interview_round = ir.round_number
        """
    )
    op.create_index(
        "ix_tasks_application_type_round",
        "tasks",
        ["application_id", "task_type", "interview_round"],
        unique=False,
    )
    op.drop_index("ix_tasks_application_id", table_name="tasks")

    op.add_column(
        "job_applications",
        sa.Column("interview_result", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_job_applications_ck_job_applications_interview_result"),
        "job_applications",
        "interview_result IN ('PENDING', 'PASSED', 'FAILED')",
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
