"""Conversation model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.blockchain_anchor import BlockchainAnchor
    from app.models.conversation_member import ConversationMember
    from app.models.message import Message
    from app.models.user import User


class Conversation(Base):
    """Messaging thread protected by membership records."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_created_by", "created_by"),
        Index("ix_conversations_deleted_at", "deleted_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    created_by: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_conversations",
        foreign_keys=[created_by],
    )
    members: Mapped[list["ConversationMember"]] = relationship(
        "ConversationMember",
        back_populates="conversation",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
    )
    blockchain_anchors: Mapped[list["BlockchainAnchor"]] = relationship(
        "BlockchainAnchor",
        back_populates="conversation",
    )
