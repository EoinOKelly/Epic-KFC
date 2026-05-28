"""Integration tests for device key and one-time prekey repositories."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    device_key_repository,
    one_time_prekey_repository,
    user_repository,
)
from app.schemas.device_key import DeviceKeyUploadRequest
from app.schemas.one_time_prekey import OneTimePreKeyUpload


pytestmark = pytest.mark.asyncio

PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"
UPDATED_KEY_B64 = "dXBkYXRlZC1rZXktbWF0ZXJpYWw="


async def test_create_device_key(integration_db: AsyncSession) -> None:
    """Device keys can be created for a user/device pair."""
    user = await _create_user(integration_db, "alice")

    device_key = await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        _device_request(device_id=1),
    )

    assert device_key.user_id == user.id
    assert device_key.device_id == 1
    assert device_key.identity_key_public_b64 == KEY_B64
    assert device_key.signed_prekey_created_at is not None
    assert device_key.is_active is True


async def test_update_existing_device_key(integration_db: AsyncSession) -> None:
    """Existing device key rows are updated in place."""
    user = await _create_user(integration_db, "bob")
    original = await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        _device_request(device_id=1, registration_id=101),
    )
    updated = await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        _device_request(
            device_id=1,
            registration_id=202,
            identity_key_public_b64=UPDATED_KEY_B64,
        ),
    )

    assert updated.id == original.id
    assert updated.registration_id == 202
    assert updated.identity_key_public_b64 == UPDATED_KEY_B64
    assert updated.is_active is True
    assert updated.revoked_at is None


async def test_fetch_active_device_key(integration_db: AsyncSession) -> None:
    """Active device keys can be fetched by user/device pair."""
    user = await _create_user(integration_db, "carol")
    created = await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        _device_request(device_id=2),
    )

    found = await device_key_repository.get_active_by_user_and_device(
        integration_db,
        user.id,
        2,
    )

    assert found is not None
    assert found.id == created.id


async def test_revoked_device_key_is_not_active(
    integration_db: AsyncSession,
) -> None:
    """Revoked device keys are excluded from active lookups."""
    user = await _create_user(integration_db, "dave")
    await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        _device_request(device_id=3),
    )

    revoked = await device_key_repository.revoke_device_key(integration_db, user.id, 3)
    active = await device_key_repository.get_active_by_user_and_device(
        integration_db,
        user.id,
        3,
    )

    assert revoked is not None
    assert revoked.revoked_at is not None
    assert revoked.is_active is False
    assert active is None


async def test_list_active_devices_for_user(integration_db: AsyncSession) -> None:
    """Only active devices are listed for a user."""
    user = await _create_user(integration_db, "erin")
    await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        _device_request(device_id=1),
    )
    await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        _device_request(device_id=2),
    )
    await device_key_repository.revoke_device_key(integration_db, user.id, 2)

    devices = await device_key_repository.list_active_devices_for_user(
        integration_db,
        user.id,
    )

    assert [device.device_id for device in devices] == [1]


async def test_upload_one_time_prekey_batch(integration_db: AsyncSession) -> None:
    """One-time public prekeys can be inserted in a batch."""
    user = await _create_user(integration_db, "frank")

    prekeys = await one_time_prekey_repository.create_batch(
        integration_db,
        user.id,
        1,
        [_prekey(1, 10), _prekey(1, 11)],
    )

    assert len(prekeys) == 2
    assert {prekey.prekey_id for prekey in prekeys} == {10, 11}
    assert all(prekey.user_id == user.id for prekey in prekeys)


async def test_duplicate_one_time_prekey_ids_raise_integrity_error(
    integration_db: AsyncSession,
) -> None:
    """Duplicate prekey IDs for the same user/device fail at the DB layer."""
    user = await _create_user(integration_db, "grace")
    await one_time_prekey_repository.create_batch(
        integration_db,
        user.id,
        1,
        [_prekey(1, 20)],
    )

    with pytest.raises(IntegrityError):
        await one_time_prekey_repository.create_batch(
            integration_db,
            user.id,
            1,
            [_prekey(1, 20)],
        )


async def test_unused_prekey_fetch_ignores_used_prekeys(
    integration_db: AsyncSession,
) -> None:
    """Used prekeys are ignored by unused lookup."""
    user = await _create_user(integration_db, "heidi")
    prekeys = await one_time_prekey_repository.create_batch(
        integration_db,
        user.id,
        1,
        [_prekey(1, 30), _prekey(1, 31)],
    )
    await one_time_prekey_repository.mark_used(integration_db, prekeys[0])

    unused = await one_time_prekey_repository.get_unused_for_device(
        integration_db,
        user.id,
        1,
    )

    assert unused is not None
    assert unused.prekey_id == 31


async def test_mark_used_sets_used_at(integration_db: AsyncSession) -> None:
    """mark_used sets the used_at timestamp."""
    user = await _create_user(integration_db, "ivan")
    prekeys = await one_time_prekey_repository.create_batch(
        integration_db,
        user.id,
        1,
        [_prekey(1, 40)],
    )

    used = await one_time_prekey_repository.mark_used(integration_db, prekeys[0])

    assert used.used_at is not None


async def test_count_unused_prekeys(integration_db: AsyncSession) -> None:
    """Unused prekey counts exclude used prekeys."""
    user = await _create_user(integration_db, "judy")
    prekeys = await one_time_prekey_repository.create_batch(
        integration_db,
        user.id,
        1,
        [_prekey(1, 50), _prekey(1, 51), _prekey(1, 52)],
    )
    await one_time_prekey_repository.mark_used(integration_db, prekeys[0])

    count = await one_time_prekey_repository.count_unused_for_device(
        integration_db,
        user.id,
        1,
    )

    assert count == 2


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a user for key repository tests."""
    return await user_repository.create_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password_hash=PASSWORD_HASH,
    )


def _device_request(
    *,
    device_id: int,
    registration_id: int = 1001,
    identity_key_public_b64: str = KEY_B64,
) -> DeviceKeyUploadRequest:
    """Build a valid device key upload request."""
    return DeviceKeyUploadRequest(
        device_id=device_id,
        registration_id=registration_id,
        identity_key_public_b64=identity_key_public_b64,
        identity_signing_public_b64=KEY_B64,
        signed_prekey_id=2001,
        signed_prekey_public_b64=KEY_B64,
        signed_prekey_signature_b64=KEY_B64,
    )


def _prekey(device_id: int, prekey_id: int) -> OneTimePreKeyUpload:
    """Build a valid one-time prekey upload item."""
    return OneTimePreKeyUpload(
        device_id=device_id,
        prekey_id=prekey_id,
        prekey_public_b64=KEY_B64,
    )
