from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session

from app.infrastructure.db.models.application_event import ApplicationEvent
from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_account import EmailAccount
from app.infrastructure.db.models.email_analysis import EmailAnalysis
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.reply_draft import ReplyDraft
from app.infrastructure.db.models.task import Task


class EntityNotFoundError(LookupError):
    pass


class VersionConflictError(RuntimeError):
    pass


class ResourceConflictError(RuntimeError):
    pass


def _paginate(statement: Select[tuple[object]], *, offset: int, limit: int) -> Select:
    return statement.offset(offset).limit(limit)


class EmailAccountRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def list(self) -> list[EmailAccount]:
        statement = (
            select(EmailAccount)
            .where(EmailAccount.user_id == self._user_id)
            .order_by(EmailAccount.id)
        )
        return list(self._session.scalars(statement))

    def get(self, account_id: int, *, for_update: bool = False) -> EmailAccount:
        statement = select(EmailAccount).where(
            EmailAccount.id == account_id,
            EmailAccount.user_id == self._user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        account = self._session.scalar(statement)
        if account is None:
            raise EntityNotFoundError(f"Email account {account_id} does not exist")
        return account

    def add(self, account: EmailAccount) -> EmailAccount:
        self._session.add(account)
        self._session.flush()
        return account

    def deactivate_others(self, *, except_account_id: int | None = None) -> None:
        statement = update(EmailAccount).where(
            EmailAccount.user_id == self._user_id,
            EmailAccount.is_active.is_(True),
        )
        if except_account_id is not None:
            statement = statement.where(EmailAccount.id != except_account_id)
        self._session.execute(statement.values(is_active=False))


class EmailRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def get(self, email_id: int) -> Email:
        statement = (
            select(Email)
            .join(EmailAccount, Email.account_id == EmailAccount.id)
            .where(Email.id == email_id, EmailAccount.user_id == self._user_id)
        )
        email = self._session.scalar(statement)
        if email is None:
            raise EntityNotFoundError(f"Email {email_id} does not exist")
        return email

    def query(
        self,
        *,
        offset: int,
        limit: int,
        account_id: int | None = None,
        keyword: str | None = None,
        application_id: int | None = None,
        linked: bool | None = None,
        category: str | None = None,
        direction: str | None = None,
        archive_status: str | None = None,
    ) -> tuple[list[Email], int]:
        conditions = [EmailAccount.user_id == self._user_id]
        if account_id is not None:
            conditions.append(Email.account_id == account_id)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    Email.subject.like(pattern),
                    Email.from_name.like(pattern),
                    Email.from_address.like(pattern),
                )
            )
        if application_id is not None:
            conditions.append(Email.application_id == application_id)
        if linked is True:
            conditions.append(Email.application_id.is_not(None))
        elif linked is False:
            conditions.append(Email.application_id.is_(None))
        if archive_status:
            conditions.append(Email.archive_status == archive_status)
        if direction == "SENT":
            conditions.append(
                func.lower(Email.from_address) == func.lower(EmailAccount.email_address)
            )
        elif direction == "RECEIVED":
            conditions.append(
                func.lower(Email.from_address) != func.lower(EmailAccount.email_address)
            )
        statement = select(Email).join(EmailAccount).where(*conditions)
        count_statement = (
            select(func.count(Email.id)).join(EmailAccount).where(*conditions)
        )
        if category:
            statement = statement.join(
                EmailAnalysis,
                (EmailAnalysis.email_id == Email.id)
                & EmailAnalysis.is_current.is_(True),
            ).where(EmailAnalysis.category == category)
            count_statement = count_statement.join(
                EmailAnalysis,
                (EmailAnalysis.email_id == Email.id)
                & EmailAnalysis.is_current.is_(True),
            ).where(EmailAnalysis.category == category)
        total = int(self._session.scalar(count_statement) or 0)
        statement = statement.order_by(
            Email.received_at.desc(), Email.id.desc()
        )
        return (
            list(
                self._session.scalars(
                    _paginate(statement, offset=offset, limit=limit)
                )
            ),
            total,
        )

    def find_by_imap_identity(
        self,
        *,
        account_id: int,
        source_folder: str,
        uid_validity: int,
        imap_uid: int,
    ) -> Email | None:
        return self._session.scalar(
            select(Email).where(
                Email.account_id == account_id,
                Email.source_folder == source_folder,
                Email.uid_validity == uid_validity,
                Email.imap_uid == imap_uid,
            )
        )

    def find_by_message_id(
        self,
        *,
        account_id: int,
        message_id: str,
    ) -> Email | None:
        return self._session.scalar(
            select(Email).where(
                Email.account_id == account_id,
                Email.message_id == message_id,
            )
        )

    def add(self, email: Email) -> Email:
        self._session.add(email)
        self._session.flush()
        return email


class JobApplicationRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def get(self, application_id: int, *, for_update: bool = False) -> JobApplication:
        statement = select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == self._user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        application = self._session.scalar(statement)
        if application is None:
            raise EntityNotFoundError(
                f"Job application {application_id} does not exist"
            )
        return application

    def add(self, application: JobApplication) -> JobApplication:
        self._session.add(application)
        self._session.flush()
        return application

    def query(
        self,
        *,
        offset: int,
        limit: int,
        keyword: str | None = None,
        stage: str | None = None,
        status: str | None = None,
    ) -> tuple[list[JobApplication], int]:
        conditions = [JobApplication.user_id == self._user_id]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    JobApplication.company_name.like(pattern),
                    JobApplication.company_alias.like(pattern),
                    JobApplication.position_name.like(pattern),
                )
            )
        if stage:
            conditions.append(JobApplication.current_stage == stage)
        if status:
            conditions.append(JobApplication.status == status)
        total = int(
            self._session.scalar(
                select(func.count(JobApplication.id)).where(*conditions)
            )
            or 0
        )
        statement = (
            select(JobApplication)
            .where(*conditions)
            .order_by(JobApplication.updated_at.desc(), JobApplication.id.desc())
        )
        return (
            list(
                self._session.scalars(
                    _paginate(statement, offset=offset, limit=limit)
                )
            ),
            total,
        )

    def list_events(
        self,
        application_id: int,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[ApplicationEvent], int]:
        self.get(application_id)
        condition = ApplicationEvent.application_id == application_id
        total = int(
            self._session.scalar(
                select(func.count(ApplicationEvent.id)).where(condition)
            )
            or 0
        )
        statement = (
            select(ApplicationEvent)
            .where(condition)
            .order_by(
                ApplicationEvent.event_at.desc(),
                ApplicationEvent.created_at.desc(),
                ApplicationEvent.id.desc(),
            )
        )
        return (
            list(
                self._session.scalars(
                    _paginate(statement, offset=offset, limit=limit)
                )
            ),
            total,
        )


class TaskRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def get(self, task_id: int, *, for_update: bool = False) -> Task:
        statement = select(Task).where(
            Task.id == task_id,
            Task.user_id == self._user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        task = self._session.scalar(statement)
        if task is None:
            raise EntityNotFoundError(f"Task {task_id} does not exist")
        return task

    def add(self, task: Task) -> Task:
        self._session.add(task)
        self._session.flush()
        return task

    def query(
        self,
        *,
        offset: int,
        limit: int,
        application_id: int | None = None,
        status: str | None = None,
        task_type: str | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
    ) -> tuple[list[Task], int]:
        conditions = [Task.user_id == self._user_id]
        if application_id is not None:
            conditions.append(Task.application_id == application_id)
        if status:
            conditions.append(Task.status == status)
        if task_type:
            conditions.append(Task.task_type == task_type)
        if start_from is not None:
            conditions.append(
                or_(
                    Task.start_at >= _db_datetime(start_from),
                    Task.deadline_at >= _db_datetime(start_from),
                )
            )
        if start_to is not None:
            conditions.append(
                or_(
                    Task.start_at <= _db_datetime(start_to),
                    Task.deadline_at <= _db_datetime(start_to),
                )
            )
        total = int(
            self._session.scalar(select(func.count(Task.id)).where(*conditions))
            or 0
        )
        statement = (
            select(Task)
            .where(*conditions)
            .order_by(Task.start_at.asc(), Task.deadline_at.asc(), Task.id.desc())
        )
        return (
            list(
                self._session.scalars(
                    _paginate(statement, offset=offset, limit=limit)
                )
            ),
            total,
        )


class ReplyDraftRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def list(self, *, offset: int, limit: int) -> list[ReplyDraft]:
        statement = (
            select(ReplyDraft)
            .join(Email, ReplyDraft.email_id == Email.id)
            .join(EmailAccount, Email.account_id == EmailAccount.id)
            .where(EmailAccount.user_id == self._user_id)
            .order_by(ReplyDraft.updated_at.desc(), ReplyDraft.id.desc())
        )
        return list(self._session.scalars(_paginate(statement, offset=offset, limit=limit)))

    def get(self, draft_id: int, *, for_update: bool = False) -> ReplyDraft:
        statement = (
            select(ReplyDraft)
            .join(Email, ReplyDraft.email_id == Email.id)
            .join(EmailAccount, Email.account_id == EmailAccount.id)
            .where(ReplyDraft.id == draft_id, EmailAccount.user_id == self._user_id)
        )
        if for_update:
            statement = statement.with_for_update()
        draft = self._session.scalar(statement)
        if draft is None:
            raise EntityNotFoundError(f"Reply draft {draft_id} does not exist")
        return draft

    def add_version(self, draft: ReplyDraft) -> ReplyDraft:
        email = EmailRepository(self._session, self._user_id).get(draft.email_id)
        self._session.scalar(
            select(Email.id).where(Email.id == email.id).with_for_update()
        )
        latest = self._session.scalar(
            select(ReplyDraft.version)
            .where(ReplyDraft.email_id == email.id)
            .order_by(ReplyDraft.version.desc())
            .limit(1)
        )
        draft.version = (latest or 0) + 1
        self._session.add(draft)
        self._session.flush()
        return draft


def _db_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
