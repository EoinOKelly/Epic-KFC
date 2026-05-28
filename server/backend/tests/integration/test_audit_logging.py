"""Integration tests for security audit logging."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.models.audit_log import AuditLog
from app.repositories import (
    audit_log_repository,
    device_key_repository,
    one_time_prekey_repository,
    user_repository,
)
from app.schemas.device_key import DeviceKeyUploadRequest
from app.schemas.one_time_prekey import OneTimePreKeyUpload
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "audit-test-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "audit-test-refresh-secret-with-at-least-thirty-two-bytes"
VALID_PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "wrong-horse-battery-staple"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"
WIRE_PAYLOAD = (
    '{"counter":0,"previousCounter":0,"ciphertext":"b3JpZ2luYWw=",'
    '"iv":"aXY=","authTag":"dGFn"}'
)


@pytest.fixture(autouse=True)
def configure_audit_route_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for audit route integration tests."""
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
async def audit_client(
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
        headers={"user-agent": "pytest-audit"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def test_register_success_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Successful registration creates an audit event."""
    response = await _register(audit_client, username="alice")
    event = await _latest_event(integration_db, "auth.register_success")

    assert response.status_code == 201
    assert event.actor_user_id == UUID(response.json()["id"])
    assert event.resource_type == "user"
    assert event.success is True


async def test_duplicate_registration_creates_safe_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Duplicate registration attempts create a safe failure event."""
    await _register(audit_client, username="bob", email="bob@example.com")

    response = await _register(
        audit_client,
        username="bob2",
        email="BOB@example.com",
    )
    event = await _latest_event(integration_db, "auth.register_duplicate_rejected")

    assert response.status_code == 409
    assert event.actor_user_id is None
    assert event.success is False
    assert event.details == {"reason": "duplicate_user"}
    assert "bob@example.com" not in _audit_log_text([event]).lower()


async def test_login_success_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Successful login creates an audit event."""
    await _register(audit_client, username="carol")

    response = await _login(audit_client, username_or_email="carol")
    event = await _latest_event(integration_db, "auth.login_success")

    assert response.status_code == 200
    assert event.success is True
    assert event.actor_user_id is not None
    assert event.resource_type == "user"


async def test_login_failure_creates_audit_log_without_password(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Failed login creates an audit event without storing passwords."""
    await _register(audit_client, username="dave")

    response = await _login(
        audit_client,
        username_or_email="dave",
        password=WRONG_PASSWORD,
    )
    event = await _latest_event(integration_db, "auth.login_failed")

    assert response.status_code == 401
    assert event.success is False
    assert event.details == {"reason": "invalid_credentials"}
    assert WRONG_PASSWORD not in _audit_log_text([event])


async def test_device_key_upload_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Device key upload creates an audit event."""
    user = await _create_user(integration_db, "erin")

    response = await _put_device_key(audit_client, user, 1)
    event = await _latest_event(integration_db, "keys.device_upserted")

    assert response.status_code == 200
    assert event.actor_user_id == user.id
    assert event.resource_type == "device_key"
    assert event.success is True
    assert event.details == {"device_id": 1}


async def test_one_time_prekey_upload_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """One-time prekey batch upload creates an audit event."""
    user = await _create_user(integration_db, "frank")

    response = await _post_prekeys(audit_client, user, 1, [10, 11])
    event = await _latest_event(integration_db, "keys.one_time_prekeys_uploaded")

    assert response.status_code == 200
    assert event.actor_user_id == user.id
    assert event.success is True
    assert event.details == {"device_id": 1, "prekey_count": 2}


async def test_prekey_bundle_fetch_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Fetching a prekey bundle creates an audit event."""
    requester = await _create_user(integration_db, "grace")
    target = await _create_user(integration_db, "heidi")
    device_key = await _create_device_key(integration_db, target, 1)
    await _create_prekeys(integration_db, target, 1, [20])
    await integration_db.commit()

    response = await _get_bundle(audit_client, requester, target.id, 1)
    event = await _latest_event(integration_db, "keys.prekey_bundle_fetched")

    assert response.status_code == 200
    assert event.actor_user_id == requester.id
    assert event.resource_id == device_key.id
    assert event.success is True
    assert event.details == {
        "target_device_id": 1,
        "one_time_prekey_included": True,
    }


async def test_message_send_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sending a message creates an audit event."""
    sender, recipient = await _create_ready_users(integration_db, "ivan", "judy")

    response = await _send_message(audit_client, sender, recipient)
    event = await _latest_event(integration_db, "message.sent")

    assert response.status_code == 201
    assert event.actor_user_id == sender.id
    assert event.resource_id == UUID(response.json()["id"])
    assert event.success is True


async def test_message_fetch_success_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Fetching an accessible message creates an audit event."""
    sender, recipient = await _create_ready_users(integration_db, "kate", "laura")
    message_id = (await _send_message(audit_client, sender, recipient)).json()["id"]

    response = await _get_message(audit_client, recipient, message_id)
    event = await _latest_event(integration_db, "message.fetched")

    assert response.status_code == 200
    assert event.actor_user_id == recipient.id
    assert event.resource_id == UUID(message_id)
    assert event.success is True


async def test_unrelated_fetch_denial_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Denied message fetches create safe audit events."""
    sender, recipient = await _create_ready_users(integration_db, "mallory", "nancy")
    unrelated = await _create_user(integration_db, "olivia")
    message_id = (await _send_message(audit_client, sender, recipient)).json()["id"]

    response = await _get_message(audit_client, unrelated, message_id)
    event = await _latest_event(integration_db, "message.fetch_denied")

    assert response.status_code == 404
    assert event.actor_user_id == unrelated.id
    assert event.resource_id == UUID(message_id)
    assert event.success is False
    assert event.details == {"reason": "not_found_or_inaccessible"}


async def test_sender_revoke_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Sender revocation creates an audit event."""
    sender, recipient = await _create_ready_users(integration_db, "peggy", "quinn")
    message_id = (await _send_message(audit_client, sender, recipient)).json()["id"]

    response = await _revoke_message(audit_client, sender, message_id)
    event = await _latest_event(integration_db, "message.revoked")

    assert response.status_code == 200
    assert event.actor_user_id == sender.id
    assert event.resource_id == UUID(message_id)
    assert event.success is True


async def test_non_sender_revoke_denial_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Denied revocation creates a safe audit event."""
    sender, recipient = await _create_ready_users(integration_db, "ruth", "sam")
    recipient_id = recipient.id
    message_id = (await _send_message(audit_client, sender, recipient)).json()["id"]

    response = await _revoke_message(audit_client, recipient, message_id)
    event = await _latest_event(integration_db, "message.revoke_denied")

    assert response.status_code == 404
    assert event.actor_user_id == recipient_id
    assert event.resource_id == UUID(message_id)
    assert event.success is False


async def test_delete_creates_audit_log(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Deleting a visible copy creates an audit event."""
    sender, recipient = await _create_ready_users(integration_db, "trent", "ursula")
    message_id = (await _send_message(audit_client, sender, recipient)).json()["id"]

    response = await _delete_message(audit_client, sender, message_id)
    event = await _latest_event(integration_db, "message.deleted")

    assert response.status_code == 200
    assert event.actor_user_id == sender.id
    assert event.resource_id == UUID(message_id)
    assert event.success is True


async def test_audit_logging_does_not_break_successful_route_behavior(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Routes still return normal responses when audit logging is present."""
    sender, recipient = await _create_ready_users(integration_db, "victor", "wendy")

    response = await _send_message(audit_client, sender, recipient)
    event = await _latest_event(integration_db, "message.sent")

    assert response.status_code == 201
    assert response.json()["wire_payload_json"] == WIRE_PAYLOAD
    assert event.resource_id == UUID(response.json()["id"])


async def test_audit_logs_do_not_store_secrets_or_payloads(
    audit_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Audit rows must not store secrets, key material, or message payloads."""
    await _register(audit_client, username="xavier", password=VALID_PASSWORD)
    login = await _login(audit_client, username_or_email="xavier")
    sender, recipient = await _create_ready_users(integration_db, "yvonne", "zara")
    await _put_device_key(audit_client, sender, 1)
    message = await _send_message(audit_client, sender, recipient)

    events = await audit_log_repository.list_by_event_type(
        integration_db,
        "message.sent",
        limit=20,
    )
    all_user_events = await audit_log_repository.list_for_user(
        integration_db,
        sender.id,
        limit=50,
    )
    audit_text = _audit_log_text(events + all_user_events)

    assert login.status_code == 200
    assert message.status_code == 201
    assert VALID_PASSWORD not in audit_text
    assert login.json()["access_token"] not in audit_text
    assert login.json()["refresh_token"] not in audit_text
    assert PASSWORD_HASH not in audit_text
    assert WIRE_PAYLOAD not in audit_text
    assert KEY_B64 not in audit_text
    for forbidden in (
        "password_hash",
        "access_token",
        "refresh_token",
        "wire_payload_json",
        "private_key",
        "body",
        "content",
        "plaintext",
    ):
        assert forbidden not in audit_text


async def _latest_event(integration_db: AsyncSession, event_type: str) -> AuditLog:
    """Return the newest audit event for an event type."""
    events = await audit_log_repository.list_by_event_type(
        integration_db,
        event_type,
        limit=1,
    )
    assert events
    return events[0]


def _audit_log_text(events: list[AuditLog]) -> str:
    """Serialize audit rows for negative secret assertions."""
    return json.dumps(
        [
            {
                "event_type": event.event_type,
                "resource_type": event.resource_type,
                "resource_id": str(event.resource_id) if event.resource_id else None,
                "success": event.success,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "details": event.details,
            }
            for event in events
        ],
        sort_keys=True,
    ).lower()


async def _register(
    client: AsyncClient,
    *,
    username: str,
    email: str | None = None,
    password: str = VALID_PASSWORD,
) -> Response:
    """Register through the route."""
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
) -> Response:
    """Log in through the route."""
    return await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


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
        [
            OneTimePreKeyUpload(**_prekey_payload(device_id, prekey_id))
            for prekey_id in prekey_ids
        ],
    )


async def _put_device_key(
    client: AsyncClient,
    user,
    device_id: int,
) -> Response:
    """Upload a device key through the route."""
    return await client.put(
        f"/api/v1/keys/devices/{device_id}",
        json=_device_payload(device_id),
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
        json={
            "prekeys": [
                _prekey_payload(device_id, prekey_id) for prekey_id in prekey_ids
            ]
        },
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


def _message_payload(recipient_user_id) -> dict[str, object]:
    """Build a valid direct message route payload."""
    return {
        "sender_device_id": 1,
        "recipient_user_id": str(recipient_user_id),
        "recipient_device_id": 1,
        "wire_payload_json": WIRE_PAYLOAD,
    }
