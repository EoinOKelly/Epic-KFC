"""Integration tests for refresh session repository functions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import refresh_session_repository, user_repository


pytestmark = pytest.mark.asyncio

PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
RAW_REFRESH_TOKEN = "raw-refresh-token-value"
REFRESH_TOKEN_HASH = "hmac_sha256:" + ("a" * 64)


async def test_create_refresh_session_stores_hash_and_metadata(
    integration_db: AsyncSession,
) -> None:
    """create_refresh_session stores the token hash and metadata."""
    user = await _create_user(integration_db, "alice")
    expires_at = datetime.now(UTC) + timedelta(days=7)

    session = await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-create",
        expires_at=expires_at,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert session.user_id == user.id
    assert session.refresh_token_hash == REFRESH_TOKEN_HASH
    assert session.jti == "jti-create"
    assert session.ip_address == "127.0.0.1"
    assert session.user_agent == "pytest"


async def test_raw_refresh_token_is_never_stored(integration_db: AsyncSession) -> None:
    """Repository stores only the caller-provided hash, not a raw token."""
    user = await _create_user(integration_db, "bob")

    session = await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-raw-token",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    assert session.refresh_token_hash != RAW_REFRESH_TOKEN
    assert RAW_REFRESH_TOKEN not in session.refresh_token_hash


async def test_get_active_by_hash_returns_active_session(
    integration_db: AsyncSession,
) -> None:
    """Active sessions are returned by hash."""
    user = await _create_user(integration_db, "carol")
    session = await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-active",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    found = await refresh_session_repository.get_active_by_hash(
        integration_db,
        REFRESH_TOKEN_HASH,
    )

    assert found is not None
    assert found.id == session.id


async def test_expired_session_is_not_returned_as_active(
    integration_db: AsyncSession,
) -> None:
    """Expired sessions are not active."""
    user = await _create_user(integration_db, "dave")
    await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-expired",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    found = await refresh_session_repository.get_active_by_hash(
        integration_db,
        REFRESH_TOKEN_HASH,
    )

    assert found is None


async def test_revoked_session_is_not_returned_as_active(
    integration_db: AsyncSession,
) -> None:
    """Revoked sessions are not active."""
    user = await _create_user(integration_db, "erin")
    session = await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-revoked",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await refresh_session_repository.revoke_session(integration_db, session.id)

    found = await refresh_session_repository.get_active_by_hash(
        integration_db,
        REFRESH_TOKEN_HASH,
    )

    assert found is None


async def test_get_by_jti_works(integration_db: AsyncSession) -> None:
    """Sessions can be fetched by JTI."""
    user = await _create_user(integration_db, "frank")
    session = await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-lookup",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    found = await refresh_session_repository.get_by_jti(integration_db, "jti-lookup")

    assert found is not None
    assert found.id == session.id


async def test_revoke_by_hash_sets_revoked_at(integration_db: AsyncSession) -> None:
    """Revoking by hash sets revoked_at."""
    user = await _create_user(integration_db, "grace")
    await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-revoke-hash",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    revoked = await refresh_session_repository.revoke_by_hash(
        integration_db,
        REFRESH_TOKEN_HASH,
    )

    assert revoked is not None
    assert revoked.revoked_at is not None


async def test_revoke_session_sets_revoked_at(integration_db: AsyncSession) -> None:
    """Revoking by session ID sets revoked_at."""
    user = await _create_user(integration_db, "heidi")
    session = await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=REFRESH_TOKEN_HASH,
        jti="jti-revoke-session",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    revoked = await refresh_session_repository.revoke_session(integration_db, session.id)

    assert revoked is not None
    assert revoked.revoked_at is not None


async def test_revoke_all_for_user_revokes_multiple_active_sessions(
    integration_db: AsyncSession,
) -> None:
    """Revoking all user sessions updates multiple active rows."""
    user = await _create_user(integration_db, "ivan")
    await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash="hmac_sha256:" + ("b" * 64),
        jti="jti-revoke-all-1",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash="hmac_sha256:" + ("c" * 64),
        jti="jti-revoke-all-2",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    revoked_count = await refresh_session_repository.revoke_all_for_user(
        integration_db,
        user.id,
    )

    assert revoked_count == 2


async def test_unknown_hash_returns_none(integration_db: AsyncSession) -> None:
    """Unknown refresh-token hashes return None."""
    found = await refresh_session_repository.get_active_by_hash(
        integration_db,
        "hmac_sha256:" + ("d" * 64),
    )

    assert found is None


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a user for refresh-session tests."""
    return await user_repository.create_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password_hash=PASSWORD_HASH,
    )
