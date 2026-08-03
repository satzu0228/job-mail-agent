from __future__ import annotations

import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.application.schemas import (
    LlmConfigCreate,
    LlmConfigTestResult,
    LlmConfigUpdate,
)
from app.core.config import Settings, get_settings
from app.infrastructure.db.models.llm_config import LlmConfig
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories import LlmConfigRepository, ResourceConflictError
from app.infrastructure.llm import LLMConfigurationError, create_chat_model
from app.infrastructure.security import EncryptedCredentialResolver

LLM_PROVIDER = "deepseek"


def create_chat_model_for_user(
    session: Session,
    settings: Settings,
) -> BaseChatModel:
    """按用户配置创建聊天模型：数据库活跃配置优先，否则回退环境变量。"""
    runtime_config = LlmConfigService(
        session,
        settings.demo_user_id,
    ).resolve_effective_config()
    return create_chat_model(settings, runtime_config)


class LlmConfigService:
    """LLM 配置的增删改查、测试连接与运行时配置解析。"""

    def __init__(
        self,
        session: Session,
        user_id: int,
        *,
        credential_resolver: EncryptedCredentialResolver | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._configs = LlmConfigRepository(session, user_id)
        self._credential_resolver = credential_resolver or EncryptedCredentialResolver()

    # ---------- CRUD ----------

    def list_configs(self) -> list[LlmConfig]:
        return self._configs.list()

    def create_config(self, data: LlmConfigCreate) -> LlmConfig:
        api_key = data.api_key.get_secret_value() if data.api_key else None
        ciphertext = self._credential_resolver.protect(api_key) if api_key else None
        with self._session.begin():
            self._ensure_demo_user()
            if data.is_active:
                self._configs.deactivate_others()
            config = LlmConfig(
                user_id=self._user_id,
                provider=LLM_PROVIDER,
                model=data.model,
                base_url=data.base_url,
                temperature=data.temperature,
                timeout_seconds=data.timeout_seconds,
                max_retries=data.max_retries,
                is_active=data.is_active,
                api_key_ciphertext=ciphertext,
            )
            return self._configs.add(config)

    def update_config(self, config_id: int, data: LlmConfigUpdate) -> LlmConfig:
        with self._session.begin():
            config = self._configs.get(config_id, for_update=True)
            values = data.model_dump(exclude_unset=True)
            api_key = values.pop("api_key", None)
            if api_key is not None:
                config.api_key_ciphertext = self._credential_resolver.protect(api_key)
            for name, value in values.items():
                setattr(config, name, value)
            self._session.flush()
            return config

    def delete_config(self, config_id: int) -> None:
        with self._session.begin():
            config = self._configs.get(config_id, for_update=True)
            if config.is_active:
                raise ResourceConflictError("当前启用中的 AI 配置不能删除")
            self._configs.delete(config_id)

    def set_active(self, config_id: int, is_active: bool) -> LlmConfig:
        with self._session.begin():
            config = self._configs.get(config_id, for_update=True)
            if is_active:
                self._configs.deactivate_others(except_config_id=config_id)
            config.is_active = is_active
            self._session.flush()
            return config

    # ---------- 测试连接 ----------

    def test_config(
        self,
        config_id: int,
        *,
        api_key_override: SecretStr | None = None,
    ) -> LlmConfigTestResult:
        """用存储的配置（可临时换新 api_key）向模型发送一条测试消息。"""
        config = self._configs.get(config_id)
        started = time.monotonic()
        try:
            api_key = (
                api_key_override.get_secret_value()
                if api_key_override is not None
                else self._credential_resolver.resolve(config.api_key_ciphertext)
            )
            resolved = self._to_runtime_config(config, api_key=api_key)
            model = create_chat_model(get_settings(), resolved)
            model.invoke("只回复两个字：正常")
            latency_ms = int((time.monotonic() - started) * 1000)
            return LlmConfigTestResult(
                success=True,
                message=f"连接成功，模型 {resolved['model']} 响应正常",
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.monotonic() - started) * 1000)
            return LlmConfigTestResult(
                success=False,
                message=str(exc) or exc.__class__.__name__,
                latency_ms=latency_ms,
            )

    # ---------- 运行时配置解析 ----------

    def resolve_effective_config(
        self,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        """返回用于创建聊天模型的完整配置。

        优先级：数据库中的活跃配置 > 环境变量；都没有则抛出异常。
        """
        active = self._configs.get_active()
        if active is not None:
            api_key = self._credential_resolver.resolve(active.api_key_ciphertext)
            return self._to_runtime_config(active, api_key=api_key)

        settings = settings or get_settings()
        if settings.llm_api_key is None:
            raise LLMConfigurationError(
                "未配置 AI 模型 API Key：请在设置页填写，或配置 JOB_MAIL_LLM_API_KEY 环境变量"
            )
        return {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "api_key": settings.llm_api_key.get_secret_value(),
            "base_url": None,
            "temperature": settings.llm_temperature,
            "timeout_seconds": settings.llm_timeout_seconds,
            "max_retries": settings.llm_max_retries,
        }

    @staticmethod
    def _to_runtime_config(
        config: LlmConfig,
        *,
        api_key: str,
    ) -> dict[str, Any]:
        return {
            "provider": config.provider,
            "model": config.model,
            "api_key": api_key,
            "base_url": config.base_url,
            "temperature": config.temperature,
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
        }

    def _ensure_demo_user(self) -> None:
        if self._session.get(User, self._user_id) is None:
            self._session.add(
                User(
                    id=self._user_id,
                    display_name="演示用户",
                    timezone="Asia/Shanghai",
                    reply_preferences={},
                )
            )
            self._session.flush()
