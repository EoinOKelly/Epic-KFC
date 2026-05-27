"""Unit tests for token service utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest

from app.services import token_service
from app.services.token_service import (
    JWT_ACCESS_TYPE,
    JWT_ALLOWED_ALGORITHM,
    REFRESH_TOKEN_HASH_PREFIX,
    TokenServiceError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_refresh_token,
    verify_refresh_token_hash,
)


JWT_SECRET = "unit-test-jwt-secret-with-at-least-sixty-four-bytes-for-hmac-tests-12345"
WRONG_JWT_SECRET = "wrong-unit-test-jwt-secret-with-at-least-thirty-two-bytes-123"
REFRESH_HASH_SECRET = "unit-test-refresh-hash-secret-with-at-least-thirty-two-bytes"


@pytest.fixture(autouse=True)
def configure_token_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure token secrets for isolated unit tests."""
    monkeypatch.setattr(token_service.settings, "jwt_secret_key", JWT_SECRET)
    monkeypatch.setattr(
        token_service.settings,
        "refresh_token_hash_secret",
        REFRESH_HASH_SECRET,
    )
    monkeypatch.setattr(token_service.settings, "jwt_algorithm", JWT_ALLOWED_ALGORITHM)
    monkeypatch.setattr(token_service.settings, "access_token_expire_minutes", 15)
    monkeypatch.setattr(token_service.settings, "refresh_token_expire_days", 7)


def test_create_access_token_returns_string() -> None:
    """Access-token creation returns a JWT string."""
    token = create_access_token(uuid4(), "user")

    assert isinstance(token, str)


def test_decoded_token_contains_required_claims() -> None:
    """Decoded access tokens expose all required claims."""
    user_id = uuid4()
    token = create_access_token(user_id, "admin")

    payload = decode_access_token(token)

    assert payload.sub == str(user_id)
    assert payload.role == "admin"
    assert payload.jti
    assert isinstance(payload.iat, int)
    assert isinstance(payload.exp, int)
    assert payload.type == JWT_ACCESS_TYPE


def test_decoded_token_type_is_access() -> None:
    """Access-token payload type should be access."""
    token = create_access_token(uuid4(), "user")

    payload = decode_access_token(token)

    assert payload.type == "access"


def test_expired_token_is_rejected() -> None:
    """Expired JWTs should fail with the generic service error."""
    user_id = uuid4()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "role": "user",
            "jti": "expired-token-id",
            "iat": int((now - timedelta(minutes=30)).timestamp()),
            "exp": int((now - timedelta(minutes=15)).timestamp()),
            "type": JWT_ACCESS_TYPE,
        },
        JWT_SECRET,
        algorithm=JWT_ALLOWED_ALGORITHM,
    )

    with pytest.raises(TokenServiceError):
        decode_access_token(token)


def test_malformed_token_is_rejected() -> None:
    """Malformed JWT strings should fail safely."""
    with pytest.raises(TokenServiceError):
        decode_access_token("not-a-jwt")


def test_token_signed_with_wrong_secret_is_rejected() -> None:
    """JWT signature verification must reject the wrong secret."""
    token = jwt.encode(
        _valid_payload(),
        WRONG_JWT_SECRET,
        algorithm=JWT_ALLOWED_ALGORITHM,
    )

    with pytest.raises(TokenServiceError):
        decode_access_token(token)


def test_token_with_wrong_type_is_rejected() -> None:
    """Only access tokens should decode through the access-token helper."""
    payload = _valid_payload()
    payload["type"] = "refresh"
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALLOWED_ALGORITHM)

    with pytest.raises(TokenServiceError):
        decode_access_token(token)


def test_token_missing_required_claims_is_rejected() -> None:
    """Tokens missing required claims should fail safely."""
    payload = _valid_payload()
    del payload["jti"]
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALLOWED_ALGORITHM)

    with pytest.raises(TokenServiceError):
        decode_access_token(token)


def test_token_with_invalid_uuid_subject_is_rejected() -> None:
    """The sub claim must be a valid UUID string."""
    payload = _valid_payload()
    payload["sub"] = "not-a-uuid"
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALLOWED_ALGORITHM)

    with pytest.raises(TokenServiceError):
        decode_access_token(token)


def test_missing_jwt_secret_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT helpers should fail safely without a configured secret."""
    monkeypatch.setattr(token_service.settings, "jwt_secret_key", None)

    with pytest.raises(TokenServiceError):
        create_access_token(uuid4(), "user")

    with pytest.raises(TokenServiceError):
        decode_access_token("not-a-jwt")


def test_create_refresh_token_returns_string() -> None:
    """Refresh-token creation returns an opaque string."""
    refresh_token = create_refresh_token()

    assert isinstance(refresh_token, str)


def test_refresh_tokens_differ_each_time() -> None:
    """Refresh tokens should have fresh entropy."""
    first_token = create_refresh_token()
    second_token = create_refresh_token()

    assert first_token != second_token


def test_refresh_token_hash_is_not_raw_token() -> None:
    """Stored refresh-token hashes must not equal raw tokens."""
    refresh_token = create_refresh_token()
    token_hash = hash_refresh_token(refresh_token)

    assert token_hash != refresh_token


def test_refresh_token_hash_prefix() -> None:
    """Refresh-token hashes should use the documented wrapper prefix."""
    token_hash = hash_refresh_token(create_refresh_token())

    assert token_hash.startswith(REFRESH_TOKEN_HASH_PREFIX)


def test_correct_refresh_token_verifies() -> None:
    """Correct refresh token should match its HMAC hash."""
    refresh_token = create_refresh_token()
    token_hash = hash_refresh_token(refresh_token)

    assert verify_refresh_token_hash(refresh_token, token_hash) is True


def test_wrong_refresh_token_fails() -> None:
    """Wrong refresh token should not match."""
    token_hash = hash_refresh_token(create_refresh_token())

    assert verify_refresh_token_hash("wrong-refresh-token", token_hash) is False


def test_malformed_stored_refresh_hash_fails_safely() -> None:
    """Malformed refresh-token hashes should return False."""
    assert verify_refresh_token_hash(create_refresh_token(), "not-a-refresh-hash") is False


def test_missing_refresh_token_hash_secret_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh-token hash helpers should fail safely without a secret."""
    monkeypatch.setattr(token_service.settings, "refresh_token_hash_secret", None)

    with pytest.raises(TokenServiceError):
        hash_refresh_token(create_refresh_token())

    assert verify_refresh_token_hash(create_refresh_token(), "not-a-refresh-hash") is False


def test_hs512_token_is_rejected() -> None:
    """The decoder must not trust the algorithm from the token header."""
    token = jwt.encode(_valid_payload(), JWT_SECRET, algorithm="HS512")

    with pytest.raises(TokenServiceError):
        decode_access_token(token)


def _valid_payload() -> dict[str, object]:
    """Create a valid JWT payload for negative tests."""
    now = datetime.now(UTC)
    return {
        "sub": str(UUID(str(uuid4()))),
        "role": "user",
        "jti": "unit-test-token-id",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "type": JWT_ACCESS_TYPE,
    }
