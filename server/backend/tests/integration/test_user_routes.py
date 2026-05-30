"""Integration tests for user discovery routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.repositories import device_key_repository, user_repository
from app.schemas.device_key import DeviceKeyUploadRequest
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "user-routes-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "user-routes-test-refresh-secret-with-at-least-thirty-two"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"


@pytest.fixture(autouse=True)
def configure_user_route_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for user route integration tests."""
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
async def user_client(
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


async def test_lookup_by_username_requires_authentication(
    user_client: AsyncClient,
) -> None:
    """User lookup should be protected."""
    response = await user_client.get("/api/v1/users/by-username/alice")

    assert response.status_code == 401


async def test_lookup_by_username_returns_safe_user_and_devices(
    user_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Lookup returns only id, username, and device summaries."""
    requester = await _create_user(integration_db, "requester")
    target = await _create_user(integration_db, "alice")
    await _create_device_key(integration_db, target, 1)
    await _create_device_key(integration_db, target, 2)
    await device_key_repository.revoke_device_key(integration_db, target.id, 2)
    await integration_db.commit()

    response = await _get_user_by_username(user_client, requester, "alice")

    body = response.json()
    assert response.status_code == 200
    assert body == {
        "id": str(target.id),
        "username": "alice",
        "devices": [
            {"device_id": 1, "is_active": True},
            {"device_id": 2, "is_active": False},
        ],
    }


async def test_lookup_by_username_excludes_sensitive_fields(
    user_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Lookup must not expose auth data or public key material."""
    requester = await _create_user(integration_db, "requester-sensitive")
    target = await _create_user(integration_db, "bob")
    await _create_device_key(integration_db, target, 1)
    await integration_db.commit()

    response = await _get_user_by_username(user_client, requester, "bob")

    response_text = response.text
    assert response.status_code == 200
    assert "email" not in response.json()
    assert "password_hash" not in response_text
    assert "refresh_token_hash" not in response_text
    assert "identity_key_public_b64" not in response_text
    assert "signed_prekey_public_b64" not in response_text
    assert "private_key" not in response_text


async def test_lookup_missing_username_returns_404(
    user_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Missing users should return a safe not-found response."""
    requester = await _create_user(integration_db, "requester-missing")

    response = await _get_user_by_username(user_client, requester, "missing-user")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


async def test_lookup_inactive_username_returns_404(
    user_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Inactive target users should not be discoverable."""
    requester = await _create_user(integration_db, "requester-inactive")
    target = await _create_user(integration_db, "inactive-user")
    await user_repository.set_user_active_status(integration_db, target.id, False)
    await integration_db.commit()

    response = await _get_user_by_username(user_client, requester, "inactive-user")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


async def test_lookup_invalid_username_format_returns_422(
    user_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Invalid username path values should fail validation."""
    requester = await _create_user(integration_db, "requester-invalid")

    response = await _get_user_by_username(user_client, requester, "bad username")

    assert response.status_code == 422


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a committed user for user route tests."""
    user = await user_repository.create_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password_hash=PASSWORD_HASH,
    )
    await integration_db.commit()
    await integration_db.refresh(user)
    return user


async def _create_device_key(integration_db: AsyncSession, user, device_id: int):
    """Create a device key through the repository."""
    return await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        DeviceKeyUploadRequest(
            device_id=device_id,
            registration_id=1000 + device_id,
            identity_key_public_b64=KEY_B64,
            identity_signing_public_b64=KEY_B64,
            signed_prekey_id=2000 + device_id,
            signed_prekey_public_b64=KEY_B64,
            signed_prekey_signature_b64=KEY_B64,
        ),
    )


async def _get_user_by_username(
    client: AsyncClient,
    requester,
    username: str,
) -> Response:
    """Lookup a user by username through the route."""
    return await client.get(
        f"/api/v1/users/by-username/{username}",
        headers=_auth_headers(requester),
    )


def _auth_headers(user) -> dict[str, str]:
    """Return Bearer auth headers for a user."""
    token = token_service.create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}
