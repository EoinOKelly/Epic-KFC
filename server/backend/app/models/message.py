"""Opaque relay message model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.blockchain_anchor import BlockchainAnchor
    from app.models.conversation import Conversation
    from app.models.user import User


class Message(Base):
    """Opaque wire message produced by the client crypto package.

    The backend validates and stores the relay payload, but it must not decrypt
    messages, split cryptographic fields, or store client cryptographic state.
    """

    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "ix_messages_recipient_user_id_device_id_created_at",
            "recipient_user_id",
            "recipient_device_id",
            "created_at",
        ),
        Index("ix_messages_sender_user_id_created_at", "sender_user_id", "created_at"),
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_deleted_at", "deleted_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    sender_user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    sender_device_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    recipient_device_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=True,
    )
    wire_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    consumed_one_time_prekey_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sender: Mapped["User"] = relationship(
        "User",
        back_populates="sent_messages",
        foreign_keys=[sender_user_id],
    )
    recipient: Mapped["User"] = relationship(
        "User",
        back_populates="received_messages",
        foreign_keys=[recipient_user_id],
    )
    conversation: Mapped["Conversation | None"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    blockchain_anchors: Mapped[list["BlockchainAnchor"]] = relationship(
        "BlockchainAnchor",
        back_populates="message",
    )
