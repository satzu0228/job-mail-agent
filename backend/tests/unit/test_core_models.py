from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.infrastructure.db.models  # noqa: F401
from app.domain.enums import ApplicationStage, ArchiveStatus, EmailParseStatus
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import Email, JobApplication


def test_first_migration_metadata_contains_only_four_business_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "email_accounts",
        "job_applications",
        "emails",
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
    assert Email.__table__.c.parse_status.default.arg == EmailParseStatus.PENDING
    assert Email.__table__.c.archive_status.default.arg == ArchiveStatus.NONE
    assert JobApplication.__table__.c.current_stage.default.arg == ApplicationStage.APPLIED
