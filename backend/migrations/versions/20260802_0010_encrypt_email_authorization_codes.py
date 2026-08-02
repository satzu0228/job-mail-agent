"""Replace environment references with encrypted email authorization codes.

Revision ID: 20260802_0010
Revises: 20260802_0009
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0010"
down_revision: str | Sequence[str] | None = "20260802_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 旧引用无法安全转换为授权码，迁移后由用户在设置页重新授权。
    op.add_column(
        "email_accounts",
        sa.Column("credential_ciphertext", sa.Text(), nullable=True),
    )
    op.drop_column("email_accounts", "credential_ref")


def downgrade() -> None:
    op.add_column(
        "email_accounts",
        sa.Column("credential_ref", sa.String(length=128), nullable=True),
    )
    op.drop_column("email_accounts", "credential_ciphertext")
