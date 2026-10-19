from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "Fight IQ AI"
    environment: str = "development"
    debug: bool = False
    cors_origins: str = "http://localhost:8000,http://localhost:3000"
    openai_api_key: str | None = None
    openai_model: str = "gpt-6-astra"
    beta_access_code: str = ""
    session_hours: int = Field(default=8, ge=1, le=24)
    coach_hourly_limit: int = Field(default=10, ge=1, le=100)
    coach_daily_limit: int = Field(default=30, ge=1, le=500)
    usage_db_path: str = ".data/usage.sqlite3"
    public_origin: str = ""
    render_external_url: str = ""
    database_url: str = ""
    training_db_path: str = ".data/training.sqlite3"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
