from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[2]


def make_alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def test_compatibility_cleanup_migration_is_the_only_head() -> None:
    scripts = ScriptDirectory.from_config(make_alembic_config())

    assert scripts.get_current_head() == "20261014_0014"


def test_initial_migration_generates_ordered_mysql_sql() -> None:
    config = make_alembic_config()
    output = StringIO()
    config.output_buffer = output

    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()

    table_positions = [
        sql.index("CREATE TABLE users"),
        sql.index("CREATE TABLE email_accounts"),
        sql.index("CREATE TABLE job_applications"),
        sql.index("CREATE TABLE emails"),
        sql.index("CREATE TABLE email_analyses"),
        sql.index("CREATE TABLE workflow_runs"),
        sql.index("CREATE TABLE application_events"),
        sql.index("CREATE TABLE tasks"),
        sql.index("CREATE TABLE reply_drafts"),
        sql.index("CREATE TABLE review_tasks"),
        sql.index("CREATE TABLE action_executions"),
        sql.index("CREATE TABLE automation_rules"),
        sql.index("CREATE TABLE reminders"),
        sql.index("CREATE TABLE automation_rule_runs"),
    ]

    assert table_positions == sorted(table_positions)
    assert "message_id(191)" in sql
    assert "uq_emails_imap_identity" in sql
    assert "credential_ref VARCHAR(128) NOT NULL" in sql
    assert "uq_email_analyses_email_version" in sql
    assert "classification_confidence BETWEEN 0 AND 1" in sql
    assert "fk_tasks_source_review_task_id_review_tasks" in sql
    assert "fk_workflow_runs_pending_review_task_id_review_tasks" in sql
    assert "20260728_0003" in sql
    assert "20260730_0004" in sql
    assert "auto_sync_enabled BOOL NOT NULL DEFAULT 0" in sql
    assert "uq_reminders_task_id" in sql
    assert "current_uid_validity BIGINT UNSIGNED" in sql
    assert "ix_emails_current_imap_pointer" in sql
    assert "offer_result VARCHAR(16)" in sql
    assert "uq_automation_rule_runs_rule_email_analysis" in sql
    assert "decision_status VARCHAR(16)" in sql
    assert "parent_review_task_id CHAR(36)" in sql
    assert "fk_review_tasks_parent_review_task_id_review_tasks" in sql
    assert "interview_round_id BIGINT UNSIGNED" in sql
    assert "fk_tasks_interview_round_id_interview_rounds" in sql
    assert "'PLANNED', 'SCHEDULED', 'COMPLETED'" in sql
    assert "active_email_id BIGINT UNSIGNED" in sql
    assert "uq_workflow_runs_active_email_id" in sql
    assert "DROP COLUMN interview_result" in sql
    assert "DROP COLUMN interview_round" in sql
    assert "DROP COLUMN status" in sql
    assert "SET offer_result = 'PENDING'" in sql


def test_initial_migration_downgrades_in_reverse_dependency_order() -> None:
    config = make_alembic_config()
    output = StringIO()
    config.output_buffer = output

    command.downgrade(config, "20260727_0001:base", sql=True)
    sql = output.getvalue()

    table_positions = [
        sql.index("DROP TABLE emails"),
        sql.index("DROP TABLE job_applications"),
        sql.index("DROP TABLE email_accounts"),
        sql.index("DROP TABLE users"),
    ]

    assert table_positions == sorted(table_positions)


def test_second_migration_can_downgrade_without_touching_email_facts() -> None:
    config = make_alembic_config()
    output = StringIO()
    config.output_buffer = output

    command.downgrade(config, "20260728_0002:20260727_0001", sql=True)
    sql = output.getvalue()

    assert "DROP TABLE email_analyses" in sql
    assert "DROP TABLE emails" not in sql


def test_third_migration_drops_circular_foreign_keys_before_tables() -> None:
    config = make_alembic_config()
    output = StringIO()
    config.output_buffer = output

    command.downgrade(config, "20260728_0003:20260728_0002", sql=True)
    sql = output.getvalue()

    constraint_position = sql.index(
        "fk_workflow_runs_pending_review_task_id_review_tasks"
    )
    review_table_position = sql.index("DROP TABLE review_tasks")
    workflow_table_position = sql.index("DROP TABLE workflow_runs")
    assert constraint_position < review_table_position < workflow_table_position


def test_interview_authority_migration_downgrades_compatibly() -> None:
    config = make_alembic_config()
    output = StringIO()
    config.output_buffer = output

    command.downgrade(config, "20261011_0012:20261010_0011", sql=True)
    sql = output.getvalue()

    assert "DROP FOREIGN KEY fk_tasks_interview_round_id_interview_rounds" in sql
    assert "DROP COLUMN interview_round_id" in sql
    assert "status = 'SCHEDULED'" in sql


def test_active_workflow_migration_downgrades_compatibly() -> None:
    config = make_alembic_config()
    output = StringIO()
    config.output_buffer = output

    command.downgrade(config, "20261011_0013:20261011_0012", sql=True)
    sql = output.getvalue()

    assert "DROP INDEX uq_workflow_runs_active_email_id" in sql
    assert "DROP FOREIGN KEY fk_workflow_runs_active_email_id_emails" in sql
    assert "DROP COLUMN active_email_id" in sql


def test_compatibility_cleanup_migration_downgrades_with_backfill() -> None:
    config = make_alembic_config()
    output = StringIO()
    config.output_buffer = output

    command.downgrade(config, "20261014_0014:20261011_0013", sql=True)
    sql = output.getvalue()

    assert "ADD COLUMN status VARCHAR(32)" in sql
    assert "SET status = decision_status" in sql
    assert "ADD COLUMN interview_round SMALLINT UNSIGNED" in sql
    assert "SET t.interview_round = ir.round_number" in sql
    assert "ADD COLUMN interview_result VARCHAR(16)" in sql
    assert "SET ja.interview_result = ir.result" in sql
