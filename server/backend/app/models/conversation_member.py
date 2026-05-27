"""Conversation membership and revocation model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class ConversationMember(Base):
    """Conversation-level access-control record."""

    __tablename__ = "conversation_members"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "user_id",
            name="uq_conversation_members_conversation_id_user_id",
        ),
        Index("ix_conversation_members_conversation_id", "conversation_id"),
        Index("ix_conversation_members_user_id", "user_id"),
        Index(
            "ix_conversation_members_conversation_id_is_active",
            "conversation_id",
            "is_active",
        ),
        Index("ix_conversation_members_revoked_at", "revoked_at"),
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
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    member_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="member",
        server_default="member",
    )
    added_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="members",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="conversation_memberships",
        foreign_keys=[user_id],
    )
    added_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[added_by],
    )
