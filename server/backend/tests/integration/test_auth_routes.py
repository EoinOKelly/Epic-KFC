"""Integration tests for authentication API routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.repositories import user_repository
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "auth-routes-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "auth-routes-test-refresh-secret-with-at-least-thirty-two-bytes"
VALID_PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "wrong-horse-battery-staple"


@pytest.fixture(autouse=True)
def configure_auth_route_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for auth route integration tests."""
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


@pytest_asyncio.fixture
async def auth_client(
    integration_db: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client wired to the guarded test database session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield integration_db

    app.dependency_overrides[api_deps.get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"user-agent": "pytest"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def test_register_success_returns_201(auth_client: AsyncClient) -> None:
    """Successful registration returns Created."""
    response = await _register(auth_client, username="alice")

    assert response.status_code == 201


async def test_register_response_includes_safe_user_fields(
    auth_client: AsyncClient,
) -> None:
    """Registration response includes safe user fields only."""
    response = await _register(auth_client, username="bob")

    body = response.json()
    assert response.status_code == 201
    assert body["id"]
    assert body["username"] == "bob"
    assert body["email"] == "bob@example.com"
    assert body["role"] == "user"
    assert body["is_active"] is True


async def test_register_response_excludes_password_hash(
    auth_client: AsyncClient,
) -> None:
    """Registration response must not expose password hashes."""
    response = await _register(auth_client, username="carol")

    assert response.status_code == 201
    assert "password_hash" not in response.json()


async def test_duplicate_username_returns_409(auth_client: AsyncClient) -> None:
    """Duplicate usernames return a safe conflict response."""
    first = await _register(auth_client, username="dave")
    second = await _register(
        auth_client,
        username="dave",
        email="dave2@example.com",
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_duplicate_email_returns_409(auth_client: AsyncClient) -> None:
    """Duplicate emails return a safe conflict response."""
    first = await _register(auth_client, username="erin", email="erin@example.com")
    second = await _register(
        auth_client,
        username="erin2",
        email="ERIN@example.com",
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_duplicate_error_does_not_expose_database_exception_text(
    auth_client: AsyncClient,
) -> None:
    """Duplicate responses should not leak database internals."""
    await _register(auth_client, username="frank", email="frank@example.com")

    response = await _register(
        auth_client,
        username="frank2",
        email="frank@example.com",
    )

    body = response.json()
    assert response.status_code == 409
    assert body["detail"] == "Username or email is unavailable"
    assert "IntegrityError" not in body["detail"]
    assert "users" not in body["detail"].lower()


async def test_login_success_returns_tokens(auth_client: AsyncClient) -> None:
    """Successful login returns token response fields."""
    await _register(auth_client, username="grace")

    response = await _login(auth_client, username_or_email="grace")

    body = response.json()
    assert response.status_code == 200
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900


async def test_login_wrong_password_returns_401(auth_client: AsyncClient) -> None:
    """Wrong passwords return Unauthorized."""
    await _register(auth_client, username="heidi")

    response = await _login(
        auth_client,
        username_or_email="heidi",
        password=WRONG_PASSWORD,
    )

    assert response.status_code == 401


async def test_login_unknown_user_returns_401(auth_client: AsyncClient) -> None:
    """Unknown users return Unauthorized."""
    response = await _login(auth_client, username_or_email="unknown")

    assert response.status_code == 401


async def test_login_inactive_user_returns_401(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Inactive accounts should receive the same generic login failure."""
    await _register(auth_client, username="ivan")
    user = await user_repository.get_by_username(integration_db, "ivan")
    assert user is not None
    await user_repository.set_user_active_status(integration_db, user.id, False)
    await integration_db.commit()

    response = await _login(auth_client, username_or_email="ivan")

    assert response.status_code == 401


async def test_login_failure_response_is_generic(auth_client: AsyncClient) -> None:
    """Login failures should not reveal account existence or status."""
    response = await _login(auth_client, username_or_email="unknown")

    body = response.json()
    assert response.status_code == 401
    assert body["detail"] == "Invalid credentials"


async def test_refresh_success_returns_rotated_tokens(
    auth_client: AsyncClient,
) -> None:
    """Refresh should rotate the refresh token."""
    await _register(auth_client, username="judy")
    login_response = await _login(auth_client, username_or_email="judy")
    old_refresh_token = login_response.json()["refresh_token"]

    response = await _refresh(auth_client, old_refresh_token)

    body = response.json()
    assert response.status_code == 200
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != old_refresh_token
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900


async def test_old_refresh_token_cannot_be_reused_after_rotation(
    auth_client: AsyncClient,
) -> None:
    """A rotated refresh token should be rejected if reused."""
    await _register(auth_client, username="kate")
    login_response = await _login(auth_client, username_or_email="kate")
    old_refresh_token = login_response.json()["refresh_token"]
    refresh_response = await _refresh(auth_client, old_refresh_token)

    reuse_response = await _refresh(auth_client, old_refresh_token)

    assert refresh_response.status_code == 200
    assert reuse_response.status_code == 401
    assert reuse_response.json()["detail"] == "Invalid refresh token"


async def test_invalid_refresh_token_returns_401(auth_client: AsyncClient) -> None:
    """Invalid refresh tokens return Unauthorized."""
    response = await _refresh(auth_client, "invalid-refresh-token")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


async def test_logout_returns_success(auth_client: AsyncClient) -> None:
    """Logout returns success for a known refresh token."""
    await _register(auth_client, username="laura")
    login_response = await _login(auth_client, username_or_email="laura")
    refresh_token = login_response.json()["refresh_token"]

    response = await _logout(auth_client, refresh_token)

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Logged out"


async def test_logout_unknown_token_still_returns_success(
    auth_client: AsyncClient,
) -> None:
    """Logout should not reveal refresh-token validity."""
    response = await _logout(auth_client, "unknown-refresh-token")

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Logged out"


async def test_bad_email_rejected_with_422(auth_client: AsyncClient) -> None:
    """Invalid emails are rejected by request validation."""
    response = await _register(
        auth_client,
        username="mallory",
        email="not-an-email",
    )

    assert response.status_code == 422


async def test_short_password_rejected_with_422(auth_client: AsyncClient) -> None:
    """Short passwords are rejected by request validation."""
    response = await _register(
        auth_client,
        username="nancy",
        password="too-short",
    )

    assert response.status_code == 422


async def test_extra_fields_rejected_with_422(auth_client: AsyncClient) -> None:
    """Unexpected request fields are rejected."""
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "username": "olivia",
            "email": "olivia@example.com",
            "password": VALID_PASSWORD,
            "password_hash": "$argon2id$not-allowed",
        },
    )

    assert response.status_code == 422


async def _register(
    client: AsyncClient,
    *,
    username: str,
    email: str | None = None,
    password: str = VALID_PASSWORD,
):
    """Register a test user through the route."""
    return await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
    )


async def _login(
    client: AsyncClient,
    *,
    username_or_email: str,
    password: str = VALID_PASSWORD,
):
    """Log in through the route."""
    return await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


async def _refresh(client: AsyncClient, refresh_token: str):
    """Refresh tokens through the route."""
    return await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )


async def _logout(client: AsyncClient, refresh_token: str):
    """Log out through the route."""
    return await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
