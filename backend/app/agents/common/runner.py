from pathlib import Path
from typing import Protocol, TypeVar

from langchain_core.messages import BaseMessage

OutputT = TypeVar("OutputT")
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class StructuredOutputInvoker(Protocol[OutputT]):
    def invoke(self, input: list[BaseMessage]) -> OutputT: ...


def load_prompt(agent_name: str, version: str) -> str:
    """加载纳入版本控制的提示词，名称只能由应用代码中的常量指定。"""
    path = PROMPTS_DIR / agent_name / f"{version}.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(f"Prompt file not found: {path}") from exc
