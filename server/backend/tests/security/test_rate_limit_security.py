"""Security tests for rate limiting and abuse prevention."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.core import rate_limit
from app.main import app
from app.repositories import device_key_repository, user_repository
from app.schemas.device_key import DeviceKeyUploadRequest
from app.services import auth_service, token_service
from tests.fixtures.wire_payloads import WIRE_PAYLOAD


pytestmark = pytest.mark.asyncio

JWT_SECRET = "security-rate-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "security-rate-refresh-secret-with-at-least-thirty-two"
PASSWORD = "correct-horse-battery-staple"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"


@pytest.fixture(autouse=True)
def configure_rate_security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure auth settings and small rate limits for security tests."""
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
    monkeypatch.setattr(api_deps.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        rate_limit,
        "REGISTER_RATE_LIMIT",
        rate_limit.RateLimitRule(limit=2, window_seconds=60),
    )
    monkeypatch.setattr(
        rate_limit,
        "LOGIN_RATE_LIMIT",
        rate_limit.RateLimitRule(limit=2, window_seconds=60),
    )
    monkeypatch.setattr(
        rate_limit,
        "MESSAGE_SEND_RATE_LIMIT",
        rate_limit.RateLimitRule(limit=2, window_seconds=60),
    )


@pytest_asyncio.fixture
async def rate_security_client(
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
        headers={"user-agent": "pytest-security-rate"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def test_repeated_login_returns_429(rate_security_client: AsyncClient) -> None:
    """Repeated login attempts are rate limited."""
    first = await _login(rate_security_client, "missing-user")
    second = await _login(rate_security_client, "missing-user")
    third = await _login(rate_security_client, "missing-user")

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert third.json()["detail"] == "Too many requests"


async def test_repeated_register_returns_429(rate_security_client: AsyncClient) -> None:
    """Repeated registration attempts are rate limited."""
    first = await _register(rate_security_client, "register-one")
    second = await _register(rate_security_client, "register-two")
    third = await _register(rate_security_client, "register-three")

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429


async def test_repeated_message_sending_returns_429(
    rate_security_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Repeated message sending is rate limited per user."""
    sender, recipient = await _create_ready_users(integration_db, "alice", "bob")

    first = await _send_message(rate_security_client, sender, recipient)
    second = await _send_message(rate_security_client, sender, recipient)
    third = await _send_message(rate_security_client, sender, recipient)

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429


async def test_429_includes_retry_after(rate_security_client: AsyncClient) -> None:
    """Rate-limit responses include Retry-After."""
    await _login(rate_security_client, "missing-user")
    await _login(rate_security_client, "missing-user")

    response = await _login(rate_security_client, "missing-user")

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


async def test_429_does_not_reveal_account_existence(
    rate_security_client: AsyncClient,
) -> None:
    """Rate-limit responses remain generic."""
    await _login(rate_security_client, "nonexistent@example.com")
    await _login(rate_security_client, "nonexistent@example.com")

    response = await _login(rate_security_client, "nonexistent@example.com")

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many requests"
    assert "nonexistent" not in response.text
    assert "Invalid credentials" not in response.text


async def test_authenticated_users_have_independent_message_limits(
    rate_security_client: AsyncClient,
    integration_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One authenticated user's rate limit does not block another user."""
    monkeypatch.setattr(
        rate_limit,
        "MESSAGE_SEND_RATE_LIMIT",
        rate_limit.RateLimitRule(limit=1, window_seconds=60),
    )
    first_sender, recipient = await _create_ready_users(integration_db, "carol", "dave")
    second_sender = await _create_user(integration_db, "erin")
    await _create_device_key(integration_db, second_sender, 1)
    await integration_db.commit()

    first = await _send_message(rate_security_client, first_sender, recipient)
    blocked = await _send_message(rate_security_client, first_sender, recipient)
    independent = await _send_message(rate_security_client, second_sender, recipient)

    assert first.status_code == 201
    assert blocked.status_code == 429
    assert independent.status_code == 201


async def test_normal_requests_still_work_under_limit(
    rate_security_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Valid requests remain usable under the configured limits."""
    register = await _register(rate_security_client, "frank")
    login = await _login(rate_security_client, "frank")
    sender, recipient = await _create_ready_users(integration_db, "grace", "heidi")
    message = await _send_message(rate_security_client, sender, recipient)

    assert register.status_code == 201
    assert login.status_code == 200
    assert message.status_code == 201


async def _register(client: AsyncClient, username: str) -> Response:
    """Register through the route."""
    return await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )


async def _login(client: AsyncClient, username_or_email: str) -> Response:
    """Log in through the route."""
    return await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username_or_email, "password": PASSWORD},
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


def _auth_headers(user) -> dict[str, str]:
    """Return Bearer auth headers for a user."""
    token = token_service.create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}
