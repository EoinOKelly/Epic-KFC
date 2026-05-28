"""Shared FastAPI dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import (
    GLOBAL_RATE_LIMITER,
    RateLimitExceeded,
    RateLimitRule,
    build_windowed_key,
)
from app.models.user import User
from app.repositories import user_repository
from app.services import token_service

from ..db.session import get_db as _get_db


bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for route dependencies."""
    async for session in _get_db():
        yield session


def _authentication_error() -> HTTPException:
    """Return a generic authentication failure without leaking details."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Return the active user identified by a verified Bearer access token."""
    if credentials is None:
        raise _authentication_error()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _authentication_error()

    try:
        token_payload = token_service.decode_access_token(credentials.credentials)
        user_id = UUID(token_payload.sub)
    except (ValueError, token_service.TokenServiceError) as exc:
        raise _authentication_error() from exc

    user = await user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise _authentication_error()

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current active user for future protected routes."""
    return current_user


async def enforce_ip_rate_limit(
    request: Request,
    scope: str,
    rule: RateLimitRule,
) -> None:
    """Enforce a rate limit keyed by direct client IP."""
    caller_id = _get_client_ip(request)
    key = build_windowed_key(scope, "ip", caller_id, rule)
    await _enforce_rate_limit(key, rule)


async def enforce_user_rate_limit(
    user_id: UUID,
    scope: str,
    rule: RateLimitRule,
) -> None:
    """Enforce a rate limit keyed by authenticated user ID."""
    key = build_windowed_key(scope, "user", str(user_id), rule)
    await _enforce_rate_limit(key, rule)


async def _enforce_rate_limit(key: str, rule: RateLimitRule) -> None:
    """Raise a safe HTTP 429 when the configured limit is exceeded."""
    try:
        await GLOBAL_RATE_LIMITER.check(
            key,
            rule,
            enabled=settings.rate_limit_enabled,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


def _get_client_ip(request: Request) -> str:
    """Return a non-secret IP identity for unauthenticated rate limits."""
    if request.client is None:
        return "unknown"
    return request.client.host
