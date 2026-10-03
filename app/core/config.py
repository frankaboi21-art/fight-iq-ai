from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fight IQ AI"
    environment: str = "development"
    debug: bool = False
    cors_origins: str = "http://localhost:8000,http://localhost:3000"
    openai_api_key: str | None = None
    openai_model: str = "gpt-6-astra"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
