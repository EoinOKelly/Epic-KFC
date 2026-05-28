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

WIRE_REQUIRED_KEYS = {"counter", "previousCounter", "ciphertext", "iv", "authTag"}
WIRE_BASE64_KEYS = {"ciphertext", "iv", "authTag", "ratchetPublicKey"}
X3DH_BASE64_KEYS = {"identityKey", "ephemeralKey"}

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
    """Validate relay wire payload structure while returning the original string."""
    if len(value.encode("utf-8")) > MAX_WIRE_PAYLOAD_BYTES:
        raise ValueError("wire_payload_json exceeds the maximum allowed size.")

    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("wire_payload_json must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("wire_payload_json must contain a JSON object.")

    _reject_forbidden_payload_keys(payload)

    missing_keys = WIRE_REQUIRED_KEYS.difference(payload)
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(f"wire_payload_json is missing required keys: {missing}.")

    for counter_key in ("counter", "previousCounter"):
        counter_value = payload[counter_key]
        if isinstance(counter_value, bool) or not isinstance(counter_value, int):
            raise ValueError(f"{counter_key} must be a non-negative integer.")
        if counter_value < 0:
            raise ValueError(f"{counter_key} must be a non-negative integer.")

    for base64_key in WIRE_BASE64_KEYS:
        if base64_key in payload:
            if not isinstance(payload[base64_key], str):
                raise ValueError(f"{base64_key} must be a base64 string.")
            validate_base64(
                payload[base64_key],
                max_length=MAX_WIRE_PAYLOAD_BYTES,
            )

    x3dh = payload.get("x3dh")
    if x3dh is not None:
        if not isinstance(x3dh, dict):
            raise ValueError("x3dh must be an object when present.")
        for base64_key in X3DH_BASE64_KEYS:
            if base64_key in x3dh:
                if not isinstance(x3dh[base64_key], str):
                    raise ValueError(f"x3dh.{base64_key} must be a base64 string.")
                validate_base64(
                    x3dh[base64_key],
                    max_length=MAX_BASE64_FIELD_LENGTH,
                )

    return value


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
