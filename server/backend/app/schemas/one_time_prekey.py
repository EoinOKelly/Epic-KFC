"""One-time public prekey schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import (
    MAX_BASE64_FIELD_LENGTH,
    ORMResponseModel,
    StrictRequestModel,
    validate_base64,
)


class OneTimePreKeyUpload(StrictRequestModel):
    """Single one-time public prekey upload item."""

    device_id: int = Field(gt=0)
    prekey_id: int = Field(gt=0)
    prekey_public_b64: str = Field(min_length=1, max_length=MAX_BASE64_FIELD_LENGTH)

    @field_validator("prekey_public_b64")
    @classmethod
    def validate_prekey_public_b64(cls, value: str) -> str:
        """Validate prekey public material as base64."""
        return validate_base64(value)


class OneTimePreKeyBatchUploadRequest(StrictRequestModel):
    """Batch upload for one-time public prekeys."""

    prekeys: list[OneTimePreKeyUpload] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_batch_prekeys(self) -> Self:
        """Reject duplicate device/prekey pairs in one batch."""
        seen: set[tuple[int, int]] = set()
        for prekey in self.prekeys:
            key = (prekey.device_id, prekey.prekey_id)
            if key in seen:
                raise ValueError("Duplicate device_id and prekey_id in batch.")
            seen.add(key)
        return self


class OneTimePreKeyResponse(ORMResponseModel):
    """Stored one-time public prekey response."""

    id: UUID
    user_id: UUID
    device_id: int
    prekey_id: int
    prekey_public_b64: str
    used_at: datetime | None
    created_at: datetime
