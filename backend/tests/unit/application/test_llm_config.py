from contextlib import nullcontext

import pytest

from app.application.llm_config import LlmConfigService
from app.application.schemas import LlmConfigCreate, LlmConfigUpdate
from app.core.config import Settings
from app.infrastructure.db.models.llm_config import LlmConfig
from app.infrastructure.db.repositories import ResourceConflictError
from app.infrastructure.llm import LLMConfigurationError
from app.infrastructure.security import EncryptedCredentialResolver

TEST_KEY = "33" * 32


class FakeSession:
    def begin(self):  # noqa: ANN201
        return nullcontext()

    def get(self, model: object, entity_id: int) -> object:
        return object()

    def flush(self) -> None:
        pass


class FakeConfigs:
    def __init__(
        self,
        *,
        active: LlmConfig | None = None,
        existing: LlmConfig | None = None,
    ) -> None:
        self.active = active
        self.existing = existing
        self.created: LlmConfig | None = None
        self.deleted_id: int | None = None
        self.deactivated_except: int | None = None

    def get_active(self) -> LlmConfig | None:
        return self.active

    def get(self, config_id: int, *, for_update: bool = False) -> LlmConfig:
        assert config_id == 7
        assert self.existing is not None
        return self.existing

    def list(self) -> list[LlmConfig]:
        return []

    def add(self, config: LlmConfig) -> LlmConfig:
        self.created = config
        return config

    def delete(self, config_id: int) -> None:
        self.deleted_id = config_id

    def deactivate_others(self, *, except_config_id: int | None = None) -> None:
        self.deactivated_except = except_config_id


def _service(configs: FakeConfigs) -> LlmConfigService:
    service = LlmConfigService(
        FakeSession(),  # type: ignore[arg-type]
        1,
        credential_resolver=EncryptedCredentialResolver(TEST_KEY),
    )
    service._configs = configs  # type: ignore[assignment]
    return service


def _active_config(*, api_key: str, model: str = "deepseek-chat") -> LlmConfig:
    resolver = EncryptedCredentialResolver(TEST_KEY)
    return LlmConfig(
        id=7,
        user_id=1,
        provider="deepseek",
        model=model,
        api_key_ciphertext=resolver.protect(api_key),
        temperature=0.3,
        timeout_seconds=45.0,
        max_retries=1,
        is_active=True,
    )


def test_create_config_encrypts_api_key_and_forces_provider() -> None:
    configs = FakeConfigs()
    service = _service(configs)

    config = service.create_config(
        LlmConfigCreate(
            model="deepseek-reasoner",
            api_key="sk-fixture-api-key",
            temperature=0.5,
        )
    )

    assert config.provider == "deepseek"
    assert config.model == "deepseek-reasoner"
    assert config.api_key_ciphertext is not None
    assert "sk-fixture-api-key" not in config.api_key_ciphertext
    assert (
        EncryptedCredentialResolver(TEST_KEY).resolve(config.api_key_ciphertext)
        == "sk-fixture-api-key"
    )


def test_update_config_keeps_original_key_when_not_provided() -> None:
    existing = _active_config(api_key="sk-original-key")
    service = _service(FakeConfigs(existing=existing))

    updated = service.update_config(7, LlmConfigUpdate(model="deepseek-chat"))

    assert updated.api_key_ciphertext == existing.api_key_ciphertext
    assert (
        EncryptedCredentialResolver(TEST_KEY).resolve(updated.api_key_ciphertext)
        == "sk-original-key"
    )


def test_update_config_replaces_key_when_provided() -> None:
    existing = _active_config(api_key="sk-original-key")
    service = _service(FakeConfigs(existing=existing))

    updated = service.update_config(
        7,
        LlmConfigUpdate(api_key="sk-new-key", temperature=0.9),
    )

    assert updated.temperature == 0.9
    assert (
        EncryptedCredentialResolver(TEST_KEY).resolve(updated.api_key_ciphertext)
        == "sk-new-key"
    )


def test_delete_active_config_is_rejected() -> None:
    existing = _active_config(api_key="sk-active-key")
    service = _service(FakeConfigs(existing=existing))

    with pytest.raises(ResourceConflictError):
        service.delete_config(7)
    assert service._configs.deleted_id is None  # type: ignore[attr-defined]


def test_set_active_deactivates_other_configs() -> None:
    existing = LlmConfig(id=7, user_id=1, is_active=False)
    configs = FakeConfigs(existing=existing)
    service = _service(configs)

    updated = service.set_active(7, is_active=True)

    assert updated.is_active is True
    assert configs.deactivated_except == 7


def test_resolve_effective_config_uses_active_db_config() -> None:
    configs = FakeConfigs(active=_active_config(api_key="sk-db-key"))
    service = _service(configs)

    resolved = service.resolve_effective_config()

    assert resolved["provider"] == "deepseek"
    assert resolved["api_key"] == "sk-db-key"
    assert resolved["model"] == "deepseek-chat"
    assert resolved["temperature"] == 0.3
    assert resolved["timeout_seconds"] == 45.0
    assert resolved["max_retries"] == 1


def test_resolve_effective_config_requires_db_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无活跃数据库配置时直接报错，不再回退到环境变量。"""
    monkeypatch.setenv("JOB_MAIL_LLM_API_KEY", "sk-env-key")
    service = _service(FakeConfigs())
    settings = Settings(
        _env_file=None,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
        llm_temperature=0.0,
        llm_timeout_seconds=60.0,
        llm_max_retries=2,
    )

    with pytest.raises(LLMConfigurationError) as exc:
        service.resolve_effective_config(settings)
    assert "设置" in str(exc.value)


def test_resolve_effective_config_raises_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JOB_MAIL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    service = _service(FakeConfigs())
    settings = Settings(_env_file=None)

    with pytest.raises(LLMConfigurationError):
        service.resolve_effective_config(settings)
