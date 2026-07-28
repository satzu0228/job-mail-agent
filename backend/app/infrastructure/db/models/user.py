from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, JsonObject, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.email_account import EmailAccount
    from app.infrastructure.db.models.job_application import JobApplication


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = MYSQL_TABLE_OPTIONS

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Shanghai",
        server_default="Asia/Shanghai",
    )
    reply_preferences: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    email_accounts: Mapped[list[EmailAccount]] = relationship(back_populates="user")
    job_applications: Mapped[list[JobApplication]] = relationship(back_populates="user")
