"""创建用户、邮箱账户、求职申请和邮件表。

迁移版本：20260727_0001
上一个版本：无
创建日期：2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260727_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=sa.text("'Asia/Shanghai'"),
            nullable=False,
        ),
        sa.Column("reply_preferences", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    op.create_table(
        "email_accounts",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("imap_host", sa.String(length=255), nullable=False),
        sa.Column("imap_port", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column("imap_security", sa.String(length=16), nullable=False),
        sa.Column("smtp_host", sa.String(length=255), nullable=False),
        sa.Column("smtp_port", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column("smtp_security", sa.String(length=16), nullable=False),
        sa.Column("credential_ref", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("inbox_uid_validity", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("last_synced_uid", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("last_sync_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("last_sync_status", sa.String(length=32), nullable=True),
        sa.Column("last_sync_error", sa.String(length=500), nullable=True),
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
        sa.CheckConstraint(
            "imap_security IN ('SSL', 'STARTTLS')",
            name=op.f("ck_email_accounts_imap_security"),
        ),
        sa.CheckConstraint(
            "smtp_security IN ('SSL', 'STARTTLS')",
            name=op.f("ck_email_accounts_smtp_security"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_email_accounts_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_email_accounts"),
        sa.UniqueConstraint(
            "user_id",
            "email_address",
            name="uq_email_accounts_user_email_address",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )

    op.create_table(
        "job_applications",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("company_alias", sa.String(length=255), nullable=True),
        sa.Column("position_name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column(
            "current_stage",
            sa.String(length=32),
            server_default=sa.text("'APPLIED'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default=sa.text("'MANUAL'"),
            nullable=False,
        ),
        sa.Column("applied_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "version",
            mysql.INTEGER(unsigned=True),
            server_default=sa.text("1"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "current_stage IN "
            "('APPLIED', 'ASSESSMENT', 'INTERVIEW', 'OFFER', 'REJECTED', 'WITHDRAWN')",
            name=op.f("ck_job_applications_application_stage"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CLOSED', 'WITHDRAWN')",
            name=op.f("ck_job_applications_application_status"),
        ),
        sa.CheckConstraint(
            "source IN ('MANUAL', 'EMAIL')",
            name=op.f("ck_job_applications_application_source"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_job_applications_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_applications"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index(
        "ix_job_applications_user_stage_updated",
        "job_applications",
        ["user_id", "current_stage", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_job_applications_user_company_position",
        "job_applications",
        ["user_id", "company_name", "position_name"],
        unique=False,
    )

    op.create_table(
        "emails",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("account_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("source_folder", sa.String(length=255), nullable=False),
        sa.Column("current_folder", sa.String(length=255), nullable=False),
        sa.Column("previous_folder", sa.String(length=255), nullable=True),
        sa.Column("uid_validity", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("imap_uid", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("message_id", sa.String(length=998), nullable=True),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("reply_to_address", sa.String(length=320), nullable=True),
        sa.Column("to_recipients", sa.JSON(), nullable=False),
        sa.Column("cc_recipients", sa.JSON(), nullable=False),
        sa.Column("sent_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("received_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("plain_body", mysql.LONGTEXT(), nullable=True),
        sa.Column("html_sanitized", mysql.LONGTEXT(), nullable=True),
        sa.Column("analysis_text", mysql.LONGTEXT(), nullable=False),
        sa.Column("attachment_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "parse_status",
            sa.String(length=32),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "archive_status",
            sa.String(length=32),
            server_default=sa.text("'NONE'"),
            nullable=False,
        ),
        sa.Column("archived_at", mysql.DATETIME(fsp=6), nullable=True),
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
        sa.CheckConstraint(
            "parse_status IN ('PENDING', 'SUCCEEDED', 'PARTIAL', 'FAILED')",
            name=op.f("ck_emails_email_parse_status"),
        ),
        sa.CheckConstraint(
            "archive_status IN ('NONE', 'PROPOSED', 'ARCHIVED', 'RESTORED', 'FAILED')",
            name=op.f("ck_emails_email_archive_status"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["email_accounts.id"],
            name="fk_emails_account_id_email_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["job_applications.id"],
            name="fk_emails_application_id_job_applications",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_emails"),
        sa.UniqueConstraint(
            "account_id",
            "source_folder",
            "uid_validity",
            "imap_uid",
            name="uq_emails_imap_identity",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index(
        "ix_emails_account_received",
        "emails",
        ["account_id", "received_at"],
        unique=False,
    )
    op.create_index(
        "ix_emails_message_id",
        "emails",
        ["message_id"],
        unique=False,
        mysql_length=191,
    )
    op.create_index(
        "ix_emails_application_received",
        "emails",
        ["application_id", "received_at"],
        unique=False,
    )
    op.create_index(
        "ix_emails_archive_status",
        "emails",
        ["archive_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("emails")
    op.drop_table("job_applications")
    op.drop_table("email_accounts")
    op.drop_table("users")
