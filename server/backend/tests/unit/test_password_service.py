"""Unit tests for Argon2id password service."""

from argon2 import PasswordHasher, Type

from app.services.password_service import (
    hash_password,
    password_needs_rehash,
    verify_password,
)


PLAINTEXT_PASSWORD = "correct-horse-battery-staple"


def test_hash_password_returns_string() -> None:
    """hash_password returns a PHC string."""
    password_hash = hash_password(PLAINTEXT_PASSWORD)

    assert isinstance(password_hash, str)


def test_hash_password_is_not_plaintext() -> None:
    """Password hashes must not equal the plaintext password."""
    password_hash = hash_password(PLAINTEXT_PASSWORD)

    assert password_hash != PLAINTEXT_PASSWORD


def test_hash_password_starts_with_argon2id_phc_prefix() -> None:
    """Password hashes should use PHC Argon2id format."""
    password_hash = hash_password(PLAINTEXT_PASSWORD)

    assert password_hash.startswith("$argon2id$")


def test_correct_password_verifies() -> None:
    """The correct password verifies against its hash."""
    password_hash = hash_password(PLAINTEXT_PASSWORD)

    assert verify_password(PLAINTEXT_PASSWORD, password_hash) is True


def test_wrong_password_fails() -> None:
    """An incorrect password must not verify."""
    password_hash = hash_password(PLAINTEXT_PASSWORD)

    assert verify_password("wrong-password-value", password_hash) is False


def test_same_password_produces_different_hashes() -> None:
    """Random salts should make repeated hashes different."""
    first_hash = hash_password(PLAINTEXT_PASSWORD)
    second_hash = hash_password(PLAINTEXT_PASSWORD)

    assert first_hash != second_hash


def test_malformed_stored_hash_returns_false() -> None:
    """Malformed hashes should fail verification safely."""
    assert verify_password(PLAINTEXT_PASSWORD, "not-a-phc-hash") is False


def test_fresh_hash_does_not_need_rehash() -> None:
    """A hash generated with current parameters should not need rehashing."""
    password_hash = hash_password(PLAINTEXT_PASSWORD)

    assert password_needs_rehash(password_hash) is False


def test_weaker_argon2id_hash_needs_rehash() -> None:
    """Older or weaker Argon2id parameters should be flagged for upgrade."""
    weaker_hasher = PasswordHasher(
        memory_cost=8192,
        time_cost=1,
        parallelism=1,
        hash_len=16,
        salt_len=8,
        type=Type.ID,
    )
    weaker_hash = weaker_hasher.hash(PLAINTEXT_PASSWORD)

    assert password_needs_rehash(weaker_hash) is True


def test_hash_does_not_contain_plaintext_password() -> None:
    """The plaintext password should not appear inside the PHC string."""
    password_hash = hash_password(PLAINTEXT_PASSWORD)

    assert PLAINTEXT_PASSWORD not in password_hash


def test_malformed_hash_needs_rehash() -> None:
    """Malformed hashes should be treated as needing replacement."""
    assert password_needs_rehash("not-a-phc-hash") is True
