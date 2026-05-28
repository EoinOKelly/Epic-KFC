"""Async repository functions for refresh-token sessions."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession


async def create_refresh_session(
    db: AsyncSession,
    user_id: UUID,
    refresh_token_hash: str,
    jti: str,
    expires_at: datetime,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RefreshSession:
    """Create a refresh session with a stored token hash only."""
    session = RefreshSession(
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        jti=jti,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def get_active_by_hash(
    db: AsyncSession,
    refresh_token_hash: str,
    *,
    for_update: bool = False,
) -> RefreshSession | None:
    """Return an active refresh session by token hash."""
    statement = select(RefreshSession).where(
        RefreshSession.refresh_token_hash == refresh_token_hash,
        RefreshSession.revoked_at.is_(None),
        RefreshSession.expires_at > datetime.now(UTC),
    )
    if for_update:
        statement = statement.with_for_update()

    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_by_jti(db: AsyncSession, jti: str) -> RefreshSession | None:
    """Return a refresh session by JWT ID."""
    result = await db.execute(select(RefreshSession).where(RefreshSession.jti == jti))
    return result.scalar_one_or_none()


async def revoke_session(
    db: AsyncSession,
    session_id: UUID,
) -> RefreshSession | None:
    """Revoke a refresh session by setting revoked_at."""
    result = await db.execute(
        select(RefreshSession).where(RefreshSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None

    session.revoked_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(session)
    return session


async def revoke_by_hash(
    db: AsyncSession,
    refresh_token_hash: str,
) -> RefreshSession | None:
    """Revoke a refresh session by its stored hash."""
    result = await db.execute(
        select(RefreshSession).where(
            RefreshSession.refresh_token_hash == refresh_token_hash
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None

    session.revoked_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(session)
    return session


async def revoke_all_for_user(db: AsyncSession, user_id: UUID) -> int:
    """Revoke all active refresh sessions for a user."""
    result = await db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.flush()
    return result.rowcount or 0
