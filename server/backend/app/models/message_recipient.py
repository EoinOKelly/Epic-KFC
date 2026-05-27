"""Per-recipient encrypted message key model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class MessageRecipient(Base):
    """Per-recipient access metadata with encrypted AES message keys only."""

    __tablename__ = "message_recipients"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "recipient_id",
            name="uq_message_recipients_message_id_recipient_id",
        ),
        Index("ix_message_recipients_message_id", "message_id"),
        Index("ix_message_recipients_recipient_id", "recipient_id"),
        Index(
            "ix_message_recipients_recipient_key_fingerprint",
            "recipient_key_fingerprint",
        ),
        Index("ix_message_recipients_access_revoked_at", "access_revoked_at"),
        Index("ix_message_recipients_deleted_at", "deleted_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    message_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("messages.id"),
        nullable=False,
    )
    recipient_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    recipient_key_fingerprint: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    key_encryption_scheme: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="public_key_encrypted_message_key_v1",
        server_default="public_key_encrypted_message_key_v1",
    )
    encrypted_message_key: Mapped[str] = mapped_column(Text, nullable=False)
    access_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    message: Mapped["Message"] = relationship(
        "Message",
        back_populates="recipients",
    )
    recipient: Mapped["User"] = relationship(
        "User",
        back_populates="message_recipients",
    )
