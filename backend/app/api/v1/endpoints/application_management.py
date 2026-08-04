from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, sessionmaker

from app.agents.application.agent import ApplicationAgent
from app.api.v1.endpoints.workflow import (
    ReviewDecisionCoordinator,
    review_decision_service,
)
from app.application.application_management import (
    ApplicationManagementService,
    ReviewTaskService,
)
from app.application.archive import EmailArchiveService
from app.application.llm_config import create_chat_model_for_user
from app.application.schemas import (
    ApplicationMatchResponse,
    ReviewDecision,
    ReviewDecisionResponse,
    ReviewTaskPage,
    ReviewTaskRead,
)
from app.core.config import Settings, get_settings
from app.domain.enums import ReviewActionType, ReviewTaskStatus
from app.infrastructure.db.session import get_db_session

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def management_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ApplicationManagementService:
    model = create_chat_model_for_user(session, settings)
    factory = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )
    return ApplicationManagementService(
        session,
        settings.demo_user_id,
        ApplicationAgent.from_model(model, factory),
        model_provider=settings.llm_provider,
        model_name=settings.llm_model,
    )


def review_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReviewTaskService:
    return ReviewTaskService(session, settings.demo_user_id)


def archive_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> EmailArchiveService:
    return EmailArchiveService(
        session,
        settings.demo_user_id,
        timeout_seconds=settings.email_connect_timeout_seconds,
    )


ManagementDependency = Annotated[
    ApplicationManagementService,
    Depends(management_service),
]
ReviewDependency = Annotated[ReviewTaskService, Depends(review_service)]
ArchiveDependency = Annotated[EmailArchiveService, Depends(archive_service)]
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


@router.post(
    "/emails/{email_id}/archive-review",
    response_model=ReviewTaskRead,
    tags=["email-archive"],
)
def propose_email_archive(
    email_id: int,
    use_case: ArchiveDependency,
) -> ReviewTaskRead:
    return ReviewTaskRead.model_validate(use_case.propose_archive(email_id))


@router.post(
    "/emails/{email_id}/restore-review",
    response_model=ReviewTaskRead,
    tags=["email-archive"],
)
def propose_email_restore(
    email_id: int,
    use_case: ArchiveDependency,
) -> ReviewTaskRead:
    return ReviewTaskRead.model_validate(use_case.propose_restore(email_id))


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
    "/review-tasks/query",
    response_model=ReviewTaskPage,
    tags=["review-tasks"],
)
def query_review_tasks(
    use_case: ReviewDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    task_status: Annotated[
        ReviewTaskStatus | None, Query(alias="status")
    ] = None,
    action_type: ReviewActionType | None = None,
) -> ReviewTaskPage:
    items, total = use_case.query(
        offset=offset,
        limit=limit,
        status=task_status,
        action_type=action_type,
    )
    return ReviewTaskPage(
        items=[ReviewTaskRead.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


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
