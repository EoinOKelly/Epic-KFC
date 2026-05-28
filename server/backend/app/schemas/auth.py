"""Authentication and user schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, SecretStr, field_validator

from app.schemas.common import ORMResponseModel, StrictRequestModel, validate_username


class RegisterRequest(StrictRequestModel):
    """Registration request body."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: SecretStr

    @field_validator("username")
    @classmethod
    def validate_register_username(cls, value: str) -> str:
        """Validate username length and character set."""
        return validate_username(value)

    @field_validator("password")
    @classmethod
    def validate_register_password(cls, value: SecretStr) -> SecretStr:
        """Validate password length without exposing its value."""
        password = value.get_secret_value()
        if not 12 <= len(password) <= 128:
            raise ValueError("Password must be between 12 and 128 characters.")
        return value


class LoginRequest(StrictRequestModel):
    """Login request body."""

    username_or_email: str = Field(min_length=1, max_length=255)
    password: SecretStr

    @field_validator("username_or_email")
    @classmethod
    def validate_username_or_email(cls, value: str) -> str:
        """Reject blank login identifiers."""
        identifier = value.strip()
        if not identifier:
            raise ValueError("Username or email must not be blank.")
        return identifier

    @field_validator("password")
    @classmethod
    def validate_login_password(cls, value: SecretStr) -> SecretStr:
        """Validate password length without exposing its value."""
        password = value.get_secret_value()
        if not 12 <= len(password) <= 128:
            raise ValueError("Password must be between 12 and 128 characters.")
        return value


class RefreshTokenRequest(StrictRequestModel):
    """Refresh-token request body."""

    refresh_token: SecretStr = Field(min_length=1, max_length=4096)


class UserResponse(ORMResponseModel):
    """Safe user response without password hash exposure."""

    id: UUID
    username: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(ORMResponseModel):
    """Token response for future authentication endpoints."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(gt=0)
