from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

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


def make_agent_runner(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    output_schema: type[BaseModel],
    *,
    recursion_limit: int = 6,
) -> Callable[..., Any]:
    """创建 Tool Calling Agent 的两阶段运行器。

    Phase 1: Agent 自主调工具搜集信息（ReAct 循环）
    Phase 2: Structured LLM 将收集到的信息格式化为 Pydantic 输出

    工具通过 RunnableConfig 参数获取运行时 user_id，Agent 初始化时不绑定用户。
    """

    agent_graph = create_react_agent(
        model,
        tools,
        prompt=system_prompt,
    )

    def run(agent_input: BaseModel, *, config: RunnableConfig) -> Any:
        # ---- Phase 1: Agent 自主调工具搜集信息 ----
        agent_result = agent_graph.invoke(
            {"messages": [HumanMessage(
                content=json.dumps(agent_input.model_dump(mode="json"), ensure_ascii=False)
            )]},
            config={"recursion_limit": recursion_limit, **config},
        )

        # 提取所有工具返回结果 + Agent 最终判断
        messages = agent_result["messages"]
        tool_results: list[dict[str, Any]] = []
        for m in messages:
            if getattr(m, "type", None) == "tool":
                tool_results.append({
                    "tool": getattr(m, "name", "unknown"),
                    "result": _safe_tool_content(m.content),
                })
        agent_summary = messages[-1].content if messages else ""

        # ---- Phase 2: Structured LLM 格式化输出 ----
        output_schema_json = output_schema.model_json_schema()
        structured = model.with_structured_output(
            output_schema,
            method="json_mode",
        )
        final = structured.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=(
                "请根据以上规则，将搜集到的信息整理成符合输出 Schema 的 JSON 对象，"
                "只返回 JSON，不要包含 Markdown、解释或额外字段。\n"
                f"输出 Schema：\n"
                f"{json.dumps(output_schema_json, ensure_ascii=False)}\n"
                f"输入信息：\n"
                + json.dumps({
                    "original_input": agent_input.model_dump(mode="json"),
                    "tool_results": tool_results,
                    "agent_summary": agent_summary,
                }, ensure_ascii=False)
            )),
        ])
        return output_schema.model_validate(final)

    return run


def _safe_tool_content(content: Any) -> Any:
    """安全地提取工具返回内容，避免嵌套 JSON 字符串。"""
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return content
    if isinstance(content, list):
        return [_safe_tool_content(item) for item in content]
    return content
