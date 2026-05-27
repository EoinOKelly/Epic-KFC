"""One-time public prekey model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class OneTimePreKey(Base):
    """Public one-time prekey consumed by the relay when handed out."""

    __tablename__ = "one_time_prekeys"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "device_id",
            "prekey_id",
            name="uq_one_time_prekeys_user_id_device_id_prekey_id",
        ),
        Index("ix_one_time_prekeys_user_id_device_id", "user_id", "device_id"),
        Index(
            "ix_one_time_prekeys_user_id_device_id_used_at",
            "user_id",
            "device_id",
            "used_at",
        ),
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
    device_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prekey_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prekey_public_b64: Mapped[str] = mapped_column(Text, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="one_time_prekeys",
    )
