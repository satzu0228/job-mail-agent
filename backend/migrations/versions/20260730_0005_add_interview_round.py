"""为面试日程增加结构化轮次。

迁移版本：20260730_0005
上一个版本：20260730_0004
创建日期：2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260730_0005"
down_revision: str | Sequence[str] | None = "20260730_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "interview_round",
            mysql.SMALLINT(unsigned=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tasks_application_type_round",
        "tasks",
        ["application_id", "task_type", "interview_round"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_application_type_round", table_name="tasks")
    op.drop_column("tasks", "interview_round")
