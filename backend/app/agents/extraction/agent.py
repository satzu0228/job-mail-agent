import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.common.runner import StructuredOutputInvoker, load_prompt
from app.agents.extraction.schemas import ExtractionInput, ExtractionOutput


class ExtractionAgent:
    prompt_version = "v2"

    def __init__(
        self,
        invoker: StructuredOutputInvoker[ExtractionOutput],
    ) -> None:
        self._invoker = invoker

    @classmethod
    def from_model(cls, model: BaseChatModel) -> "ExtractionAgent":
        invoker = model.with_structured_output(
            ExtractionOutput,
            method="json_mode",
        )
        return cls(invoker)

    def run(self, agent_input: ExtractionInput) -> ExtractionOutput:
        schema = ExtractionOutput.model_json_schema()
        payload = agent_input.model_dump(mode="json")
        messages = [
            SystemMessage(content=load_prompt("extraction", self.prompt_version)),
            HumanMessage(
                content=(
                    "请从下面的求职邮件中抽取信息，并且只返回一个符合输出 Schema 的 JSON 对象。\n"
                    f"输出 Schema：\n{json.dumps(schema, ensure_ascii=False)}\n"
                    f"邮件与分类输入：\n{json.dumps(payload, ensure_ascii=False)}"
                )
            ),
        ]
        result = self._invoker.invoke(messages)
        return ExtractionOutput.model_validate(result)
