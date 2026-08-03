from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek

from app.core.config import Settings


class LLMConfigurationError(RuntimeError):
    """模型供应商配置无法初始化时抛出的异常。"""


def create_chat_model(
    settings: Settings,
    llm_config: dict[str, Any] | None = None,
) -> BaseChatModel:
    """创建聊天模型，同时避免智能体直接依赖具体供应商 SDK。

    llm_config 来自数据库中的用户配置；未传入时回退到环境变量 settings。
    """
    provider = (llm_config or {}).get("provider", settings.llm_provider)
    if provider != "deepseek":
        raise LLMConfigurationError(
            f"LLM provider {provider!r} is reserved but not implemented in the MVP"
        )

    api_key = (llm_config or {}).get("api_key")
    if api_key is None:
        api_key = settings.llm_api_key
    if api_key is None:
        raise LLMConfigurationError(
            "Missing LLM API key: set JOB_MAIL_LLM_API_KEY or DEEPSEEK_API_KEY, "
            "or configure one in the settings page"
        )

    return ChatDeepSeek(
        model=(llm_config or {}).get("model", settings.llm_model),
        api_key=api_key,
        temperature=(llm_config or {}).get("temperature", settings.llm_temperature),
        timeout=(llm_config or {}).get(
            "timeout_seconds", settings.llm_timeout_seconds
        ),
        max_retries=(llm_config or {}).get("max_retries", settings.llm_max_retries),
        **(
            {"base_url": llm_config["base_url"]}
            if llm_config and llm_config.get("base_url")
            else {}
        ),
    )
