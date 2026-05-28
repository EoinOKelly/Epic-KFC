"""Security tests for authentication and token handling."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.core import rate_limit
from app.main import app
from app.repositories import user_repository
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "security-auth-jwt-secret-with-at-least-sixty-four-bytes-123456789"
WRONG_JWT_SECRET = "wrong-security-auth-jwt-secret-with-at-least-sixty-four-bytes"
REFRESH_HASH_SECRET = "security-auth-refresh-secret-with-at-least-thirty-two"
PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "wrong-horse-battery-staple"


@pytest.fixture(autouse=True)
def configure_auth_security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure deterministic auth settings for security tests."""
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
    monkeypatch.setattr(api_deps.settings, "rate_limit_enabled", False)


@pytest_asyncio.fixture
async def auth_security_client(
    integration_db: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async client using the guarded test database session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield integration_db

    app.dependency_overrides[api_deps.get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"user-agent": "pytest-security-auth"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def test_unknown_user_login_returns_generic_401(
    auth_security_client: AsyncClient,
) -> None:
    """Unknown users should receive a generic login failure."""
    response = await _login(auth_security_client, "missing-user")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_wrong_password_returns_same_generic_401(
    auth_security_client: AsyncClient,
) -> None:
    """Wrong passwords should not reveal account existence."""
    await _register(auth_security_client, "alice")

    unknown = await _login(auth_security_client, "missing-user")
    wrong_password = await _login(auth_security_client, "alice", WRONG_PASSWORD)

    assert unknown.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()


async def test_inactive_user_cannot_log_in(
    auth_security_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Inactive accounts are rejected with the generic login failure."""
    await _register(auth_security_client, "bob")
    user = await user_repository.get_by_username(integration_db, "bob")
    assert user is not None
    await user_repository.set_user_active_status(integration_db, user.id, False)
    await integration_db.commit()

    response = await _login(auth_security_client, "bob")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_malformed_jwt_rejected_by_auth_me(
    auth_security_client: AsyncClient,
) -> None:
    """Malformed Bearer tokens are rejected generically."""
    response = await auth_security_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


async def test_expired_jwt_rejected(
    auth_security_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Expired access tokens cannot authenticate."""
    user_id = await _create_user_id(auth_security_client, integration_db, "carol")
    token = _encode_access_token(user_id, expires_delta=timedelta(minutes=-1))

    response = await _get_me(auth_security_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


async def test_wrong_signature_jwt_rejected(
    auth_security_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Access tokens signed with the wrong secret are rejected."""
    user_id = await _create_user_id(auth_security_client, integration_db, "dave")
    token = _encode_access_token(user_id, secret=WRONG_JWT_SECRET)

    response = await _get_me(auth_security_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


async def test_wrong_token_type_rejected(
    auth_security_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """JWTs with a non-access type cannot authenticate."""
    user_id = await _create_user_id(auth_security_client, integration_db, "erin")
    token = _encode_access_token(user_id, token_type="refresh")

    response = await _get_me(auth_security_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


async def test_raw_refresh_token_cannot_be_used_as_bearer_access_token(
    auth_security_client: AsyncClient,
) -> None:
    """Opaque refresh tokens are not valid Bearer access tokens."""
    await _register(auth_security_client, "frank")
    login = await _login(auth_security_client, "frank")
    refresh_token = login.json()["refresh_token"]

    response = await _get_me(auth_security_client, refresh_token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


async def test_refresh_rotation_makes_old_refresh_token_unusable(
    auth_security_client: AsyncClient,
) -> None:
    """Refresh-token rotation prevents replay of the old token."""
    await _register(auth_security_client, "grace")
    login = await _login(auth_security_client, "grace")
    old_refresh_token = login.json()["refresh_token"]

    first_refresh = await _refresh(auth_security_client, old_refresh_token)
    replay = await _refresh(auth_security_client, old_refresh_token)

    assert first_refresh.status_code == 200
    assert replay.status_code == 401
    assert replay.json()["detail"] == "Invalid refresh token"


async def test_logout_makes_refresh_token_unusable(
    auth_security_client: AsyncClient,
) -> None:
    """Logout revokes the submitted refresh token."""
    await _register(auth_security_client, "heidi")
    login = await _login(auth_security_client, "heidi")
    refresh_token = login.json()["refresh_token"]

    logout = await auth_security_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    refresh = await _refresh(auth_security_client, refresh_token)

    assert logout.status_code == 200
    assert refresh.status_code == 401
    assert refresh.json()["detail"] == "Invalid refresh token"


async def test_repeated_login_attempts_trigger_429(
    auth_security_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brute-force-style login attempts are rate limited."""
    monkeypatch.setattr(api_deps.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        rate_limit,
        "LOGIN_RATE_LIMIT",
        rate_limit.RateLimitRule(limit=2, window_seconds=60),
    )

    first = await _login(auth_security_client, "missing-user")
    second = await _login(auth_security_client, "missing-user")
    third = await _login(auth_security_client, "missing-user")

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert third.json()["detail"] == "Too many requests"


async def test_auth_failures_do_not_expose_account_existence(
    auth_security_client: AsyncClient,
) -> None:
    """Auth failure bodies should not mention whether an account exists."""
    await _register(auth_security_client, "ivan")

    response = await _login(auth_security_client, "ivan", WRONG_PASSWORD)
    body = response.text.lower()

    assert response.status_code == 401
    assert "ivan" not in body
    assert "exists" not in body
    assert "inactive" not in body


async def _register(client: AsyncClient, username: str) -> Response:
    """Register a test user."""
    return await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )


async def _login(
    client: AsyncClient,
    username_or_email: str,
    password: str = PASSWORD,
) -> Response:
    """Attempt login."""
    return await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username_or_email, "password": password},
    )


async def _refresh(client: AsyncClient, refresh_token: str) -> Response:
    """Attempt refresh-token rotation."""
    return await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )


async def _get_me(client: AsyncClient, token: str) -> Response:
    """Call /auth/me with a Bearer token."""
    return await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _create_user_id(
    client: AsyncClient,
    integration_db: AsyncSession,
    username: str,
):
    """Register a user and return its UUID."""
    response = await _register(client, username)
    assert response.status_code == 201
    user = await user_repository.get_by_username(integration_db, username)
    assert user is not None
    return user.id


def _encode_access_token(
    user_id,
    *,
    secret: str = JWT_SECRET,
    expires_delta: timedelta = timedelta(minutes=15),
    token_type: str = "access",
) -> str:
    """Create a JWT with controlled claims for security tests."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": "user",
        "jti": "security-test-jti",
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "type": token_type,
    }
    return jwt.encode(payload, secret, algorithm="HS256")
