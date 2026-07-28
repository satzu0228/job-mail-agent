from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AutomationRuleType
from app.infrastructure.db.base import MYSQL_TABLE_OPTIONS, Base, TimestampMixin, varchar_enum


class AutomationRule(TimestampMixin, Base):
    __tablename__ = "automation_rules"
    __table_args__ = MYSQL_TABLE_OPTIONS

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey("email_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[AutomationRuleType] = mapped_column(
        varchar_enum(AutomationRuleType, name="automation_rule_type", length=32),
        nullable=False,
        default=AutomationRuleType.LOW_PRIORITY_ARCHIVE,
        server_default=AutomationRuleType.LOW_PRIORITY_ARCHIVE.value,
    )
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    action_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    requires_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    version: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    __mapper_args__ = {"version_id_col": version}
