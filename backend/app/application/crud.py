from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.application.application_commands import ApplicationCommandHandler
from app.application.schemas import (
    InterviewRoundResultUpdate,
    InterviewTaskWithdrawApplication,
    JobApplicationCreate,
    JobApplicationInterviewResultUpdate,
    JobApplicationNextInterviewCreate,
    JobApplicationOfferResultUpdate,
    JobApplicationReopen,
    JobApplicationStageTransition,
    JobApplicationUpdate,
    ReplyDraftCreate,
    ReplyDraftUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.domain.application import (
    CommandContext,
    InterviewApplicationOutcome,
    RecordInterviewResultCommand,
    RecordInterviewScheduleCommand,
    RecordOfferDecisionCommand,
    ReopenApplicationCommand,
    ScheduleInterviewRoundCommand,
    TransitionApplicationCommand,
)
from app.domain.enums import (
    ApplicationSource,
    ApplicationStage,
    DecisionSource,
    InterviewResult,
    InterviewRoundSource,
    ReplyDraftStatus,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.models.application_event import ApplicationEvent
from app.infrastructure.db.models.interview_round import InterviewRound
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
            self._application_commands().transition_stage(
                application,
                TransitionApplicationCommand(
                    application_id=application_id,
                    expected_version=data.version,
                    proposed_stage=data.proposed_stage,
                    context=CommandContext(
                        reason=data.reason,
                        decision_source=DecisionSource.USER,
                    ),
                    event_type="MANUAL_STAGE_CHANGED",
                ),
            )
            return application

    def update_interview_result(
        self,
        application_id: int,
        data: JobApplicationInterviewResultUpdate,
    ) -> JobApplication:
        """记录用户确认的面试结果；结果与宏观求职阶段分别保存。"""
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            round_number = self._session.scalar(
                select(func.max(InterviewRound.round_number)).where(
                    InterviewRound.application_id == application.id
                )
            )
            self._application_commands().record_interview_result(
                application,
                RecordInterviewResultCommand(
                    application_id=application_id,
                    expected_version=data.version,
                    round_number=int(round_number or 1),
                    result=data.result,
                    outcome=(
                        InterviewApplicationOutcome.CLOSE_AS_REJECTED
                        if data.result is InterviewResult.FAILED
                        and data.close_application
                        else InterviewApplicationOutcome.KEEP_ACTIVE
                    ),
                    round_source=InterviewRoundSource.MANUAL,
                    context=CommandContext(
                        reason=data.reason,
                        decision_source=DecisionSource.USER,
                    ),
                ),
            )
            return application

    def schedule_next_interview(
        self,
        application_id: int,
        data: JobApplicationNextInterviewCreate,
    ) -> tuple[JobApplication, Task]:
        """在同一事务中登记下一轮面试，并将新一轮结果恢复为待确认。"""
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            _, _, task = self._application_commands().schedule_next_interview(
                application,
                ScheduleInterviewRoundCommand(
                    application_id=application_id,
                    expected_version=data.version,
                    title=data.title,
                    start_at=self._db_values({"value": data.start_at})["value"],
                    deadline_at=self._db_values({"value": data.deadline_at})["value"],
                    raw_time_text=data.raw_time_text,
                    source_timezone=data.source_timezone,
                    location=data.location,
                    meeting_url=data.meeting_url,
                    context=CommandContext(
                        reason=data.reason,
                        decision_source=DecisionSource.USER,
                    ),
                ),
            )
            return application, task

    def update_offer_result(
        self,
        application_id: int,
        data: JobApplicationOfferResultUpdate,
    ) -> JobApplication:
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            self._application_commands().record_offer_decision(
                application,
                RecordOfferDecisionCommand(
                    application_id=application_id,
                    expected_version=data.version,
                    result=data.result,
                    context=CommandContext(
                        reason=data.reason,
                        decision_source=DecisionSource.USER,
                    ),
                ),
            )
            return application

    def reopen_application(
        self,
        application_id: int,
        data: JobApplicationReopen,
    ) -> JobApplication:
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            self._application_commands().reopen(
                application,
                ReopenApplicationCommand(
                    application_id=application_id,
                    expected_version=data.version,
                    target_stage=data.target_stage,
                    context=CommandContext(
                        reason=data.reason,
                        decision_source=DecisionSource.USER,
                    ),
                ),
            )
            return application

    def create_task(self, data: TaskCreate) -> Task:
        with self._session.begin():
            self._ensure_demo_user()
            application = None
            if data.application_id is not None:
                application = self.applications.get(data.application_id)
            if data.source_email_id is not None:
                self.emails.get(data.source_email_id)
            task = Task(user_id=self._user_id, **self._db_values(data.model_dump()))
            task = self.tasks.add(task)
            if data.task_type is TaskType.INTERVIEW:
                if application is None or data.interview_round is None:
                    raise ResourceConflictError("面试日程必须关联申请和面试轮次")
                round_record = self._application_commands().record_interview_schedule(
                    application,
                    RecordInterviewScheduleCommand(
                        application_id=application.id,
                        expected_version=application.version,
                        round_number=data.interview_round,
                        interview_date=task.start_at,
                        location=task.location,
                        meeting_url=task.meeting_url,
                        round_source=(
                            InterviewRoundSource.EMAIL
                            if task.source_email_id is not None
                            else InterviewRoundSource.MANUAL
                        ),
                        source_task_id=task.id,
                        context=CommandContext(
                            reason="用户手动创建面试日程",
                            decision_source=DecisionSource.USER,
                            source_email_id=task.source_email_id,
                        ),
                    ),
                )
                task.interview_round_id = round_record.id
            return task

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
            if task.task_type is TaskType.INTERVIEW:
                if task.application_id is None or task.interview_round is None:
                    raise ResourceConflictError("面试日程缺少申请或轮次关联")
                application = self.applications.get(
                    task.application_id,
                    for_update=True,
                )
                round_record = self._application_commands().record_interview_schedule(
                    application,
                    RecordInterviewScheduleCommand(
                        application_id=application.id,
                        expected_version=application.version,
                        round_number=task.interview_round,
                        interview_date=task.start_at,
                        location=task.location,
                        meeting_url=task.meeting_url,
                        round_source=(
                            InterviewRoundSource.EMAIL
                            if task.source_email_id is not None
                            else InterviewRoundSource.MANUAL
                        ),
                        source_task_id=task.id,
                        context=CommandContext(
                            reason="用户修改面试日程",
                            decision_source=DecisionSource.USER,
                            source_email_id=task.source_email_id,
                        ),
                    ),
                )
                task.interview_round_id = round_record.id
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
            self._application_commands().transition_stage(
                application,
                TransitionApplicationCommand(
                    application_id=application.id,
                    expected_version=data.application_version,
                    proposed_stage=ApplicationStage.WITHDRAWN,
                    context=CommandContext(
                        reason=data.reason,
                        decision_source=DecisionSource.USER,
                    ),
                    event_type="APPLICATION_WITHDRAWN_FROM_CALENDAR",
                ),
            )
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

    def list_interview_rounds(self, application_id: int) -> list[InterviewRound]:
        """获取申请的所有面试轮次，按轮次号升序排列。"""
        self.applications.get(application_id)  # 校验归属权
        return list(
            self._session.scalars(
                select(InterviewRound)
                .where(InterviewRound.application_id == application_id)
                .order_by(InterviewRound.round_number.asc())
            )
        )

    def update_interview_round_result(
        self,
        application_id: int,
        round_number: int,
        data: InterviewRoundResultUpdate,
    ) -> tuple[JobApplication, InterviewRound]:
        """手动更新某轮面试的结果。"""
        with self._session.begin():
            application = self.applications.get(application_id, for_update=True)
            _, existing = self._application_commands().record_interview_result(
                application,
                RecordInterviewResultCommand(
                    application_id=application_id,
                    expected_version=data.version,
                    round_number=round_number,
                    result=data.result,
                    outcome=(
                        InterviewApplicationOutcome.CLOSE_AS_REJECTED
                        if data.result is InterviewResult.FAILED
                        and data.close_application
                        else InterviewApplicationOutcome.KEEP_ACTIVE
                    ),
                    round_source=InterviewRoundSource.MANUAL,
                    context=CommandContext(
                        reason=data.reason,
                        decision_source=DecisionSource.USER,
                    ),
                ),
            )
            return application, existing

    def _application_commands(self) -> ApplicationCommandHandler:
        return ApplicationCommandHandler(self._session, self._user_id)

    def link_email_application(
        self,
        email_id: int,
        application_id: int,
    ) -> object:
        """手动将邮件关联到求职申请，不依赖 AI 工作流。"""
        with self._session.begin():
            email = self.emails.get(email_id)
            self.applications.get(application_id)
            if email.application_id and email.application_id != application_id:
                raise ResourceConflictError("邮件已关联到其他求职申请")
            email.application_id = application_id
            self._session.add(
                ApplicationEvent(
                    application_id=application_id,
                    source_email_id=email_id,
                    event_type="EMAIL_LINKED",
                    details={"source": "manual", "previous_application_id": email.application_id},
                )
            )
            self._session.flush()
            return email

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
