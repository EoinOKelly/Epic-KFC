"""Authentication routes for API v1."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_ip_rate_limit, get_current_user, get_db
from app.core import rate_limit
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import SuccessResponse
from app.services import audit_service, auth_service
from app.services.auth_service import AuthError, DuplicateUserError


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register a user without issuing login tokens."""
    await enforce_ip_rate_limit(
        http_request,
        "auth.register",
        rate_limit.REGISTER_RATE_LIMIT,
    )
    try:
        user = await auth_service.register_user(
            db,
            username=request.username,
            email=str(request.email),
            password=request.password.get_secret_value(),
        )
    except DuplicateUserError as exc:
        await _record_audit_event(
            db,
            http_request,
            event_type="auth.register_duplicate_rejected",
            success=False,
            details={"reason": "duplicate_user"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is unavailable",
        ) from exc

    await _record_audit_event(
        db,
        http_request,
        event_type="auth.register_success",
        actor_user_id=user.id,
        success=True,
        resource_type="user",
        resource_id=user.id,
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate a user and issue access and refresh tokens."""
    await enforce_ip_rate_limit(
        http_request,
        "auth.login",
        rate_limit.LOGIN_RATE_LIMIT,
    )
    user = await auth_service.authenticate_user(
        db,
        username_or_email=request.username_or_email,
        password=request.password.get_secret_value(),
    )
    if user is None:
        await _record_audit_event(
            db,
            http_request,
            event_type="auth.login_failed",
            success=False,
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token_result = await auth_service.create_login_tokens(
        db,
        user,
        ip_address=_get_client_ip(http_request),
        user_agent=_get_user_agent(http_request),
    )
    await _record_audit_event(
        db,
        http_request,
        event_type="auth.login_success",
        actor_user_id=user.id,
        success=True,
        resource_type="user",
        resource_id=user.id,
    )
    return TokenResponse.model_validate(token_result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshTokenRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Rotate a refresh token and issue a new access token."""
    await enforce_ip_rate_limit(
        http_request,
        "auth.refresh",
        rate_limit.REFRESH_RATE_LIMIT,
    )
    try:
        token_result = await auth_service.refresh_access_token(
            db,
            refresh_token=request.refresh_token.get_secret_value(),
            ip_address=_get_client_ip(http_request),
            user_agent=_get_user_agent(http_request),
        )
    except AuthError as exc:
        await _record_audit_event(
            db,
            http_request,
            event_type="auth.refresh_failed",
            success=False,
            details={"reason": "invalid_refresh_token"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    await _record_audit_event(
        db,
        http_request,
        event_type="auth.refresh_success",
        success=True,
    )
    return TokenResponse.model_validate(token_result)


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    request: RefreshTokenRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """Revoke a refresh token without revealing whether it was valid."""
    await auth_service.logout(db, request.refresh_token.get_secret_value())
    await _record_audit_event(
        db,
        http_request,
        event_type="auth.logout",
        success=True,
    )
    return SuccessResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the authenticated user's safe profile."""
    return UserResponse.model_validate(current_user)


def _get_client_ip(request: Request) -> str | None:
    """Return the direct client IP when FastAPI provides it."""
    if request.client is None:
        return None
    return request.client.host


def _get_user_agent(request: Request) -> str | None:
    """Return the user-agent header without proxy-aware parsing."""
    return request.headers.get("user-agent")


async def _record_audit_event(
    db: AsyncSession,
    request: Request,
    event_type: str,
    success: bool,
    actor_user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    """Record an auth audit event without changing public route behavior."""
    await audit_service.record_audit_event_best_effort(
        db,
        actor_user_id=actor_user_id,
        event_type=event_type,
        success=success,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
        details=details,
    )
