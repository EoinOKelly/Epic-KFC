"""Contract-compatible hashing helpers for blockchain integrity anchors."""

from __future__ import annotations

import json
from uuid import UUID

from eth_hash.auto import keccak

from app.models.message import Message


def derive_message_record_id(message_id: UUID) -> str:
    """Return the contract record ID for a direct message anchor."""
    return _keccak_hex(f"message:{message_id}".encode("utf-8"))


def derive_batch_record_id(batch_id: UUID) -> str:
    """Return the contract record ID for a Merkle batch anchor."""
    return _keccak_hex(f"batch:{batch_id}".encode("utf-8"))


def derive_message_digest(message: Message) -> str:
    """Hash the canonical encrypted relay message record.

    The canonical record includes encrypted relay payload text and metadata only.
    It does not include plaintext, private keys, or client ratchet state.
    """
    return _keccak_hex(_canonical_message_bytes(message))


def _canonical_message_bytes(message: Message) -> bytes:
    """Serialize stable message metadata for integrity hashing."""
    canonical = {
        "created_at": message.created_at.isoformat(),
        "id": str(message.id),
        "recipient_device_id": message.recipient_device_id,
        "recipient_user_id": str(message.recipient_user_id),
        "sender_device_id": message.sender_device_id,
        "sender_user_id": str(message.sender_user_id),
        "wire_payload_json": message.wire_payload_json,
    }
    return json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _keccak_hex(data: bytes) -> str:
    """Return Ethereum Keccak-256 as a 0x-prefixed 32-byte hex string."""
    return "0x" + keccak(data).hex()
