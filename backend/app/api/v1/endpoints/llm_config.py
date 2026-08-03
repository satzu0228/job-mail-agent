from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.llm_config import LlmConfigService
from app.application.schemas import (
    LlmConfigActiveUpdate,
    LlmConfigCreate,
    LlmConfigRead,
    LlmConfigTestResult,
    LlmConfigUpdate,
)
from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_db_session

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def llm_config_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> LlmConfigService:
    return LlmConfigService(session, settings.demo_user_id)


LlmConfigServiceDependency = Annotated[LlmConfigService, Depends(llm_config_service)]


def to_read(config) -> LlmConfigRead:
    return LlmConfigRead(
        id=config.id,
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
        is_active=config.is_active,
        api_key_configured=bool(config.api_key_ciphertext),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/llm-configs", response_model=list[LlmConfigRead], tags=["llm-configs"])
def list_llm_configs(service: LlmConfigServiceDependency) -> list[LlmConfigRead]:
    return [to_read(config) for config in service.list_configs()]


@router.post("/llm-configs", response_model=LlmConfigRead, tags=["llm-configs"])
def create_llm_config(
    data: LlmConfigCreate,
    service: LlmConfigServiceDependency,
) -> LlmConfigRead:
    return to_read(service.create_config(data))


@router.patch(
    "/llm-configs/{config_id}",
    response_model=LlmConfigRead,
    tags=["llm-configs"],
)
def update_llm_config(
    config_id: int,
    data: LlmConfigUpdate,
    service: LlmConfigServiceDependency,
) -> LlmConfigRead:
    return to_read(service.update_config(config_id, data))


@router.delete("/llm-configs/{config_id}", status_code=204, tags=["llm-configs"])
def delete_llm_config(
    config_id: int,
    service: LlmConfigServiceDependency,
) -> None:
    service.delete_config(config_id)


@router.patch(
    "/llm-configs/{config_id}/active",
    response_model=LlmConfigRead,
    tags=["llm-configs"],
)
def set_llm_config_active(
    config_id: int,
    data: LlmConfigActiveUpdate,
    service: LlmConfigServiceDependency,
) -> LlmConfigRead:
    return to_read(service.set_active(config_id, data.is_active))


@router.post(
    "/llm-configs/{config_id}/test",
    response_model=LlmConfigTestResult,
    tags=["llm-configs"],
)
def test_llm_config(
    config_id: int,
    service: LlmConfigServiceDependency,
    data: LlmConfigUpdate | None = None,
) -> LlmConfigTestResult:
    api_key_override = data.api_key if data is not None else None
    return service.test_config(config_id, api_key_override=api_key_override)
