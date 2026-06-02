"""add message forwarding lineage

Revision ID: 20260602_0003
Revises: 20260602_0002
Create Date: 2026-06-02

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260602_0003"
down_revision: str | Sequence[str] | None = "20260602_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store internal provenance for forwarded encrypted relay messages."""
    op.add_column(
        "messages",
        sa.Column(
            "forwarded_from_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_messages_forwarded_from_message_id_messages",
        "messages",
        "messages",
        ["forwarded_from_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_messages_forwarded_from_message_id",
        "messages",
        ["forwarded_from_message_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove forwarded message provenance metadata."""
    op.drop_index("ix_messages_forwarded_from_message_id", table_name="messages")
    op.drop_constraint(
        "fk_messages_forwarded_from_message_id_messages",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "forwarded_from_message_id")
