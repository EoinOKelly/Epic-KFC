"""Blockchain anchor service for integrity evidence metadata."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.blockchain_hashing import derive_message_digest, derive_message_record_id
from app.models.blockchain_anchor import BlockchainAnchor
from app.models.message import Message
from app.models.user import User
from app.repositories import blockchain_anchor_repository, message_repository
from app.schemas.blockchain_anchor import (
    BlockchainMessageAnchorCreateRequest,
    BlockchainVerifyRequest,
    BlockchainVerifyResponse,
)


class BlockchainAnchorNotFoundError(Exception):
    """Raised when an anchor is missing or inaccessible."""


@dataclass(frozen=True)
class MessageAnchorResult:
    """Result of creating or reusing a message anchor."""

    anchor: BlockchainAnchor
    created: bool


async def create_message_anchor(
    db: AsyncSession,
    current_user: User,
    request_data: BlockchainMessageAnchorCreateRequest,
) -> MessageAnchorResult:
    """Create or return a pending/confirmed anchor for an accessible message."""
    try:
        message = await _require_message_access(db, current_user, request_data.message_id)
        result = await create_pending_anchor_for_message(db, message)
        if result.created:
            await db.commit()
            await db.refresh(result.anchor)
        return result
    except Exception:
        await db.rollback()
        raise


async def create_pending_anchor_for_message(
    db: AsyncSession,
    message: Message,
) -> MessageAnchorResult:
    """Create or return a pending/confirmed anchor without committing.

    This is used inside message send/forward transactions so a new encrypted
    message and its pending blockchain evidence are created atomically.
    """
    existing = await blockchain_anchor_repository.get_latest_active_for_message(
        db,
        message.id,
    )
    if existing is not None:
        return MessageAnchorResult(anchor=existing, created=False)

    anchor = await blockchain_anchor_repository.create_anchor(
        db,
        message_id=message.id,
        record_id=derive_message_record_id(message.id),
        digest=derive_message_digest(message),
        chain="sepolia",
        status="pending",
    )
    return MessageAnchorResult(anchor=anchor, created=True)


async def get_anchor_for_user(
    db: AsyncSession,
    current_user: User,
    anchor_id: UUID,
) -> BlockchainAnchor:
    """Return an anchor only if the user can access the linked message."""
    anchor = await blockchain_anchor_repository.get_by_id(db, anchor_id)
    if anchor is None or anchor.message_id is None:
        raise BlockchainAnchorNotFoundError("Anchor not found.")

    await _require_message_access(db, current_user, anchor.message_id)
    return anchor


async def get_anchor_public(
    db: AsyncSession,
    anchor_id: UUID,
) -> BlockchainAnchor:
    """Return an anchor without requiring message access, used for public verification."""
    anchor = await blockchain_anchor_repository.get_by_id(db, anchor_id)
    if anchor is None or anchor.message_id is None:
        raise BlockchainAnchorNotFoundError("Anchor not found.")
    return anchor


async def get_latest_message_anchor_for_user(
    db: AsyncSession,
    current_user: User,
    message_id: UUID,
) -> BlockchainAnchor:
    """Return the latest anchor for a message visible to the user."""
    await _require_message_access(db, current_user, message_id)
    anchor = await blockchain_anchor_repository.get_latest_for_message(db, message_id)
    if anchor is None:
        raise BlockchainAnchorNotFoundError("Anchor not found.")
    return anchor


async def verify_anchor_metadata(
    db: AsyncSession,
    request_data: BlockchainVerifyRequest,
) -> BlockchainVerifyResponse:
    """Verify supplied digest/root values against confirmed backend metadata.

    This does not contact Sepolia. The worker is responsible for on-chain writes
    and confirmation updates; this endpoint verifies backend proof metadata.
    """
    anchor = await blockchain_anchor_repository.find_matching_anchor(
        db,
        digest=request_data.digest,
        chain=request_data.chain,
        record_id=request_data.record_id,
        merkle_root=request_data.merkle_root,
        transaction_hash=request_data.transaction_hash,
    )
    if anchor is None:
        return BlockchainVerifyResponse(
            valid=False,
            chain=request_data.chain,
            digest=request_data.digest,
            merkle_root=request_data.merkle_root,
            transaction_hash=request_data.transaction_hash,
            record_id=request_data.record_id,
        )

    return BlockchainVerifyResponse(
        valid=True,
        chain=anchor.chain,
        status=anchor.status,
        anchor_id=anchor.id,
        message_id=anchor.message_id,
        batch_id=anchor.batch_id,
        record_id=anchor.record_id,
        digest=anchor.digest,
        merkle_root=anchor.merkle_root,
        transaction_hash=anchor.transaction_hash,
        contract_address=anchor.contract_address,
        anchored_at=anchor.anchored_at,
    )


async def _require_message_access(
    db: AsyncSession,
    current_user: User,
    message_id: UUID,
) -> Message:
    """Load a visible message or raise an anchor-safe not-found error."""
    message = await message_repository.get_accessible_by_id(
        db,
        message_id,
        current_user.id,
    )
    if message is None:
        raise BlockchainAnchorNotFoundError("Anchor not found.")
    return message
