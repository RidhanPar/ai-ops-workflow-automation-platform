from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Operations & Workflow Automation Platform"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg2://aiops:aiops@localhost:5432/aiops"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
