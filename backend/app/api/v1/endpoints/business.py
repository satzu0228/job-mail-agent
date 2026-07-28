from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.application.crud import BusinessCrudService
from app.application.schemas import (
    EmailDetail,
    EmailListItem,
    JobApplicationCreate,
    JobApplicationRead,
    JobApplicationUpdate,
    ReplyDraftCreate,
    ReplyDraftRead,
    ReplyDraftUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.core.config import Settings, get_settings
from app.infrastructure.db.session import get_db_session

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
PageOffset = Annotated[int, Query(ge=0)]
PageLimit = Annotated[int, Query(ge=1, le=100)]


def service(session: SessionDependency, settings: SettingsDependency) -> BusinessCrudService:
    return BusinessCrudService(session, settings.demo_user_id)


ServiceDependency = Annotated[BusinessCrudService, Depends(service)]


@router.get("/emails", response_model=list[EmailListItem], tags=["emails"])
def list_emails(
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
) -> list[EmailListItem]:
    return [
        EmailListItem.model_validate(item)
        for item in use_case.emails.list(offset=offset, limit=limit)
    ]


@router.get("/emails/{email_id}", response_model=EmailDetail, tags=["emails"])
def get_email(email_id: int, use_case: ServiceDependency) -> EmailDetail:
    return EmailDetail.model_validate(use_case.emails.get(email_id))


@router.get(
    "/job-applications",
    response_model=list[JobApplicationRead],
    tags=["job-applications"],
)
def list_applications(
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
) -> list[JobApplicationRead]:
    return [
        JobApplicationRead.model_validate(item)
        for item in use_case.applications.list(offset=offset, limit=limit)
    ]


@router.post(
    "/job-applications",
    response_model=JobApplicationRead,
    status_code=status.HTTP_201_CREATED,
    tags=["job-applications"],
)
def create_application(
    payload: JobApplicationCreate,
    use_case: ServiceDependency,
) -> JobApplicationRead:
    return JobApplicationRead.model_validate(use_case.create_application(payload))


@router.get(
    "/job-applications/{application_id}",
    response_model=JobApplicationRead,
    tags=["job-applications"],
)
def get_application(
    application_id: int,
    use_case: ServiceDependency,
) -> JobApplicationRead:
    return JobApplicationRead.model_validate(
        use_case.applications.get(application_id)
    )


@router.patch(
    "/job-applications/{application_id}",
    response_model=JobApplicationRead,
    tags=["job-applications"],
)
def update_application(
    application_id: int,
    payload: JobApplicationUpdate,
    use_case: ServiceDependency,
) -> JobApplicationRead:
    return JobApplicationRead.model_validate(
        use_case.update_application(application_id, payload)
    )


@router.get("/tasks", response_model=list[TaskRead], tags=["tasks"])
def list_tasks(
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
) -> list[TaskRead]:
    return [
        TaskRead.model_validate(item)
        for item in use_case.tasks.list(offset=offset, limit=limit)
    ]


@router.post(
    "/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
)
def create_task(payload: TaskCreate, use_case: ServiceDependency) -> TaskRead:
    return TaskRead.model_validate(use_case.create_task(payload))


@router.get("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def get_task(task_id: int, use_case: ServiceDependency) -> TaskRead:
    return TaskRead.model_validate(use_case.tasks.get(task_id))


@router.patch("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def update_task(
    task_id: int,
    payload: TaskUpdate,
    use_case: ServiceDependency,
) -> TaskRead:
    return TaskRead.model_validate(use_case.update_task(task_id, payload))


@router.get(
    "/reply-drafts",
    response_model=list[ReplyDraftRead],
    tags=["reply-drafts"],
)
def list_reply_drafts(
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
) -> list[ReplyDraftRead]:
    return [
        ReplyDraftRead.model_validate(item)
        for item in use_case.drafts.list(offset=offset, limit=limit)
    ]


@router.post(
    "/reply-drafts",
    response_model=ReplyDraftRead,
    status_code=status.HTTP_201_CREATED,
    tags=["reply-drafts"],
)
def create_reply_draft(
    payload: ReplyDraftCreate,
    use_case: ServiceDependency,
) -> ReplyDraftRead:
    return ReplyDraftRead.model_validate(use_case.create_draft(payload))


@router.get(
    "/reply-drafts/{draft_id}",
    response_model=ReplyDraftRead,
    tags=["reply-drafts"],
)
def get_reply_draft(
    draft_id: int,
    use_case: ServiceDependency,
) -> ReplyDraftRead:
    return ReplyDraftRead.model_validate(use_case.drafts.get(draft_id))


@router.patch(
    "/reply-drafts/{draft_id}",
    response_model=ReplyDraftRead,
    tags=["reply-drafts"],
)
def update_reply_draft(
    draft_id: int,
    payload: ReplyDraftUpdate,
    use_case: ServiceDependency,
) -> ReplyDraftRead:
    return ReplyDraftRead.model_validate(use_case.update_draft(draft_id, payload))
