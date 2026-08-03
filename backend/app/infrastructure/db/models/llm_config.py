from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.user import User


class LlmConfig(TimestampMixin, Base):
    """用户在界面上配置的 LLM 调用参数，api_key 加密存储。"""

    __tablename__ = "llm_configs"
    __table_args__ = MYSQL_TABLE_OPTIONS

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
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    temperature: Mapped[float] = mapped_column(
        mysql.FLOAT,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )
    timeout_seconds: Mapped[float] = mapped_column(
        mysql.FLOAT,
        nullable=False,
        default=60.0,
        server_default=text("60"),
    )
    max_retries: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=2,
        server_default=text("2"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    user: Mapped[User] = relationship(back_populates="llm_configs")
