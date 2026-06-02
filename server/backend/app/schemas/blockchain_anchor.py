"""Blockchain anchor schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import (
    ORMResponseModel,
    StrictRequestModel,
    validate_eth_address,
    validate_eth_hash,
)


class BlockchainAnchorCreateRequest(StrictRequestModel):
    """Create blockchain digest/transaction metadata."""

    message_id: UUID | None = None
    batch_id: UUID | None = None
    record_id: str | None = None
    digest: str
    merkle_root: str | None = None
    transaction_hash: str | None = None
    contract_address: str | None = None
    chain: Literal["sepolia"] = "sepolia"
    status: Literal["pending", "confirmed", "failed"] = "pending"
    anchored_at: datetime | None = None

    @model_validator(mode="after")
    def validate_anchor_target(self) -> Self:
        """Require either a message or a batch anchor target."""
        if self.message_id is None and self.batch_id is None:
            raise ValueError("Either message_id or batch_id is required.")
        return self

    @field_validator("record_id")
    @classmethod
    def validate_record_id(cls, value: str | None) -> str | None:
        """Validate contract record ID format when present."""
        if value is None:
            return None
        return validate_eth_hash(value)

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        """Validate keccak256 digest format."""
        return validate_eth_hash(value)

    @field_validator("merkle_root")
    @classmethod
    def validate_merkle_root(cls, value: str | None) -> str | None:
        """Validate Merkle root format when present."""
        if value is None:
            return None
        return validate_eth_hash(value)

    @field_validator("transaction_hash")
    @classmethod
    def validate_transaction_hash(cls, value: str | None) -> str | None:
        """Validate transaction hash format when present."""
        if value is None:
            return None
        return validate_eth_hash(value)

    @field_validator("contract_address")
    @classmethod
    def validate_contract_address(cls, value: str | None) -> str | None:
        """Validate contract address format when present."""
        if value is None:
            return None
        return validate_eth_address(value)


class BlockchainMessageAnchorCreateRequest(StrictRequestModel):
    """Request to create a pending anchor for an accessible message."""

    message_id: UUID


class BlockchainVerifyRequest(StrictRequestModel):
    """Verify a digest/root against backend anchor metadata."""

    digest: str
    record_id: str | None = None
    merkle_root: str | None = None
    transaction_hash: str | None = None
    chain: Literal["sepolia"] = "sepolia"

    @field_validator("digest")
    @classmethod
    def validate_verify_digest(cls, value: str) -> str:
        """Validate digest format."""
        return validate_eth_hash(value)

    @field_validator("record_id")
    @classmethod
    def validate_verify_record_id(cls, value: str | None) -> str | None:
        """Validate contract record ID format when present."""
        if value is None:
            return None
        return validate_eth_hash(value)

    @field_validator("merkle_root")
    @classmethod
    def validate_verify_merkle_root(cls, value: str | None) -> str | None:
        """Validate Merkle root format when present."""
        if value is None:
            return None
        return validate_eth_hash(value)

    @field_validator("transaction_hash")
    @classmethod
    def validate_verify_transaction_hash(cls, value: str | None) -> str | None:
        """Validate transaction hash format when present."""
        if value is None:
            return None
        return validate_eth_hash(value)


class BlockchainVerifyResponse(ORMResponseModel):
    """Verification result for backend anchor metadata."""

    valid: bool
    chain: str
    status: str | None = None
    anchor_id: UUID | None = None
    message_id: UUID | None = None
    batch_id: UUID | None = None
    record_id: str | None = None
    digest: str
    merkle_root: str | None = None
    transaction_hash: str | None = None
    contract_address: str | None = None
    anchored_at: datetime | None = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BlockchainAnchorResponse(ORMResponseModel):
    """Blockchain anchor metadata response."""

    id: UUID
    message_id: UUID | None
    batch_id: UUID | None
    record_id: str | None
    digest: str
    merkle_root: str | None
    transaction_hash: str | None
    contract_address: str | None
    chain: str
    status: str
    created_at: datetime
    anchored_at: datetime | None
