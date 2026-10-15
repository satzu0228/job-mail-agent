import ast
from pathlib import Path

from app.infrastructure.db.models.workflow_run import WorkflowRun

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_only_formal_workflow_service_constructs_workflow_runs() -> None:
    offenders: list[str] = []
    for path in (BACKEND_DIR / "app" / "application").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if path.name == "workflow.py":
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "WorkflowRun"
            ):
                offenders.append(path.name)

    assert offenders == []


def test_active_email_has_database_unique_constraint() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in WorkflowRun.__table__.constraints
        if constraint.name
    }

    assert constraints["uq_workflow_runs_active_email_id"] == ("active_email_id",)
