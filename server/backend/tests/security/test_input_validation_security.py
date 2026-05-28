"""Security tests for input validation and injection resistance."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as api_deps
from app.main import app
from app.repositories import device_key_repository, user_repository
from app.schemas.blockchain_anchor import BlockchainAnchorCreateRequest
from app.schemas.common import MAX_WIRE_PAYLOAD_BYTES
from app.schemas.device_key import DeviceKeyUploadRequest
from app.services import auth_service, token_service


pytestmark = pytest.mark.asyncio

JWT_SECRET = "security-input-jwt-secret-with-at-least-sixty-four-bytes-123456789"
REFRESH_HASH_SECRET = "security-input-refresh-secret-with-at-least-thirty-two"
PASSWORD = "correct-horse-battery-staple"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"
WIRE_PAYLOAD = (
    '{"counter":0,"previousCounter":0,"ciphertext":"b3JpZ2luYWw=",'
    '"iv":"aXY=","authTag":"dGFn"}'
)


@pytest.fixture(autouse=True)
def configure_input_security_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure auth settings and disable rate limits for validation tests."""
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
async def validation_client(
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
        headers={"user-agent": "pytest-security-validation"},
    ) as client:
        yield client

    app.dependency_overrides.clear()


async def test_extra_request_fields_rejected(validation_client: AsyncClient) -> None:
    """Request schemas reject unexpected fields."""
    response = await validation_client.post(
        "/api/v1/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": PASSWORD,
            "password_hash": "$argon2id$not-allowed",
        },
    )

    assert response.status_code == 422
    _assert_no_secret_leak(response.text)


@pytest.mark.parametrize("field_name", ["body", "content", "plaintext"])
async def test_plaintext_like_message_fields_rejected(
    validation_client: AsyncClient,
    integration_db: AsyncSession,
    field_name: str,
) -> None:
    """Message requests reject plaintext-like fields."""
    sender, recipient = await _create_ready_users(
        integration_db,
        f"sender-{field_name}",
        f"recipient-{field_name}",
    )
    payload = _message_payload(recipient.id)
    payload[field_name] = "do not store this"

    response = await validation_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422
    _assert_no_secret_leak(response.text)


async def test_malformed_wire_payload_json_rejected(
    validation_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Malformed opaque wire payloads are rejected structurally."""
    sender, recipient = await _create_ready_users(integration_db, "bob", "carol")
    payload = _message_payload(recipient.id)
    payload["wire_payload_json"] = "not-json"

    response = await validation_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


async def test_oversized_wire_payload_json_rejected(
    validation_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Oversized encrypted relay payloads are rejected."""
    sender, recipient = await _create_ready_users(integration_db, "dave", "erin")
    payload = _message_payload(recipient.id)
    payload["wire_payload_json"] = "x" * (MAX_WIRE_PAYLOAD_BYTES + 1)

    response = await validation_client.post(
        "/api/v1/messages",
        json=payload,
        headers=_auth_headers(sender),
    )

    assert response.status_code == 422


async def test_malformed_base64_device_field_rejected(
    validation_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Malformed public key base64 is rejected."""
    user = await _create_user(integration_db, "frank")
    payload = _device_payload(1)
    payload["identity_key_public_b64"] = "not valid base64"

    response = await validation_client.put(
        "/api/v1/keys/devices/1",
        json=payload,
        headers=_auth_headers(user),
    )

    assert response.status_code == 422


async def test_invalid_device_ids_rejected(
    validation_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Device IDs must be positive."""
    user = await _create_user(integration_db, "grace")
    payload = _device_payload(0)

    response = await validation_client.put(
        "/api/v1/keys/devices/0",
        json=payload,
        headers=_auth_headers(user),
    )

    assert response.status_code == 422


async def test_invalid_uuid_path_params_rejected(
    validation_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """Malformed UUID path params return validation errors."""
    user = await _create_user(integration_db, "heidi")

    response = await validation_client.get(
        "/api/v1/messages/not-a-uuid",
        headers=_auth_headers(user),
    )

    assert response.status_code == 422
    _assert_no_secret_leak(response.text)


async def test_oversized_one_time_prekey_batch_rejected(
    validation_client: AsyncClient,
    integration_db: AsyncSession,
) -> None:
    """One-time prekey uploads enforce the batch-size limit."""
    user = await _create_user(integration_db, "ivan")
    payload = {
        "prekeys": [
            {"device_id": 1, "prekey_id": prekey_id, "prekey_public_b64": KEY_B64}
            for prekey_id in range(1, 102)
        ]
    }

    response = await validation_client.post(
        "/api/v1/keys/devices/1/one-time-prekeys",
        json=payload,
        headers=_auth_headers(user),
    )

    assert response.status_code == 422


async def test_malformed_email_rejected(validation_client: AsyncClient) -> None:
    """Registration rejects malformed emails."""
    response = await validation_client.post(
        "/api/v1/auth/register",
        json={
            "username": "judy",
            "email": "not-an-email",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 422


async def test_short_password_rejected(validation_client: AsyncClient) -> None:
    """Registration rejects short passwords."""
    response = await validation_client.post(
        "/api/v1/auth/register",
        json={
            "username": "kate",
            "email": "kate@example.com",
            "password": "too-short",
        },
    )

    assert response.status_code == 422


async def test_invalid_ethereum_hash_rejected() -> None:
    """Blockchain schemas reject invalid Ethereum digest formats."""
    with pytest.raises(ValidationError):
        BlockchainAnchorCreateRequest.model_validate(
            {
                "message_id": str(uuid4()),
                "digest": "not-a-keccak-hash",
                "chain": "sepolia",
                "status": "pending",
            }
        )


async def test_sql_injection_login_payload_does_not_bypass_auth(
    validation_client: AsyncClient,
) -> None:
    """SQL injection-style login payloads do not authenticate."""
    response = await validation_client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "' OR '1'='1",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_sql_injection_registration_username_rejected(
    validation_client: AsyncClient,
) -> None:
    """Injection-style usernames are rejected by validation."""
    response = await validation_client.post(
        "/api/v1/auth/register",
        json={
            "username": "admin' OR '1'='1",
            "email": "inject@example.com",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 422


async def test_duplicate_registration_returns_generic_409(
    validation_client: AsyncClient,
) -> None:
    """Duplicate registration should not leak database errors."""
    first = await _register(validation_client, "laura")
    second = await _register(validation_client, "laura")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Username or email is unavailable"
    assert "IntegrityError" not in second.text
    assert "users" not in second.text.lower()
    assert "traceback" not in second.text.lower()


async def test_repository_files_do_not_use_session_query_or_obvious_f_string_sql() -> None:
    """Repositories should use SQLAlchemy 2.x parameterized query APIs."""
    repository_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("app/repositories").glob("*.py")
    )

    assert "Session.query(" not in repository_text
    assert ".query(" not in repository_text
    assert "execute(f\"" not in repository_text
    assert "execute(f'" not in repository_text


async def _register(client: AsyncClient, username: str):
    """Register a user through the route."""
    return await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
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


def _auth_headers(user) -> dict[str, str]:
    """Return Bearer auth headers for a user."""
    token = token_service.create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _device_payload(device_id: int) -> dict[str, object]:
    """Build a valid device key payload."""
    return {
        "device_id": device_id,
        "registration_id": 1001,
        "identity_key_public_b64": KEY_B64,
        "identity_signing_public_b64": KEY_B64,
        "signed_prekey_id": 2001,
        "signed_prekey_public_b64": KEY_B64,
        "signed_prekey_signature_b64": KEY_B64,
    }


def _message_payload(recipient_user_id) -> dict[str, object]:
    """Build a valid direct message payload."""
    return {
        "sender_device_id": 1,
        "recipient_user_id": str(recipient_user_id),
        "recipient_device_id": 1,
        "wire_payload_json": WIRE_PAYLOAD,
    }


def _assert_no_secret_leak(response_text: str) -> None:
    """Ensure validation responses do not contain secret-bearing terms."""
    lower_text = response_text.lower()
    assert "traceback" not in lower_text
    assert "integrityerror" not in lower_text
    assert "password_hash" not in lower_text
    assert "refresh_token_hash" not in lower_text
