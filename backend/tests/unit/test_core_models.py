from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.infrastructure.db.models  # noqa: F401
from app.domain.enums import (
    ApplicationStage,
    ArchiveStatus,
    EmailDirection,
    EmailParseStatus,
    TaskStatus,
)
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (
    AutomationRule,
    Email,
    EmailAnalysis,
    JobApplication,
    ReviewTask,
    Task,
)
from app.infrastructure.db.models.email_account import EmailAccount


def test_metadata_contains_all_business_tables() -> None:
    assert set(Base.metadata.tables) == {
        "action_executions",
        "application_events",
        "automation_rules",
        "automation_rule_runs",
        "users",
        "email_accounts",
        "job_applications",
        "emails",
        "email_analyses",
        "interview_rounds",
        "llm_configs",
        "reply_drafts",
        "reminders",
        "review_tasks",
        "tasks",
        "workflow_runs",
    }


def test_email_account_identity_and_email_imap_identity_are_unique() -> None:
    account_uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in Base.metadata.tables["email_accounts"].constraints
        if isinstance(constraint, UniqueConstraint)
    }
    email_uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in Base.metadata.tables["emails"].constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("user_id", "email_address") in account_uniques
    assert ("account_id", "source_folder", "uid_validity", "imap_uid") in email_uniques


def test_enum_fields_generate_named_check_constraints() -> None:
    expected_names = {
        "ck_job_applications_application_stage",
        "ck_job_applications_application_status",
        "ck_job_applications_application_source",
        "ck_job_applications_interview_result",
        "ck_job_applications_offer_result",
    }
    actual_names = {
        constraint.name
        for constraint in Base.metadata.tables["job_applications"].constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert actual_names == expected_names


def test_mysql_ddl_uses_unsigned_ids_json_and_utf8mb4() -> None:
    user_ddl = str(
        CreateTable(Base.metadata.tables["users"]).compile(dialect=mysql.dialect())
    )
    email_ddl = str(
        CreateTable(Base.metadata.tables["emails"]).compile(dialect=mysql.dialect())
    )

    assert "BIGINT UNSIGNED" in user_ddl
    assert "reply_preferences JSON NOT NULL" in user_ddl
    assert "COLLATE utf8mb4_0900_ai_ci" in user_ddl
    assert "analysis_text LONGTEXT NOT NULL" in email_ddl


def test_message_id_uses_mysql_prefix_index() -> None:
    index = next(index for index in Email.__table__.indexes if index.name == "ix_emails_message_id")
    ddl = str(CreateIndex(index).compile(dialect=mysql.dialect()))

    assert "message_id(191)" in ddl
    assert index.unique is False


def test_model_defaults_and_optimistic_lock_configuration() -> None:
    assert JobApplication.__mapper__.version_id_col is JobApplication.__table__.c.version
    assert Task.__mapper__.version_id_col is Task.__table__.c.version
    assert ReviewTask.__mapper__.version_id_col is ReviewTask.__table__.c.version
    assert AutomationRule.__mapper__.version_id_col is AutomationRule.__table__.c.version
    assert Email.__table__.c.parse_status.default.arg == EmailParseStatus.PENDING
    assert Email.__table__.c.archive_status.default.arg == ArchiveStatus.NONE
    assert JobApplication.__table__.c.current_stage.default.arg == ApplicationStage.APPLIED
    assert Task.__table__.c.status.default.arg == TaskStatus.PENDING
    assert AutomationRule.__table__.c.is_enabled.default.arg is False
    assert AutomationRule.__table__.c.requires_confirmation.default.arg is True


def test_email_analysis_version_and_workflow_run_are_unique() -> None:
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in EmailAnalysis.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("email_id", "version") in unique_columns
    assert ("workflow_run_id",) in unique_columns
    assert EmailAnalysis.__table__.c.extraction_confidence.nullable is True


def test_each_task_has_at_most_one_internal_reminder() -> None:
    reminder_uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in Base.metadata.tables["reminders"].constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("task_id",) in reminder_uniques


def test_email_direction_uses_the_owning_account_address() -> None:
    account = EmailAccount(id=2, user_id=1, email_address="candidate@example.com")
    received = Email(from_address="hr@example.com")
    sent = Email(from_address="Candidate@Example.com")
    received.account = account
    sent.account = account

    assert received.direction is EmailDirection.RECEIVED
    assert sent.direction is EmailDirection.SENT
