"""Public device key material model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class DeviceKey(Base):
    """Public key material for one user device.

    This stores public keys only. It must not contain private keys or client
    cryptographic session state.
    """

    __tablename__ = "device_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_device_keys_user_id_device_id"),
        Index("ix_device_keys_user_id", "user_id"),
        Index("ix_device_keys_user_id_is_active", "user_id", "is_active"),
        Index("ix_device_keys_revoked_at", "revoked_at"),
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
    registration_id: Mapped[int] = mapped_column(Integer, nullable=False)
    identity_key_public_b64: Mapped[str] = mapped_column(Text, nullable=False)
    identity_signing_public_b64: Mapped[str] = mapped_column(Text, nullable=False)
    signed_prekey_id: Mapped[int] = mapped_column(Integer, nullable=False)
    signed_prekey_public_b64: Mapped[str] = mapped_column(Text, nullable=False)
    signed_prekey_signature_b64: Mapped[str] = mapped_column(Text, nullable=False)
    signed_prekey_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="device_keys",
    )
