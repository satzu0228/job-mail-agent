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

    llm_config 来自数据库中用户在前端页面配置的活跃 LLM 配置；必须传入。
    """
    if not llm_config:
        raise LLMConfigurationError(
            "未配置 AI 模型，请前往「设置 > AI 模型」页面添加 DeepSeek API Key"
        )

    provider = llm_config.get("provider", settings.llm_provider)
    if provider != "deepseek":
        raise LLMConfigurationError(
            f"LLM provider {provider!r} is reserved but not implemented in the MVP"
        )

    api_key = llm_config.get("api_key")
    if not api_key:
        raise LLMConfigurationError(
            "未配置 AI 模型 API Key，请前往「设置 > AI 模型」页面添加 DeepSeek API Key"
        )

    return ChatDeepSeek(
        model=llm_config.get("model", settings.llm_model),
        api_key=api_key,
        temperature=llm_config.get("temperature", settings.llm_temperature),
        timeout=llm_config.get("timeout_seconds", settings.llm_timeout_seconds),
        max_retries=llm_config.get("max_retries", settings.llm_max_retries),
        **(
            {"base_url": llm_config["base_url"]}
            if llm_config.get("base_url")
            else {}
        ),
    )
