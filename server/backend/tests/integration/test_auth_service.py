"""Integration tests for authentication service workflows."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import refresh_session_repository, user_repository
from app.services import auth_service, token_service
from app.services.auth_service import AuthError, DuplicateUserError


pytestmark = pytest.mark.asyncio

JWT_SECRET = "auth-service-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "auth-service-test-refresh-secret-with-at-least-thirty-two-bytes"
VALID_PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "wrong-horse-battery-staple"


@pytest.fixture(autouse=True)
def configure_auth_service_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for auth service integration tests."""
    monkeypatch.setattr(token_service.settings, "jwt_secret_key", JWT_SECRET)
    monkeypatch.setattr(
        token_service.settings,
        "refresh_token_hash_secret",
        REFRESH_HASH_SECRET,
    )
    monkeypatch.setattr(token_service.settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(token_service.settings, "access_token_expire_minutes", 15)
    monkeypatch.setattr(token_service.settings, "refresh_token_expire_days", 7)
    monkeypatch.setattr(auth_service.settings, "access_token_expire_minutes", 15)
    monkeypatch.setattr(auth_service.settings, "refresh_token_expire_days", 7)


async def test_register_user_creates_user(integration_db: AsyncSession) -> None:
    """register_user creates a persisted user."""
    user = await auth_service.register_user(
        integration_db,
        username="alice",
        email="alice@example.com",
        password=VALID_PASSWORD,
    )

    found = await user_repository.get_by_id(integration_db, user.id)
    assert found is not None
    assert found.username == "alice"


async def test_register_user_stores_argon2id_phc_password_hash(
    integration_db: AsyncSession,
) -> None:
    """Registered users should store Argon2id PHC password hashes."""
    user = await auth_service.register_user(
        integration_db,
        username="bob",
        email="bob@example.com",
        password=VALID_PASSWORD,
    )

    assert user.password_hash.startswith("$argon2id$")


async def test_register_user_does_not_store_plaintext_password(
    integration_db: AsyncSession,
) -> None:
    """Registered users should not store plaintext passwords."""
    user = await auth_service.register_user(
        integration_db,
        username="carol",
        email="carol@example.com",
        password=VALID_PASSWORD,
    )

    assert user.password_hash != VALID_PASSWORD
    assert VALID_PASSWORD not in user.password_hash


async def test_duplicate_username_raises_duplicate_user_error(
    integration_db: AsyncSession,
) -> None:
    """Duplicate usernames should fail safely."""
    await auth_service.register_user(
        integration_db,
        username="dave",
        email="dave@example.com",
        password=VALID_PASSWORD,
    )

    with pytest.raises(DuplicateUserError):
        await auth_service.register_user(
            integration_db,
            username="dave",
            email="dave2@example.com",
            password=VALID_PASSWORD,
        )


async def test_duplicate_email_raises_duplicate_user_error(
    integration_db: AsyncSession,
) -> None:
    """Duplicate normalized emails should fail safely."""
    await auth_service.register_user(
        integration_db,
        username="erin",
        email="erin@example.com",
        password=VALID_PASSWORD,
    )

    with pytest.raises(DuplicateUserError):
        await auth_service.register_user(
            integration_db,
            username="erin2",
            email=" ERIN@EXAMPLE.COM ",
            password=VALID_PASSWORD,
        )


async def test_authenticate_user_succeeds_with_correct_password(
    integration_db: AsyncSession,
) -> None:
    """Correct credentials should return the user."""
    user = await _register_user(integration_db, "frank")

    authenticated = await auth_service.authenticate_user(
        integration_db,
        "frank",
        VALID_PASSWORD,
    )

    assert authenticated is not None
    assert authenticated.id == user.id


async def test_authenticate_user_fails_with_wrong_password(
    integration_db: AsyncSession,
) -> None:
    """Wrong password should return None."""
    await _register_user(integration_db, "grace")

    authenticated = await auth_service.authenticate_user(
        integration_db,
        "grace",
        WRONG_PASSWORD,
    )

    assert authenticated is None


async def test_authenticate_user_fails_for_unknown_user(
    integration_db: AsyncSession,
) -> None:
    """Unknown users should return None."""
    authenticated = await auth_service.authenticate_user(
        integration_db,
        "unknown",
        VALID_PASSWORD,
    )

    assert authenticated is None


async def test_authenticate_user_fails_for_inactive_user(
    integration_db: AsyncSession,
) -> None:
    """Inactive users should not authenticate."""
    user = await _register_user(integration_db, "heidi")
    await user_repository.set_user_active_status(integration_db, user.id, False)
    await integration_db.commit()

    authenticated = await auth_service.authenticate_user(
        integration_db,
        "heidi",
        VALID_PASSWORD,
    )

    assert authenticated is None


async def test_create_login_tokens_returns_access_and_refresh_tokens(
    integration_db: AsyncSession,
) -> None:
    """create_login_tokens returns token response-compatible data."""
    user = await _register_user(integration_db, "ivan")

    token_result = await auth_service.create_login_tokens(
        integration_db,
        user,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert token_result.access_token
    assert token_result.refresh_token
    assert token_result.token_type == "bearer"
    assert token_result.expires_in == 900


async def test_create_login_tokens_stores_refresh_token_hash_only(
    integration_db: AsyncSession,
) -> None:
    """Refresh sessions should store only the HMAC hash."""
    user = await _register_user(integration_db, "judy")

    token_result = await auth_service.create_login_tokens(integration_db, user)
    refresh_token_hash = token_service.hash_refresh_token(token_result.refresh_token)
    session = await refresh_session_repository.get_active_by_hash(
        integration_db,
        refresh_token_hash,
    )

    assert session is not None
    assert session.refresh_token_hash == refresh_token_hash
    assert session.refresh_token_hash != token_result.refresh_token
    assert token_result.refresh_token not in session.refresh_token_hash


async def test_refresh_access_token_works_for_active_refresh_token(
    integration_db: AsyncSession,
) -> None:
    """Active refresh tokens should rotate and return new tokens."""
    user = await _register_user(integration_db, "kate")
    token_result = await auth_service.create_login_tokens(integration_db, user)

    refreshed = await auth_service.refresh_access_token(
        integration_db,
        token_result.refresh_token,
    )

    assert refreshed.access_token
    assert refreshed.refresh_token
    assert refreshed.refresh_token != token_result.refresh_token


async def test_refresh_access_token_rotates_refresh_token(
    integration_db: AsyncSession,
) -> None:
    """Refresh rotation should create a new active refresh session."""
    user = await _register_user(integration_db, "laura")
    token_result = await auth_service.create_login_tokens(integration_db, user)

    refreshed = await auth_service.refresh_access_token(
        integration_db,
        token_result.refresh_token,
    )
    new_hash = token_service.hash_refresh_token(refreshed.refresh_token)
    new_session = await refresh_session_repository.get_active_by_hash(
        integration_db,
        new_hash,
    )

    assert new_session is not None
    assert new_session.user_id == user.id


async def test_refresh_access_token_revokes_old_refresh_session(
    integration_db: AsyncSession,
) -> None:
    """Refresh rotation should revoke the old session."""
    user = await _register_user(integration_db, "mallory")
    token_result = await auth_service.create_login_tokens(integration_db, user)
    old_hash = token_service.hash_refresh_token(token_result.refresh_token)
    old_session = await refresh_session_repository.get_active_by_hash(
        integration_db,
        old_hash,
    )
    assert old_session is not None
    old_jti = old_session.jti

    await auth_service.refresh_access_token(integration_db, token_result.refresh_token)
    old_session = await refresh_session_repository.get_by_jti(integration_db, old_jti)
    old_active = await refresh_session_repository.get_active_by_hash(
        integration_db,
        old_hash,
    )

    assert old_session is not None
    assert old_session.revoked_at is not None
    assert old_active is None


async def test_old_refresh_token_cannot_be_reused_after_rotation(
    integration_db: AsyncSession,
) -> None:
    """A rotated refresh token should not be reusable."""
    user = await _register_user(integration_db, "nancy")
    token_result = await auth_service.create_login_tokens(integration_db, user)
    await auth_service.refresh_access_token(integration_db, token_result.refresh_token)

    with pytest.raises(AuthError):
        await auth_service.refresh_access_token(integration_db, token_result.refresh_token)


async def test_refresh_access_token_rejects_invalid_token(
    integration_db: AsyncSession,
) -> None:
    """Unknown refresh tokens should fail generically."""
    with pytest.raises(AuthError):
        await auth_service.refresh_access_token(integration_db, "unknown-refresh-token")


async def test_refresh_access_token_rejects_revoked_token(
    integration_db: AsyncSession,
) -> None:
    """Revoked refresh tokens should fail generically."""
    user = await _register_user(integration_db, "olivia")
    token_result = await auth_service.create_login_tokens(integration_db, user)
    await auth_service.logout(integration_db, token_result.refresh_token)

    with pytest.raises(AuthError):
        await auth_service.refresh_access_token(integration_db, token_result.refresh_token)


async def test_refresh_access_token_rejects_expired_token(
    integration_db: AsyncSession,
) -> None:
    """Expired refresh sessions should fail generically."""
    user = await _register_user(integration_db, "peggy")
    raw_token = token_service.create_refresh_token()
    token_hash = token_service.hash_refresh_token(raw_token)
    await refresh_session_repository.create_refresh_session(
        integration_db,
        user_id=user.id,
        refresh_token_hash=token_hash,
        jti=token_service.create_token_jti(),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    await integration_db.commit()

    with pytest.raises(AuthError):
        await auth_service.refresh_access_token(integration_db, raw_token)


async def test_logout_revokes_refresh_session(integration_db: AsyncSession) -> None:
    """logout should revoke the matching active refresh session."""
    user = await _register_user(integration_db, "quentin")
    token_result = await auth_service.create_login_tokens(integration_db, user)
    token_hash = token_service.hash_refresh_token(token_result.refresh_token)

    result = await auth_service.logout(integration_db, token_result.refresh_token)
    active_session = await refresh_session_repository.get_active_by_hash(
        integration_db,
        token_hash,
    )

    assert result is True
    assert active_session is None


async def test_logout_returns_success_for_unknown_token(
    integration_db: AsyncSession,
) -> None:
    """logout should not reveal token validity."""
    result = await auth_service.logout(integration_db, "unknown-refresh-token")

    assert result is True


async def test_logout_all_revokes_all_user_sessions(
    integration_db: AsyncSession,
) -> None:
    """logout_all should revoke all active user sessions."""
    user = await _register_user(integration_db, "rachel")
    first = await auth_service.create_login_tokens(integration_db, user)
    second = await auth_service.create_login_tokens(integration_db, user)

    revoked_count = await auth_service.logout_all(integration_db, user.id)

    assert revoked_count == 2
    assert (
        await refresh_session_repository.get_active_by_hash(
            integration_db,
            token_service.hash_refresh_token(first.refresh_token),
        )
        is None
    )
    assert (
        await refresh_session_repository.get_active_by_hash(
            integration_db,
            token_service.hash_refresh_token(second.refresh_token),
        )
        is None
    )


async def _register_user(integration_db: AsyncSession, username: str):
    """Register a test user with a predictable email address."""
    return await auth_service.register_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password=VALID_PASSWORD,
    )
