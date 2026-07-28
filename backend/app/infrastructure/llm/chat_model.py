from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek

from app.core.config import Settings


class LLMConfigurationError(RuntimeError):
    """模型供应商配置无法初始化时抛出的异常。"""


def create_chat_model(settings: Settings) -> BaseChatModel:
    """创建聊天模型，同时避免智能体直接依赖具体供应商 SDK。"""
    if settings.llm_provider != "deepseek":
        raise LLMConfigurationError(
            f"LLM provider {settings.llm_provider!r} is reserved but not implemented in the MVP"
        )
    if settings.llm_api_key is None:
        raise LLMConfigurationError(
            "Missing LLM API key: set JOB_MAIL_LLM_API_KEY or DEEPSEEK_API_KEY"
        )

    return ChatDeepSeek(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
