"""Async repository functions for blockchain anchor metadata."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blockchain_anchor import BlockchainAnchor


async def create_anchor(
    db: AsyncSession,
    *,
    digest: str,
    record_id: str | None = None,
    message_id: UUID | None = None,
    batch_id: UUID | None = None,
    merkle_root: str | None = None,
    transaction_hash: str | None = None,
    contract_address: str | None = None,
    chain: str = "sepolia",
    status: str = "pending",
    anchored_at: datetime | None = None,
) -> BlockchainAnchor:
    """Create blockchain anchor metadata without committing."""
    anchor = BlockchainAnchor(
        message_id=message_id,
        batch_id=batch_id,
        record_id=record_id,
        digest=digest,
        merkle_root=merkle_root,
        transaction_hash=transaction_hash,
        contract_address=contract_address,
        chain=chain,
        status=status,
        anchored_at=anchored_at,
    )
    db.add(anchor)
    await db.flush()
    await db.refresh(anchor)
    return anchor


async def get_by_id(
    db: AsyncSession,
    anchor_id: UUID,
) -> BlockchainAnchor | None:
    """Return an anchor by primary key."""
    result = await db.execute(
        select(BlockchainAnchor).where(BlockchainAnchor.id == anchor_id)
    )
    return result.scalar_one_or_none()


async def get_latest_for_message(
    db: AsyncSession,
    message_id: UUID,
) -> BlockchainAnchor | None:
    """Return the latest anchor for a message."""
    result = await db.execute(
        select(BlockchainAnchor)
        .where(BlockchainAnchor.message_id == message_id)
        .order_by(desc(BlockchainAnchor.created_at), desc(BlockchainAnchor.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_active_for_message(
    db: AsyncSession,
    message_id: UUID,
) -> BlockchainAnchor | None:
    """Return the latest non-failed anchor for a message."""
    result = await db.execute(
        select(BlockchainAnchor)
        .where(
            BlockchainAnchor.message_id == message_id,
            BlockchainAnchor.status.in_(("pending", "confirmed")),
        )
        .order_by(desc(BlockchainAnchor.created_at), desc(BlockchainAnchor.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def find_matching_anchor(
    db: AsyncSession,
    *,
    digest: str,
    chain: str,
    record_id: str | None = None,
    merkle_root: str | None = None,
    transaction_hash: str | None = None,
) -> BlockchainAnchor | None:
    """Return a confirmed anchor matching public verification metadata."""
    statement = select(BlockchainAnchor).where(
        BlockchainAnchor.digest == digest,
        BlockchainAnchor.chain == chain,
        BlockchainAnchor.status == "confirmed",
    )
    if record_id is not None:
        statement = statement.where(BlockchainAnchor.record_id == record_id)
    if merkle_root is not None:
        statement = statement.where(BlockchainAnchor.merkle_root == merkle_root)
    if transaction_hash is not None:
        statement = statement.where(BlockchainAnchor.transaction_hash == transaction_hash)

    result = await db.execute(
        statement.order_by(desc(BlockchainAnchor.anchored_at), desc(BlockchainAnchor.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_pending(
    db: AsyncSession,
    *,
    limit: int = 100,
    for_update: bool = False,
) -> list[BlockchainAnchor]:
    """Return pending anchors for the blockchain worker."""
    statement = (
        select(BlockchainAnchor)
        .where(BlockchainAnchor.status == "pending")
        .order_by(BlockchainAnchor.created_at, BlockchainAnchor.id)
        .limit(limit)
    )
    if for_update:
        statement = statement.with_for_update(skip_locked=True)

    result = await db.execute(statement)
    return list(result.scalars().all())


async def get_next_pending_for_update(db: AsyncSession) -> BlockchainAnchor | None:
    """Return and lock the oldest pending anchor for one worker transaction."""
    result = await db.execute(
        select(BlockchainAnchor)
        .where(BlockchainAnchor.status == "pending")
        .order_by(BlockchainAnchor.created_at, BlockchainAnchor.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return result.scalar_one_or_none()


async def update_anchor_status(
    db: AsyncSession,
    anchor_id: UUID,
    *,
    status: str,
    transaction_hash: str | None = None,
    contract_address: str | None = None,
    merkle_root: str | None = None,
    anchored_at: datetime | None = None,
) -> BlockchainAnchor | None:
    """Update worker-controlled anchor status fields without committing."""
    anchor = await get_by_id(db, anchor_id)
    if anchor is None:
        return None

    anchor.status = status
    if transaction_hash is not None:
        anchor.transaction_hash = transaction_hash
    if contract_address is not None:
        anchor.contract_address = contract_address
    if merkle_root is not None:
        anchor.merkle_root = merkle_root
    if anchored_at is not None:
        anchor.anchored_at = anchored_at

    await db.flush()
    await db.refresh(anchor)
    return anchor
