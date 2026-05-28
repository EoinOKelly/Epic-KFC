"""Opaque relay message model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.blockchain_anchor import BlockchainAnchor
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
        Index("ix_messages_access_revoked_at", "access_revoked_at"),
        Index("ix_messages_sender_deleted_at", "sender_deleted_at"),
        Index("ix_messages_recipient_deleted_at", "recipient_deleted_at"),
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
    wire_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    consumed_one_time_prekey_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    access_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sender_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    recipient_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
    blockchain_anchors: Mapped[list["BlockchainAnchor"]] = relationship(
        "BlockchainAnchor",
        back_populates="message",
    )
