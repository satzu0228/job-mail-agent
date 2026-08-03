from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.reply import ReplyAgent
from app.application.llm_config import create_chat_model_for_user
from app.application.reply import ReplyGenerationService, ReplySendService
from app.application.schemas import (
    ReplyGenerationRequest,
    ReplyGenerationResponse,
    ReplySendRequest,
    ReplySendResponse,
)
from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_db_session

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def generation_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReplyGenerationService:
    return ReplyGenerationService(
        session,
        settings.demo_user_id,
        ReplyAgent.from_model(create_chat_model_for_user(session, settings)),
    )


def send_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReplySendService:
    return ReplySendService(
        session,
        settings.demo_user_id,
        timeout_seconds=settings.email_connect_timeout_seconds,
    )


GenerationDependency = Annotated[
    ReplyGenerationService,
    Depends(generation_service),
]
SendDependency = Annotated[ReplySendService, Depends(send_service)]


@router.post(
    "/emails/{email_id}/generate-reply",
    response_model=ReplyGenerationResponse,
    tags=["reply-drafts"],
)
def generate_reply(
    email_id: int,
    use_case: GenerationDependency,
    payload: ReplyGenerationRequest | None = None,
) -> ReplyGenerationResponse:
    return use_case.generate(email_id, payload or ReplyGenerationRequest())


@router.post(
    "/reply-drafts/{draft_id}/send",
    response_model=ReplySendResponse,
    tags=["reply-drafts"],
)
def send_reply(
    draft_id: int,
    payload: ReplySendRequest,
    use_case: SendDependency,
) -> ReplySendResponse:
    return use_case.send(draft_id, payload)
