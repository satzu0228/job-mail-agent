from sqlalchemy.dialects import mysql

from app.application.state_audit import build_state_audit_queries


def test_state_audit_covers_every_r0_data_risk() -> None:
    assert set(build_state_audit_queries()) == {
        "illegal_application_state",
        "orphan_interview_task",
        "unauthorized_action_execution",
        "duplicate_active_workflow",
        "update_task_review",
    }


def test_state_audit_only_builds_select_statements() -> None:
    for statement in build_state_audit_queries().values():
        sql = str(
            statement.compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).upper()

        assert sql.lstrip().startswith("SELECT")
        assert " INSERT " not in f" {sql} "
        assert " UPDATE " not in f" {sql} "
        assert " DELETE " not in f" {sql} "
