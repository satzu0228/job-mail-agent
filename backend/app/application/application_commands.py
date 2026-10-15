from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.application.task_linkage import settle_interview_tasks
from app.domain.application import (
    ApplicationState,
    ApplicationStateChange,
    ApplicationStateError,
    ApplicationStatePolicy,
    CommandContext,
    RecordInterviewResultCommand,
    RecordInterviewScheduleCommand,
    RecordOfferDecisionCommand,
    ReopenApplicationCommand,
    ScheduleInterviewRoundCommand,
    TransitionApplicationCommand,
)
from app.domain.enums import (
    ApplicationStage,
    ApplicationStatus,
    InterviewResult,
    InterviewRoundSource,
    InterviewRoundStatus,
    ReminderStatus,
    TaskStatus,
    TaskType,
)
from app.infrastructure.db.models.application_event import ApplicationEvent
from app.infrastructure.db.models.interview_round import InterviewRound
from app.infrastructure.db.models.job_application import JobApplication
from app.infrastructure.db.models.reminder import Reminder
from app.infrastructure.db.models.task import Task
from app.infrastructure.db.repositories.business import (
    ResourceConflictError,
    VersionConflictError,
)

_ROUND_NOT_LOADED = object()


class ApplicationCommandHandler:
    """在调用方事务内执行申请聚合命令和关联副作用。"""

    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def transition_stage(
        self,
        application: JobApplication,
        command: TransitionApplicationCommand,
    ) -> ApplicationStateChange:
        self._check_target(application, command.application_id, command.expected_version)
        has_passed_interview = self._has_passed_interview(application.id)
        try:
            change = ApplicationStatePolicy.transition_stage(
                self._snapshot(application),
                command.proposed_stage,
                interview_result=command.interview_result,
                has_passed_interview=has_passed_interview,
            )
        except ApplicationStateError as exc:
            raise ResourceConflictError(str(exc)) from exc

        previous_stage = application.current_stage
        if command.proposed_stage is ApplicationStage.INTERVIEW:
            self._create_next_round_if_needed(
                application.id,
                result=command.interview_result or InterviewResult.PENDING,
                source=(
                    InterviewRoundSource.EMAIL
                    if command.context.source_email_id is not None
                    else InterviewRoundSource.MANUAL
                ),
                source_email_id=command.context.source_email_id,
                notes=command.context.reason,
            )
        elif (
            previous_stage is ApplicationStage.INTERVIEW
            and command.proposed_stage is ApplicationStage.REJECTED
        ):
            self._complete_latest_round(
                application.id,
                InterviewResult.FAILED,
                notes=command.context.reason,
            )
        elif (
            previous_stage is ApplicationStage.INTERVIEW
            and command.proposed_stage is ApplicationStage.OFFER
        ):
            self._complete_latest_round(
                application.id,
                InterviewResult.PASSED,
                notes=command.context.reason,
            )

        self._apply(application, change)
        self._settle_for_stage_transition(
            application.id,
            previous_stage=previous_stage,
            proposed_stage=command.proposed_stage,
        )
        self._session.add(
            ApplicationEvent(
                application_id=application.id,
                source_email_id=command.context.source_email_id,
                workflow_run_id=command.context.workflow_run_id,
                event_type=command.event_type,
                previous_stage=previous_stage,
                proposed_stage=command.proposed_stage,
                confirmed_stage=command.proposed_stage,
                event_at=self._now(),
                details=self._event_details(command.context),
            )
        )
        self._session.flush()
        return change

    def record_interview_result(
        self,
        application: JobApplication,
        command: RecordInterviewResultCommand,
    ) -> tuple[ApplicationStateChange, InterviewRound]:
        self._check_target(application, command.application_id, command.expected_version)
        if not 1 <= command.round_number <= 20:
            raise ResourceConflictError("面试轮次必须在 1～20 之间")
        previous_result = application.interview_result
        round_record = self._upsert_round(
            application_id=application.id,
            round_number=command.round_number,
            result=command.result,
            source=command.round_source,
            source_email_id=command.context.source_email_id,
            notes=command.context.reason,
        )
        state = self._snapshot(application)
        has_newer_round = (
            self._session.scalar(
                select(InterviewRound.id)
                .where(
                    InterviewRound.application_id == application.id,
                    InterviewRound.round_number > command.round_number,
                )
                .limit(1)
            )
            is not None
        )
        if not has_newer_round:
            try:
                change = ApplicationStatePolicy.record_interview_result(
                    state,
                    command.result,
                    command.outcome,
                )
            except ApplicationStateError as exc:
                raise ResourceConflictError(str(exc)) from exc
            self._apply(application, change)
        else:
            change = ApplicationStateChange(previous=state, current=state)
        if command.result in {InterviewResult.PASSED, InterviewResult.FAILED}:
            settle_interview_tasks(
                self._session,
                application_id=application.id,
                status=TaskStatus.COMPLETED,
                current_round_only=False,
                round_number=command.round_number,
            )
        details = self._event_details(command.context)
        details.update(
            {
                "round_number": command.round_number,
                "previous_result": previous_result.value if previous_result else None,
                "interview_result": command.result.value,
                "application_outcome": command.outcome.value,
            }
        )
        self._session.add(
            ApplicationEvent(
                application_id=application.id,
                source_email_id=command.context.source_email_id,
                workflow_run_id=command.context.workflow_run_id,
                event_type="INTERVIEW_RESULT_CHANGED",
                previous_stage=change.previous.current_stage,
                proposed_stage=change.current.current_stage,
                confirmed_stage=change.current.current_stage,
                event_at=self._now(),
                details=details,
            )
        )
        self._session.flush()
        return change, round_record

    def schedule_next_interview(
        self,
        application: JobApplication,
        command: ScheduleInterviewRoundCommand,
    ) -> tuple[ApplicationStateChange, InterviewRound, Task]:
        self._check_target(application, command.application_id, command.expected_version)
        state = self._snapshot(application)
        if state.current_stage is not ApplicationStage.INTERVIEW:
            raise ResourceConflictError("只有面试阶段的申请可以登记下一轮面试")
        if state.interview_result is not InterviewResult.PASSED:
            raise ResourceConflictError("确认本轮面试已通过后才能登记下一轮")

        next_round = self._next_round_number(application.id)
        round_record = self._upsert_round(
            application_id=application.id,
            round_number=next_round,
            result=InterviewResult.PENDING,
            source=InterviewRoundSource.MANUAL,
            interview_date=command.start_at,
            location=command.location,
            meeting_url=command.meeting_url,
            notes=command.context.reason,
            round_status=InterviewRoundStatus.SCHEDULED,
        )
        change = ApplicationStateChange(
            previous=state,
            current=ApplicationState(
                current_stage=ApplicationStage.INTERVIEW,
                status=ApplicationStatus.ACTIVE,
                interview_result=InterviewResult.PENDING,
                offer_result=None,
            ),
        )
        self._apply(application, change)
        task = Task(
            user_id=self._user_id,
            application_id=application.id,
            source_email_id=None,
            task_type=TaskType.INTERVIEW,
            round_record=round_record,
            title=command.title,
            raw_time_text=command.raw_time_text,
            start_at=command.start_at,
            deadline_at=command.deadline_at,
            source_timezone=command.source_timezone,
            location=command.location,
            meeting_url=command.meeting_url,
            status=TaskStatus.CONFIRMED,
        )
        self._session.add(task)
        self._session.flush()
        round_record.source_task_id = task.id
        details = self._event_details(command.context)
        details.update(
            {
                "previous_result": InterviewResult.PASSED.value,
                "interview_result": InterviewResult.PENDING.value,
                "interview_round": next_round,
                "task_id": task.id,
            }
        )
        self._session.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="NEXT_INTERVIEW_SCHEDULED",
                previous_stage=ApplicationStage.INTERVIEW,
                proposed_stage=ApplicationStage.INTERVIEW,
                confirmed_stage=ApplicationStage.INTERVIEW,
                raw_time_text=command.raw_time_text,
                event_at=self._now(),
                source_timezone=command.source_timezone,
                details=details,
            )
        )
        self._session.flush()
        return change, round_record, task

    def record_interview_schedule(
        self,
        application: JobApplication,
        command: RecordInterviewScheduleCommand,
    ) -> InterviewRound:
        """登记或更新已审核的面试安排，不覆盖已有确定结果。"""
        self._check_target(application, command.application_id, command.expected_version)
        if not 1 <= command.round_number <= 20:
            raise ResourceConflictError("面试轮次必须在 1～20 之间")
        existing = self._session.scalar(
            select(InterviewRound).where(
                InterviewRound.application_id == application.id,
                InterviewRound.round_number == command.round_number,
            )
        )
        result = (
            existing.result
            if existing is not None
            and existing.result in {InterviewResult.PASSED, InterviewResult.FAILED}
            else InterviewResult.PENDING
        )
        record = self._upsert_round(
            application_id=application.id,
            round_number=command.round_number,
            result=result,
            source=command.round_source,
            source_email_id=command.context.source_email_id,
            source_task_id=command.source_task_id,
            interview_date=command.interview_date,
            location=command.location,
            meeting_url=command.meeting_url,
            notes=command.context.reason,
            existing_record=existing,
            round_status=(
                InterviewRoundStatus.SCHEDULED
                if command.interview_date is not None or command.source_task_id is not None
                else InterviewRoundStatus.PLANNED
            ),
        )
        latest_number = self._next_round_number(application.id) - 1
        if (
            application.current_stage is ApplicationStage.INTERVIEW
            and command.round_number >= latest_number
        ):
            state = self._snapshot(application)
            self._apply(
                application,
                ApplicationStateChange(
                    previous=state,
                    current=ApplicationState(
                        current_stage=ApplicationStage.INTERVIEW,
                        status=ApplicationStatus.ACTIVE,
                        interview_result=record.result,
                        offer_result=None,
                    ),
                ),
            )
        self._session.flush()
        return record

    def record_offer_decision(
        self,
        application: JobApplication,
        command: RecordOfferDecisionCommand,
    ) -> ApplicationStateChange:
        self._check_target(application, command.application_id, command.expected_version)
        try:
            change = ApplicationStatePolicy.record_offer_decision(
                self._snapshot(application), command.result
            )
        except ApplicationStateError as exc:
            raise ResourceConflictError(str(exc)) from exc
        previous_result = application.offer_result
        self._apply(application, change)
        details = self._event_details(command.context)
        details.update(
            {
                "previous_result": previous_result.value if previous_result else None,
                "offer_result": command.result.value,
            }
        )
        self._session.add(
            ApplicationEvent(
                application_id=application.id,
                source_email_id=command.context.source_email_id,
                workflow_run_id=command.context.workflow_run_id,
                event_type="OFFER_RESULT_CHANGED",
                previous_stage=application.current_stage,
                proposed_stage=application.current_stage,
                confirmed_stage=application.current_stage,
                event_at=self._now(),
                details=details,
            )
        )
        self._session.flush()
        return change

    def reopen(
        self,
        application: JobApplication,
        command: ReopenApplicationCommand,
    ) -> ApplicationStateChange:
        self._check_target(application, command.application_id, command.expected_version)
        try:
            change = ApplicationStatePolicy.reopen(
                self._snapshot(application), command.target_stage
            )
        except ApplicationStateError as exc:
            raise ResourceConflictError(str(exc)) from exc
        if command.target_stage is ApplicationStage.INTERVIEW:
            self._create_next_round_if_needed(
                application.id,
                result=InterviewResult.PENDING,
                source=InterviewRoundSource.MANUAL,
                notes=command.context.reason,
                force_new=True,
            )
        self._apply(application, change)
        self._session.add(
            ApplicationEvent(
                application_id=application.id,
                source_email_id=command.context.source_email_id,
                workflow_run_id=command.context.workflow_run_id,
                event_type="APPLICATION_REOPENED",
                previous_stage=change.previous.current_stage,
                proposed_stage=command.target_stage,
                confirmed_stage=command.target_stage,
                event_at=self._now(),
                details=self._event_details(command.context),
            )
        )
        self._session.flush()
        return change

    @staticmethod
    def _snapshot(application: JobApplication) -> ApplicationState:
        return ApplicationState(
            current_stage=application.current_stage,
            status=application.status,
            interview_result=application.interview_result,
            offer_result=application.offer_result,
        )

    @staticmethod
    def _apply(application: JobApplication, change: ApplicationStateChange) -> None:
        interview_changed = (
            application.interview_result is not change.current.interview_result
        )
        persistent_state_changed = (
            application.current_stage is not change.current.current_stage
            or application.status is not change.current.status
            or application.offer_result is not change.current.offer_result
        )
        application.current_stage = change.current.current_stage
        application.status = change.current.status
        # interview_result 是由最新 InterviewRound 派生的查询属性；这里只更新当前
        # ORM 实例的读取缓存，提交后会从权威轮次重新加载。
        application.interview_result = change.current.interview_result
        application.offer_result = change.current.offer_result
        if interview_changed and not persistent_state_changed:
            application.version += 1

    @staticmethod
    def _check_target(
        application: JobApplication,
        application_id: int,
        expected_version: int,
    ) -> None:
        if application.id != application_id:
            raise ResourceConflictError("领域命令引用了错误的申请记录")
        if application.version != expected_version:
            raise VersionConflictError(
                f"Resource version changed: expected {expected_version}, "
                f"actual {application.version}"
            )

    def _has_passed_interview(self, application_id: int) -> bool:
        return (
            self._session.scalar(
                select(InterviewRound.id)
                .where(
                    InterviewRound.application_id == application_id,
                    InterviewRound.result == InterviewResult.PASSED,
                )
                .limit(1)
            )
            is not None
        )

    def _next_round_number(self, application_id: int) -> int:
        latest = self._session.scalar(
            select(func.max(InterviewRound.round_number)).where(
                InterviewRound.application_id == application_id
            )
        )
        return int(latest or 0) + 1

    def _round(
        self,
        application_id: int,
        round_number: int,
    ) -> InterviewRound | None:
        return self._session.scalar(
            select(InterviewRound).where(
                InterviewRound.application_id == application_id,
                InterviewRound.round_number == round_number,
            )
        )

    def _create_next_round_if_needed(
        self,
        application_id: int,
        *,
        result: InterviewResult,
        source: InterviewRoundSource,
        source_email_id: int | None = None,
        notes: str | None = None,
        force_new: bool = False,
    ) -> InterviewRound:
        latest = self._session.scalar(
            select(InterviewRound)
            .where(InterviewRound.application_id == application_id)
            .order_by(InterviewRound.round_number.desc())
            .limit(1)
        )
        if latest is not None and not force_new and latest.result is InterviewResult.PENDING:
            return latest
        return self._upsert_round(
            application_id=application_id,
            round_number=(latest.round_number + 1 if latest is not None else 1),
            result=result,
            source=source,
            source_email_id=source_email_id,
            notes=notes,
        )

    def _complete_latest_round(
        self,
        application_id: int,
        result: InterviewResult,
        *,
        notes: str | None,
    ) -> InterviewRound:
        latest = self._session.scalar(
            select(InterviewRound)
            .where(InterviewRound.application_id == application_id)
            .order_by(InterviewRound.round_number.desc())
            .limit(1)
        )
        round_number = latest.round_number if latest is not None else 1
        return self._upsert_round(
            application_id=application_id,
            round_number=round_number,
            result=result,
            source=latest.source if latest is not None else InterviewRoundSource.MANUAL,
            source_email_id=latest.source_email_id if latest is not None else None,
            notes=notes,
        )

    def _upsert_round(
        self,
        *,
        application_id: int,
        round_number: int,
        result: InterviewResult,
        source: InterviewRoundSource,
        source_email_id: int | None = None,
        source_task_id: int | None = None,
        interview_date: datetime | None = None,
        location: str | None = None,
        meeting_url: str | None = None,
        notes: str | None = None,
        round_status: InterviewRoundStatus | None = None,
        existing_record: InterviewRound | None | object = _ROUND_NOT_LOADED,
    ) -> InterviewRound:
        record = (
            self._round(application_id, round_number)
            if existing_record is _ROUND_NOT_LOADED
            else cast(InterviewRound | None, existing_record)
        )
        if record is None:
            record = InterviewRound(
                application_id=application_id,
                round_number=round_number,
                source=source,
            )
            self._session.add(record)
        record.result = result
        if result in {InterviewResult.PASSED, InterviewResult.FAILED}:
            record.status = InterviewRoundStatus.COMPLETED
        elif round_status is not None:
            record.status = round_status
        elif interview_date is not None or source_task_id is not None:
            record.status = InterviewRoundStatus.SCHEDULED
        elif record.status not in {
            InterviewRoundStatus.SCHEDULED,
            InterviewRoundStatus.NO_SHOW,
        }:
            record.status = InterviewRoundStatus.PLANNED
        record.source = source
        if source_email_id is not None:
            record.source_email_id = source_email_id
        if source_task_id is not None:
            record.source_task_id = source_task_id
        if interview_date is not None:
            record.interview_date = interview_date
        if location is not None:
            record.location = location
        if meeting_url is not None:
            record.meeting_url = meeting_url
        if notes is not None:
            record.notes = notes
        self._session.flush()
        return record

    def _settle_for_stage_transition(
        self,
        application_id: int,
        *,
        previous_stage: ApplicationStage,
        proposed_stage: ApplicationStage,
    ) -> None:
        if previous_stage is ApplicationStage.ASSESSMENT:
            self._settle_tasks(
                application_id,
                task_type=TaskType.ASSESSMENT,
                status=TaskStatus.COMPLETED,
            )
        if previous_stage is not ApplicationStage.INTERVIEW:
            return
        if proposed_stage is ApplicationStage.WITHDRAWN:
            latest = self._session.scalar(
                select(InterviewRound)
                .where(InterviewRound.application_id == application_id)
                .order_by(InterviewRound.round_number.desc())
                .limit(1)
            )
            if latest is not None and latest.status in {
                InterviewRoundStatus.PLANNED,
                InterviewRoundStatus.SCHEDULED,
            }:
                latest.status = InterviewRoundStatus.CANCELLED
        settle_interview_tasks(
            self._session,
            application_id=application_id,
            status=(
                TaskStatus.CANCELLED
                if proposed_stage is ApplicationStage.WITHDRAWN
                else TaskStatus.COMPLETED
            ),
            current_round_only=False,
        )

    def _settle_tasks(
        self,
        application_id: int,
        *,
        task_type: TaskType,
        status: TaskStatus,
    ) -> int:
        tasks = list(
            self._session.scalars(
                select(Task)
                .where(
                    Task.application_id == application_id,
                    Task.task_type == task_type,
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.CONFIRMED]),
                )
                .with_for_update()
            )
        )
        for task in tasks:
            task.status = status
        if tasks:
            self._session.execute(
                update(Reminder)
                .where(
                    Reminder.task_id.in_([task.id for task in tasks]),
                    Reminder.status == ReminderStatus.DELIVERED,
                )
                .values(status=ReminderStatus.CANCELLED)
            )
        return len(tasks)

    @staticmethod
    def _event_details(context: CommandContext) -> dict[str, object]:
        details: dict[str, object] = {
            "decision_source": context.decision_source.value,
            "reason": context.reason,
        }
        if context.review_task_id is not None:
            details["review_task_id"] = context.review_task_id
        return details

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
