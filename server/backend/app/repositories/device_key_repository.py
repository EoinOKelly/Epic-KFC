"""Async repository functions for public device key material."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_key import DeviceKey
from app.schemas.device_key import DeviceKeyUploadRequest


async def get_by_user_and_device(
    db: AsyncSession,
    user_id: UUID,
    device_id: int,
) -> DeviceKey | None:
    """Return a device key row for a user/device pair."""
    result = await db.execute(
        select(DeviceKey).where(
            DeviceKey.user_id == user_id,
            DeviceKey.device_id == device_id,
        )
    )
    return result.scalar_one_or_none()


async def get_active_by_user_and_device(
    db: AsyncSession,
    user_id: UUID,
    device_id: int,
) -> DeviceKey | None:
    """Return an active, non-revoked device key row for a user/device pair."""
    result = await db.execute(
        select(DeviceKey).where(
            DeviceKey.user_id == user_id,
            DeviceKey.device_id == device_id,
            DeviceKey.is_active.is_(True),
            DeviceKey.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def create_or_update_device_key(
    db: AsyncSession,
    user_id: UUID,
    data: DeviceKeyUploadRequest,
) -> DeviceKey:
    """Create or update public device key material for a user device."""
    device_key = await get_by_user_and_device(db, user_id, data.device_id)
    signed_prekey_created_at = datetime.now(UTC)

    if device_key is None:
        device_key = DeviceKey(
            user_id=user_id,
            device_id=data.device_id,
            registration_id=data.registration_id,
            identity_key_public_b64=data.identity_key_public_b64,
            identity_signing_public_b64=data.identity_signing_public_b64,
            signed_prekey_id=data.signed_prekey_id,
            signed_prekey_public_b64=data.signed_prekey_public_b64,
            signed_prekey_signature_b64=data.signed_prekey_signature_b64,
            signed_prekey_created_at=signed_prekey_created_at,
        )
        db.add(device_key)
    else:
        device_key.registration_id = data.registration_id
        device_key.identity_key_public_b64 = data.identity_key_public_b64
        device_key.identity_signing_public_b64 = data.identity_signing_public_b64
        device_key.signed_prekey_id = data.signed_prekey_id
        device_key.signed_prekey_public_b64 = data.signed_prekey_public_b64
        device_key.signed_prekey_signature_b64 = data.signed_prekey_signature_b64
        device_key.signed_prekey_created_at = signed_prekey_created_at
        device_key.is_active = True
        device_key.revoked_at = None

    await db.flush()
    await db.refresh(device_key)
    return device_key


async def revoke_device_key(
    db: AsyncSession,
    user_id: UUID,
    device_id: int,
) -> DeviceKey | None:
    """Revoke a user's public device key row."""
    device_key = await get_by_user_and_device(db, user_id, device_id)
    if device_key is None:
        return None

    device_key.is_active = False
    device_key.revoked_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(device_key)
    return device_key


async def list_active_devices_for_user(
    db: AsyncSession,
    user_id: UUID,
) -> list[DeviceKey]:
    """Return active, non-revoked device keys for a user."""
    result = await db.execute(
        select(DeviceKey)
        .where(
            DeviceKey.user_id == user_id,
            DeviceKey.is_active.is_(True),
            DeviceKey.revoked_at.is_(None),
        )
        .order_by(DeviceKey.device_id)
    )
    return list(result.scalars().all())
