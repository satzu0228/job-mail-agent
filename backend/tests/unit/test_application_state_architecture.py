import ast
from pathlib import Path

CRITICAL_FIELDS = {"current_stage", "status", "interview_result", "offer_result"}
ALLOWED_WRITER = Path("application/application_commands.py")


def _application_attribute(target: ast.expr) -> str | None:
    if not isinstance(target, ast.Attribute) or target.attr not in CRITICAL_FIELDS:
        return None
    if target.attr != "status":
        return target.attr
    owner = target.value
    if not isinstance(owner, ast.Name) or "application" not in owner.id:
        return None
    return target.attr


def _critical_setattr(node: ast.Call) -> str | None:
    if not isinstance(node.func, ast.Name) or node.func.id != "setattr":
        return None
    if len(node.args) < 2 or not isinstance(node.args[0], ast.Name):
        return None
    field = node.args[1]
    if (
        "application" in node.args[0].id
        and isinstance(field, ast.Constant)
        and field.value in CRITICAL_FIELDS
    ):
        return str(field.value)
    return None


def test_only_application_command_handler_writes_critical_application_state() -> None:
    app_root = Path(__file__).resolve().parents[2] / "app"
    violations: list[str] = []
    for path in app_root.rglob("*.py"):
        relative = path.relative_to(app_root)
        if relative == ALLOWED_WRITER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            for target in targets:
                field = _application_attribute(target)
                if field is not None:
                    violations.append(f"{relative}:{node.lineno}:{field}")
            if isinstance(node, ast.Call):
                field = _critical_setattr(node)
                if field is not None:
                    violations.append(f"{relative}:{node.lineno}:{field}")

    assert violations == [], "申请关键状态只能由 ApplicationCommandHandler 写入：" + ", ".join(
        violations
    )
