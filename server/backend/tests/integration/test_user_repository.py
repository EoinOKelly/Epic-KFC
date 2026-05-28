"""Integration tests for user repository functions."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import user_repository


pytestmark = pytest.mark.asyncio

PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"


async def test_create_user_stores_password_hash(integration_db: AsyncSession) -> None:
    """create_user stores only the provided password hash."""
    user = await user_repository.create_user(
        integration_db,
        username="alice",
        email=" Alice@Example.COM ",
        password_hash=PASSWORD_HASH,
    )

    assert user.password_hash == PASSWORD_HASH
    assert user.email == "alice@example.com"


async def test_user_model_has_no_plaintext_password_field() -> None:
    """The user model should not expose a plaintext password column."""
    column_names = set(User.__table__.columns.keys())

    assert "password_hash" in column_names
    assert "password" not in column_names
    assert "plaintext_password" not in column_names


async def test_get_by_email_works(integration_db: AsyncSession) -> None:
    """Users can be fetched by normalized email."""
    user = await user_repository.create_user(
        integration_db,
        username="bob",
        email="bob@example.com",
        password_hash=PASSWORD_HASH,
    )

    found = await user_repository.get_by_email(integration_db, " BOB@EXAMPLE.COM ")

    assert found is not None
    assert found.id == user.id


async def test_get_by_username_works(integration_db: AsyncSession) -> None:
    """Users can be fetched by exact-case username."""
    user = await user_repository.create_user(
        integration_db,
        username="CaseSensitiveUser",
        email="case@example.com",
        password_hash=PASSWORD_HASH,
    )

    found = await user_repository.get_by_username(integration_db, "CaseSensitiveUser")

    assert found is not None
    assert found.id == user.id


async def test_get_by_username_or_email_works_for_email(
    integration_db: AsyncSession,
) -> None:
    """Combined lookup works for email values."""
    user = await user_repository.create_user(
        integration_db,
        username="carol",
        email="carol@example.com",
        password_hash=PASSWORD_HASH,
    )

    found = await user_repository.get_by_username_or_email(
        integration_db,
        "CAROL@EXAMPLE.COM",
    )

    assert found is not None
    assert found.id == user.id


async def test_get_by_username_or_email_works_for_username(
    integration_db: AsyncSession,
) -> None:
    """Combined lookup works for username values."""
    user = await user_repository.create_user(
        integration_db,
        username="dave",
        email="dave@example.com",
        password_hash=PASSWORD_HASH,
    )

    found = await user_repository.get_by_username_or_email(integration_db, "dave")

    assert found is not None
    assert found.id == user.id


async def test_username_exists_true_and_false(integration_db: AsyncSession) -> None:
    """username_exists reports presence accurately."""
    await user_repository.create_user(
        integration_db,
        username="erin",
        email="erin@example.com",
        password_hash=PASSWORD_HASH,
    )

    assert await user_repository.username_exists(integration_db, "erin") is True
    assert await user_repository.username_exists(integration_db, "missing") is False


async def test_email_exists_true_and_false(integration_db: AsyncSession) -> None:
    """email_exists normalizes email before lookup."""
    await user_repository.create_user(
        integration_db,
        username="frank",
        email="frank@example.com",
        password_hash=PASSWORD_HASH,
    )

    assert await user_repository.email_exists(integration_db, " FRANK@EXAMPLE.COM ") is True
    assert await user_repository.email_exists(integration_db, "missing@example.com") is False


async def test_duplicate_username_raises_integrity_error(
    integration_db: AsyncSession,
) -> None:
    """Duplicate usernames should surface as database integrity errors."""
    await user_repository.create_user(
        integration_db,
        username="grace",
        email="grace@example.com",
        password_hash=PASSWORD_HASH,
    )

    with pytest.raises(IntegrityError):
        await user_repository.create_user(
            integration_db,
            username="grace",
            email="grace2@example.com",
            password_hash=PASSWORD_HASH,
        )


async def test_duplicate_email_raises_integrity_error(
    integration_db: AsyncSession,
) -> None:
    """Duplicate normalized emails should surface as integrity errors."""
    await user_repository.create_user(
        integration_db,
        username="heidi",
        email="heidi@example.com",
        password_hash=PASSWORD_HASH,
    )

    with pytest.raises(IntegrityError):
        await user_repository.create_user(
            integration_db,
            username="heidi2",
            email=" HEIDI@EXAMPLE.COM ",
            password_hash=PASSWORD_HASH,
        )


async def test_get_by_id_returns_none_for_unknown_uuid(
    integration_db: AsyncSession,
) -> None:
    """Unknown user IDs return None."""
    found = await user_repository.get_by_id(integration_db, uuid4())

    assert found is None


async def test_set_user_active_status_updates_is_active(
    integration_db: AsyncSession,
) -> None:
    """set_user_active_status updates and refreshes the user."""
    user = await user_repository.create_user(
        integration_db,
        username="ivan",
        email="ivan@example.com",
        password_hash=PASSWORD_HASH,
    )

    updated = await user_repository.set_user_active_status(
        integration_db,
        user.id,
        False,
    )

    assert updated is not None
    assert updated.is_active is False
