import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.classification.schemas import (
    ClassificationInput,
    ClassificationOutput,
)
from app.agents.common.runner import StructuredOutputInvoker, load_prompt


class ClassificationAgent:
    prompt_version = "v1"

    def __init__(
        self,
        invoker: StructuredOutputInvoker[ClassificationOutput],
    ) -> None:
        self._invoker = invoker

    @classmethod
    def from_model(cls, model: BaseChatModel) -> "ClassificationAgent":
        invoker = model.with_structured_output(
            ClassificationOutput,
            method="json_mode",
        )
        return cls(invoker)

    def run(self, agent_input: ClassificationInput) -> ClassificationOutput:
        schema = ClassificationOutput.model_json_schema()
        payload = agent_input.model_dump(mode="json")
        messages = [
            SystemMessage(content=load_prompt("classification", self.prompt_version)),
            HumanMessage(
                content=(
                    "请分析下面的邮件输入，并且只返回一个符合输出 Schema 的 JSON 对象。\n"
                    f"输出 Schema：\n{json.dumps(schema, ensure_ascii=False)}\n"
                    f"邮件输入：\n{json.dumps(payload, ensure_ascii=False)}"
                )
            ),
        ]
        result = self._invoker.invoke(messages)
        return ClassificationOutput.model_validate(result)
