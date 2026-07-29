from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.agents.application.agent import ApplicationAgent
from app.api.v1.endpoints.workflow import (
    ReviewDecisionCoordinator,
    review_decision_service,
)
from app.application.application_management import (
    ApplicationManagementService,
    ReviewTaskService,
)
from app.application.schemas import (
    ApplicationMatchResponse,
    ReviewDecision,
    ReviewDecisionResponse,
    ReviewTaskRead,
)
from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_db_session
from app.infrastructure.llm import create_chat_model

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def management_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ApplicationManagementService:
    model = create_chat_model(settings)
    return ApplicationManagementService(
        session,
        settings.demo_user_id,
        ApplicationAgent.from_model(model),
        model_provider=settings.llm_provider,
        model_name=settings.llm_model,
    )


def review_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReviewTaskService:
    return ReviewTaskService(session, settings.demo_user_id)


ManagementDependency = Annotated[
    ApplicationManagementService,
    Depends(management_service),
]
ReviewDependency = Annotated[ReviewTaskService, Depends(review_service)]
ReviewDecisionDependency = Annotated[
    ReviewDecisionCoordinator,
    Depends(review_decision_service),
]


@router.post(
    "/emails/{email_id}/match-application",
    response_model=ApplicationMatchResponse,
    tags=["application-management"],
)
def match_application(
    email_id: int,
    use_case: ManagementDependency,
) -> ApplicationMatchResponse:
    return use_case.match_email(email_id)


@router.get(
    "/review-tasks",
    response_model=list[ReviewTaskRead],
    tags=["review-tasks"],
)
def list_review_tasks(
    use_case: ReviewDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ReviewTaskRead]:
    return [
        ReviewTaskRead.model_validate(item)
        for item in use_case.list(offset=offset, limit=limit)
    ]


@router.get(
    "/review-tasks/{task_id}",
    response_model=ReviewTaskRead,
    tags=["review-tasks"],
)
def get_review_task(
    task_id: str,
    use_case: ReviewDependency,
) -> ReviewTaskRead:
    return ReviewTaskRead.model_validate(use_case.get(task_id))


@router.post(
    "/review-tasks/{task_id}/decision",
    response_model=ReviewDecisionResponse,
    tags=["review-tasks"],
)
def decide_review_task(
    task_id: str,
    payload: ReviewDecision,
    use_case: ReviewDecisionDependency,
) -> ReviewDecisionResponse:
    return use_case.decide(task_id, payload)
