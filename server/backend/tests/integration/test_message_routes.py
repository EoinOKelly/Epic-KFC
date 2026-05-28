"""Integration tests for authenticated direct message routes."""

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

JWT_SECRET = "message-routes-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "message-routes-test-refresh-secret-with-at-least-thirty-two"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"
WIRE_PAYLOAD = (
    '{"counter":0,"previousCounter":0,"ciphertext":"b3JpZ2luYWw=",'
    '"iv":"aXY=","authTag":"dGFn"}'
)
NEW_WIRE_PAYLOAD = (
    '{ "counter": 1, "previousCounter": 0, "ciphertext": "bmV3", '
    '"iv": "aXY=", "authTag": "dGFn" }'
)


@pytest.fixture(autouse=True)
def configure_message_route_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for message route integration tests."""
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
async def message_client(
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


async def test_unauthenticated_send_returns_401(
    message_client: AsyncClient,
) -> None:
    """Sending requires authentication."""
    response = await message_client.post("/api/v1/messages", json={})

    assert response.status_code == 401


async def test_send_message_succeeds(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Authenticated users can send direct opaque relay messages."""
    sender, recipient = await _create_ready_users(integration_db, "alice", "bob")

    response = await _send_message(message_client, sender, recipient)

    body = response.json()
    assert response.status_code == 201
    assert body["sender_user_id"] == str(sender.id)
    assert body["recipient_user_id"] == str(recipient.id)
    assert body["wire_payload_json"] == WIRE_PAYLOAD


async def test_send_response_excludes_plaintext_private_fields(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Message responses must not expose plaintext or private key fields."""
    sender, recipient = await _create_ready_users(integration_db, "carol", "dave")

    response = await _send_message(message_client, sender, recipient)

    body = response.json()
    assert response.status_code == 201
    assert "plaintext" not in body
    assert "content" not in body
    assert "body" not in body
    assert "private_key" not in body
    assert "ratchet_state" not in body


async def test_send_cannot_spoof_sender_user_id(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Public send requests cannot include sender_user_id."""
    sender, recipient = await _create_ready_users(integration_db, "erin", "frank")
    payload = _message_payload(recipient.id)
    payload["sender_user_id"] = str(recipient.id)

    response = await message_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


async def test_send_rejects_unexpected_fields(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Public message routes reject unsupported client-supplied fields."""
    sender, recipient = await _create_ready_users(integration_db, "grace", "heidi")
    payload = _message_payload(recipient.id)
    payload["client_supplied_group_id"] = "00000000-0000-0000-0000-000000000000"

    response = await message_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("field_name", ["plaintext", "content", "body"])
async def test_send_rejects_plaintext_content_body_fields(
    message_client: AsyncClient,
    integration_db: AsyncSession,
    field_name: str,
) -> None:
    """Public message routes reject plaintext-like fields."""
    sender, recipient = await _create_ready_users(
        integration_db,
        f"ivan-{field_name}",
        f"judy-{field_name}",
    )
    payload = _message_payload(recipient.id)
    payload[field_name] = "secret text"

    response = await message_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


async def test_send_rejects_malformed_wire_payload_json(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Malformed wire payloads are rejected by schema validation."""
    sender, recipient = await _create_ready_users(integration_db, "kate", "laura")
    payload = _message_payload(recipient.id)
    payload["wire_payload_json"] = "not-json"

    response = await message_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


async def test_received_list_returns_only_recipient_messages(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Received list only includes messages where current user is recipient."""
    sender, recipient = await _create_ready_users(integration_db, "mallory", "nancy")
    other = await _create_user(integration_db, "olivia")
    await _create_device_key(integration_db, other, 1)
    sent_to_recipient = await _send_message(message_client, sender, recipient)
    await _send_message(message_client, sender, other)

    response = await message_client.get(
        "/api/v1/messages/received",
        headers=_auth_headers(recipient),
    )

    body = response.json()
    assert response.status_code == 200
    assert [message["id"] for message in body] == [sent_to_recipient.json()["id"]]


async def test_sent_list_returns_only_sender_messages(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sent list only includes messages where current user is sender."""
    sender, recipient = await _create_ready_users(integration_db, "peggy", "quinn")
    other = await _create_user(integration_db, "ruth")
    await _create_device_key(integration_db, other, 1)
    sent_by_sender = await _send_message(message_client, sender, recipient)
    await _send_message(message_client, other, recipient)

    response = await message_client.get(
        "/api/v1/messages/sent",
        headers=_auth_headers(sender),
    )

    body = response.json()
    assert response.status_code == 200
    assert [message["id"] for message in body] == [sent_by_sender.json()["id"]]


async def test_sender_can_fetch_sent_message(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sender can fetch a visible sent message."""
    sender, recipient = await _create_ready_users(integration_db, "sam", "trent")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    response = await _get_message(message_client, sender, message_id)

    assert response.status_code == 200
    assert response.json()["id"] == message_id


async def test_recipient_can_fetch_received_message(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Recipient can fetch a visible received message."""
    sender, recipient = await _create_ready_users(integration_db, "ursula", "victor")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    response = await _get_message(message_client, recipient, message_id)

    assert response.status_code == 200
    assert response.json()["id"] == message_id


async def test_unrelated_user_cannot_fetch_message(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Unrelated users get safe 404 for inaccessible messages."""
    sender, recipient = await _create_ready_users(integration_db, "wendy", "xavier")
    unrelated = await _create_user(integration_db, "yvonne")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    response = await _get_message(message_client, unrelated, message_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Message not found"


async def test_recipient_cannot_fetch_after_revoke(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Recipient cannot fetch after sender revokes access."""
    sender, recipient = await _create_ready_users(integration_db, "zara", "amy")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]
    await _revoke_message(message_client, sender, message_id)

    response = await _get_message(message_client, recipient, message_id)

    assert response.status_code == 404


async def test_recipient_cannot_see_revoked_message_in_received_list(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Revoked messages disappear from recipient received list."""
    sender, recipient = await _create_ready_users(integration_db, "ben", "chloe")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]
    await _revoke_message(message_client, sender, message_id)

    response = await message_client.get(
        "/api/v1/messages/received",
        headers=_auth_headers(recipient),
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_non_sender_cannot_revoke(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Non-senders cannot revoke message access."""
    sender, recipient = await _create_ready_users(integration_db, "dan", "ella")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    response = await _revoke_message(message_client, recipient, message_id)

    assert response.status_code == 404


async def test_sender_can_revoke(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sender can revoke recipient access."""
    sender, recipient = await _create_ready_users(integration_db, "fiona", "george")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    response = await _revoke_message(message_client, sender, message_id)

    assert response.status_code == 200
    assert response.json()["access_revoked_at"] is not None


async def test_sender_delete_hides_only_from_sender(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sender delete hides from sender but not recipient."""
    sender, recipient = await _create_ready_users(integration_db, "harry", "irene")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    delete_response = await _delete_message(message_client, sender, message_id)
    sender_fetch = await _get_message(message_client, sender, message_id)
    recipient_fetch = await _get_message(message_client, recipient, message_id)

    assert delete_response.status_code == 200
    assert sender_fetch.status_code == 404
    assert recipient_fetch.status_code == 200


async def test_recipient_delete_hides_only_from_recipient(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Recipient delete hides from recipient but not sender."""
    sender, recipient = await _create_ready_users(integration_db, "jack", "kelly")
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    delete_response = await _delete_message(message_client, recipient, message_id)
    recipient_fetch = await _get_message(message_client, recipient, message_id)
    sender_fetch = await _get_message(message_client, sender, message_id)

    assert delete_response.status_code == 200
    assert recipient_fetch.status_code == 404
    assert sender_fetch.status_code == 200


async def test_forward_requires_access_to_original(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Forwarding requires access to the original message."""
    sender, recipient = await _create_ready_users(integration_db, "louis", "maya")
    unrelated = await _create_user(integration_db, "noah")
    new_recipient = await _create_user(integration_db, "ophelia")
    await _create_device_key(integration_db, unrelated, 1)
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    message_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    response = await _forward_message(
        message_client,
        unrelated,
        message_id,
        new_recipient.id,
    )

    assert response.status_code == 404


async def test_forward_creates_new_message_with_new_opaque_payload(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Forwarding creates a new row with the supplied new payload."""
    sender, recipient = await _create_ready_users(integration_db, "paula", "ryan")
    new_recipient = await _create_user(integration_db, "sara")
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    original = await _send_message(message_client, sender, recipient)

    response = await _forward_message(
        message_client,
        sender,
        original.json()["id"],
        new_recipient.id,
    )

    body = response.json()
    assert response.status_code == 201
    assert body["id"] != original.json()["id"]
    assert body["wire_payload_json"] == NEW_WIRE_PAYLOAD
    assert body["wire_payload_json"] != original.json()["wire_payload_json"]


async def test_forward_preserves_new_wire_payload_json_exactly(
    message_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Forwarding preserves the new serialized wire payload exactly."""
    sender, recipient = await _create_ready_users(integration_db, "tina", "uma")
    new_recipient = await _create_user(integration_db, "violet")
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    original_id = (await _send_message(message_client, sender, recipient)).json()["id"]

    response = await _forward_message(
        message_client,
        sender,
        original_id,
        new_recipient.id,
    )

    assert response.status_code == 201
    assert response.json()["wire_payload_json"] == NEW_WIRE_PAYLOAD


async def _create_ready_users(
    integration_db: AsyncSession,
    sender_username: str,
    recipient_username: str,
):
    """Create sender and recipient users with active device 1."""
    sender = await _create_user(integration_db, sender_username)
    recipient = await _create_user(integration_db, recipient_username)
    await _create_device_key(integration_db, sender, 1)
    await _create_device_key(integration_db, recipient, 1)
    await integration_db.commit()
    await integration_db.refresh(sender)
    await integration_db.refresh(recipient)
    return sender, recipient


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a user for message route tests."""
    return await user_repository.create_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password_hash=PASSWORD_HASH,
    )


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


async def _send_message(
    client: AsyncClient,
    sender,
    recipient,
    *,
    wire_payload_json: str = WIRE_PAYLOAD,
) -> Response:
    """Send a direct message through the route."""
    return await client.post(
        "/api/v1/messages",
        json=_message_payload(recipient.id, wire_payload_json=wire_payload_json),
        headers=_auth_headers(sender),
    )


async def _get_message(client: AsyncClient, user, message_id: str) -> Response:
    """Fetch a message through the route."""
    return await client.get(
        f"/api/v1/messages/{message_id}",
        headers=_auth_headers(user),
    )


async def _revoke_message(client: AsyncClient, user, message_id: str) -> Response:
    """Revoke a message through the route."""
    return await client.post(
        f"/api/v1/messages/{message_id}/revoke",
        headers=_auth_headers(user),
    )


async def _delete_message(client: AsyncClient, user, message_id: str) -> Response:
    """Delete a message through the route."""
    return await client.delete(
        f"/api/v1/messages/{message_id}",
        headers=_auth_headers(user),
    )


async def _forward_message(
    client: AsyncClient,
    user,
    message_id: str,
    recipient_user_id,
) -> Response:
    """Forward a message through the route."""
    return await client.post(
        f"/api/v1/messages/{message_id}/forward",
        json=_message_payload(recipient_user_id, wire_payload_json=NEW_WIRE_PAYLOAD),
        headers=_auth_headers(user),
    )


def _auth_headers(user) -> dict[str, str]:
    """Return Bearer auth headers for a user."""
    token = token_service.create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _message_payload(
    recipient_user_id,
    *,
    wire_payload_json: str = WIRE_PAYLOAD,
) -> dict[str, object]:
    """Build a valid direct message route payload."""
    return {
        "sender_device_id": 1,
        "recipient_user_id": str(recipient_user_id),
        "recipient_device_id": 1,
        "wire_payload_json": wire_payload_json,
    }
