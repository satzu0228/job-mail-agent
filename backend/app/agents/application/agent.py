import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.application.schemas import (
    ApplicationAgentInput,
    ApplicationAgentOutput,
)
from app.agents.common.runner import StructuredOutputInvoker, load_prompt


class ApplicationAgent:
    prompt_version = "v1"

    def __init__(
        self,
        invoker: StructuredOutputInvoker[ApplicationAgentOutput],
    ) -> None:
        self._invoker = invoker

    @classmethod
    def from_model(cls, model: BaseChatModel) -> "ApplicationAgent":
        return cls(
            model.with_structured_output(
                ApplicationAgentOutput,
                method="json_mode",
            )
        )

    def run(self, agent_input: ApplicationAgentInput) -> ApplicationAgentOutput:
        schema = ApplicationAgentOutput.model_json_schema()
        messages = [
            SystemMessage(content=load_prompt("application", self.prompt_version)),
            HumanMessage(
                content=(
                    "请比较分析事实与候选申请，只返回符合输出 Schema 的 JSON 对象。\n"
                    f"输出 Schema：\n"
                    f"{json.dumps(schema, ensure_ascii=False)}\n"
                    f"输入：\n{json.dumps(agent_input.model_dump(mode='json'), ensure_ascii=False)}"
                )
            ),
        ]
        return ApplicationAgentOutput.model_validate(self._invoker.invoke(messages))
