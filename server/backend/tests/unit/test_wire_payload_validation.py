"""Unit tests for libsignal-v1 wire payload validation."""

import pytest

from app.schemas.common import validate_wire_payload_json
from tests.fixtures.wire_payloads import NEW_WIRE_PAYLOAD, WIRE_PAYLOAD


def test_accepts_libsignal_prekey_message() -> None:
    """PreKeyWhisperMessage wire shape (type 3) is accepted."""
    assert validate_wire_payload_json(WIRE_PAYLOAD) == WIRE_PAYLOAD


def test_accepts_libsignal_whisper_message() -> None:
    """WhisperMessage wire shape (type 1) is accepted."""
    assert validate_wire_payload_json(NEW_WIRE_PAYLOAD) == NEW_WIRE_PAYLOAD


def test_rejects_legacy_counter_format() -> None:
    """Old hand-rolled wire format must be rejected."""
    legacy = (
        '{"counter":0,"previousCounter":0,"ciphertext":"b3JpZ2luYWw=",'
        '"iv":"aXY=","authTag":"dGFn"}'
    )
    with pytest.raises(ValueError, match='format must be "libsignal-v1"'):
        validate_wire_payload_json(legacy)


def test_rejects_missing_body_b64() -> None:
    """bodyB64 is required."""
    payload = '{"format":"libsignal-v1","type":1}'
    with pytest.raises(ValueError, match="bodyB64"):
        validate_wire_payload_json(payload)


def test_rejects_forbidden_plaintext_key() -> None:
    """Plaintext must not appear in wire JSON."""
    payload = (
        '{"format":"libsignal-v1","type":1,"bodyB64":"bmV3",'
        '"plaintext":"hello"}'
    )
    with pytest.raises(ValueError, match="Forbidden key"):
        validate_wire_payload_json(payload)
