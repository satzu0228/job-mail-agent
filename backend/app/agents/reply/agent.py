import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.common.runner import StructuredOutputInvoker, load_prompt
from app.agents.reply.schemas import ReplyAgentInput, ReplyAgentOutput


class ReplyAgent:
    prompt_version = "v1"

    def __init__(self, invoker: StructuredOutputInvoker[ReplyAgentOutput]) -> None:
        self._invoker = invoker

    @classmethod
    def from_model(cls, model: BaseChatModel) -> "ReplyAgent":
        return cls(
            model.with_structured_output(
                ReplyAgentOutput,
                method="json_mode",
            )
        )

    def run(self, agent_input: ReplyAgentInput) -> ReplyAgentOutput:
        schema = ReplyAgentOutput.model_json_schema()
        messages = [
            SystemMessage(content=load_prompt("reply", self.prompt_version)),
            HumanMessage(
                content=(
                    "请根据邮件、分析、申请和用户上下文判断是否需要回复，并只返回符合"
                    "输出 Schema 的 JSON 对象。\n"
                    f"输出 Schema：\n{json.dumps(schema, ensure_ascii=False)}\n"
                    f"输入：\n"
                    f"{json.dumps(agent_input.model_dump(mode='json'), ensure_ascii=False)}"
                )
            ),
        ]
        return ReplyAgentOutput.model_validate(self._invoker.invoke(messages))
