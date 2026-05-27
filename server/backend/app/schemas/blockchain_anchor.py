"""Blockchain anchor schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.schemas.common import (
    ORMResponseModel,
    StrictRequestModel,
    validate_eth_address,
    validate_eth_hash,
)


class BlockchainAnchorCreateRequest(StrictRequestModel):
    """Create blockchain digest/transaction metadata."""

    message_id: UUID | None = None
    conversation_id: UUID | None = None
    digest: str
    transaction_hash: str | None = None
    contract_address: str | None = None
    chain: Literal["sepolia"]
    status: Literal["pending", "confirmed", "failed"]
    anchored_at: datetime | None = None

    @model_validator(mode="after")
    def validate_anchor_target(self) -> Self:
        """Require at least one anchored resource identifier."""
        if self.message_id is None and self.conversation_id is None:
            raise ValueError("At least one of message_id or conversation_id is required.")
        return self

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        """Validate keccak256 digest format."""
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


class BlockchainAnchorResponse(ORMResponseModel):
    """Blockchain anchor metadata response."""

    id: UUID
    message_id: UUID | None
    conversation_id: UUID | None
    digest: str
    transaction_hash: str | None
    contract_address: str | None
    chain: str
    status: str
    created_at: datetime
    anchored_at: datetime | None
