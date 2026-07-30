"""增加邮箱自动同步配置和系统内部提醒。

迁移版本：20260730_0004
上一个版本：20260728_0003
创建日期：2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260730_0004"
down_revision: str | Sequence[str] | None = "20260728_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.add_column(
        "email_accounts",
        sa.Column(
            "auto_sync_enabled",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "sync_interval_minutes",
            mysql.SMALLINT(unsigned=True),
            server_default=sa.text("10"),
            nullable=False,
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column("next_sync_at", mysql.DATETIME(fsp=6), nullable=True),
    )
    op.add_column(
        "email_accounts",
        sa.Column("last_auto_sync_at", mysql.DATETIME(fsp=6), nullable=True),
    )

    op.create_table(
        "reminders",
        sa.Column(
            "id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False
        ),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("task_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("remind_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("event_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DELIVERED",
                "READ",
                "CANCELLED",
                name="reminder_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            server_default=sa.text("'DELIVERED'"),
            nullable=False,
        ),
        sa.Column("delivered_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("read_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_reminders_task_id"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_reminders_user_status_remind",
        "reminders",
        ["user_id", "status", "remind_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reminders_user_status_remind", table_name="reminders")
    op.drop_table("reminders")
    op.drop_column("email_accounts", "last_auto_sync_at")
    op.drop_column("email_accounts", "next_sync_at")
    op.drop_column("email_accounts", "sync_interval_minutes")
    op.drop_column("email_accounts", "auto_sync_enabled")
