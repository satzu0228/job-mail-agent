from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOB_MAIL_",
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Job Mail Agent API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    demo_user_id: int = Field(default=1, gt=0)

    database_url: str = (
        "mysql+pymysql://job_mail:change-me@127.0.0.1:3306/"
        "job_mail_agent?charset=utf8mb4"
    )
    db_pool_recycle: int = Field(default=1800, ge=1)
    checkpoint_path: Path = Path("runtime/checkpoints.sqlite")
    checkpoint_encryption_key: SecretStr | None = None
    email_connect_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    email_sync_limit: int = Field(default=50, ge=1, le=200)
    email_max_message_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=64 * 1024,
        le=50 * 1024 * 1024,
    )
    automation_enabled: bool = True
    automation_poll_seconds: float = Field(default=30.0, ge=5.0, le=300.0)
    reminder_lead_minutes: int = Field(default=60, ge=5, le=24 * 60)

    llm_provider: Literal["deepseek", "qwen"] = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("JOB_MAIL_LLM_API_KEY", "DEEPSEEK_API_KEY"),
    )
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()
