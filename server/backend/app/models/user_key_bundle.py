"""Public cryptographic key bundle model."""

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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserKeyBundle(Base):
    """Public key material for recipient lookup and identity verification."""

    __tablename__ = "user_key_bundles"
    __table_args__ = (
        UniqueConstraint(
            "key_fingerprint",
            name="uq_user_key_bundles_key_fingerprint",
        ),
        Index("ix_user_key_bundles_user_id", "user_id"),
        Index("ix_user_key_bundles_user_id_is_active", "user_id", "is_active"),
        Index("ix_user_key_bundles_revoked_at", "revoked_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    encryption_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    signing_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    key_algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="key_bundles",
    )
