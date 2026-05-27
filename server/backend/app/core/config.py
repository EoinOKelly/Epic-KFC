"""Environment-based application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables."""

    app_name: str = "Secure Messaging API"
    app_env: str = "development"
    database_url: str | None = Field(
        default=None,
        description="Async SQLAlchemy database URL.",
    )
    test_database_url: str | None = Field(
        default=None,
        description="Async SQLAlchemy database URL for tests.",
    )
    log_level: str = "INFO"
    jwt_secret_key: str | None = None
    refresh_token_hash_secret: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
