"""Integration tests for authenticated public key relay routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.repositories import (
    device_key_repository,
    one_time_prekey_repository,
    user_repository,
)
from app.schemas.device_key import DeviceKeyUploadRequest
from app.schemas.one_time_prekey import OneTimePreKeyUpload
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "key-routes-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "key-routes-test-refresh-secret-with-at-least-thirty-two-bytes"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"


@pytest.fixture(autouse=True)
def configure_key_route_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for key route integration tests."""
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
async def key_client(
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


async def test_unauthenticated_device_key_upload_returns_401(
    key_client: AsyncClient,
) -> None:
    """Device key upload requires authentication."""
    response = await key_client.put(
        "/api/v1/keys/devices/1",
        json=_device_payload(1),
    )

    assert response.status_code == 401


async def test_authenticated_device_key_upload_succeeds(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Authenticated users can upload their public device key bundle."""
    user = await _create_user(integration_db, "alice")

    response = await _put_device_key(key_client, user, 1)

    body = response.json()
    assert response.status_code == 200
    assert body["user_id"] == str(user.id)
    assert body["device_id"] == 1
    assert body["identity_key_public_b64"] == KEY_B64


async def test_path_body_device_id_mismatch_returns_400(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Path and body device IDs must match."""
    user = await _create_user(integration_db, "bob")

    response = await _put_device_key(key_client, user, 1, payload_device_id=2)

    assert response.status_code == 400


async def test_device_key_response_excludes_private_key_fields(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Device key responses should contain public material only."""
    user = await _create_user(integration_db, "carol")

    response = await _put_device_key(key_client, user, 1)

    body = response.json()
    assert response.status_code == 200
    assert "private_key" not in body
    assert "ratchet_state" not in body
    assert "session_state" not in body


async def test_malformed_base64_returns_422(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Malformed public key base64 should be rejected by validation."""
    user = await _create_user(integration_db, "dave")
    payload = _device_payload(1)
    payload["identity_key_public_b64"] = "not valid base64"

    response = await _put_device_key(key_client, user, 1, payload=payload)

    assert response.status_code == 422


async def test_extra_private_key_field_returns_422(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Unexpected private key fields should be rejected by validation."""
    user = await _create_user(integration_db, "erin")
    payload = _device_payload(1)
    payload["private_key"] = KEY_B64

    response = await _put_device_key(key_client, user, 1, payload=payload)

    assert response.status_code == 422


async def test_one_time_prekey_upload_succeeds(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Authenticated users can upload public one-time prekeys."""
    user = await _create_user(integration_db, "frank")

    response = await _post_prekeys(key_client, user, 1, [10, 11])

    body = response.json()
    assert response.status_code == 200
    assert len(body) == 2
    assert {prekey["prekey_id"] for prekey in body} == {10, 11}
    assert all(prekey["user_id"] == str(user.id) for prekey in body)


async def test_oversized_prekey_batch_returns_422(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Prekey batches are limited by schema validation."""
    user = await _create_user(integration_db, "grace")
    payload = {"prekeys": [_prekey_payload(1, prekey_id) for prekey_id in range(1, 102)]}

    response = await key_client.post(
        "/api/v1/keys/devices/1/one-time-prekeys",
        json=payload,
        headers=_auth_headers(user),
    )

    assert response.status_code == 422


async def test_duplicate_prekey_ids_return_409(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Existing prekey IDs for the same user/device return a safe conflict."""
    user = await _create_user(integration_db, "heidi")
    first = await _post_prekeys(key_client, user, 1, [20])
    second = await _post_prekeys(key_client, user, 1, [20])

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "One-time prekey already exists"


async def test_fetch_prekey_bundle_returns_public_device_key_material(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Authenticated users can fetch public prekey bundles."""
    requester = await _create_user(integration_db, "ivan")
    target = await _create_user(integration_db, "judy")
    await _create_device_key(integration_db, target, 1)
    await _create_prekeys(integration_db, target, 1, [30])
    await integration_db.commit()

    response = await _get_bundle(key_client, requester, target.id, 1)

    body = response.json()
    assert response.status_code == 200
    assert body["registrationId"] == 1001
    assert body["deviceId"] == 1
    assert body["identityKey"] == KEY_B64
    assert body["identitySigningKey"] == KEY_B64
    assert body["signedPreKeyId"] == 2001
    assert body["signedPreKey"] == KEY_B64
    assert body["signedPreKeySignature"] == KEY_B64


async def test_prekey_bundle_response_uses_camel_case_aliases(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Prekey bundles should use the crypto-compatible alias contract."""
    requester = await _create_user(integration_db, "kate")
    target = await _create_user(integration_db, "laura")
    await _create_device_key(integration_db, target, 1)
    await _create_prekeys(integration_db, target, 1, [40])
    await integration_db.commit()

    response = await _get_bundle(key_client, requester, target.id, 1)

    body = response.json()
    assert response.status_code == 200
    assert "registrationId" in body
    assert "deviceId" in body
    assert "signedPreKeyId" in body
    assert "oneTimePreKeyId" in body
    assert "registration_id" not in body
    assert "one_time_prekey_id" not in body


async def test_fetching_bundle_marks_one_time_prekey_as_used(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Fetching a bundle consumes one one-time prekey."""
    requester = await _create_user(integration_db, "mallory")
    target = await _create_user(integration_db, "nancy")
    await _create_device_key(integration_db, target, 1)
    await _create_prekeys(integration_db, target, 1, [50])
    await integration_db.commit()

    response = await _get_bundle(key_client, requester, target.id, 1)
    unused_count = await one_time_prekey_repository.count_unused_for_device(
        integration_db,
        target.id,
        1,
    )

    assert response.status_code == 200
    assert response.json()["oneTimePreKeyId"] == 50
    assert unused_count == 0


async def test_same_one_time_prekey_is_not_returned_twice(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Each bundle fetch should consume a different available one-time prekey."""
    requester = await _create_user(integration_db, "olivia")
    target = await _create_user(integration_db, "peggy")
    await _create_device_key(integration_db, target, 1)
    await _create_prekeys(integration_db, target, 1, [60, 61])
    await integration_db.commit()

    first = await _get_bundle(key_client, requester, target.id, 1)
    second = await _get_bundle(key_client, requester, target.id, 1)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["oneTimePreKeyId"] == 60
    assert second.json()["oneTimePreKeyId"] == 61


async def test_missing_target_device_returns_404(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Missing target devices should return Not Found."""
    requester = await _create_user(integration_db, "quinn")
    target = await _create_user(integration_db, "ruth")

    response = await _get_bundle(key_client, requester, target.id, 1)

    assert response.status_code == 404


async def test_revoked_target_device_returns_404(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Revoked target devices should not be returned."""
    requester = await _create_user(integration_db, "sam")
    target = await _create_user(integration_db, "trent")
    await _create_device_key(integration_db, target, 1)
    await device_key_repository.revoke_device_key(integration_db, target.id, 1)
    await integration_db.commit()

    response = await _get_bundle(key_client, requester, target.id, 1)

    assert response.status_code == 404


async def test_upload_routes_use_token_subject_not_spoofed_user_id(
    key_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Upload routes should ignore any client-provided user_id query value."""
    alice = await _create_user(integration_db, "alice-spoof")
    bob = await _create_user(integration_db, "bob-spoof")

    response = await key_client.put(
        f"/api/v1/keys/devices/1?user_id={bob.id}",
        json=_device_payload(1),
        headers=_auth_headers(alice),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["user_id"] == str(alice.id)
    assert body["user_id"] != str(bob.id)


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a committed user for key route tests."""
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
        DeviceKeyUploadRequest(**_device_payload(device_id)),
    )


async def _create_prekeys(
    integration_db: AsyncSession,
    user,
    device_id: int,
    prekey_ids: list[int],
):
    """Create public one-time prekeys through the repository."""
    return await one_time_prekey_repository.create_batch(
        integration_db,
        user.id,
        device_id,
        [OneTimePreKeyUpload(**_prekey_payload(device_id, prekey_id)) for prekey_id in prekey_ids],
    )


async def _put_device_key(
    client: AsyncClient,
    user,
    path_device_id: int,
    *,
    payload_device_id: int | None = None,
    payload: dict[str, object] | None = None,
) -> Response:
    """Upload a device key through the route."""
    return await client.put(
        f"/api/v1/keys/devices/{path_device_id}",
        json=payload or _device_payload(payload_device_id or path_device_id),
        headers=_auth_headers(user),
    )


async def _post_prekeys(
    client: AsyncClient,
    user,
    device_id: int,
    prekey_ids: list[int],
) -> Response:
    """Upload one-time prekeys through the route."""
    return await client.post(
        f"/api/v1/keys/devices/{device_id}/one-time-prekeys",
        json={"prekeys": [_prekey_payload(device_id, prekey_id) for prekey_id in prekey_ids]},
        headers=_auth_headers(user),
    )


async def _get_bundle(
    client: AsyncClient,
    requester,
    target_user_id,
    device_id: int,
) -> Response:
    """Fetch a target user's prekey bundle through the route."""
    return await client.get(
        f"/api/v1/keys/users/{target_user_id}/devices/{device_id}/prekey-bundle",
        headers=_auth_headers(requester),
    )


def _auth_headers(user) -> dict[str, str]:
    """Return Bearer auth headers for a user."""
    token = token_service.create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _device_payload(device_id: int) -> dict[str, object]:
    """Build a valid device key route payload."""
    return {
        "device_id": device_id,
        "registration_id": 1001,
        "identity_key_public_b64": KEY_B64,
        "identity_signing_public_b64": KEY_B64,
        "signed_prekey_id": 2001,
        "signed_prekey_public_b64": KEY_B64,
        "signed_prekey_signature_b64": KEY_B64,
    }


def _prekey_payload(device_id: int, prekey_id: int) -> dict[str, object]:
    """Build a valid one-time prekey route payload."""
    return {
        "device_id": device_id,
        "prekey_id": prekey_id,
        "prekey_public_b64": KEY_B64,
    }
