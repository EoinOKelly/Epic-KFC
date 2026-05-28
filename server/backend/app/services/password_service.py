"""Argon2id password hashing and verification service."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


_PASSWORD_HASHER = PasswordHasher(
    memory_cost=65536,
    time_cost=3,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Return a PHC-encoded Argon2id hash for a plaintext password."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PHC hash."""
    try:
        return _PASSWORD_HASHER.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    """Return whether a stored hash should be upgraded to current parameters."""
    try:
        return _PASSWORD_HASHER.check_needs_rehash(stored_hash)
    except (InvalidHashError, VerificationError, TypeError, ValueError):
        return True
