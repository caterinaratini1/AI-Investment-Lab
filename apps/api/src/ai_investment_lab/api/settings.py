"""Environment-driven API settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AIL_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://ai_lab:ai_lab@localhost:5432/ai_investment_lab",
    )
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    eodhd_api_token: str | None = None
    eodhd_base_url: str = "https://eodhd.com/api"


@lru_cache
def get_settings() -> Settings:
    return Settings()
