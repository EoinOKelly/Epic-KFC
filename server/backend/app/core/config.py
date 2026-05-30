"""Environment-based application configuration."""

import json
from functools import lru_cache
from typing import Any, Self

from pydantic import Field, field_validator, model_validator
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
    rate_limit_enabled: bool = True
    security_headers_enabled: bool = True
    allowed_origins: list[str] | str = Field(default_factory=list)
    cors_allow_credentials: bool = False

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        """Accept allowed origins as JSON array or comma-separated string."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("ALLOWED_ORIGINS JSON value must be a list.")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise ValueError("ALLOWED_ORIGINS must be a list or comma-separated string.")

    @model_validator(mode="after")
    def validate_production_cors(self) -> Self:
        """Reject wildcard CORS origins in production."""
        if self.app_env.lower() == "production" and "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must not contain '*' in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
