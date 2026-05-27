"""Opaque message relay schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import (
    MAX_WIRE_PAYLOAD_BYTES,
    ORMResponseModel,
    StrictRequestModel,
    validate_wire_payload_json,
)


class MessageCreateRequest(StrictRequestModel):
    """Create an opaque relay message for a recipient device."""

    sender_device_id: int = Field(gt=0)
    recipient_user_id: UUID
    recipient_device_id: int = Field(gt=0)
    conversation_id: UUID | None = None
    wire_payload_json: str = Field(min_length=2, max_length=MAX_WIRE_PAYLOAD_BYTES)
    consumed_one_time_prekey_id: int | None = Field(default=None, gt=0)

    @field_validator("wire_payload_json")
    @classmethod
    def validate_wire_payload(cls, value: str) -> str:
        """Validate wire payload structure without modifying the original string."""
        return validate_wire_payload_json(value)


class MessageResponse(ORMResponseModel):
    """Stored opaque relay message response."""

    id: UUID
    sender_user_id: UUID
    sender_device_id: int
    recipient_user_id: UUID
    recipient_device_id: int
    conversation_id: UUID | None
    wire_payload_json: str
    consumed_one_time_prekey_id: int | None
    created_at: datetime
    deleted_at: datetime | None


class InboxMessageResponse(ORMResponseModel):
    """Inbox-oriented opaque message response."""

    id: UUID
    sender_user_id: UUID
    sender_device_id: int
    conversation_id: UUID | None
    wire_payload_json: str
    created_at: datetime
