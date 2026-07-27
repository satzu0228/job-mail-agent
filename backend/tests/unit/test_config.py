from app.core.config import Settings


def test_settings_use_mysql_pymysql_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("mysql+pymysql://")
    assert settings.api_v1_prefix == "/api/v1"
