"""Security tests for direct-message object-level access control."""

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
from tests.fixtures.wire_payloads import WIRE_PAYLOAD


pytestmark = pytest.mark.asyncio

JWT_SECRET = "security-access-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "security-access-refresh-secret-with-at-least-thirty-two"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"


@pytest.fixture(autouse=True)
def configure_access_security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure auth settings and disable rate limits for access tests."""
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
async def access_client(
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
        headers={"user-agent": "pytest-security-access"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def test_unrelated_user_cannot_fetch_another_users_message(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Users outside sender/recipient relationship receive safe 404."""
    sender, recipient = await _create_ready_users(integration_db, "alice", "bob")
    unrelated = await _create_user(integration_db, "carol")
    message_id = (await _send_message(access_client, sender, recipient)).json()["id"]

    response = await _get_message(access_client, unrelated, message_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Message not found"


async def test_received_list_only_returns_current_user_recipient_messages(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Received listing enforces recipient object ownership."""
    sender, recipient = await _create_ready_users(integration_db, "dave", "erin")
    other = await _create_user(integration_db, "frank")
    await _create_device_key(integration_db, other, 1)
    await integration_db.commit()
    visible = await _send_message(access_client, sender, recipient)
    await _send_message(access_client, sender, other)

    response = await access_client.get(
        "/api/v1/messages/received",
        headers=_auth_headers(recipient),
    )

    assert response.status_code == 200
    assert [message["id"] for message in response.json()] == [visible.json()["id"]]


async def test_sent_list_only_returns_current_user_sender_messages(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sent listing enforces sender object ownership."""
    sender, recipient = await _create_ready_users(integration_db, "grace", "heidi")
    other = await _create_user(integration_db, "ivan")
    await _create_device_key(integration_db, other, 1)
    await integration_db.commit()
    visible = await _send_message(access_client, sender, recipient)
    await _send_message(access_client, other, recipient)

    response = await access_client.get(
        "/api/v1/messages/sent",
        headers=_auth_headers(sender),
    )

    assert response.status_code == 200
    assert [message["id"] for message in response.json()] == [visible.json()["id"]]


async def test_non_sender_cannot_revoke_message(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Only the sender can revoke recipient access."""
    sender, recipient = await _create_ready_users(integration_db, "judy", "kate")
    message_id = (await _send_message(access_client, sender, recipient)).json()["id"]

    response = await _revoke_message(access_client, recipient, message_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Message not found"


async def test_unrelated_user_cannot_delete_message(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Unrelated users cannot hide or delete another user's message."""
    sender, recipient = await _create_ready_users(integration_db, "laura", "mallory")
    unrelated = await _create_user(integration_db, "nancy")
    message_id = (await _send_message(access_client, sender, recipient)).json()["id"]

    response = await _delete_message(access_client, unrelated, message_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Message not found"


async def test_sender_user_id_spoofing_is_rejected(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Public send requests must not accept sender_user_id."""
    sender, recipient = await _create_ready_users(integration_db, "olivia", "peggy")
    payload = _message_payload(recipient.id)
    payload["sender_user_id"] = str(recipient.id)

    response = await access_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


async def test_recipient_cannot_fetch_after_sender_revokes_access(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Revocation removes recipient fetch access."""
    sender, recipient = await _create_ready_users(integration_db, "quinn", "ruth")
    message_id = (await _send_message(access_client, sender, recipient)).json()["id"]
    await _revoke_message(access_client, sender, message_id)

    response = await _get_message(access_client, recipient, message_id)

    assert response.status_code == 404


async def test_recipient_cannot_list_after_sender_revokes_access(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Revoked messages disappear from recipient received lists."""
    sender, recipient = await _create_ready_users(integration_db, "sam", "trent")
    await _revoke_message(
        access_client,
        sender,
        (await _send_message(access_client, sender, recipient)).json()["id"],
    )

    response = await access_client.get(
        "/api/v1/messages/received",
        headers=_auth_headers(recipient),
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_sender_delete_hides_only_from_sender(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sender delete should not hide the recipient copy."""
    sender, recipient = await _create_ready_users(integration_db, "ursula", "victor")
    message_id = (await _send_message(access_client, sender, recipient)).json()["id"]

    await _delete_message(access_client, sender, message_id)

    assert (await _get_message(access_client, sender, message_id)).status_code == 404
    assert (await _get_message(access_client, recipient, message_id)).status_code == 200


async def test_recipient_delete_hides_only_from_recipient(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Recipient delete should not hide the sender copy."""
    sender, recipient = await _create_ready_users(integration_db, "wendy", "xavier")
    message_id = (await _send_message(access_client, sender, recipient)).json()["id"]

    await _delete_message(access_client, recipient, message_id)

    assert (await _get_message(access_client, recipient, message_id)).status_code == 404
    assert (await _get_message(access_client, sender, message_id)).status_code == 200


async def test_direct_message_routes_reject_conversation_id(
    access_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Direct 1:1 route contract rejects conversation/group fields."""
    sender, recipient = await _create_ready_users(integration_db, "yvonne", "zara")
    payload = _message_payload(recipient.id)
    payload["conversation_id"] = "00000000-0000-0000-0000-000000000000"

    response = await access_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


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
    """Create a committed user."""
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
    """Send a direct message through the route."""
    return await client.post(
        "/api/v1/messages",
        json=_message_payload(recipient.id),
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


def _auth_headers(user) -> dict[str, str]:
    """Return Bearer auth headers for a user."""
    token = token_service.create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _message_payload(recipient_user_id) -> dict[str, object]:
    """Build a valid direct message payload."""
    return {
        "sender_device_id": 1,
        "recipient_user_id": str(recipient_user_id),
        "recipient_device_id": 1,
        "wire_payload_json": WIRE_PAYLOAD,
    }
