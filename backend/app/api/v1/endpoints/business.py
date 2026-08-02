from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.application.automation_rules import AutomationRuleService
from app.application.crud import BusinessCrudService
from app.application.email_access import (
    EmailAccessService,
    mask_email_address,
)
from app.application.reminders import ReminderService
from app.application.schemas import (
    ApplicationEventPage,
    ApplicationEventRead,
    AutomationRuleCreate,
    AutomationRuleExecuteResponse,
    AutomationRulePreview,
    AutomationRuleRead,
    AutomationRuleUpdate,
    EmailAccountActiveUpdate,
    EmailAccountAuthorizationUpdate,
    EmailAccountCreate,
    EmailAccountRead,
    EmailAccountSyncSettingsUpdate,
    EmailConnectionTestResult,
    EmailDetail,
    EmailListItem,
    EmailPage,
    EmailSyncRequest,
    EmailSyncResult,
    InterviewRoundRead,
    InterviewRoundResultResponse,
    InterviewRoundResultUpdate,
    InterviewTaskWithdrawApplication,
    JobApplicationCreate,
    JobApplicationInterviewResultUpdate,
    JobApplicationNextInterviewCreate,
    JobApplicationNextInterviewResponse,
    JobApplicationOfferResultUpdate,
    JobApplicationPage,
    JobApplicationRead,
    JobApplicationReopen,
    JobApplicationStageTransition,
    JobApplicationUpdate,
    ReminderRead,
    ReminderReadUpdate,
    ReplyDraftCreate,
    ReplyDraftRead,
    ReplyDraftUpdate,
    TaskCreate,
    TaskPage,
    TaskRead,
    TaskUpdate,
)
from app.core.config import Settings, get_settings
from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    ArchiveStatus,
    EmailCategory,
    EmailDirection,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.db.session import get_db_session

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
PageOffset = Annotated[int, Query(ge=0)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
ApplicationStatusFilter = Annotated[ApplicationStatus | None, Query(alias="status")]
TaskStatusFilter = Annotated[TaskStatus | None, Query(alias="status")]


def service(session: SessionDependency, settings: SettingsDependency) -> BusinessCrudService:
    return BusinessCrudService(session, settings.demo_user_id)


ServiceDependency = Annotated[BusinessCrudService, Depends(service)]


def automation_rule_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> AutomationRuleService:
    return AutomationRuleService(session, settings.demo_user_id)


AutomationRuleDependency = Annotated[
    AutomationRuleService,
    Depends(automation_rule_service),
]


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
        email_address=account.email_address,
        email_address_masked=mask_email_address(account.email_address),
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_security=account.imap_security,
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_security=account.smtp_security,
        credential_configured=bool(account.credential_ciphertext),
        is_active=account.is_active,
        auto_sync_enabled=bool(account.auto_sync_enabled),
        sync_interval_minutes=account.sync_interval_minutes or 10,
        next_sync_at=account.next_sync_at,
        last_auto_sync_at=account.last_auto_sync_at,
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


@router.patch(
    "/email-accounts/{account_id}/authorization-code",
    response_model=EmailAccountRead,
    tags=["email-accounts"],
)
def update_email_account_authorization_code(
    account_id: int,
    payload: EmailAccountAuthorizationUpdate,
    use_case: EmailAccessDependency,
) -> EmailAccountRead:
    return _account_read(
        use_case.update_authorization_code(
            account_id,
            authorization_code=payload.authorization_code,
        )
    )


@router.patch(
    "/email-accounts/{account_id}/active",
    response_model=EmailAccountRead,
    tags=["email-accounts"],
)
def set_email_account_active(
    account_id: int,
    payload: EmailAccountActiveUpdate,
    use_case: EmailAccessDependency,
) -> EmailAccountRead:
    return _account_read(
        use_case.set_account_active(account_id, is_active=payload.is_active)
    )


@router.patch(
    "/email-accounts/{account_id}/sync-settings",
    response_model=EmailAccountRead,
    tags=["email-accounts"],
)
def update_email_account_sync_settings(
    account_id: int,
    payload: EmailAccountSyncSettingsUpdate,
    use_case: EmailAccessDependency,
) -> EmailAccountRead:
    return _account_read(
        use_case.update_sync_settings(
            account_id,
            enabled=payload.enabled,
            interval_minutes=payload.interval_minutes,
        )
    )


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


@router.get("/emails/query", response_model=EmailPage, tags=["emails"])
def query_emails(
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
    account_id: int | None = Query(default=None, gt=0),
    keyword: str | None = Query(default=None, max_length=200),
    application_id: int | None = Query(default=None, gt=0),
    linked: bool | None = None,
    category: EmailCategory | None = None,
    direction: EmailDirection | None = None,
    archive_status: ArchiveStatus | None = None,
) -> EmailPage:
    items, total = use_case.emails.query(
        offset=offset,
        limit=limit,
        account_id=account_id,
        keyword=keyword,
        application_id=application_id,
        linked=linked,
        category=category,
        direction=direction,
        archive_status=archive_status,
    )
    return EmailPage(
        items=[EmailListItem.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/emails/{email_id}/attachments/{attachment_index}",
    tags=["emails"],
)
def download_email_attachment(
    email_id: int,
    attachment_index: int,
    use_case: EmailAccessDependency,
) -> Response:
    attachment = use_case.download_attachment(email_id, attachment_index)
    safe_ascii_characters = frozenset(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- "
    )
    ascii_name = "".join(
        character if character in safe_ascii_characters else "_"
        for character in attachment.filename
    ).strip() or "attachment"
    disposition = (
        f"attachment; filename=\"{ascii_name}\"; "
        f"filename*=UTF-8''{quote(attachment.filename, safe='')}"
    )
    return Response(
        content=attachment.content,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/emails/{email_id}", response_model=EmailDetail, tags=["emails"])
def get_email(email_id: int, use_case: ServiceDependency) -> EmailDetail:
    return EmailDetail.model_validate(use_case.emails.get(email_id))


@router.post(
    "/emails/{email_id}/refresh-content",
    response_model=EmailDetail,
    tags=["emails"],
)
def refresh_email_content(
    email_id: int,
    use_case: EmailAccessDependency,
) -> EmailDetail:
    return EmailDetail.model_validate(use_case.refresh_content(email_id))


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


@router.get(
    "/job-applications/query",
    response_model=JobApplicationPage,
    tags=["job-applications"],
)
def query_applications(
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
    keyword: str | None = Query(default=None, max_length=200),
    stage: ApplicationStage | None = None,
    application_status: ApplicationStatusFilter = None,
) -> JobApplicationPage:
    items, total = use_case.applications.query(
        offset=offset,
        limit=limit,
        keyword=keyword,
        stage=stage,
        status=application_status,
    )
    return JobApplicationPage(
        items=[JobApplicationRead.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/job-applications/{application_id}/events",
    response_model=ApplicationEventPage,
    tags=["job-applications"],
)
def list_application_events(
    application_id: int,
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
) -> ApplicationEventPage:
    items, total = use_case.applications.list_events(
        application_id,
        offset=offset,
        limit=limit,
    )
    return ApplicationEventPage(
        items=[ApplicationEventRead.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


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


@router.post(
    "/job-applications/{application_id}/stage-transitions",
    response_model=JobApplicationRead,
    tags=["job-applications"],
)
def transition_application_stage(
    application_id: int,
    payload: JobApplicationStageTransition,
    use_case: ServiceDependency,
) -> JobApplicationRead:
    return JobApplicationRead.model_validate(
        use_case.transition_application_stage(application_id, payload)
    )


@router.post(
    "/job-applications/{application_id}/interview-result",
    response_model=JobApplicationRead,
    tags=["job-applications"],
)
def update_application_interview_result(
    application_id: int,
    payload: JobApplicationInterviewResultUpdate,
    use_case: ServiceDependency,
) -> JobApplicationRead:
    return JobApplicationRead.model_validate(
        use_case.update_interview_result(application_id, payload)
    )


@router.post(
    "/job-applications/{application_id}/next-interview",
    response_model=JobApplicationNextInterviewResponse,
    tags=["job-applications"],
)
def schedule_application_next_interview(
    application_id: int,
    payload: JobApplicationNextInterviewCreate,
    use_case: ServiceDependency,
) -> JobApplicationNextInterviewResponse:
    application, task = use_case.schedule_next_interview(application_id, payload)
    return JobApplicationNextInterviewResponse(
        application=JobApplicationRead.model_validate(application),
        task=TaskRead.model_validate(task),
    )


@router.post(
    "/job-applications/{application_id}/offer-result",
    response_model=JobApplicationRead,
    tags=["job-applications"],
)
def update_application_offer_result(
    application_id: int,
    payload: JobApplicationOfferResultUpdate,
    use_case: ServiceDependency,
) -> JobApplicationRead:
    return JobApplicationRead.model_validate(
        use_case.update_offer_result(application_id, payload)
    )


@router.post(
    "/job-applications/{application_id}/reopen",
    response_model=JobApplicationRead,
    tags=["job-applications"],
)
def reopen_application(
    application_id: int,
    payload: JobApplicationReopen,
    use_case: ServiceDependency,
) -> JobApplicationRead:
    return JobApplicationRead.model_validate(
        use_case.reopen_application(application_id, payload)
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


@router.get("/tasks/query", response_model=TaskPage, tags=["tasks"])
def query_tasks(
    use_case: ServiceDependency,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
    application_id: int | None = Query(default=None, gt=0),
    task_status: TaskStatusFilter = None,
    task_type: TaskType | None = None,
    start_from: Annotated[datetime | None, Query()] = None,
    start_to: Annotated[datetime | None, Query()] = None,
) -> TaskPage:
    items, total = use_case.tasks.query(
        offset=offset,
        limit=limit,
        application_id=application_id,
        status=task_status,
        task_type=task_type,
        start_from=start_from,
        start_to=start_to,
    )
    return TaskPage(
        items=[TaskRead.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


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


@router.post(
    "/tasks/{task_id}/withdraw-application",
    response_model=TaskRead,
    tags=["tasks"],
)
def withdraw_application_from_interview_task(
    task_id: int,
    payload: InterviewTaskWithdrawApplication,
    use_case: ServiceDependency,
) -> TaskRead:
    return TaskRead.model_validate(
        use_case.withdraw_application_from_interview_task(task_id, payload)
    )


@router.post(
    "/emails/{email_id}/link-application",
    response_model=EmailDetail,
    tags=["emails"],
)
def link_email_to_application(
    email_id: int,
    application_id: Annotated[int, Query(gt=0, alias="application_id")],
    use_case: ServiceDependency,
) -> EmailDetail:
    return EmailDetail.model_validate(
        use_case.link_email_application(email_id, application_id)
    )


@router.get(
    "/job-applications/{application_id}/interview-rounds",
    response_model=list[InterviewRoundRead],
    tags=["interview-rounds"],
)
def list_interview_rounds(
    application_id: int,
    use_case: ServiceDependency,
) -> list[InterviewRoundRead]:
    return [
        InterviewRoundRead.model_validate(item)
        for item in use_case.list_interview_rounds(application_id)
    ]


@router.put(
    "/job-applications/{application_id}/interview-rounds/{round_number}/result",
    response_model=InterviewRoundResultResponse,
    tags=["interview-rounds"],
)
def update_interview_round_result(
    application_id: int,
    round_number: int,
    payload: InterviewRoundResultUpdate,
    use_case: ServiceDependency,
) -> InterviewRoundResultResponse:
    application, round_record = use_case.update_interview_round_result(
        application_id,
        round_number,
        payload,
    )
    return InterviewRoundResultResponse(
        application=JobApplicationRead.model_validate(application),
        round=InterviewRoundRead.model_validate(round_record),
    )


@router.get("/reminders", response_model=list[ReminderRead], tags=["reminders"])
def list_reminders(
    session: SessionDependency,
    settings: SettingsDependency,
    unread_only: bool = False,
    offset: PageOffset = 0,
    limit: PageLimit = 50,
) -> list[ReminderRead]:
    reminders = ReminderService(session, settings.demo_user_id).list(
        unread_only=unread_only,
        offset=offset,
        limit=limit,
    )
    return [ReminderRead.model_validate(item) for item in reminders]


@router.patch(
    "/reminders/{reminder_id}/read",
    response_model=ReminderRead,
    tags=["reminders"],
)
def update_reminder_read(
    reminder_id: int,
    payload: ReminderReadUpdate,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReminderRead:
    reminder = ReminderService(session, settings.demo_user_id).set_read(
        reminder_id,
        read=payload.read,
    )
    return ReminderRead.model_validate(reminder)


@router.get(
    "/automation-rules",
    response_model=list[AutomationRuleRead],
    tags=["automation-rules"],
)
def list_automation_rules(
    use_case: AutomationRuleDependency,
) -> list[AutomationRuleRead]:
    return [AutomationRuleRead.model_validate(item) for item in use_case.list()]


@router.post(
    "/automation-rules",
    response_model=AutomationRuleRead,
    status_code=status.HTTP_201_CREATED,
    tags=["automation-rules"],
)
def create_automation_rule(
    payload: AutomationRuleCreate,
    use_case: AutomationRuleDependency,
) -> AutomationRuleRead:
    return AutomationRuleRead.model_validate(use_case.create(payload))


@router.patch(
    "/automation-rules/{rule_id}",
    response_model=AutomationRuleRead,
    tags=["automation-rules"],
)
def update_automation_rule(
    rule_id: int,
    payload: AutomationRuleUpdate,
    use_case: AutomationRuleDependency,
) -> AutomationRuleRead:
    return AutomationRuleRead.model_validate(use_case.update(rule_id, payload))


@router.get(
    "/automation-rules/{rule_id}/preview",
    response_model=AutomationRulePreview,
    tags=["automation-rules"],
)
def preview_automation_rule(
    rule_id: int,
    use_case: AutomationRuleDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AutomationRulePreview:
    rule = use_case.get(rule_id)
    candidates, total = use_case.preview(rule_id, limit=limit)
    return AutomationRulePreview(
        rule=AutomationRuleRead.model_validate(rule),
        candidates=[EmailListItem.model_validate(item) for item in candidates],
        total=total,
    )


@router.post(
    "/automation-rules/{rule_id}/execute",
    response_model=AutomationRuleExecuteResponse,
    tags=["automation-rules"],
)
def execute_automation_rule(
    rule_id: int,
    use_case: AutomationRuleDependency,
) -> AutomationRuleExecuteResponse:
    return use_case.execute(rule_id)


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
