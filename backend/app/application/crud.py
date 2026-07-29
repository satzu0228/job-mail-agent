from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.schemas import (
    JobApplicationCreate,
    JobApplicationUpdate,
    ReplyDraftCreate,
    ReplyDraftUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.domain.enums import ApplicationSource, ReplyDraftStatus
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.reply_draft import ReplyDraft
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.business import (
    EmailRepository,
    JobApplicationRepository,
    ReplyDraftRepository,
    TaskRepository,
    VersionConflictError,
)


class BusinessCrudService:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self.emails = EmailRepository(session, user_id)
        self.applications = JobApplicationRepository(session, user_id)
        self.tasks = TaskRepository(session, user_id)
        self.drafts = ReplyDraftRepository(session, user_id)
        self._user_id = user_id

    def create_application(self, data: JobApplicationCreate) -> JobApplication:
        with self._session.begin():
            self._ensure_demo_user()
            application = JobApplication(
                user_id=self._user_id,
                source=ApplicationSource.MANUAL,
                **self._db_values(data.model_dump()),
            )
            return self.applications.add(application)

    def update_application(
        self, application_id: int, data: JobApplicationUpdate
    ) -> JobApplication:
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            self._check_version(application.version, data.version)
            self._apply(
                application,
                self._db_values(
                    data.model_dump(exclude={"version"}, exclude_unset=True)
                ),
            )
            self._session.flush()
            return application

    def create_task(self, data: TaskCreate) -> Task:
        with self._session.begin():
            self._ensure_demo_user()
            if data.application_id is not None:
                self.applications.get(data.application_id)
            if data.source_email_id is not None:
                self.emails.get(data.source_email_id)
            task = Task(user_id=self._user_id, **self._db_values(data.model_dump()))
            return self.tasks.add(task)

    def update_task(self, task_id: int, data: TaskUpdate) -> Task:
        with self._session.begin():
            task = self.tasks.get(task_id, for_update=True)
            self._check_version(task.version, data.version)
            self._apply(
                task,
                self._db_values(
                    data.model_dump(exclude={"version"}, exclude_unset=True)
                ),
            )
            self._session.flush()
            return task

    def create_draft(self, data: ReplyDraftCreate) -> ReplyDraft:
        with self._session.begin():
            self.emails.get(data.email_id)
            if data.application_id is not None:
                self.applications.get(data.application_id)
            draft = ReplyDraft(version=0, **data.model_dump())
            return self.drafts.add_version(draft)

    def update_draft(self, draft_id: int, data: ReplyDraftUpdate) -> ReplyDraft:
        with self._session.begin():
            draft = self.drafts.get(draft_id, for_update=True)
            if draft.status is not ReplyDraftStatus.PENDING:
                raise VersionConflictError("只有待审核的最新回复草稿可以修改")
            latest = self._session.scalar(
                select(func.max(ReplyDraft.version)).where(
                    ReplyDraft.email_id == draft.email_id
                )
            )
            if latest != draft.version:
                raise VersionConflictError("旧版本回复草稿不能修改")
            draft.reviewed_body = data.reviewed_body
            self._session.flush()
            return draft

    @staticmethod
    def _check_version(actual: int, expected: int) -> None:
        if actual != expected:
            raise VersionConflictError(
                f"Resource version changed: expected {expected}, actual {actual}"
            )

    @staticmethod
    def _apply(target: object, values: dict[str, Any]) -> None:
        for name, value in values.items():
            setattr(target, name, value)

    @staticmethod
    def _db_values(values: dict[str, Any]) -> dict[str, Any]:
        return {
            name: (
                value.astimezone(UTC).replace(tzinfo=None)
                if isinstance(value, datetime)
                else value
            )
            for name, value in values.items()
        }

    def _ensure_demo_user(self) -> None:
        if self._session.get(User, self._user_id) is None:
            self._session.add(
                User(
                    id=self._user_id,
                    display_name="演示用户",
                    timezone="Asia/Shanghai",
                    reply_preferences={},
                )
            )
            self._session.flush()
