"""Device public key schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import (
    MAX_BASE64_FIELD_LENGTH,
    ORMResponseModel,
    StrictRequestModel,
    validate_base64,
)


class DeviceKeyUploadRequest(StrictRequestModel):
    """Upload public device key material for the current user."""

    device_id: int = Field(gt=0)
    registration_id: int = Field(gt=0)
    identity_key_public_b64: str = Field(min_length=1, max_length=MAX_BASE64_FIELD_LENGTH)
    identity_signing_public_b64: str = Field(
        min_length=1,
        max_length=MAX_BASE64_FIELD_LENGTH,
    )
    signed_prekey_id: int = Field(gt=0)
    signed_prekey_public_b64: str = Field(
        min_length=1,
        max_length=MAX_BASE64_FIELD_LENGTH,
    )
    signed_prekey_signature_b64: str = Field(
        min_length=1,
        max_length=MAX_BASE64_FIELD_LENGTH,
    )

    @field_validator(
        "identity_key_public_b64",
        "identity_signing_public_b64",
        "signed_prekey_public_b64",
        "signed_prekey_signature_b64",
    )
    @classmethod
    def validate_base64_fields(cls, value: str) -> str:
        """Validate public key and signature fields as base64."""
        return validate_base64(value)


class DeviceKeyResponse(ORMResponseModel):
    """Stored public device key response."""

    id: UUID
    user_id: UUID
    device_id: int
    registration_id: int
    identity_key_public_b64: str
    identity_signing_public_b64: str
    signed_prekey_id: int
    signed_prekey_public_b64: str
    signed_prekey_signature_b64: str
    signed_prekey_created_at: datetime
    created_at: datetime
    revoked_at: datetime | None
    is_active: bool


class PreKeyBundleResponse(ORMResponseModel):
    """Crypto-package-compatible public prekey bundle response."""

    registration_id: int = Field(alias="registrationId")
    device_id: int = Field(alias="deviceId")
    identity_key_public_b64: str = Field(alias="identityKey")
    identity_signing_public_b64: str = Field(alias="identitySigningKey")
    signed_prekey_id: int = Field(alias="signedPreKeyId")
    signed_prekey_public_b64: str = Field(alias="signedPreKey")
    signed_prekey_signature_b64: str = Field(alias="signedPreKeySignature")
    one_time_prekey_id: int | None = Field(default=None, alias="oneTimePreKeyId")
    one_time_prekey_public_b64: str | None = Field(default=None, alias="oneTimePreKey")
