"""extend blockchain anchor metadata

Revision ID: 20260602_0002
Revises: 20260527_0001
Create Date: 2026-06-02

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260602_0002"
down_revision: str | Sequence[str] | None = "20260527_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add contract-compatible record and batch metadata for anchors."""
    op.add_column(
        "blockchain_anchors",
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "blockchain_anchors",
        sa.Column("record_id", sa.String(length=66), nullable=True),
    )
    op.add_column(
        "blockchain_anchors",
        sa.Column("merkle_root", sa.String(length=66), nullable=True),
    )
    op.alter_column(
        "blockchain_anchors",
        "message_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column(
        "blockchain_anchors",
        "digest",
        existing_type=sa.String(length=128),
        type_=sa.String(length=66),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_blockchain_anchors_message_or_batch",
        "blockchain_anchors",
        "message_id IS NOT NULL OR batch_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_blockchain_anchors_status",
        "blockchain_anchors",
        "status IN ('pending', 'confirmed', 'failed')",
    )
    op.create_check_constraint(
        "ck_blockchain_anchors_chain",
        "blockchain_anchors",
        "chain = 'sepolia'",
    )
    op.create_index(
        "ix_blockchain_anchors_batch_id",
        "blockchain_anchors",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_blockchain_anchors_record_id",
        "blockchain_anchors",
        ["record_id"],
        unique=False,
    )
    op.create_index(
        "ix_blockchain_anchors_merkle_root",
        "blockchain_anchors",
        ["merkle_root"],
        unique=False,
    )


def downgrade() -> None:
    """Remove extended blockchain anchor metadata."""
    op.drop_index("ix_blockchain_anchors_merkle_root", table_name="blockchain_anchors")
    op.drop_index("ix_blockchain_anchors_record_id", table_name="blockchain_anchors")
    op.drop_index("ix_blockchain_anchors_batch_id", table_name="blockchain_anchors")
    op.drop_constraint(
        "ck_blockchain_anchors_chain",
        "blockchain_anchors",
        type_="check",
    )
    op.drop_constraint(
        "ck_blockchain_anchors_status",
        "blockchain_anchors",
        type_="check",
    )
    op.drop_constraint(
        "ck_blockchain_anchors_message_or_batch",
        "blockchain_anchors",
        type_="check",
    )
    op.execute("DELETE FROM blockchain_anchors WHERE message_id IS NULL")
    op.alter_column(
        "blockchain_anchors",
        "digest",
        existing_type=sa.String(length=66),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
    op.alter_column(
        "blockchain_anchors",
        "message_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_column("blockchain_anchors", "merkle_root")
    op.drop_column("blockchain_anchors", "record_id")
    op.drop_column("blockchain_anchors", "batch_id")
