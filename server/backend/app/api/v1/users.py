"""User discovery routes for API v1."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_user_rate_limit, get_current_user, get_db
from app.core import rate_limit
from app.models.user import User
from app.repositories import device_key_repository, user_repository
from app.schemas.user import UserByUsernameResponse, UserDeviceSummary


router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/by-username/{username}",
    response_model=UserByUsernameResponse,
)
async def get_user_by_username(
    username: Annotated[
        str,
        Path(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$"),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserByUsernameResponse:
    """Return a public-safe user/device summary by username."""
    await enforce_user_rate_limit(
        current_user.id,
        "users.by_username",
        rate_limit.USER_LOOKUP_RATE_LIMIT,
    )
    user = await user_repository.get_by_username(db, username)
    if user is None or not user.is_active:
        raise _user_not_found_error()

    devices = await device_key_repository.list_devices_for_user(db, user.id)
    return UserByUsernameResponse(
        id=user.id,
        username=user.username,
        devices=[
            UserDeviceSummary(
                device_id=device.device_id,
                is_active=device.is_active and device.revoked_at is None,
            )
            for device in devices
        ],
    )


def _user_not_found_error() -> HTTPException:
    """Return a safe user lookup failure."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found",
    )
