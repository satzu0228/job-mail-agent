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


def test_initial_migration_is_the_only_head() -> None:
    scripts = ScriptDirectory.from_config(make_alembic_config())

    assert scripts.get_current_head() == "20260727_0001"


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
    ]

    assert table_positions == sorted(table_positions)
    assert "message_id(191)" in sql
    assert "uq_emails_imap_identity" in sql
    assert "credential_ref VARCHAR(128) NOT NULL" in sql
    assert "20260727_0001" in sql


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
