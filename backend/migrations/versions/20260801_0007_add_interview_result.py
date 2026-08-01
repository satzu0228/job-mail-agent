"""为求职申请增加面试结果。

迁移版本：20260801_0007
上一个版本：20260730_0006
创建日期：2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0007"
down_revision: str | Sequence[str] | None = "20260730_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_applications",
        sa.Column("interview_result", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_job_applications_interview_result",
        "job_applications",
        "interview_result IN ('PENDING', 'PASSED', 'FAILED')",
    )
    op.execute(
        "UPDATE job_applications SET interview_result = 'PENDING' "
        "WHERE current_stage = 'INTERVIEW'"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_job_applications_interview_result",
        "job_applications",
        type_="check",
    )
    op.drop_column("job_applications", "interview_result")
