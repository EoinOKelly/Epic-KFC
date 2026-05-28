"""Security tests for sensitive data exposure and audit evidence."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.models.audit_log import AuditLog
from app.repositories import audit_log_repository, device_key_repository, user_repository
from app.schemas.device_key import DeviceKeyUploadRequest
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "security-sensitive-jwt-secret-with-at-least-sixty-four-bytes-123456"
REFRESH_HASH_SECRET = "security-sensitive-refresh-secret-with-at-least-thirty-two"
PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "wrong-horse-battery-staple"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"
WIRE_PAYLOAD = (
    '{"counter":0,"previousCounter":0,"ciphertext":"b3JpZ2luYWw=",'
    '"iv":"aXY=","authTag":"dGFn"}'
)
FORWARDED_WIRE_PAYLOAD = (
    '{"counter":1,"previousCounter":0,"ciphertext":"Zm9yd2FyZA==",'
    '"iv":"aXY=","authTag":"dGFn"}'
)


@pytest.fixture(autouse=True)
def configure_sensitive_security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure auth settings and disable rate limits for data exposure tests."""
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
async def sensitive_client(
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
        headers={"user-agent": "pytest-security-sensitive"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def test_auth_responses_do_not_expose_password_or_session_hashes(
    sensitive_client: AsyncClient,
) -> None:
    """Auth responses should only expose intended token fields."""
    register = await _register(sensitive_client, "alice")
    login = await _login(sensitive_client, "alice")
    access_token = login.json()["access_token"]
    me = await sensitive_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    for response in (register, login, me):
        body = response.text.lower()
        assert "password_hash" not in body
        assert "refresh_token_hash" not in body
        assert "traceback" not in body
        assert "integrityerror" not in body

    assert login.status_code == 200
    assert "access_token" in login.json()
    assert "refresh_token" in login.json()
    assert "access_token" not in register.text
    assert "refresh_token" not in register.text
    assert "access_token" not in me.text
    assert "refresh_token" not in me.text


async def test_key_and_message_responses_do_not_expose_plaintext_or_private_fields(
    sensitive_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Key and message responses avoid private keys and plaintext-like fields."""
    sender, recipient = await _create_ready_users(integration_db, "bob", "carol")
    device_response = await _put_device_key(sensitive_client, sender, 1)
    message_response = await _send_message(sensitive_client, sender, recipient)
    response_text = (device_response.text + message_response.text).lower()

    assert device_response.status_code == 200
    assert message_response.status_code == 201
    for forbidden in ("private_key", "ratchet_state", "body", "content", "plaintext"):
        assert forbidden not in response_text


async def test_database_errors_and_stack_traces_are_not_exposed(
    sensitive_client: AsyncClient,
) -> None:
    """Duplicate registration should return a generic safe conflict."""
    first = await _register(sensitive_client, "dave")
    second = await _register(sensitive_client, "dave")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Username or email is unavailable"
    assert "traceback" not in second.text.lower()
    assert "integrityerror" not in second.text.lower()
    assert "users" not in second.text.lower()


async def test_successful_auth_events_create_audit_logs(
    sensitive_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Successful register/login events are auditable."""
    await _register(sensitive_client, "erin")
    await _login(sensitive_client, "erin")

    register_events = await audit_log_repository.list_by_event_type(
        integration_db,
        "auth.register_success",
    )
    login_events = await audit_log_repository.list_by_event_type(
        integration_db,
        "auth.login_success",
    )

    assert register_events
    assert login_events
    assert register_events[0].success is True
    assert login_events[0].success is True


async def test_failed_login_audit_log_does_not_store_password(
    sensitive_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Failed login audit events must not contain the submitted password."""
    await _register(sensitive_client, "frank")

    response = await _login(sensitive_client, "frank", WRONG_PASSWORD)
    events = await audit_log_repository.list_by_event_type(
        integration_db,
        "auth.login_failed",
    )

    assert response.status_code == 401
    assert events
    assert WRONG_PASSWORD not in _audit_log_text(events)


async def test_denied_message_fetch_creates_audit_log(
    sensitive_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Denied object access is recorded without exposing the message."""
    sender, recipient = await _create_ready_users(integration_db, "grace", "heidi")
    unrelated = await _create_user(integration_db, "ivan")
    message_id = (await _send_message(sensitive_client, sender, recipient)).json()["id"]

    response = await _get_message(sensitive_client, unrelated, message_id)
    events = await audit_log_repository.list_by_event_type(
        integration_db,
        "message.fetch_denied",
    )

    assert response.status_code == 404
    assert events
    assert events[0].success is False


async def test_message_forward_revoke_delete_audit_events_recorded(
    sensitive_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Forward, revoke, and delete success events are auditable."""
    sender, recipient = await _create_ready_users(integration_db, "judy", "kate")
    new_recipient = await _create_user(integration_db, "laura")
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    message_id = (await _send_message(sensitive_client, sender, recipient)).json()["id"]

    forward = await _forward_message(sensitive_client, sender, message_id, new_recipient)
    revoke = await _revoke_message(sensitive_client, sender, message_id)
    delete = await _delete_message(sensitive_client, sender, message_id)

    assert forward.status_code == 201
    assert revoke.status_code == 200
    assert delete.status_code == 200
    assert await audit_log_repository.list_by_event_type(
        integration_db,
        "message.forwarded",
    )
    assert await audit_log_repository.list_by_event_type(
        integration_db,
        "message.revoked",
    )
    assert await audit_log_repository.list_by_event_type(
        integration_db,
        "message.deleted",
    )


async def test_message_denial_audit_events_recorded(
    sensitive_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Forward, revoke, and delete denial events are auditable."""
    sender, recipient = await _create_ready_users(integration_db, "mallory", "nancy")
    unrelated = await _create_user(integration_db, "olivia")
    new_recipient = await _create_user(integration_db, "peggy")
    await _create_device_key(integration_db, unrelated, 1)
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    message_id = (await _send_message(sensitive_client, sender, recipient)).json()["id"]
    unrelated_headers = _auth_headers(unrelated)
    forward = await sensitive_client.post(
        f"/api/v1/messages/{message_id}/forward",
        json={
            "sender_device_id": 1,
            "recipient_user_id": str(new_recipient.id),
            "recipient_device_id": 1,
            "wire_payload_json": FORWARDED_WIRE_PAYLOAD,
        },
        headers=unrelated_headers,
    )
    revoke = await sensitive_client.post(
        f"/api/v1/messages/{message_id}/revoke",
        headers=unrelated_headers,
    )
    delete = await sensitive_client.delete(
        f"/api/v1/messages/{message_id}",
        headers=unrelated_headers,
    )

    assert forward.status_code == 404
    assert revoke.status_code == 404
    assert delete.status_code == 404
    assert await audit_log_repository.list_by_event_type(
        integration_db,
        "message.forward_denied",
    )
    assert await audit_log_repository.list_by_event_type(
        integration_db,
        "message.revoke_denied",
    )
    assert await audit_log_repository.list_by_event_type(
        integration_db,
        "message.delete_denied",
    )


async def test_audit_logs_do_not_contain_secrets_or_payloads(
    sensitive_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Audit logs store event metadata only."""
    await _register(sensitive_client, "quinn")
    login = await _login(sensitive_client, "quinn")
    sender, recipient = await _create_ready_users(integration_db, "ruth", "sam")
    await _send_message(sensitive_client, sender, recipient)

    events = await audit_log_repository.list_for_user(integration_db, sender.id)
    audit_text = _audit_log_text(events)

    assert login.status_code == 200
    for forbidden in (
        PASSWORD,
        PASSWORD_HASH,
        login.json()["access_token"],
        login.json()["refresh_token"],
        WIRE_PAYLOAD,
        KEY_B64,
        "password_hash",
        "refresh_token_hash",
        "wire_payload_json",
        "private_key",
        "body",
        "content",
        "plaintext",
    ):
        assert forbidden.lower() not in audit_text


def _audit_log_text(events: list[AuditLog]) -> str:
    """Serialize audit rows for negative secret assertions."""
    return json.dumps(
        [
            {
                "event_type": event.event_type,
                "resource_type": event.resource_type,
                "success": event.success,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "details": event.details,
            }
            for event in events
        ],
        sort_keys=True,
    ).lower()


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
    """Log in through the route."""
    return await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username_or_email, "password": password},
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


async def _put_device_key(client: AsyncClient, user, device_id: int) -> Response:
    """Upload a device key through the route."""
    return await client.put(
        f"/api/v1/keys/devices/{device_id}",
        json={
            "device_id": device_id,
            "registration_id": 1000 + device_id,
            "identity_key_public_b64": KEY_B64,
            "identity_signing_public_b64": KEY_B64,
            "signed_prekey_id": 2000 + device_id,
            "signed_prekey_public_b64": KEY_B64,
            "signed_prekey_signature_b64": KEY_B64,
        },
        headers=_auth_headers(user),
    )


async def _send_message(client: AsyncClient, sender, recipient) -> Response:
    """Send a direct message through the route."""
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


async def _get_message(client: AsyncClient, user, message_id: str) -> Response:
    """Fetch a message through the route."""
    return await client.get(
        f"/api/v1/messages/{message_id}",
        headers=_auth_headers(user),
    )


async def _forward_message(client: AsyncClient, user, message_id: str, recipient) -> Response:
    """Forward a message through the route."""
    return await client.post(
        f"/api/v1/messages/{message_id}/forward",
        json={
            "sender_device_id": 1,
            "recipient_user_id": str(recipient.id),
            "recipient_device_id": 1,
            "wire_payload_json": FORWARDED_WIRE_PAYLOAD,
        },
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
