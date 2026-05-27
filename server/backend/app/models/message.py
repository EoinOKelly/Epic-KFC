"""Encrypted message model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.blockchain_anchor import BlockchainAnchor
    from app.models.conversation import Conversation
    from app.models.message_recipient import MessageRecipient
    from app.models.user import User


class Message(Base):
    """Client-generated AES-256-GCM encrypted message envelope.

    The "system" message type is reserved for future use; no system-message
    behavior is implemented in this backend step.
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "message_type IN ('direct', 'forwarded', 'system')",
            name="ck_messages_message_type",
        ),
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_sender_id", "sender_id"),
        Index("ix_messages_sent_at", "sent_at"),
        Index("ix_messages_deleted_at", "deleted_at"),
        Index("ix_messages_conversation_id_sent_at", "conversation_id", "sent_at"),
        Index("ix_messages_sender_id_nonce", "sender_id", "nonce"),
        Index("ix_messages_sender_key_fingerprint", "sender_key_fingerprint"),
        Index("ix_messages_forwarded_from_message_id", "forwarded_from_message_id"),
        Index("ix_messages_ciphertext_hash", "ciphertext_hash", unique=True),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=False,
    )
    sender_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    sender_key_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="direct",
        server_default="direct",
        comment="Allowed: direct, forwarded, system. system is reserved.",
    )
    forwarded_from_message_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("messages.id"),
        nullable=True,
    )
    encryption_scheme: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="client_aes_gcm_v1",
        server_default="client_aes_gcm_v1",
    )
    algorithm: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="AES-256-GCM",
        server_default="AES-256-GCM",
    )
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    associated_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    ciphertext_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    sender: Mapped["User"] = relationship(
        "User",
        back_populates="sent_messages",
        foreign_keys=[sender_id],
    )
    forwarded_from: Mapped["Message | None"] = relationship(
        "Message",
        back_populates="forwarded_messages",
        foreign_keys=[forwarded_from_message_id],
        remote_side=[id],
    )
    forwarded_messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="forwarded_from",
    )
    recipients: Mapped[list["MessageRecipient"]] = relationship(
        "MessageRecipient",
        back_populates="message",
    )
    blockchain_anchors: Mapped[list["BlockchainAnchor"]] = relationship(
        "BlockchainAnchor",
        back_populates="message",
    )
