"""add message visibility fields

Revision ID: 20260528_0002
Revises: 20260527_0001
Create Date: 2026-05-28

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260528_0002"
down_revision: str | Sequence[str] | None = "20260527_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add role-aware message revocation and delete timestamps."""
    op.add_column(
        "messages",
        sa.Column("access_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("sender_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("recipient_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_messages_access_revoked_at",
        "messages",
        ["access_revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_sender_deleted_at",
        "messages",
        ["sender_deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_recipient_deleted_at",
        "messages",
        ["recipient_deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove role-aware message revocation and delete timestamps."""
    op.drop_index("ix_messages_recipient_deleted_at", table_name="messages")
    op.drop_index("ix_messages_sender_deleted_at", table_name="messages")
    op.drop_index("ix_messages_access_revoked_at", table_name="messages")
    op.drop_column("messages", "recipient_deleted_at")
    op.drop_column("messages", "sender_deleted_at")
    op.drop_column("messages", "access_revoked_at")
