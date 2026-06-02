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
    enforce_https: bool = False
    trust_x_forwarded_proto: bool = False
    hsts_enabled: bool = True
    hsts_max_age_seconds: int = Field(default=31_536_000, ge=0)
    allowed_origins: list[str] | str = Field(default_factory=list)
    cors_allow_credentials: bool = False
    blockchain_worker_enabled: bool = False
    sepolia_rpc_url: str | None = None
    deployer_private_key: str | None = None
    message_fidelity_address: str | None = None
    blockchain_worker_poll_interval_seconds: float = Field(default=15.0, gt=0)
    blockchain_worker_batch_size: int = Field(default=10, ge=1, le=100)
    blockchain_worker_receipt_timeout_seconds: int = Field(default=180, ge=1)
    blockchain_worker_chain_id: int = Field(default=11155111, ge=1)
    blockchain_worker_gas_limit: int = Field(default=150_000, ge=21_000)
    blockchain_worker_mark_failed_on_error: bool = False

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
    def validate_security_settings(self) -> Self:
        """Reject unsafe production and CORS settings."""
        if self.cors_allow_credentials and "*" in self.allowed_origins:
            raise ValueError(
                "ALLOWED_ORIGINS must not contain '*' when CORS_ALLOW_CREDENTIALS is true."
            )

        if _is_production(self.app_env) and "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must not contain '*' in production.")
        if _is_production(self.app_env):
            _validate_production_secret("JWT_SECRET_KEY", self.jwt_secret_key)
            _validate_production_secret(
                "REFRESH_TOKEN_HASH_SECRET",
                self.refresh_token_hash_secret,
            )
        if self.blockchain_worker_enabled:
            _validate_blockchain_worker_settings(self)
        return self


def _is_production(app_env: str) -> bool:
    """Return whether the configured environment is production-like."""
    return app_env.strip().lower() in {"prod", "production"}


def _validate_production_secret(name: str, value: str | None) -> None:
    """Reject missing, short, or placeholder secrets in production."""
    if not value:
        raise ValueError(f"{name} must be set in production.")
    if len(value) < 32:
        raise ValueError(f"{name} must be at least 32 characters in production.")

    normalized = value.lower()
    placeholder_markers = ("change_me", "changeme", "placeholder", "local_only")
    if any(marker in normalized for marker in placeholder_markers):
        raise ValueError(f"{name} must not use a placeholder value in production.")


def _validate_blockchain_worker_settings(settings: Settings) -> None:
    """Reject incomplete worker configuration when the worker is enabled."""
    missing: list[str] = []
    if not settings.sepolia_rpc_url:
        missing.append("SEPOLIA_RPC_URL")
    if not settings.deployer_private_key:
        missing.append("DEPLOYER_PRIVATE_KEY")
    if not settings.message_fidelity_address:
        missing.append("MESSAGE_FIDELITY_ADDRESS")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Blockchain worker is enabled but missing: {joined}.")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
