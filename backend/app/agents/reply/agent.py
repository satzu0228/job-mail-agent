from __future__ import annotations

from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from app.agents.common.runner import make_agent_runner, load_prompt
from app.agents.reply.schemas import ReplyAgentInput, ReplyAgentOutput
from app.agents.reply.tools import create_reply_tools


class ReplyAgent:
    prompt_version = "v2"

    def __init__(
        self,
        run: Callable[..., ReplyAgentOutput],
    ) -> None:
        self._run = run

    @classmethod
    def from_model(
        cls,
        model: BaseChatModel,
        session_factory: Callable[[], Session],
    ) -> "ReplyAgent":
        tools = create_reply_tools(session_factory)
        system_prompt = load_prompt("reply", "v2")
        return cls(
            make_agent_runner(
                model,
                tools,
                system_prompt,
                ReplyAgentOutput,
            )
        )

    def run(
        self,
        agent_input: ReplyAgentInput,
        *,
        config: RunnableConfig | None = None,
    ) -> ReplyAgentOutput:
        return self._run(agent_input, config=config or {})
