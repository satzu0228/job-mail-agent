"""增加邮件移动后的当前 IMAP 指针。

迁移版本：20260730_0006
上一个版本：20260730_0005
创建日期：2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260730_0006"
down_revision: str | Sequence[str] | None = "20260730_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "emails",
        sa.Column(
            "current_uid_validity",
            mysql.BIGINT(unsigned=True),
            nullable=True,
        ),
    )
    op.add_column(
        "emails",
        sa.Column(
            "current_imap_uid",
            mysql.BIGINT(unsigned=True),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE emails
        SET current_uid_validity = uid_validity,
            current_imap_uid = imap_uid
        WHERE current_uid_validity IS NULL OR current_imap_uid IS NULL
        """
    )
    op.create_index(
        "ix_emails_current_imap_pointer",
        "emails",
        ["account_id", "current_folder", "current_uid_validity", "current_imap_uid"],
    )


def downgrade() -> None:
    op.drop_index("ix_emails_current_imap_pointer", table_name="emails")
    op.drop_column("emails", "current_imap_uid")
    op.drop_column("emails", "current_uid_validity")
