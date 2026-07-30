from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import TransportSecurity
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum

if TYPE_CHECKING:
    from app.infrastructure.db.models.email import Email
    from app.infrastructure.db.models.user import User


class EmailAccount(TimestampMixin, Base):
    __tablename__ = "email_accounts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "email_address",
            name="uq_email_accounts_user_email_address",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(mysql.SMALLINT(unsigned=True), nullable=False)
    imap_security: Mapped[TransportSecurity] = mapped_column(
        varchar_enum(TransportSecurity, name="imap_security", length=16),
        nullable=False,
    )
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(mysql.SMALLINT(unsigned=True), nullable=False)
    smtp_security: Mapped[TransportSecurity] = mapped_column(
        varchar_enum(TransportSecurity, name="smtp_security", length=16),
        nullable=False,
    )
    credential_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    auto_sync_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    sync_interval_minutes: Mapped[int] = mapped_column(
        mysql.SMALLINT(unsigned=True),
        nullable=False,
        default=10,
        server_default=text("10"),
    )
    next_sync_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    last_auto_sync_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    inbox_uid_validity: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        nullable=True,
    )
    last_synced_uid: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        nullable=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=6),
        nullable=True,
    )
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped[User] = relationship(back_populates="email_accounts")
    emails: Mapped[list[Email]] = relationship(back_populates="account")
