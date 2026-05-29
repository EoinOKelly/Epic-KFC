"""Shared Pydantic schemas and validation helpers."""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")

MAX_BASE64_FIELD_LENGTH = 8192
MAX_WIRE_PAYLOAD_BYTES = 64 * 1024

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
ETH_HASH_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
ETH_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")

LIBSIGNAL_WIRE_FORMAT = "libsignal-v1"
LIBSIGNAL_ALLOWED_MESSAGE_TYPES = {1, 3}

FORBIDDEN_INPUT_KEYS = {
    "aeskey",
    "body",
    "chainkey",
    "content",
    "message",
    "plaintext",
    "privatekey",
    "ratchetstate",
    "rootkey",
    "sessionstate",
    "text",
}


class StrictRequestModel(BaseModel):
    """Base class for request bodies that should reject unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ORMResponseModel(BaseModel):
    """Base class for response bodies that may be built from ORM objects."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class UUIDResponse(ORMResponseModel):
    """Response containing a single UUID identifier."""

    id: UUID


class TimestampedResponse(ORMResponseModel):
    """Response mixin for timestamped resources."""

    created_at: datetime
    updated_at: datetime | None = None


class PaginationParams(BaseModel):
    """Common pagination query parameters for future list routes."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response container."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: str | None = None


class ErrorResponse(BaseModel):
    """Generic client-safe error response."""

    detail: str
    code: str | None = None


def validate_username(value: str) -> str:
    """Validate and normalize a username."""
    username = value.strip()
    if not 3 <= len(username) <= 50:
        raise ValueError("Username must be between 3 and 50 characters.")
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username may contain letters, numbers, underscore, dot, and hyphen."
        )
    return username


def validate_base64(value: str, *, max_length: int = MAX_BASE64_FIELD_LENGTH) -> str:
    """Validate that a string is structurally standard base64."""
    if not value:
        raise ValueError("Base64 value must not be empty.")
    if len(value) > max_length:
        raise ValueError("Base64 value exceeds the maximum allowed length.")
    if any(character.isspace() for character in value):
        raise ValueError("Base64 value must not contain whitespace.")

    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Value must be valid base64.") from exc

    if not decoded:
        raise ValueError("Base64 value must decode to non-empty bytes.")
    return value


def validate_eth_hash(value: str) -> str:
    """Validate an Ethereum-style 32-byte hex hash."""
    if not ETH_HASH_PATTERN.fullmatch(value):
        raise ValueError("Value must match 0x followed by 64 hex characters.")
    return value


def validate_eth_address(value: str) -> str:
    """Validate an Ethereum-style address."""
    if not ETH_ADDRESS_PATTERN.fullmatch(value):
        raise ValueError("Value must match 0x followed by 40 hex characters.")
    return value


def validate_wire_payload_json(value: str) -> str:
    """Validate relay wire payload structure while returning the original string.

    Contract: ``cryptography/`` ``serializeWireMessage()`` output (libsignal-v1).
    The server stores opaque JSON only; encrypt/decrypt runs on the client.
    """
    if len(value.encode("utf-8")) > MAX_WIRE_PAYLOAD_BYTES:
        raise ValueError("wire_payload_json exceeds the maximum allowed size.")

    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("wire_payload_json must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("wire_payload_json must contain a JSON object.")

    _reject_forbidden_payload_keys(payload)
    _validate_libsignal_wire_payload(payload)

    return value


def _validate_libsignal_wire_payload(payload: dict[str, Any]) -> None:
    """Validate ``LibSignalWireMessage`` shape from @epic-messaging/cryptography."""
    wire_format = payload.get("format")
    if wire_format != LIBSIGNAL_WIRE_FORMAT:
        raise ValueError(
            f'wire_payload_json format must be "{LIBSIGNAL_WIRE_FORMAT}".'
        )

    message_type = payload.get("type")
    if isinstance(message_type, bool) or not isinstance(message_type, int):
        raise ValueError("type must be an integer.")
    if message_type not in LIBSIGNAL_ALLOWED_MESSAGE_TYPES:
        raise ValueError("type must be 1 (WhisperMessage) or 3 (PreKeyWhisperMessage).")

    body_b64 = payload.get("bodyB64")
    if not isinstance(body_b64, str):
        raise ValueError("bodyB64 must be a base64 string.")
    validate_base64(body_b64, max_length=MAX_WIRE_PAYLOAD_BYTES)

    registration_id = payload.get("registrationId")
    if registration_id is None:
        return

    if isinstance(registration_id, bool) or not isinstance(registration_id, int):
        raise ValueError("registrationId must be an integer when present.")
    if registration_id <= 0:
        raise ValueError("registrationId must be a positive integer when present.")


def _reject_forbidden_payload_keys(value: Any) -> None:
    """Reject keys that indicate plaintext, private keys, or client secret state."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in FORBIDDEN_INPUT_KEYS:
                raise ValueError(f"Forbidden key in payload: {key}.")
            _reject_forbidden_payload_keys(nested_value)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_payload_keys(item)
