from __future__ import annotations

from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from app.agents.application.schemas import (
    ApplicationAgentInput,
    ApplicationAgentOutput,
)
from app.agents.application.tools import create_application_tools
from app.agents.common.runner import make_agent_runner, load_prompt


class ApplicationAgent:
    prompt_version = "v2"

    def __init__(
        self,
        run: Callable[..., ApplicationAgentOutput],
    ) -> None:
        self._run = run

    @classmethod
    def from_model(
        cls,
        model: BaseChatModel,
        session_factory: Callable[[], Session],
    ) -> "ApplicationAgent":
        tools = create_application_tools(session_factory)
        system_prompt = load_prompt("application", "v2")
        return cls(
            make_agent_runner(
                model,
                tools,
                system_prompt,
                ApplicationAgentOutput,
            )
        )

    def run(
        self,
        agent_input: ApplicationAgentInput,
        *,
        config: RunnableConfig | None = None,
    ) -> ApplicationAgentOutput:
        return self._run(agent_input, config=config or {})
