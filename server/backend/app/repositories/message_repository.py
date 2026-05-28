"""Async repository functions for opaque relay messages."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


async def create_message(
    db: AsyncSession,
    sender_user_id: UUID,
    sender_device_id: int,
    recipient_user_id: UUID,
    recipient_device_id: int,
    wire_payload_json: str,
    consumed_one_time_prekey_id: int | None = None,
) -> Message:
    """Create an opaque relay message without committing the transaction."""
    message = Message(
        sender_user_id=sender_user_id,
        sender_device_id=sender_device_id,
        recipient_user_id=recipient_user_id,
        recipient_device_id=recipient_device_id,
        wire_payload_json=wire_payload_json,
        consumed_one_time_prekey_id=consumed_one_time_prekey_id,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return message


async def get_by_id(db: AsyncSession, message_id: UUID) -> Message | None:
    """Return a message by primary key without applying access control."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    return result.scalar_one_or_none()


async def get_accessible_by_id(
    db: AsyncSession,
    message_id: UUID,
    user_id: UUID,
) -> Message | None:
    """Return a message only when visible to the user as sender or recipient."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            _sender_visible(user_id) | _recipient_visible(user_id),
        )
    )
    return result.scalar_one_or_none()


async def list_received(db: AsyncSession, user_id: UUID, pagination) -> list[Message]:
    """Return messages visible to a recipient, newest first."""
    result = await db.execute(
        select(Message)
        .where(
            Message.recipient_user_id == user_id,
            Message.access_revoked_at.is_(None),
            Message.recipient_deleted_at.is_(None),
            Message.deleted_at.is_(None),
        )
        .order_by(desc(Message.created_at), desc(Message.id))
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


async def list_sent(db: AsyncSession, user_id: UUID, pagination) -> list[Message]:
    """Return messages visible to a sender, newest first."""
    result = await db.execute(
        select(Message)
        .where(
            Message.sender_user_id == user_id,
            Message.sender_deleted_at.is_(None),
            Message.deleted_at.is_(None),
        )
        .order_by(desc(Message.created_at), desc(Message.id))
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


async def mark_sender_deleted(
    db: AsyncSession,
    message_id: UUID,
    sender_user_id: UUID,
) -> Message | None:
    """Hide a message from the sender without hard-deleting ciphertext."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.sender_user_id == sender_user_id,
            Message.sender_deleted_at.is_(None),
            Message.deleted_at.is_(None),
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None

    message.sender_deleted_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(message)
    return message


async def mark_recipient_deleted(
    db: AsyncSession,
    message_id: UUID,
    recipient_user_id: UUID,
) -> Message | None:
    """Hide a message from the recipient without hard-deleting ciphertext."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.recipient_user_id == recipient_user_id,
            Message.recipient_deleted_at.is_(None),
            Message.access_revoked_at.is_(None),
            Message.deleted_at.is_(None),
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None

    message.recipient_deleted_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(message)
    return message


async def revoke_recipient_access(
    db: AsyncSession,
    message_id: UUID,
    sender_user_id: UUID,
) -> Message | None:
    """Revoke recipient access to a sender-owned message."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.sender_user_id == sender_user_id,
            Message.deleted_at.is_(None),
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None

    message.access_revoked_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(message)
    return message


async def create_forwarded_message(
    db: AsyncSession,
    original_message_id: UUID,
    sender_user_id: UUID,
    sender_device_id: int,
    recipient_user_id: UUID,
    recipient_device_id: int,
    wire_payload_json: str,
) -> Message:
    """Create a forwarded message as a new opaque relay message row."""
    _ = original_message_id
    return await create_message(
        db,
        sender_user_id=sender_user_id,
        sender_device_id=sender_device_id,
        recipient_user_id=recipient_user_id,
        recipient_device_id=recipient_device_id,
        wire_payload_json=wire_payload_json,
    )


def _sender_visible(user_id: UUID):
    """Build the sender-visible predicate for a user."""
    return and_(
        Message.sender_user_id == user_id,
        Message.sender_deleted_at.is_(None),
        Message.deleted_at.is_(None),
    )


def _recipient_visible(user_id: UUID):
    """Build the recipient-visible predicate for a user."""
    return and_(
        Message.recipient_user_id == user_id,
        Message.recipient_deleted_at.is_(None),
        Message.access_revoked_at.is_(None),
        Message.deleted_at.is_(None),
    )
