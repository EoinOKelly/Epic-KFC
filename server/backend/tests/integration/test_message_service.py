"""Integration tests for message service access-control workflows."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    device_key_repository,
    one_time_prekey_repository,
    user_repository,
)
from app.schemas.common import PaginationParams
from app.schemas.device_key import DeviceKeyUploadRequest
from app.schemas.message import MessageCreateRequest
from app.schemas.one_time_prekey import OneTimePreKeyUpload
from app.services import message_service
from app.services.message_service import (
    InvalidDeviceError,
    InvalidPreKeyError,
    MessageAccessDeniedError,
    MessageNotFoundError,
    RecipientNotFoundError,
)
from tests.fixtures.wire_payloads import NEW_WIRE_PAYLOAD, WIRE_PAYLOAD


pytestmark = pytest.mark.asyncio

PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$cGFzc3dvcmQ"
KEY_B64 = "a2V5LW1hdGVyaWFs"


async def test_send_message_uses_current_user_id_as_sender(
    integration_db: AsyncSession,
) -> None:
    """send_message should set sender_user_id from the authenticated user."""
    sender, recipient = await _create_ready_users(integration_db, "alice", "bob")

    message = await message_service.send_message(
        integration_db,
        sender,
        _message_request(recipient.id),
    )

    assert message.sender_user_id == sender.id
    assert message.recipient_user_id == recipient.id


async def test_sender_spoofing_is_impossible_from_request_schema(
    integration_db: AsyncSession,
) -> None:
    """MessageCreateRequest rejects a sender_user_id field."""
    sender, recipient = await _create_ready_users(integration_db, "carol", "dave")

    with pytest.raises(ValidationError):
        MessageCreateRequest(
            sender_user_id=sender.id,
            sender_device_id=1,
            recipient_user_id=recipient.id,
            recipient_device_id=1,
            wire_payload_json=WIRE_PAYLOAD,
        )


async def test_send_message_rejects_missing_recipient(
    integration_db: AsyncSession,
) -> None:
    """Missing recipients should fail before message storage."""
    sender = await _create_user(integration_db, "erin")
    await _create_device_key(integration_db, sender, 1)
    await integration_db.commit()

    with pytest.raises(RecipientNotFoundError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(uuid4()),
        )


async def test_send_message_rejects_inactive_recipient(
    integration_db: AsyncSession,
) -> None:
    """Inactive recipients should fail before message storage."""
    sender, recipient = await _create_ready_users(integration_db, "frank", "grace")
    await user_repository.set_user_active_status(integration_db, recipient.id, False)
    await integration_db.commit()

    with pytest.raises(RecipientNotFoundError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id),
        )


async def test_send_message_rejects_sender_device_not_owned_by_current_user(
    integration_db: AsyncSession,
) -> None:
    """Sender device must belong to current user."""
    sender = await _create_user(integration_db, "heidi")
    recipient = await _create_user(integration_db, "ivan")
    await _create_device_key(integration_db, recipient, 1)
    await _create_device_key(integration_db, recipient, 2)
    await integration_db.commit()

    with pytest.raises(InvalidDeviceError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id, sender_device_id=2),
        )


async def test_send_message_rejects_inactive_sender_device(
    integration_db: AsyncSession,
) -> None:
    """Sender device must be active."""
    sender, recipient = await _create_ready_users(integration_db, "judy", "kate")
    await device_key_repository.revoke_device_key(integration_db, sender.id, 1)
    await integration_db.commit()

    with pytest.raises(InvalidDeviceError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id),
        )


async def test_send_message_rejects_recipient_device_not_owned_by_recipient(
    integration_db: AsyncSession,
) -> None:
    """Recipient device must belong to the recipient."""
    sender = await _create_user(integration_db, "laura")
    recipient = await _create_user(integration_db, "mallory")
    other = await _create_user(integration_db, "nancy")
    await _create_device_key(integration_db, sender, 1)
    await _create_device_key(integration_db, other, 2)
    await integration_db.commit()

    with pytest.raises(InvalidDeviceError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id, recipient_device_id=2),
        )


async def test_send_message_rejects_inactive_recipient_device(
    integration_db: AsyncSession,
) -> None:
    """Recipient device must be active."""
    sender, recipient = await _create_ready_users(integration_db, "olivia", "peggy")
    await device_key_repository.revoke_device_key(integration_db, recipient.id, 1)
    await integration_db.commit()

    with pytest.raises(InvalidDeviceError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id),
        )


async def test_send_message_stores_direct_message(
    integration_db: AsyncSession,
) -> None:
    """Messages sent through the service are direct 1:1 messages only."""
    sender, recipient = await _create_ready_users(integration_db, "quinn", "ruth")

    message = await message_service.send_message(
        integration_db,
        sender,
        _message_request(recipient.id),
    )

    assert message.sender_user_id == sender.id
    assert message.recipient_user_id == recipient.id


async def test_send_with_valid_consumed_one_time_prekey_id_succeeds(
    integration_db: AsyncSession,
) -> None:
    """Send accepts the public prekey_id consumed by the bundle endpoint."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "quinn-prekey",
        "ruth-prekey",
    )
    await _create_used_prekey(integration_db, recipient, 1, 701)

    message = await message_service.send_message(
        integration_db,
        sender,
        _message_request(recipient.id, consumed_one_time_prekey_id=701),
    )

    assert message.consumed_one_time_prekey_id == 701


async def test_send_with_nonexistent_consumed_one_time_prekey_id_fails(
    integration_db: AsyncSession,
) -> None:
    """Send rejects prekey IDs that do not exist for the recipient device."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "quinn-missing-prekey",
        "ruth-missing-prekey",
    )

    with pytest.raises(InvalidPreKeyError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id, consumed_one_time_prekey_id=999),
        )


async def test_send_with_unused_consumed_one_time_prekey_id_fails(
    integration_db: AsyncSession,
) -> None:
    """Send only accepts prekeys already marked used by bundle fetch."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "quinn-unused-prekey",
        "ruth-unused-prekey",
    )
    await _create_unused_prekey(integration_db, recipient, 1, 700)

    with pytest.raises(InvalidPreKeyError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id, consumed_one_time_prekey_id=700),
        )


async def test_send_with_prekey_belonging_to_another_user_fails(
    integration_db: AsyncSession,
) -> None:
    """Consumed prekeys must belong to the message recipient."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "quinn-other-user-prekey",
        "ruth-other-user-prekey",
    )
    other = await _create_user(integration_db, "other-user-prekey")
    await _create_device_key(integration_db, other, 1)
    await integration_db.commit()
    await _create_used_prekey(integration_db, other, 1, 702)

    with pytest.raises(InvalidPreKeyError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id, consumed_one_time_prekey_id=702),
        )


async def test_send_with_prekey_belonging_to_another_device_fails(
    integration_db: AsyncSession,
) -> None:
    """Consumed prekeys must belong to the target recipient device."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "quinn-other-device-prekey",
        "ruth-other-device-prekey",
    )
    await _create_device_key(integration_db, recipient, 2)
    await integration_db.commit()
    await _create_used_prekey(integration_db, recipient, 2, 703)

    with pytest.raises(InvalidPreKeyError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id, consumed_one_time_prekey_id=703),
        )


async def test_send_with_prekey_belonging_to_sender_fails(
    integration_db: AsyncSession,
) -> None:
    """Sender-owned prekeys cannot satisfy recipient prekey metadata."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "quinn-sender-prekey",
        "ruth-sender-prekey",
    )
    await _create_used_prekey(integration_db, sender, 1, 704)

    with pytest.raises(InvalidPreKeyError):
        await message_service.send_message(
            integration_db,
            sender,
            _message_request(recipient.id, consumed_one_time_prekey_id=704),
        )


async def test_send_without_consumed_one_time_prekey_id_still_works(
    integration_db: AsyncSession,
) -> None:
    """The consumed prekey field remains optional for normal direct messages."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "quinn-no-prekey",
        "ruth-no-prekey",
    )

    message = await message_service.send_message(
        integration_db,
        sender,
        _message_request(recipient.id),
    )

    assert message.consumed_one_time_prekey_id is None


async def test_sender_can_fetch_sent_message(integration_db: AsyncSession) -> None:
    """Sender can fetch a visible sent message."""
    sender, recipient = await _create_ready_users(integration_db, "sam", "trent")
    message = await _send_default_message(integration_db, sender, recipient)

    fetched = await message_service.get_message_for_user(
        integration_db,
        sender,
        message.id,
    )

    assert fetched.id == message.id


async def test_recipient_can_fetch_received_message(
    integration_db: AsyncSession,
) -> None:
    """Recipient can fetch a visible received message."""
    sender, recipient = await _create_ready_users(integration_db, "ursula", "victor")
    message = await _send_default_message(integration_db, sender, recipient)

    fetched = await message_service.get_message_for_user(
        integration_db,
        recipient,
        message.id,
    )

    assert fetched.id == message.id


async def test_unrelated_user_cannot_fetch_message(
    integration_db: AsyncSession,
) -> None:
    """Unrelated users cannot fetch someone else's message."""
    sender, recipient = await _create_ready_users(integration_db, "wendy", "xavier")
    unrelated = await _create_user(integration_db, "yvonne")
    message = await _send_default_message(integration_db, sender, recipient)

    with pytest.raises(MessageNotFoundError):
        await message_service.get_message_for_user(
            integration_db,
            unrelated,
            message.id,
        )


async def test_recipient_cannot_fetch_or_list_after_revoke(
    integration_db: AsyncSession,
) -> None:
    """Revocation removes recipient fetch and list visibility."""
    sender, recipient = await _create_ready_users(integration_db, "zara", "amy")
    message = await _send_default_message(integration_db, sender, recipient)
    await message_service.revoke_message_access(integration_db, sender, message.id)

    received = await message_service.list_received_messages(
        integration_db,
        recipient,
        PaginationParams(),
    )

    assert received == []
    with pytest.raises(MessageNotFoundError):
        await message_service.get_message_for_user(
            integration_db,
            recipient,
            message.id,
        )


async def test_non_sender_cannot_revoke(integration_db: AsyncSession) -> None:
    """Only the sender can revoke recipient access."""
    sender, recipient = await _create_ready_users(integration_db, "ben", "chloe")
    message = await _send_default_message(integration_db, sender, recipient)

    with pytest.raises(MessageAccessDeniedError):
        await message_service.revoke_message_access(
            integration_db,
            recipient,
            message.id,
        )


async def test_sender_can_revoke(integration_db: AsyncSession) -> None:
    """Sender can revoke recipient access."""
    sender, recipient = await _create_ready_users(integration_db, "dan", "ella")
    message = await _send_default_message(integration_db, sender, recipient)

    revoked = await message_service.revoke_message_access(
        integration_db,
        sender,
        message.id,
    )

    assert revoked.access_revoked_at is not None


async def test_sender_delete_hides_only_from_sender(
    integration_db: AsyncSession,
) -> None:
    """Sender delete should not hide the message from the recipient."""
    sender, recipient = await _create_ready_users(integration_db, "fiona", "george")
    message = await _send_default_message(integration_db, sender, recipient)
    await message_service.delete_message_for_user(integration_db, sender, message.id)

    sent = await message_service.list_sent_messages(
        integration_db,
        sender,
        PaginationParams(),
    )
    recipient_fetch = await message_service.get_message_for_user(
        integration_db,
        recipient,
        message.id,
    )

    assert sent == []
    assert recipient_fetch.id == message.id


async def test_recipient_delete_hides_only_from_recipient(
    integration_db: AsyncSession,
) -> None:
    """Recipient delete should not hide the message from the sender."""
    sender, recipient = await _create_ready_users(integration_db, "harry", "irene")
    message = await _send_default_message(integration_db, sender, recipient)
    await message_service.delete_message_for_user(
        integration_db,
        recipient,
        message.id,
    )

    received = await message_service.list_received_messages(
        integration_db,
        recipient,
        PaginationParams(),
    )
    sender_fetch = await message_service.get_message_for_user(
        integration_db,
        sender,
        message.id,
    )

    assert received == []
    assert sender_fetch.id == message.id


async def test_forwarding_requires_access_to_original(
    integration_db: AsyncSession,
) -> None:
    """Forwarding should fail when current user cannot access the original."""
    sender, recipient = await _create_ready_users(integration_db, "jack", "kelly")
    unrelated = await _create_user(integration_db, "louis")
    await _create_device_key(integration_db, unrelated, 1)
    message = await _send_default_message(integration_db, sender, recipient)

    with pytest.raises(MessageNotFoundError):
        await message_service.forward_message(
            integration_db,
            unrelated,
            message.id,
            _message_request(recipient.id, wire_payload_json=NEW_WIRE_PAYLOAD),
        )


async def test_forwarding_stores_new_opaque_payload(
    integration_db: AsyncSession,
) -> None:
    """Forwarding creates a new message with the new supplied payload."""
    sender, recipient = await _create_ready_users(integration_db, "maya", "noah")
    new_recipient = await _create_user(integration_db, "ophelia")
    await _create_device_key(integration_db, new_recipient, 1)
    original = await _send_default_message(integration_db, sender, recipient)

    forwarded = await message_service.forward_message(
        integration_db,
        sender,
        original.id,
        _message_request(new_recipient.id, wire_payload_json=NEW_WIRE_PAYLOAD),
    )

    assert forwarded.id != original.id
    assert forwarded.wire_payload_json == NEW_WIRE_PAYLOAD
    assert forwarded.wire_payload_json != original.wire_payload_json
    assert "plaintext" not in forwarded.wire_payload_json.lower()


async def test_forwarding_with_valid_consumed_one_time_prekey_id_stores_it(
    integration_db: AsyncSession,
) -> None:
    """Forward behaves like send after access check and stores consumed prekey ID."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "maya-forward-prekey",
        "noah-forward-prekey",
    )
    new_recipient = await _create_user(integration_db, "ophelia-forward-prekey")
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    await _create_used_prekey(integration_db, new_recipient, 1, 801)
    original = await _send_default_message(integration_db, sender, recipient)

    forwarded = await message_service.forward_message(
        integration_db,
        sender,
        original.id,
        _message_request(
            new_recipient.id,
            wire_payload_json=NEW_WIRE_PAYLOAD,
            consumed_one_time_prekey_id=801,
        ),
    )

    assert forwarded.consumed_one_time_prekey_id == 801
    assert forwarded.wire_payload_json == NEW_WIRE_PAYLOAD


async def test_forwarding_with_invalid_consumed_one_time_prekey_id_fails(
    integration_db: AsyncSession,
) -> None:
    """Forward rejects invalid consumed prekey metadata for the new recipient."""
    sender, recipient = await _create_ready_users(
        integration_db,
        "maya-invalid-forward-prekey",
        "noah-invalid-forward-prekey",
    )
    new_recipient = await _create_user(integration_db, "ophelia-invalid-forward-prekey")
    await _create_device_key(integration_db, new_recipient, 1)
    await integration_db.commit()
    original = await _send_default_message(integration_db, sender, recipient)

    with pytest.raises(InvalidPreKeyError):
        await message_service.forward_message(
            integration_db,
            sender,
            original.id,
            _message_request(
                new_recipient.id,
                wire_payload_json=NEW_WIRE_PAYLOAD,
                consumed_one_time_prekey_id=802,
            ),
        )


async def test_forwarding_preserves_new_wire_payload_exactly(
    integration_db: AsyncSession,
) -> None:
    """Forwarding should preserve whitespace and formatting in the new payload."""
    sender, recipient = await _create_ready_users(integration_db, "paula", "ryan")
    new_recipient = await _create_user(integration_db, "sara")
    await _create_device_key(integration_db, new_recipient, 1)
    original = await _send_default_message(integration_db, sender, recipient)

    forwarded = await message_service.forward_message(
        integration_db,
        sender,
        original.id,
        _message_request(new_recipient.id, wire_payload_json=NEW_WIRE_PAYLOAD),
    )

    assert forwarded.wire_payload_json == NEW_WIRE_PAYLOAD


async def _create_ready_users(
    integration_db: AsyncSession,
    sender_username: str,
    recipient_username: str,
):
    """Create sender and recipient users with active device 1."""
    sender = await _create_user(integration_db, sender_username)
    recipient = await _create_user(integration_db, recipient_username)
    await _create_device_key(integration_db, sender, 1)
    await _create_device_key(integration_db, recipient, 1)
    await integration_db.commit()
    await integration_db.refresh(sender)
    await integration_db.refresh(recipient)
    return sender, recipient


async def _create_user(integration_db: AsyncSession, username: str):
    """Create a user for message service tests."""
    return await user_repository.create_user(
        integration_db,
        username=username,
        email=f"{username}@example.com",
        password_hash=PASSWORD_HASH,
    )


async def _create_device_key(integration_db: AsyncSession, user, device_id: int):
    """Create an active public device key for a user."""
    return await device_key_repository.create_or_update_device_key(
        integration_db,
        user.id,
        DeviceKeyUploadRequest(
            device_id=device_id,
            registration_id=1000 + device_id,
            identity_key_public_b64=KEY_B64,
            identity_signing_public_b64=KEY_B64,
            signed_prekey_id=2000 + device_id,
            signed_prekey_public_b64=KEY_B64,
            signed_prekey_signature_b64=KEY_B64,
        ),
    )


async def _create_used_prekey(
    integration_db: AsyncSession,
    user,
    device_id: int,
    prekey_id: int,
):
    """Create and mark a recipient public prekey as consumed by bundle fetch."""
    prekey = await _create_unused_prekey(integration_db, user, device_id, prekey_id)
    await one_time_prekey_repository.mark_used(integration_db, prekey)
    await integration_db.commit()
    await integration_db.refresh(prekey)
    return prekey


async def _create_unused_prekey(
    integration_db: AsyncSession,
    user,
    device_id: int,
    prekey_id: int,
):
    """Create a public one-time prekey without marking it used."""
    [prekey] = await one_time_prekey_repository.create_batch(
        integration_db,
        user.id,
        device_id,
        [
            OneTimePreKeyUpload(
                device_id=device_id,
                prekey_id=prekey_id,
                prekey_public_b64=KEY_B64,
            ),
        ],
    )
    await integration_db.commit()
    await integration_db.refresh(prekey)
    return prekey


async def _send_default_message(
    integration_db: AsyncSession,
    sender,
    recipient,
):
    """Send a valid default message through the service."""
    return await message_service.send_message(
        integration_db,
        sender,
        _message_request(recipient.id),
    )


def _message_request(
    recipient_user_id,
    *,
    sender_device_id: int = 1,
    recipient_device_id: int = 1,
    wire_payload_json: str = WIRE_PAYLOAD,
    consumed_one_time_prekey_id: int | None = None,
) -> MessageCreateRequest:
    """Build a valid message create request."""
    return MessageCreateRequest(
        sender_device_id=sender_device_id,
        recipient_user_id=recipient_user_id,
        recipient_device_id=recipient_device_id,
        wire_payload_json=wire_payload_json,
        consumed_one_time_prekey_id=consumed_one_time_prekey_id,
    )
