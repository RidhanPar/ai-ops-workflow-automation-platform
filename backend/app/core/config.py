from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Operations & Workflow Automation Platform"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg2://aiops:aiops@localhost:5432/aiops"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_timeout_seconds: float = 20
    openai_max_retries: int = 2
    openai_input_cost_per_1m: float = 1.25
    openai_output_cost_per_1m: float = 10.0
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_timeout_seconds: float = 20
    anthropic_max_retries: int = 2
    anthropic_max_tokens: int = 1024
    anthropic_input_cost_per_1m: float = 3.0
    anthropic_output_cost_per_1m: float = 15.0
    jwt_secret: str = "local-demo-secret-change-me-please-32"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    demo_seed_enabled: bool = False
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "ai-ops-workflow-platform"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg2://", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
