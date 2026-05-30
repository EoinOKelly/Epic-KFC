"""Async repository functions for one-time public prekeys."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.one_time_prekey import OneTimePreKey
from app.schemas.one_time_prekey import OneTimePreKeyUpload


async def create_batch(
    db: AsyncSession,
    user_id: UUID,
    device_id: int,
    prekeys: list[OneTimePreKeyUpload],
) -> list[OneTimePreKey]:
    """Create public one-time prekeys for a user device."""
    rows = [
        OneTimePreKey(
            user_id=user_id,
            device_id=device_id,
            prekey_id=prekey.prekey_id,
            prekey_public_b64=prekey.prekey_public_b64,
        )
        for prekey in prekeys
    ]
    db.add_all(rows)
    await db.flush()
    for row in rows:
        await db.refresh(row)
    return rows


async def get_unused_for_device(
    db: AsyncSession,
    user_id: UUID,
    device_id: int,
    *,
    for_update: bool = False,
) -> OneTimePreKey | None:
    """Return one unused public prekey for a user device."""
    statement = (
        select(OneTimePreKey)
        .where(
            OneTimePreKey.user_id == user_id,
            OneTimePreKey.device_id == device_id,
            OneTimePreKey.used_at.is_(None),
        )
        .order_by(OneTimePreKey.prekey_id)
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update(skip_locked=True)

    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_by_user_device_prekey_id(
    db: AsyncSession,
    user_id: UUID,
    device_id: int,
    prekey_id: int,
) -> OneTimePreKey | None:
    """Return a one-time prekey by its public logical prekey ID."""
    result = await db.execute(
        select(OneTimePreKey).where(
            OneTimePreKey.user_id == user_id,
            OneTimePreKey.device_id == device_id,
            OneTimePreKey.prekey_id == prekey_id,
        )
    )
    return result.scalar_one_or_none()


async def mark_used(
    db: AsyncSession,
    prekey: OneTimePreKey,
) -> OneTimePreKey:
    """Mark a public one-time prekey as used."""
    prekey.used_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(prekey)
    return prekey


async def count_unused_for_device(
    db: AsyncSession,
    user_id: UUID,
    device_id: int,
) -> int:
    """Return the number of unused prekeys for a user device."""
    result = await db.execute(
        select(func.count())
        .select_from(OneTimePreKey)
        .where(
            OneTimePreKey.user_id == user_id,
            OneTimePreKey.device_id == device_id,
            OneTimePreKey.used_at.is_(None),
        )
    )
    return int(result.scalar_one())
