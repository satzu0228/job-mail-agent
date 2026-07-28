from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.email import Email
from app.infrastructure.db.models.email_account import EmailAccount
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


class EmailRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def list(self, *, offset: int, limit: int) -> list[Email]:
        statement = (
            select(Email)
            .join(EmailAccount, Email.account_id == EmailAccount.id)
            .where(EmailAccount.user_id == self._user_id)
            .order_by(Email.received_at.desc(), Email.id.desc())
        )
        return list(self._session.scalars(_paginate(statement, offset=offset, limit=limit)))

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

    def list(self, *, offset: int, limit: int) -> list[JobApplication]:
        statement = (
            select(JobApplication)
            .where(JobApplication.user_id == self._user_id)
            .order_by(JobApplication.updated_at.desc(), JobApplication.id.desc())
        )
        return list(self._session.scalars(_paginate(statement, offset=offset, limit=limit)))

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


class TaskRepository:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def list(self, *, offset: int, limit: int) -> list[Task]:
        statement = (
            select(Task)
            .where(Task.user_id == self._user_id)
            .order_by(Task.start_at.asc(), Task.deadline_at.asc(), Task.id.desc())
        )
        return list(self._session.scalars(_paginate(statement, offset=offset, limit=limit)))

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
