from functools import lru_cache
from pathlib import Path

from pydantic import Field
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

    database_url: str = (
        "mysql+pymysql://job_mail:change-me@127.0.0.1:3306/"
        "job_mail_agent?charset=utf8mb4"
    )
    db_pool_recycle: int = Field(default=1800, ge=1)
    checkpoint_path: Path = Path("runtime/checkpoints.sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
