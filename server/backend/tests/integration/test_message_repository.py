"""Integration tests for opaque message repository functions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.repositories import message_repository, user_repository
from app.schemas.common import PaginationParams
from tests.fixtures.wire_payloads import ALT_WIRE_PAYLOAD, WIRE_PAYLOAD


pytestmark = pytest.mark.asyncio

PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"


async def test_create_message_stores_opaque_wire_payload_unchanged(
    integration_db: AsyncSession,
) -> None:
    """create_message stores the exact serialized relay payload string."""
    sender = await _create_user(integration_db, "alice")
    recipient = await _create_user(integration_db, "bob")

    message = await _create_message(integration_db, sender.id, recipient.id)

    assert message.wire_payload_json == WIRE_PAYLOAD


async def test_exact_wire_payload_string_is_preserved(
    integration_db: AsyncSession,
) -> None:
    """Whitespace and formatting in the submitted payload are preserved."""
    sender = await _create_user(integration_db, "carol")
    recipient = await _create_user(integration_db, "dave")

    message = await message_repository.create_message(
        integration_db,
        sender_user_id=sender.id,
        sender_device_id=1,
        recipient_user_id=recipient.id,
        recipient_device_id=1,
        wire_payload_json=ALT_WIRE_PAYLOAD,
    )

    assert message.wire_payload_json == ALT_WIRE_PAYLOAD


async def test_message_model_has_no_plaintext_content_or_body_field() -> None:
    """The message table must not expose plaintext content columns."""
    column_names = set(Message.__table__.columns.keys())

    assert "wire_payload_json" in column_names
    assert "content" not in column_names
    assert "body" not in column_names
    assert "plaintext" not in column_names
    assert "text" not in column_names


async def test_list_received_returns_only_visible_recipient_messages(
    integration_db: AsyncSession,
) -> None:
    """Received list returns only messages visible to that recipient."""
    sender = await _create_user(integration_db, "erin")
    recipient = await _create_user(integration_db, "frank")
    other = await _create_user(integration_db, "grace")
    visible = await _create_message(integration_db, sender.id, recipient.id)
    await _create_message(integration_db, sender.id, other.id)

    received = await message_repository.list_received(
        integration_db,
        recipient.id,
        PaginationParams(),
    )

    assert [message.id for message in received] == [visible.id]


async def test_list_sent_returns_only_visible_sender_messages(
    integration_db: AsyncSession,
) -> None:
    """Sent list returns only messages visible to that sender."""
    sender = await _create_user(integration_db, "heidi")
    recipient = await _create_user(integration_db, "ivan")
    other = await _create_user(integration_db, "judy")
    visible = await _create_message(integration_db, sender.id, recipient.id)
    await _create_message(integration_db, other.id, recipient.id)

    sent = await message_repository.list_sent(
        integration_db,
        sender.id,
        PaginationParams(),
    )

    assert [message.id for message in sent] == [visible.id]


async def test_sender_deleted_at_hides_from_sent_list(
    integration_db: AsyncSession,
) -> None:
    """Sender deletion hides a message from sent list."""
    sender = await _create_user(integration_db, "kate")
    recipient = await _create_user(integration_db, "laura")
    message = await _create_message(integration_db, sender.id, recipient.id)
    await message_repository.mark_sender_deleted(integration_db, message.id, sender.id)

    sent = await message_repository.list_sent(
        integration_db,
        sender.id,
        PaginationParams(),
    )

    assert sent == []


async def test_recipient_deleted_at_hides_from_received_list(
    integration_db: AsyncSession,
) -> None:
    """Recipient deletion hides a message from received list."""
    sender = await _create_user(integration_db, "mallory")
    recipient = await _create_user(integration_db, "nancy")
    message = await _create_message(integration_db, sender.id, recipient.id)
    await message_repository.mark_recipient_deleted(
        integration_db,
        message.id,
        recipient.id,
    )

    received = await message_repository.list_received(
        integration_db,
        recipient.id,
        PaginationParams(),
    )

    assert received == []


async def test_access_revoked_at_hides_from_recipient_list_and_fetch(
    integration_db: AsyncSession,
) -> None:
    """Revocation hides a message from recipient list and accessible lookup."""
    sender = await _create_user(integration_db, "olivia")
    recipient = await _create_user(integration_db, "peggy")
    message = await _create_message(integration_db, sender.id, recipient.id)
    await message_repository.revoke_recipient_access(
        integration_db,
        message.id,
        sender.id,
    )

    received = await message_repository.list_received(
        integration_db,
        recipient.id,
        PaginationParams(),
    )
    fetched = await message_repository.get_accessible_by_id(
        integration_db,
        message.id,
        recipient.id,
    )

    assert received == []
    assert fetched is None


async def test_deleted_at_hides_globally(integration_db: AsyncSession) -> None:
    """Global deletion hides a message from sent, received, and fetch."""
    sender = await _create_user(integration_db, "quinn")
    recipient = await _create_user(integration_db, "ruth")
    message = await _create_message(integration_db, sender.id, recipient.id)
    message.deleted_at = datetime.now(UTC)
    await integration_db.flush()

    sent = await message_repository.list_sent(
        integration_db,
        sender.id,
        PaginationParams(),
    )
    received = await message_repository.list_received(
        integration_db,
        recipient.id,
        PaginationParams(),
    )
    sender_fetch = await message_repository.get_accessible_by_id(
        integration_db,
        message.id,
        sender.id,
    )
    recipient_fetch = await message_repository.get_accessible_by_id(
        integration_db,
        message.id,
        recipient.id,
    )

    assert sent == []
    assert received == []
    assert sender_fetch is None
    assert recipient_fetch is None


async def test_revoke_recipient_access_sets_access_revoked_at(
    integration_db: AsyncSession,
) -> None:
    """revoke_recipient_access sets access_revoked_at."""
    sender = await _create_user(integration_db, "sam")
    recipient = await _create_user(integration_db, "trent")
    message = await _create_message(integration_db, sender.id, recipient.id)

    revoked = await message_repository.revoke_recipient_access(
        integration_db,
        message.id,
        sender.id,
    )

    assert revoked is not None
    assert revoked.access_revoked_at is not None


async def test_sender_delete_sets_sender_deleted_at(
    integration_db: AsyncSession,
) -> None:
    """mark_sender_deleted sets sender_deleted_at."""
    sender = await _create_user(integration_db, "ursula")
    recipient = await _create_user(integration_db, "victor")
    message = await _create_message(integration_db, sender.id, recipient.id)

    deleted = await message_repository.mark_sender_deleted(
        integration_db,
        message.id,
        sender.id,
    )

    assert deleted is not None
    assert deleted.sender_deleted_at is not None


async def test_recipient_delete_sets_recipient_deleted_at(
    integration_db: AsyncSession,
) -> None:
    """mark_recipient_deleted sets recipient_deleted_at."""
    sender = await _create_user(integration_db, "wendy")
    recipient = await _create_user(integration_db, "xavier")
    message = await _create_message(integration_db, sender.id, recipient.id)

    deleted = await message_repository.mark_recipient_deleted(
        integration_db,
        message.id,
        recipient.id,
    )

    assert deleted is not None
    assert deleted.recipient_deleted_at is not None


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a user for message repository tests."""
    return await user_repository.create_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password_hash=PASSWORD_HASH,
    )


async def _create_message(
    integration_db: AsyncSession,
    sender_user_id,
    recipient_user_id,
) -> Message:
    """Create a default opaque relay message."""
    return await message_repository.create_message(
        integration_db,
        sender_user_id=sender_user_id,
        sender_device_id=1,
        recipient_user_id=recipient_user_id,
        recipient_device_id=1,
        wire_payload_json=WIRE_PAYLOAD,
    )
