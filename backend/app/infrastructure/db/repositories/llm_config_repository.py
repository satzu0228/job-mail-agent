from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.infrastructure.db.models.llm_config import LlmConfig
from app.infrastructure.db.repositories.business import EntityNotFoundError


class LlmConfigRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def list(self) -> list[LlmConfig]:
        statement = (
            select(LlmConfig)
            .where(LlmConfig.user_id == self._user_id)
            .order_by(LlmConfig.is_active.desc(), LlmConfig.id)
        )
        return list(self._session.scalars(statement))

    def get(self, config_id: int, *, for_update: bool = False) -> LlmConfig:
        statement = select(LlmConfig).where(
            LlmConfig.id == config_id,
            LlmConfig.user_id == self._user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        config = self._session.scalar(statement)
        if config is None:
            raise EntityNotFoundError(f"LlmConfig {config_id} does not exist")
        return config

    def get_active(self) -> LlmConfig | None:
        statement = select(LlmConfig).where(
            LlmConfig.user_id == self._user_id,
            LlmConfig.is_active.is_(True),
        )
        return self._session.scalar(statement)

    def add(self, config: LlmConfig) -> LlmConfig:
        self._session.add(config)
        self._session.flush()
        return config

    def delete(self, config_id: int) -> None:
        config = self.get(config_id)
        self._session.delete(config)
        self._session.flush()

    def deactivate_others(self, *, except_config_id: int | None = None) -> None:
        statement = update(LlmConfig).where(
            LlmConfig.user_id == self._user_id,
            LlmConfig.is_active.is_(True),
        )
        if except_config_id is not None:
            statement = statement.where(LlmConfig.id != except_config_id)
        self._session.execute(statement.values(is_active=False))
