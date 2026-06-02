"""Unit tests for blockchain anchor digest helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.message import Message
from app.core.blockchain_hashing import (
    derive_message_digest,
    derive_message_record_id,
)
from tests.fixtures.wire_payloads import NEW_WIRE_PAYLOAD, WIRE_PAYLOAD


def test_derive_message_record_id_returns_contract_bytes32_hex() -> None:
    """Message record IDs should be stable bytes32 values for the contract."""
    message_id = uuid4()

    first = derive_message_record_id(message_id)
    second = derive_message_record_id(message_id)

    assert first == second
    assert first.startswith("0x")
    assert len(first) == 66


def test_derive_message_digest_is_stable_for_same_message() -> None:
    """Message digests should be deterministic for the canonical record."""
    message = _message(WIRE_PAYLOAD)

    assert derive_message_digest(message) == derive_message_digest(message)


def test_derive_message_digest_changes_when_payload_changes() -> None:
    """Changing encrypted relay payload changes the integrity digest."""
    first = _message(WIRE_PAYLOAD)
    second = _message(NEW_WIRE_PAYLOAD)
    second.id = first.id
    second.sender_user_id = first.sender_user_id
    second.recipient_user_id = first.recipient_user_id
    second.created_at = first.created_at

    assert derive_message_digest(first) != derive_message_digest(second)


def test_derive_message_digest_changes_when_forward_lineage_changes() -> None:
    """Forward provenance is part of the canonical integrity digest."""
    first = _message(WIRE_PAYLOAD)
    second = _message(WIRE_PAYLOAD)
    second.id = first.id
    second.sender_user_id = first.sender_user_id
    second.recipient_user_id = first.recipient_user_id
    second.created_at = first.created_at
    second.forwarded_from_message_id = uuid4()

    assert derive_message_digest(first) != derive_message_digest(second)


def _message(wire_payload_json: str) -> Message:
    """Build a minimal message model for digest tests."""
    return Message(
        id=uuid4(),
        sender_user_id=uuid4(),
        sender_device_id=1,
        recipient_user_id=uuid4(),
        recipient_device_id=1,
        wire_payload_json=wire_payload_json,
        created_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
    )
