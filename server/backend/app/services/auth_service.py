"""Authentication service workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.repositories import refresh_session_repository, user_repository
from app.services import password_service, token_service


class AuthError(Exception):
    """Generic authentication service failure."""


class DuplicateUserError(Exception):
    """Raised when a username or email cannot be used for registration."""


@dataclass(frozen=True)
class LoginTokenResult:
    """Token result returned after login."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class RefreshTokenResult:
    """Token result returned after refresh-token rotation."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


async def register_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
) -> User:
    """Register a user with an Argon2id password hash."""
    try:
        if await user_repository.username_exists(db, username):
            raise DuplicateUserError("User already exists.")
        if await user_repository.email_exists(db, email):
            raise DuplicateUserError("User already exists.")

        password_hash = password_service.hash_password(password)
        user = await user_repository.create_user(
            db,
            username=username,
            email=email,
            password_hash=password_hash,
        )
        await db.commit()
        await db.refresh(user)
        return user
    except DuplicateUserError:
        await db.rollback()
        raise
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateUserError("User already exists.") from exc


async def authenticate_user(
    db: AsyncSession,
    username_or_email: str,
    password: str,
) -> User | None:
    """Return an active user when credentials are valid."""
    user = await user_repository.get_by_username_or_email(db, username_or_email)
    if user is None or not user.is_active:
        return None

    if not password_service.verify_password(password, user.password_hash):
        return None

    return user


async def create_login_tokens(
    db: AsyncSession,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LoginTokenResult:
    """Create access and refresh tokens and store only the refresh-token hash."""
    try:
        access_token = token_service.create_access_token(user.id, user.role)
        refresh_token = token_service.create_refresh_token()
        refresh_token_hash = token_service.hash_refresh_token(refresh_token)
        await _create_refresh_session(
            db,
            user=user,
            refresh_token_hash=refresh_token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
        return LoginTokenResult(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=_access_token_expires_in_seconds(),
        )
    except Exception:
        await db.rollback()
        raise


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RefreshTokenResult:
    """Rotate a refresh token and issue a new access token."""
    try:
        refresh_token_hash = token_service.hash_refresh_token(refresh_token)
        current_session = await refresh_session_repository.get_active_by_hash(
            db,
            refresh_token_hash,
            for_update=True,
        )
        if current_session is None:
            raise AuthError("Invalid refresh token.")

        user = await user_repository.get_by_id(db, current_session.user_id)
        if user is None or not user.is_active:
            raise AuthError("Invalid refresh token.")

        current_session.revoked_at = datetime.now(UTC)
        await db.flush()

        access_token = token_service.create_access_token(user.id, user.role)
        new_refresh_token = token_service.create_refresh_token()
        new_refresh_token_hash = token_service.hash_refresh_token(new_refresh_token)
        await _create_refresh_session(
            db,
            user=user,
            refresh_token_hash=new_refresh_token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
        return RefreshTokenResult(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=_access_token_expires_in_seconds(),
        )
    except AuthError:
        await db.rollback()
        raise
    except token_service.TokenServiceError as exc:
        await db.rollback()
        raise AuthError("Invalid refresh token.") from exc
    except SQLAlchemyError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise AuthError("Invalid refresh token.") from exc


async def logout(db: AsyncSession, refresh_token: str) -> bool:
    """Revoke a refresh token if it maps to an active session."""
    try:
        refresh_token_hash = token_service.hash_refresh_token(refresh_token)
    except token_service.TokenServiceError:
        await db.rollback()
        return True

    try:
        session = await refresh_session_repository.get_active_by_hash(
            db,
            refresh_token_hash,
            for_update=True,
        )
        if session is not None:
            session.revoked_at = datetime.now(UTC)
            await db.flush()
        await db.commit()
        return True
    except SQLAlchemyError:
        await db.rollback()
        raise


async def logout_all(db: AsyncSession, user_id: UUID) -> int:
    """Revoke all active refresh sessions for a user."""
    try:
        revoked_count = await refresh_session_repository.revoke_all_for_user(db, user_id)
        await db.commit()
        return revoked_count
    except SQLAlchemyError:
        await db.rollback()
        raise


async def _create_refresh_session(
    db: AsyncSession,
    user: User,
    refresh_token_hash: str,
    ip_address: str | None,
    user_agent: str | None,
) -> RefreshSession:
    """Create a refresh session using service-owned expiry and JTI values."""
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return await refresh_session_repository.create_refresh_session(
        db,
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        jti=token_service.create_token_jti(),
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _access_token_expires_in_seconds() -> int:
    """Return configured access-token lifetime in seconds."""
    return settings.access_token_expire_minutes * 60
