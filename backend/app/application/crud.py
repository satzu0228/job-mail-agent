from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.application.schemas import (
    InterviewTaskWithdrawApplication,
    JobApplicationCreate,
    JobApplicationInterviewResultUpdate,
    JobApplicationStageTransition,
    JobApplicationUpdate,
    ReplyDraftCreate,
    ReplyDraftUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.application.task_linkage import settle_interview_tasks
from app.domain.application_state import validate_stage_transition
from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    ApplicationStatus,
    InterviewResult,
    ReplyDraftStatus,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.models.application_event import ApplicationEvent
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.reminder import Reminder
from app.infrastructure.db.models.reply_draft import ReplyDraft
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.business import (
    EmailRepository,
    JobApplicationRepository,
    ReplyDraftRepository,
    ResourceConflictError,
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

    def transition_application_stage(
        self,
        application_id: int,
        data: JobApplicationStageTransition,
    ) -> JobApplication:
        """执行用户明确确认的手动阶段变更，并写入可追踪时间线。"""
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            self._check_version(application.version, data.version)
            validation = validate_stage_transition(
                application.current_stage,
                data.proposed_stage,
            )
            if not validation.can_apply:
                raise ResourceConflictError(validation.reason)

            previous = application.current_stage
            application.current_stage = data.proposed_stage
            if data.proposed_stage is ApplicationStage.REJECTED:
                application.status = ApplicationStatus.CLOSED
            elif data.proposed_stage is ApplicationStage.WITHDRAWN:
                application.status = ApplicationStatus.WITHDRAWN
            else:
                application.status = ApplicationStatus.ACTIVE
            if previous is ApplicationStage.INTERVIEW:
                settle_interview_tasks(
                    self._session,
                    application_id=application.id,
                    status=(
                        TaskStatus.CANCELLED
                        if data.proposed_stage is ApplicationStage.WITHDRAWN
                        else TaskStatus.COMPLETED
                    ),
                    current_round_only=False,
                )
            self._session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event_type="MANUAL_STAGE_CHANGED",
                    previous_stage=previous,
                    proposed_stage=data.proposed_stage,
                    confirmed_stage=data.proposed_stage,
                    event_at=datetime.now(UTC).replace(tzinfo=None),
                    details={
                        "decision_source": "USER",
                        "reason": data.reason,
                    },
                )
            )
            self._session.flush()
            return application

    def update_interview_result(
        self,
        application_id: int,
        data: JobApplicationInterviewResultUpdate,
    ) -> JobApplication:
        """记录用户确认的面试结果；结果与宏观求职阶段分别保存。"""
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            self._check_version(application.version, data.version)
            if application.current_stage is not ApplicationStage.INTERVIEW:
                raise ResourceConflictError("只有面试阶段的申请可以记录面试结果")

            previous_result = application.interview_result
            application.interview_result = data.result
            application.status = (
                ApplicationStatus.CLOSED
                if data.result is InterviewResult.FAILED
                else ApplicationStatus.ACTIVE
            )
            if data.result in {InterviewResult.PASSED, InterviewResult.FAILED}:
                settle_interview_tasks(
                    self._session,
                    application_id=application.id,
                    status=TaskStatus.COMPLETED,
                    current_round_only=True,
                )
            interview_round = self._session.scalar(
                select(func.max(Task.interview_round)).where(
                    Task.application_id == application.id,
                    Task.task_type == TaskType.INTERVIEW,
                )
            )
            self._session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event_type="INTERVIEW_RESULT_CHANGED",
                    previous_stage=application.current_stage,
                    proposed_stage=application.current_stage,
                    confirmed_stage=application.current_stage,
                    event_at=datetime.now(UTC).replace(tzinfo=None),
                    details={
                        "decision_source": "USER",
                        "previous_result": (
                            previous_result.value if previous_result else None
                        ),
                        "interview_result": data.result.value,
                        "interview_round": interview_round,
                        "reason": data.reason,
                    },
                )
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
            if (
                task.task_type is TaskType.INTERVIEW
                and data.status is TaskStatus.CANCELLED
            ):
                raise ResourceConflictError(
                    "取消面试需要选择调整时间或放弃关联申请"
                )
            if {"start_at", "deadline_at"} & data.model_fields_set:
                self._session.execute(
                    delete(Reminder).where(Reminder.task_id == task.id)
                )
            self._apply(
                task,
                self._db_values(
                    data.model_dump(exclude={"version"}, exclude_unset=True)
                ),
            )
            self._session.flush()
            return task

    def withdraw_application_from_interview_task(
        self,
        task_id: int,
        data: InterviewTaskWithdrawApplication,
    ) -> Task:
        """用户从面试日程放弃申请，并在同一事务取消关联日程。"""
        with self._session.begin():
            task = self.tasks.get(task_id, for_update=True)
            self._check_version(task.version, data.version)
            if task.task_type is not TaskType.INTERVIEW or task.application_id is None:
                raise ResourceConflictError("只有已关联申请的面试日程支持放弃申请")
            application = self.applications.get(task.application_id, for_update=True)
            self._check_version(application.version, data.application_version)
            previous = application.current_stage
            application.current_stage = ApplicationStage.WITHDRAWN
            application.status = ApplicationStatus.WITHDRAWN
            cancelled_count = settle_interview_tasks(
                self._session,
                application_id=application.id,
                status=TaskStatus.CANCELLED,
                current_round_only=False,
            )
            self._session.add(
                ApplicationEvent(
                    application_id=application.id,
                    event_type="APPLICATION_WITHDRAWN_FROM_CALENDAR",
                    previous_stage=previous,
                    proposed_stage=ApplicationStage.WITHDRAWN,
                    confirmed_stage=ApplicationStage.WITHDRAWN,
                    event_at=datetime.now(UTC).replace(tzinfo=None),
                    details={
                        "decision_source": "USER",
                        "task_id": task.id,
                        "cancelled_task_count": cancelled_count,
                        "reason": data.reason,
                    },
                )
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
