"""Blockchain digest and transaction metadata model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message


class BlockchainAnchor(Base):
    """Blockchain proof metadata without transaction submission logic."""

    __tablename__ = "blockchain_anchors"
    __table_args__ = (
        CheckConstraint(
            "message_id IS NOT NULL OR conversation_id IS NOT NULL",
            name="ck_blockchain_anchors_message_or_conversation",
        ),
        Index("ix_blockchain_anchors_message_id", "message_id"),
        Index("ix_blockchain_anchors_conversation_id", "conversation_id"),
        Index("ix_blockchain_anchors_digest", "digest"),
        Index("ix_blockchain_anchors_transaction_hash", "transaction_hash"),
        Index("ix_blockchain_anchors_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    message_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("messages.id"),
        nullable=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=True,
    )
    digest: Mapped[str] = mapped_column(String(128), nullable=False)
    transaction_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chain: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    anchored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    message: Mapped["Message | None"] = relationship(
        "Message",
        back_populates="blockchain_anchors",
    )
    conversation: Mapped["Conversation | None"] = relationship(
        "Conversation",
        back_populates="blockchain_anchors",
    )
