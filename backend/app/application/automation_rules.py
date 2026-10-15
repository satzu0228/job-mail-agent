from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.archive import EmailArchiveService
from app.application.schemas import (
    AutomationRuleCreate,
    AutomationRuleExecuteResponse,
    AutomationRuleUpdate,
)
from app.domain.enums import (
    ArchiveStatus,
    AutomationRuleType,
    EmailCategory,
    EmailPriority,
    ReviewActionType,
    ReviewDecisionStatus,
)
from app.infrastructure.db.models import (
    AutomationRule,
    AutomationRuleRun,
    Email,
    EmailAccount,
    EmailAnalysis,
    ReviewTask,
    User,
)
from app.infrastructure.db.repositories import (
    EntityNotFoundError,
    ResourceConflictError,
    VersionConflictError,
)


class AutomationRuleService:
    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def list(self) -> list[AutomationRule]:
        return list(
            self._session.scalars(
                select(AutomationRule)
                .where(AutomationRule.user_id == self._user_id)
                .order_by(AutomationRule.id)
            )
        )

    def get(self, rule_id: int, *, for_update: bool = False) -> AutomationRule:
        statement = select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.user_id == self._user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        rule = self._session.scalar(statement)
        if rule is None:
            raise EntityNotFoundError(f"Automation rule {rule_id} does not exist")
        return rule

    def create(self, data: AutomationRuleCreate) -> AutomationRule:
        with self._session.begin():
            self._ensure_demo_user()
            self._validate_account(data.account_id)
            rule = AutomationRule(
                user_id=self._user_id,
                account_id=data.account_id,
                name=data.name.strip(),
                rule_type=data.rule_type,
                conditions=self._normalized_conditions(data.conditions),
                action_config=self._normalized_action_config(data.action_config),
                requires_confirmation=True,
                is_enabled=data.is_enabled,
            )
            self._session.add(rule)
            self._session.flush()
            return rule

    def update(self, rule_id: int, data: AutomationRuleUpdate) -> AutomationRule:
        with self._session.begin():
            rule = self.get(rule_id, for_update=True)
            if rule.version != data.version:
                raise VersionConflictError(
                    f"Resource version changed: expected {data.version}, actual {rule.version}"
                )
            if "account_id" in data.model_fields_set:
                self._validate_account(data.account_id)
                rule.account_id = data.account_id
            if data.name is not None:
                rule.name = data.name.strip()
            if data.conditions is not None:
                rule.conditions = self._normalized_conditions(data.conditions)
            if data.action_config is not None:
                rule.action_config = self._normalized_action_config(data.action_config)
            if data.requires_confirmation is not None:
                rule.requires_confirmation = True
            if data.is_enabled is not None:
                rule.is_enabled = data.is_enabled
            self._session.flush()
            return rule

    def preview(self, rule_id: int, *, limit: int = 20) -> tuple[list[Email], int]:
        rule = self.get(rule_id)
        candidates = self._candidate_emails(rule)
        return candidates[:limit], len(candidates)

    def execute(self, rule_id: int) -> AutomationRuleExecuteResponse:
        rule = self.get(rule_id)
        if not rule.is_enabled:
            raise ResourceConflictError("automation rule is disabled")
        created: list[str] = []
        skipped: list[int] = []
        failed: dict[int, str] = {}
        for email in self._candidate_emails(rule):
            analysis = email.current_analysis
            if analysis is None:
                skipped.append(email.id)
                continue
            if self._has_open_archive_review(email.id):
                skipped.append(email.id)
                continue
            try:
                review = EmailArchiveService(self._session, self._user_id).propose_archive(
                    email.id
                )
                self._record_run(
                    rule,
                    email,
                    matched=True,
                    status="PROPOSED",
                    review_task_id=review.id,
                )
                created.append(review.id)
            except (ResourceConflictError, IntegrityError) as exc:
                self._session.rollback()
                self._record_run(
                    rule,
                    email,
                    matched=False,
                    status="SKIPPED",
                    error_message=str(exc)[:500],
                )
                skipped.append(email.id)
            except Exception as exc:
                self._session.rollback()
                self._record_run(
                    rule,
                    email,
                    matched=False,
                    status="FAILED",
                    error_message=str(exc)[:500],
                )
                failed[email.id] = str(exc)[:500]
        return AutomationRuleExecuteResponse(
            created_review_task_ids=created,
            skipped_email_ids=skipped,
            failed_email_ids=failed,
        )

    def _candidate_emails(self, rule: AutomationRule) -> list[Email]:
        if rule.rule_type is not AutomationRuleType.LOW_PRIORITY_ARCHIVE:
            return []
        conditions = self._normalized_conditions(rule.conditions)
        statement = (
            select(Email)
            .join(EmailAccount, Email.account_id == EmailAccount.id)
            .join(
                EmailAnalysis,
                (EmailAnalysis.email_id == Email.id)
                & EmailAnalysis.is_current.is_(True),
            )
            .where(
                EmailAccount.user_id == self._user_id,
                Email.archive_status.in_([ArchiveStatus.NONE, ArchiveStatus.RESTORED]),
                EmailAnalysis.priority.notin_([EmailPriority.HIGH, EmailPriority.URGENT]),
                EmailAnalysis.should_reply.is_(False),
            )
            .order_by(Email.received_at.desc(), Email.id.desc())
        )
        if rule.account_id is not None:
            statement = statement.where(Email.account_id == rule.account_id)
        if conditions["unlinked_only"]:
            statement = statement.where(Email.application_id.is_(None))
        statement = statement.where(
            EmailAnalysis.category.in_(conditions["categories"]),
            EmailAnalysis.priority.in_(conditions["priorities"]),
            EmailAnalysis.classification_confidence
            >= Decimal(str(conditions["min_confidence"])),
        )
        return list(self._session.scalars(statement))

    def _has_open_archive_review(self, email_id: int) -> bool:
        task = self._session.scalar(
            select(ReviewTask.id)
            .where(
                ReviewTask.user_id == self._user_id,
                ReviewTask.source_email_id == email_id,
                ReviewTask.action_type == ReviewActionType.ARCHIVE_EMAIL,
                ReviewTask.decision_status.in_(
                    [
                        ReviewDecisionStatus.PENDING,
                        ReviewDecisionStatus.APPROVED,
                    ]
                ),
            )
            .limit(1)
        )
        return task is not None

    def _record_run(
        self,
        rule: AutomationRule,
        email: Email,
        *,
        matched: bool,
        status: str,
        review_task_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        analysis = email.current_analysis
        with self._session.begin():
            existing = self._session.scalar(
                select(AutomationRuleRun)
                .where(
                    AutomationRuleRun.rule_id == rule.id,
                    AutomationRuleRun.rule_version == rule.version,
                    AutomationRuleRun.email_id == email.id,
                    AutomationRuleRun.analysis_version
                    == (analysis.version if analysis else None),
                )
                .limit(1)
            )
            if existing is not None:
                existing.matched = matched
                existing.status = status
                existing.review_task_id = review_task_id
                existing.error_message = error_message
                return
            self._session.add(
                AutomationRuleRun(
                    rule_id=rule.id,
                    rule_version=rule.version,
                    user_id=self._user_id,
                    email_id=email.id,
                    analysis_id=analysis.id if analysis else None,
                    analysis_version=analysis.version if analysis else None,
                    matched=matched,
                    status=status,
                    match_reason={
                        "rule_type": rule.rule_type.value,
                        "conditions": rule.conditions,
                    },
                    review_task_id=review_task_id,
                    error_message=error_message,
                )
            )

    def _validate_account(self, account_id: int | None) -> None:
        if account_id is None:
            return
        account = self._session.scalar(
            select(EmailAccount.id).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == self._user_id,
            )
        )
        if account is None:
            raise EntityNotFoundError(f"Email account {account_id} does not exist")

    @staticmethod
    def _normalized_conditions(value: dict[str, Any]) -> dict[str, Any]:
        categories = value.get("categories") or [
            EmailCategory.NON_JOB.value,
            EmailCategory.JOB_RELATED_OTHER.value,
        ]
        priorities = value.get("priorities") or [EmailPriority.LOW.value]
        min_confidence = float(value.get("min_confidence", 0.75))
        return {
            "categories": [EmailCategory(item).value for item in categories],
            "priorities": [EmailPriority(item).value for item in priorities],
            "min_confidence": max(0.0, min(1.0, min_confidence)),
            "unlinked_only": bool(value.get("unlinked_only", True)),
        }

    @staticmethod
    def _normalized_action_config(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "target": value.get("target", "JobMailArchive"),
            "mode": "PROPOSE_ONLY",
        }

    def _ensure_demo_user(self) -> None:
        if self._session.get(User, self._user_id) is None:
            self._session.add(
                User(
                    id=self._user_id,
                    display_name="Demo User",
                    timezone="Asia/Shanghai",
                    reply_preferences={},
                )
            )
            self._session.flush()
