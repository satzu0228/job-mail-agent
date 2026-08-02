"""add_UPDATE_INTERVIEW_RESULT_to_review_tasks_check_constraint

Revision ID: c36cfae0b9fb
Revises: 20260802_0010
Create Date: 2026-08-02 15:24:07.805712
"""

from collections.abc import Sequence

from alembic import op

revision: str = 'c36cfae0b9fb'
down_revision: str | Sequence[str] | None = '20260802_0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_VALUES = (
    "CREATE_APPLICATION", "LINK_APPLICATION", "UPDATE_APPLICATION_STAGE",
    "CREATE_TASK", "UPDATE_TASK", "SEND_REPLY",
    "ARCHIVE_EMAIL", "RESTORE_EMAIL",
)
NEW_VALUES = (*OLD_VALUES, "UPDATE_INTERVIEW_RESULT")


def _check_clause(values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return (
        "CHECK ((`action_type` in ({quoted})))"
    ).format(quoted=quoted)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE review_tasks DROP CHECK ck_review_tasks_review_action_type"
    )
    op.execute(
        f"ALTER TABLE review_tasks ADD CONSTRAINT ck_review_tasks_review_action_type {_check_clause(NEW_VALUES)}"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE review_tasks DROP CHECK ck_review_tasks_review_action_type"
    )
    op.execute(
        f"ALTER TABLE review_tasks ADD CONSTRAINT ck_review_tasks_review_action_type {_check_clause(OLD_VALUES)}"
    )
