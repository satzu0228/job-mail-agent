from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ArchiveStatus, EmailParseStatus
from app.infrastructure.db.base import (
    MYSQL_TABLE_OPTIONS,
    Base,
    JsonObject,
    TimestampMixin,
    varchar_enum,
)

if TYPE_CHECKING:
    from app.infrastructure.db.models.email_account import EmailAccount
    from app.infrastructure.db.models.job_application import JobApplication


class Email(TimestampMixin, Base):
    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "source_folder",
            "uid_validity",
            "imap_uid",
            name="uq_emails_imap_identity",
        ),
        Index("ix_emails_account_received", "account_id", "received_at"),
        Index("ix_emails_message_id", "message_id", mysql_length=191),
        Index("ix_emails_application_received", "application_id", "received_at"),
        Index("ix_emails_archive_status", "archive_status"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    account_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("email_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    application_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("job_applications.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_folder: Mapped[str] = mapped_column(String(255), nullable=False)
    current_folder: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_folder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uid_validity: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False)
    imap_uid: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(998), nullable=True)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    reply_to_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    to_recipients: Mapped[list[JsonObject]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    cc_recipients: Mapped[list[JsonObject]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    sent_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    plain_body: Mapped[str | None] = mapped_column(mysql.LONGTEXT, nullable=True)
    html_sanitized: Mapped[str | None] = mapped_column(mysql.LONGTEXT, nullable=True)
    analysis_text: Mapped[str] = mapped_column(mysql.LONGTEXT, nullable=False)
    attachment_metadata: Mapped[list[JsonObject]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    parse_status: Mapped[EmailParseStatus] = mapped_column(
        varchar_enum(EmailParseStatus, name="email_parse_status", length=32),
        nullable=False,
        default=EmailParseStatus.PENDING,
        server_default=EmailParseStatus.PENDING.value,
    )
    archive_status: Mapped[ArchiveStatus] = mapped_column(
        varchar_enum(ArchiveStatus, name="email_archive_status", length=32),
        nullable=False,
        default=ArchiveStatus.NONE,
        server_default=ArchiveStatus.NONE.value,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )

    account: Mapped[EmailAccount] = relationship(back_populates="emails")
    application: Mapped[JobApplication | None] = relationship(back_populates="emails")
