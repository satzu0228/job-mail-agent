import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"


def test_task_automation_only_creates_review_suggestions() -> None:
    path = APP_DIR / "application" / "task_auto_creation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    direct_task_constructors = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Task"
    ]

    assert direct_task_constructors == []
