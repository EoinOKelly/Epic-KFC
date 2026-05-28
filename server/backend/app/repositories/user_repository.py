"""Async repository functions for user accounts."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Return a user by primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Return a user by normalized email address."""
    normalized_email = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == normalized_email))
    return result.scalar_one_or_none()


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    """Return a user by exact-case username."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_by_username_or_email(db: AsyncSession, value: str) -> User | None:
    """Return a user matching exact username or normalized email."""
    normalized_email = _normalize_email(value)
    result = await db.execute(
        select(User).where(
            or_(
                User.username == value,
                User.email == normalized_email,
            )
        )
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password_hash: str,
    role: str = "user",
) -> User:
    """Create a user with an already-hashed password."""
    user = User(
        username=username,
        email=_normalize_email(email),
        password_hash=password_hash,
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def username_exists(db: AsyncSession, username: str) -> bool:
    """Return whether a username already exists."""
    result = await db.execute(select(User.id).where(User.username == username))
    return result.scalar_one_or_none() is not None


async def email_exists(db: AsyncSession, email: str) -> bool:
    """Return whether a normalized email already exists."""
    normalized_email = _normalize_email(email)
    result = await db.execute(select(User.id).where(User.email == normalized_email))
    return result.scalar_one_or_none() is not None


async def set_user_active_status(
    db: AsyncSession,
    user_id: UUID,
    is_active: bool,
) -> User | None:
    """Set a user's active status."""
    user = await get_by_id(db, user_id)
    if user is None:
        return None

    user.is_active = is_active
    await db.flush()
    await db.refresh(user)
    return user


def _normalize_email(email: str) -> str:
    """Normalize email for consistent storage and lookup."""
    return email.strip().lower()
