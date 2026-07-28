from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.application.crud import BusinessCrudService
from app.application.email_access import (
    EmailAccessService,
    mask_email_address,
)
from app.application.schemas import (
    EmailAccountCreate,
    EmailAccountRead,
    EmailConnectionTestResult,
    EmailDetail,
    EmailListItem,
    EmailSyncRequest,
    EmailSyncResult,
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
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.db.session import get_db_session

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
PageOffset = Annotated[int, Query(ge=0)]
PageLimit = Annotated[int, Query(ge=1, le=100)]


def service(session: SessionDependency, settings: SettingsDependency) -> BusinessCrudService:
    return BusinessCrudService(session, settings.demo_user_id)


ServiceDependency = Annotated[BusinessCrudService, Depends(service)]


def email_access_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> EmailAccessService:
    return EmailAccessService(
        session,
        settings.demo_user_id,
        timeout_seconds=settings.email_connect_timeout_seconds,
        default_sync_limit=settings.email_sync_limit,
        max_message_bytes=settings.email_max_message_bytes,
    )


EmailAccessDependency = Annotated[EmailAccessService, Depends(email_access_service)]


def _account_read(account: EmailAccount) -> EmailAccountRead:
    return EmailAccountRead(
        id=account.id,
        provider=account.provider,
        email_address_masked=mask_email_address(account.email_address),
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_security=account.imap_security,
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_security=account.smtp_security,
        is_active=account.is_active,
        inbox_uid_validity=account.inbox_uid_validity,
        last_synced_uid=account.last_synced_uid,
        last_sync_at=account.last_sync_at,
        last_sync_status=account.last_sync_status,
        last_sync_error=account.last_sync_error,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.get(
    "/email-accounts",
    response_model=list[EmailAccountRead],
    tags=["email-accounts"],
)
def list_email_accounts(
    use_case: EmailAccessDependency,
) -> list[EmailAccountRead]:
    return [_account_read(account) for account in use_case.accounts.list()]


@router.post(
    "/email-accounts",
    response_model=EmailAccountRead,
    status_code=status.HTTP_201_CREATED,
    tags=["email-accounts"],
)
def create_email_account(
    payload: EmailAccountCreate,
    use_case: EmailAccessDependency,
) -> EmailAccountRead:
    return _account_read(use_case.create_account(payload))


@router.post(
    "/email-accounts/{account_id}/test-connection",
    response_model=EmailConnectionTestResult,
    tags=["email-accounts"],
)
def test_email_account_connection(
    account_id: int,
    use_case: EmailAccessDependency,
) -> EmailConnectionTestResult:
    return use_case.test_connection(account_id)


@router.post(
    "/email-accounts/{account_id}/sync",
    response_model=EmailSyncResult,
    tags=["email-accounts"],
)
def sync_email_account(
    account_id: int,
    use_case: EmailAccessDependency,
    payload: EmailSyncRequest | None = None,
) -> EmailSyncResult:
    return use_case.sync(account_id, limit=payload.limit if payload else None)


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
