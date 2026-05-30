"""Message relay service workflows and access-control checks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User
from app.repositories import (
    device_key_repository,
    message_repository,
    one_time_prekey_repository,
    user_repository,
)
from app.schemas.message import MessageCreateRequest


class MessageAccessDeniedError(Exception):
    """Raised when a user is not allowed to perform a message operation."""


class MessageNotFoundError(Exception):
    """Raised when a message is missing or safely hidden from the user."""


class RecipientNotFoundError(Exception):
    """Raised when the requested recipient does not exist or is inactive."""


class InvalidDeviceError(Exception):
    """Raised when sender or recipient device validation fails."""


class InvalidPreKeyError(Exception):
    """Raised when consumed one-time prekey metadata is inconsistent."""


async def send_message(
    db: AsyncSession,
    current_user: User,
    request_data: MessageCreateRequest,
) -> Message:
    """Create an opaque relay message after validating message access inputs."""
    try:
        await _validate_send_inputs(db, current_user, request_data)
        message = await message_repository.create_message(
            db,
            sender_user_id=current_user.id,
            sender_device_id=request_data.sender_device_id,
            recipient_user_id=request_data.recipient_user_id,
            recipient_device_id=request_data.recipient_device_id,
            wire_payload_json=request_data.wire_payload_json,
            consumed_one_time_prekey_id=request_data.consumed_one_time_prekey_id,
        )
        await db.commit()
        await db.refresh(message)
        return message
    except Exception:
        await db.rollback()
        raise


async def list_received_messages(db: AsyncSession, current_user: User, pagination):
    """Return messages visible to the current user as recipient."""
    return await message_repository.list_received(db, current_user.id, pagination)


async def list_sent_messages(db: AsyncSession, current_user: User, pagination):
    """Return messages visible to the current user as sender."""
    return await message_repository.list_sent(db, current_user.id, pagination)


async def get_message_for_user(
    db: AsyncSession,
    current_user: User,
    message_id: UUID,
) -> Message:
    """Return a message only when visible to the current user."""
    message = await message_repository.get_accessible_by_id(
        db,
        message_id,
        current_user.id,
    )
    if message is None:
        raise MessageNotFoundError("Message not found.")
    return message


async def delete_message_for_user(
    db: AsyncSession,
    current_user: User,
    message_id: UUID,
) -> Message:
    """Hide a message from the sender or recipient without hard deletion."""
    try:
        message = await message_repository.get_by_id(db, message_id)
        if message is None or message.deleted_at is not None:
            raise MessageNotFoundError("Message not found.")

        if message.sender_user_id == current_user.id:
            deleted = await message_repository.mark_sender_deleted(
                db,
                message_id,
                current_user.id,
            )
        elif message.recipient_user_id == current_user.id:
            deleted = await message_repository.mark_recipient_deleted(
                db,
                message_id,
                current_user.id,
            )
        else:
            raise MessageAccessDeniedError("Message access denied.")

        if deleted is None:
            raise MessageAccessDeniedError("Message access denied.")

        await db.commit()
        await db.refresh(deleted)
        return deleted
    except Exception:
        await db.rollback()
        raise


async def revoke_message_access(
    db: AsyncSession,
    current_user: User,
    message_id: UUID,
) -> Message:
    """Revoke recipient access to a sender-owned message."""
    try:
        message = await message_repository.get_by_id(db, message_id)
        if message is None or message.deleted_at is not None:
            raise MessageNotFoundError("Message not found.")
        if message.sender_user_id != current_user.id:
            raise MessageAccessDeniedError("Message access denied.")

        revoked = await message_repository.revoke_recipient_access(
            db,
            message_id,
            current_user.id,
        )
        if revoked is None:
            raise MessageAccessDeniedError("Message access denied.")

        await db.commit()
        await db.refresh(revoked)
        return revoked
    except Exception:
        await db.rollback()
        raise


async def forward_message(
    db: AsyncSession,
    current_user: User,
    message_id: UUID,
    request_data: MessageCreateRequest,
) -> Message:
    """Create a new opaque message after validating access to the original."""
    try:
        original = await message_repository.get_accessible_by_id(
            db,
            message_id,
            current_user.id,
        )
        if original is None:
            raise MessageNotFoundError("Message not found.")

        await _validate_send_inputs(db, current_user, request_data)
        forwarded = await message_repository.create_forwarded_message(
            db,
            original_message_id=original.id,
            sender_user_id=current_user.id,
            sender_device_id=request_data.sender_device_id,
            recipient_user_id=request_data.recipient_user_id,
            recipient_device_id=request_data.recipient_device_id,
            wire_payload_json=request_data.wire_payload_json,
            consumed_one_time_prekey_id=request_data.consumed_one_time_prekey_id,
        )
        await db.commit()
        await db.refresh(forwarded)
        return forwarded
    except Exception:
        await db.rollback()
        raise


async def _validate_send_inputs(
    db: AsyncSession,
    current_user: User,
    request_data: MessageCreateRequest,
) -> None:
    """Validate sender, recipient, and device access for direct messages."""
    recipient = await user_repository.get_by_id(db, request_data.recipient_user_id)
    if recipient is None or not recipient.is_active:
        raise RecipientNotFoundError("Recipient not found.")

    sender_device = await device_key_repository.get_active_by_user_and_device(
        db,
        current_user.id,
        request_data.sender_device_id,
    )
    if sender_device is None:
        raise InvalidDeviceError("Invalid sender device.")

    recipient_device = await device_key_repository.get_active_by_user_and_device(
        db,
        recipient.id,
        request_data.recipient_device_id,
    )
    if recipient_device is None:
        raise InvalidDeviceError("Invalid recipient device.")

    await _validate_consumed_one_time_prekey(db, request_data)


async def _validate_consumed_one_time_prekey(
    db: AsyncSession,
    request_data: MessageCreateRequest,
) -> None:
    """Validate optional consumed prekey metadata against relay DB state.

    consumed_one_time_prekey_id is the public/logical prekey_id returned by the
    prekey-bundle endpoint, not the database row UUID. Bundle fetch marks that
    row used, so message send accepts only a matching recipient/device prekey
    with used_at already set. The backend cannot prove the encrypted payload
    cryptographically used the prekey; that remains client crypto's job.
    """
    if request_data.consumed_one_time_prekey_id is None:
        return

    prekey = await one_time_prekey_repository.get_by_user_device_prekey_id(
        db,
        request_data.recipient_user_id,
        request_data.recipient_device_id,
        request_data.consumed_one_time_prekey_id,
    )
    if prekey is None or prekey.used_at is None:
        raise InvalidPreKeyError("Invalid consumed one-time prekey.")
