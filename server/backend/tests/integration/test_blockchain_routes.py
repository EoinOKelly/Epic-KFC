"""Integration tests for blockchain anchor routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.repositories import (
    blockchain_anchor_repository,
    device_key_repository,
    user_repository,
)
from app.schemas.device_key import DeviceKeyUploadRequest
from app.services import auth_service, token_service
from tests.fixtures.wire_payloads import WIRE_PAYLOAD


pytestmark = pytest.mark.asyncio

JWT_SECRET = "blockchain-routes-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "blockchain-routes-test-refresh-secret-with-at-least-thirty-two"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"
TX_HASH = "0x" + "1" * 64
CONTRACT_ADDRESS = "0x" + "2" * 40


@pytest.fixture(autouse=True)
def configure_blockchain_route_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for blockchain route integration tests."""
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
async def blockchain_client(
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


async def test_message_send_automatically_creates_pending_anchor(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Message send creates a pending blockchain anchor automatically."""
    sender, recipient = await _create_ready_users(integration_db, "alice", "bob")
    message = await _send_message(blockchain_client, sender, recipient)

    response = await blockchain_client.get(
        f"/api/v1/messages/{message.json()['id']}/anchor",
        headers=_auth_headers(sender),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["message_id"] == message.json()["id"]
    assert body["batch_id"] is None
    assert body["record_id"].startswith("0x")
    assert len(body["record_id"]) == 66
    assert body["digest"].startswith("0x")
    assert len(body["digest"]) == 66
    assert body["merkle_root"] is None
    assert body["chain"] == "sepolia"
    assert body["status"] == "pending"
    assert "wire_payload_json" not in body


async def test_manual_create_anchor_reuses_automatic_anchor(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """POST /blockchain/anchors acts as an idempotent retry/demo endpoint."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "alice-manual",
        "bob-manual",
    )
    message = await _send_message(blockchain_client, sender, recipient)
    existing = await blockchain_client.get(
        f"/api/v1/messages/{message.json()['id']}/anchor",
        headers=_auth_headers(sender),
    )

    response = await _create_anchor(blockchain_client, sender, message.json()["id"])

    assert response.status_code == 200
    assert response.json()["id"] == existing.json()["id"]


async def test_create_anchor_is_idempotent_for_active_anchor(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Duplicate active anchor requests return the existing anchor."""
    sender, recipient = await _create_ready_users(integration_db, "carol", "dave")
    message = await _send_message(blockchain_client, sender, recipient)

    first = await _create_anchor(blockchain_client, sender, message.json()["id"])
    second = await _create_anchor(blockchain_client, sender, message.json()["id"])

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_get_anchor_status_for_accessible_message(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Anchor status lookup returns metadata for visible linked messages."""
    sender, recipient = await _create_ready_users(integration_db, "erin", "frank")
    message = await _send_message(blockchain_client, sender, recipient)
    anchor = await blockchain_client.get(
        f"/api/v1/messages/{message.json()['id']}/anchor",
        headers=_auth_headers(sender),
    )

    response = await blockchain_client.get(
        f"/api/v1/blockchain/anchors/{anchor.json()['id']}",
        headers=_auth_headers(recipient),
    )

    assert response.status_code == 200
    assert response.json()["id"] == anchor.json()["id"]


async def test_unrelated_user_cannot_get_anchor(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Users cannot inspect anchors for inaccessible messages."""
    sender, recipient = await _create_ready_users(integration_db, "grace", "heidi")
    unrelated = await _create_user(integration_db, "ivan")
    message = await _send_message(blockchain_client, sender, recipient)
    anchor = await blockchain_client.get(
        f"/api/v1/messages/{message.json()['id']}/anchor",
        headers=_auth_headers(sender),
    )

    response = await blockchain_client.get(
        f"/api/v1/blockchain/anchors/{anchor.json()['id']}",
        headers=_auth_headers(unrelated),
    )

    assert response.status_code == 404


async def test_get_message_anchor(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Message-scoped anchor lookup returns the latest accessible anchor."""
    sender, recipient = await _create_ready_users(integration_db, "judy", "kate")
    message = await _send_message(blockchain_client, sender, recipient)
    anchor = await blockchain_client.get(
        f"/api/v1/messages/{message.json()['id']}/anchor",
        headers=_auth_headers(sender),
    )

    response = await blockchain_client.get(
        f"/api/v1/messages/{message.json()['id']}/anchor",
        headers=_auth_headers(recipient),
    )

    assert response.status_code == 200
    assert response.json()["id"] == anchor.json()["id"]


async def test_forward_automatically_creates_pending_anchor(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Forwarded messages are new encrypted messages with their own anchors."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "judy-forward",
        "kate-forward",
    )
    new_recipient = await _create_user(integration_db, "louis-forward")
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    original = await _send_message(blockchain_client, sender, recipient)
    forwarded = await _forward_message(
        blockchain_client,
        sender,
        original.json()["id"],
        new_recipient.id,
    )

    response = await blockchain_client.get(
        f"/api/v1/messages/{forwarded.json()['id']}/anchor",
        headers=_auth_headers(sender),
    )

    assert forwarded.status_code == 201
    assert response.status_code == 200
    assert response.json()["message_id"] == forwarded.json()["id"]
    assert response.json()["status"] == "pending"


async def test_verify_confirmed_anchor_metadata(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Verification compares digest/root metadata against confirmed DB rows."""
    sender, recipient = await _create_ready_users(integration_db, "laura", "mallory")
    message = await _send_message(blockchain_client, sender, recipient)
    anchor_response = await blockchain_client.get(
        f"/api/v1/messages/{message.json()['id']}/anchor",
        headers=_auth_headers(sender),
    )
    anchor_body = anchor_response.json()
    await blockchain_anchor_repository.update_anchor_status(
        integration_db,
        UUID(anchor_body["id"]),
        status="confirmed",
        transaction_hash=TX_HASH,
        contract_address=CONTRACT_ADDRESS,
        merkle_root=anchor_body["digest"],
        anchored_at=datetime.now(UTC),
    )
    await integration_db.commit()

    response = await blockchain_client.post(
        "/api/v1/blockchain/verify",
        json={
            "digest": anchor_body["digest"],
            "record_id": anchor_body["record_id"],
            "merkle_root": anchor_body["digest"],
            "transaction_hash": TX_HASH,
            "chain": "sepolia",
        },
        headers=_auth_headers(sender),
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["transaction_hash"] == TX_HASH


async def test_verify_unknown_anchor_returns_false(
    blockchain_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Unknown proof metadata returns a safe failed verification result."""
    user = await _create_user(integration_db, "nancy")

    response = await blockchain_client.post(
        "/api/v1/blockchain/verify",
        json={"digest": "0x" + "f" * 64, "chain": "sepolia"},
        headers=_auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False


async def _create_ready_users(
    integration_db: AsyncSession,
    sender_username: str,
    recipient_username: str,
):
    """Create users with active device 1."""
    sender = await _create_user(integration_db, sender_username)
    recipient = await _create_user(integration_db, recipient_username)
    await _create_device_key(integration_db, sender, 1)
    await _create_device_key(integration_db, recipient, 1)
    await integration_db.commit()
    await integration_db.refresh(sender)
    await integration_db.refresh(recipient)
    return sender, recipient


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a committed user for blockchain route tests."""
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
    """Create an active public device key for a user."""
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


async def _send_message(client: AsyncClient, sender, recipient) -> Response:
    """Send a direct encrypted relay message through the route."""
    return await client.post(
        "/api/v1/messages",
        json={
            "sender_device_id": 1,
            "recipient_user_id": str(recipient.id),
            "recipient_device_id": 1,
            "wire_payload_json": WIRE_PAYLOAD,
        },
        headers=_auth_headers(sender),
    )


async def _forward_message(
    client: AsyncClient,
    sender,
    message_id: str,
    recipient_user_id,
) -> Response:
    """Forward a direct encrypted relay message through the route."""
    return await client.post(
        f"/api/v1/messages/{message_id}/forward",
        json={
            "sender_device_id": 1,
            "recipient_user_id": str(recipient_user_id),
            "recipient_device_id": 1,
            "wire_payload_json": WIRE_PAYLOAD,
        },
        headers=_auth_headers(sender),
    )


async def _create_anchor(
    client: AsyncClient,
    user,
    message_id: str,
) -> Response:
    """Create a blockchain anchor through the route."""
    return await client.post(
        "/api/v1/blockchain/anchors",
        json={"message_id": message_id},
        headers=_auth_headers(user),
    )


def _auth_headers(user) -> dict[str, str]:
    """Return Bearer auth headers for a user."""
    token = token_service.create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}
