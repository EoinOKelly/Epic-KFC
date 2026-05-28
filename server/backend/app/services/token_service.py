"""JWT access-token utilities and refresh-token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.core.config import settings


JWT_ACCESS_TYPE = "access"
JWT_ALLOWED_ALGORITHM = "HS256"
REFRESH_TOKEN_HASH_PREFIX = "hmac_sha256:"


class TokenServiceError(Exception):
    """Generic token service error for invalid tokens or unsafe configuration."""


@dataclass(frozen=True)
class AccessTokenPayload:
    """Validated access-token claims."""

    sub: str
    role: str
    jti: str
    iat: int
    exp: int
    type: str


def create_token_jti() -> str:
    """Create a high-entropy token identifier."""
    return secrets.token_urlsafe(32)


def create_access_token(user_id: UUID, role: str) -> str:
    """Create a short-lived signed JWT access token."""
    secret_key = _get_jwt_secret_key()
    algorithm = _get_jwt_algorithm()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": create_token_jti(),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": JWT_ACCESS_TYPE,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str) -> AccessTokenPayload:
    """Decode and validate a JWT access token."""
    try:
        claims = jwt.decode(
            token,
            _get_jwt_secret_key(),
            algorithms=[JWT_ALLOWED_ALGORITHM],
            options={"require": ["sub", "role", "jti", "iat", "exp", "type"]},
        )
        return _validate_access_token_claims(claims)
    except (InvalidTokenError, TypeError, ValueError) as exc:
        raise TokenServiceError("Invalid access token.") from exc


def create_refresh_token() -> str:
    """Create a high-entropy opaque refresh token."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(refresh_token: str) -> str:
    """Create a stable HMAC-SHA256 hash for a refresh token."""
    secret = _get_refresh_token_hash_secret().encode("utf-8")
    digest = hmac.new(
        secret,
        refresh_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{REFRESH_TOKEN_HASH_PREFIX}{digest}"


def verify_refresh_token_hash(refresh_token: str, stored_hash: str) -> bool:
    """Verify a refresh token against a stored HMAC hash."""
    if not _is_refresh_token_hash_format(stored_hash):
        return False

    try:
        candidate_hash = hash_refresh_token(refresh_token)
    except TokenServiceError:
        return False

    return hmac.compare_digest(candidate_hash, stored_hash)


def _get_jwt_secret_key() -> str:
    """Return configured JWT secret or fail safely."""
    if not settings.jwt_secret_key:
        raise TokenServiceError("Token service is not configured.")
    return settings.jwt_secret_key


def _get_refresh_token_hash_secret() -> str:
    """Return configured refresh-token hash secret or fail safely."""
    if not settings.refresh_token_hash_secret:
        raise TokenServiceError("Token service is not configured.")
    return settings.refresh_token_hash_secret


def _get_jwt_algorithm() -> str:
    """Return the configured JWT algorithm if it is explicitly allowed."""
    if settings.jwt_algorithm != JWT_ALLOWED_ALGORITHM:
        raise TokenServiceError("Token service is not configured.")
    return settings.jwt_algorithm


def _validate_access_token_claims(claims: dict[str, object]) -> AccessTokenPayload:
    """Validate required access-token claims and normalize the subject."""
    if claims.get("type") != JWT_ACCESS_TYPE:
        raise ValueError("Invalid token type.")

    sub = claims.get("sub")
    role = claims.get("role")
    jti = claims.get("jti")
    iat = claims.get("iat")
    exp = claims.get("exp")

    if not isinstance(sub, str):
        raise ValueError("Invalid token subject.")
    normalized_sub = str(UUID(sub))

    if not isinstance(role, str) or not role:
        raise ValueError("Invalid token role.")
    if not isinstance(jti, str) or not jti:
        raise ValueError("Invalid token identifier.")
    if isinstance(iat, bool) or not isinstance(iat, int):
        raise ValueError("Invalid issued-at claim.")
    if isinstance(exp, bool) or not isinstance(exp, int):
        raise ValueError("Invalid expiry claim.")

    return AccessTokenPayload(
        sub=normalized_sub,
        role=role,
        jti=jti,
        iat=iat,
        exp=exp,
        type=JWT_ACCESS_TYPE,
    )


def _is_refresh_token_hash_format(stored_hash: str) -> bool:
    """Validate the stored refresh-token hash wrapper format."""
    if not isinstance(stored_hash, str):
        return False
    if not stored_hash.startswith(REFRESH_TOKEN_HASH_PREFIX):
        return False
    digest = stored_hash.removeprefix(REFRESH_TOKEN_HASH_PREFIX)
    if len(digest) != 64:
        return False
    return all(character in "0123456789abcdef" for character in digest)
