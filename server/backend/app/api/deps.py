"""Shared FastAPI dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

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
