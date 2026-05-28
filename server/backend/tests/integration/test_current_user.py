"""Integration tests for current-user authentication dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.repositories import user_repository
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "current-user-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
WRONG_JWT_SECRET = "wrong-current-user-test-jwt-secret-with-enough-length-123456789"
REFRESH_HASH_SECRET = "current-user-test-refresh-secret-with-at-least-thirty-two-bytes"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"


@pytest.fixture(autouse=True)
def configure_current_user_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for current-user integration tests."""
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

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


async def test_me_succeeds_with_valid_access_token(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """A valid Bearer access token should return the token subject user."""
    user = await _create_user(integration_db, "alice")
    token = token_service.create_access_token(user.id, user.role)

    response = await _get_me(auth_client, token)

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)


async def test_me_response_includes_safe_user_fields(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """The protected user response should include safe profile fields."""
    user = await _create_user(integration_db, "bob")
    token = token_service.create_access_token(user.id, user.role)

    response = await _get_me(auth_client, token)

    body = response.json()
    assert response.status_code == 200
    assert body["id"] == str(user.id)
    assert body["username"] == "bob"
    assert body["email"] == "bob@example.com"
    assert body["role"] == "user"
    assert body["is_active"] is True


async def test_me_response_excludes_password_hash(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """The protected user response must not expose password hashes."""
    user = await _create_user(integration_db, "carol")
    token = token_service.create_access_token(user.id, user.role)

    response = await _get_me(auth_client, token)

    assert response.status_code == 200
    assert "password_hash" not in response.json()


async def test_missing_authorization_header_returns_401(
    auth_client: AsyncClient,
) -> None:
    """Missing credentials should fail generically."""
    response = await auth_client.get("/api/v1/auth/me")

    _assert_generic_401(response)


async def test_malformed_authorization_header_returns_401(
    auth_client: AsyncClient,
) -> None:
    """Malformed credentials should fail generically."""
    response = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Basic not-a-bearer-token"},
    )

    _assert_generic_401(response)


async def test_random_invalid_token_returns_401(auth_client: AsyncClient) -> None:
    """Random token strings should fail generically."""
    response = await _get_me(auth_client, "not-a-jwt")

    _assert_generic_401(response)


async def test_expired_access_token_returns_401(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Expired access tokens should fail generically."""
    user = await _create_user(integration_db, "dave")
    token = _create_signed_token(user.id, token_type="access", expired=True)

    response = await _get_me(auth_client, token)

    _assert_generic_401(response)


async def test_token_signed_with_wrong_secret_returns_401(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Tokens signed with another secret should fail generically."""
    user = await _create_user(integration_db, "erin")
    token = _create_signed_token(
        user.id,
        token_type="access",
        secret=WRONG_JWT_SECRET,
    )

    response = await _get_me(auth_client, token)

    _assert_generic_401(response)


async def test_wrong_type_jwt_returns_401(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Non-access JWTs should fail generically."""
    user = await _create_user(integration_db, "frank")
    token = _create_signed_token(user.id, token_type="refresh")

    response = await _get_me(auth_client, token)

    _assert_generic_401(response)


async def test_raw_refresh_token_cannot_be_used_as_access_token(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Opaque refresh tokens should not authenticate protected endpoints."""
    user = await _create_user(integration_db, "grace")
    token_result = await auth_service.create_login_tokens(integration_db, user)

    response = await _get_me(auth_client, token_result.refresh_token)

    _assert_generic_401(response)


async def test_token_for_inactive_user_returns_401(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Inactive users should not authenticate with an otherwise valid token."""
    user = await _create_user(integration_db, "heidi")
    token = token_service.create_access_token(user.id, user.role)
    await user_repository.set_user_active_status(integration_db, user.id, False)
    await integration_db.commit()

    response = await _get_me(auth_client, token)

    _assert_generic_401(response)


async def test_token_for_nonexistent_user_returns_401(
    auth_client: AsyncClient,
) -> None:
    """Tokens for users that are not in the database should fail generically."""
    token = token_service.create_access_token(uuid4(), "user")

    response = await _get_me(auth_client, token)

    _assert_generic_401(response)


async def test_query_user_id_does_not_spoof_identity(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """A user_id query parameter should not override the token subject."""
    alice = await _create_user(integration_db, "alice-query")
    bob = await _create_user(integration_db, "bob-query")
    token = token_service.create_access_token(alice.id, alice.role)

    response = await auth_client.get(
        f"/api/v1/auth/me?user_id={bob.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["id"] == str(alice.id)
    assert body["id"] != str(bob.id)


async def test_dependency_returns_token_subject_not_client_provided_data(
    auth_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """The dependency should use the verified token subject as identity."""
    alice = await _create_user(integration_db, "alice-subject")
    bob = await _create_user(integration_db, "bob-subject")
    token = token_service.create_access_token(bob.id, bob.role)

    response = await auth_client.get(
        f"/api/v1/auth/me?user_id={alice.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["id"] == str(bob.id)
    assert body["id"] != str(alice.id)


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a committed user for current-user dependency tests."""
    user = await user_repository.create_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password_hash=PASSWORD_HASH,
    )
    await integration_db.commit()
    await integration_db.refresh(user)
    return user


async def _get_me(client: AsyncClient, token: str) -> Response:
    """Call the protected current-user endpoint with a Bearer token."""
    return await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )


def _create_signed_token(
    user_id: UUID,
    *,
    token_type: str,
    secret: str = JWT_SECRET,
    expired: bool = False,
) -> str:
    """Create a signed JWT for dependency rejection tests."""
    now = datetime.now(UTC)
    expires_at = now - timedelta(minutes=1) if expired else now + timedelta(minutes=15)
    payload = {
        "sub": str(user_id),
        "role": "user",
        "jti": token_service.create_token_jti(),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": token_type,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _assert_generic_401(response: Response) -> None:
    """Assert a protected route failed with the generic auth response."""
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"
    assert response.headers["www-authenticate"] == "Bearer"
