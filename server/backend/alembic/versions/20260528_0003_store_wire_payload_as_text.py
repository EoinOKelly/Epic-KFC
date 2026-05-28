"""store wire payload as text

Revision ID: 20260528_0003
Revises: 20260528_0002
Create Date: 2026-05-28

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260528_0003"
down_revision: str | Sequence[str] | None = "20260528_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store serialized crypto wire payloads verbatim as text."""
    op.alter_column(
        "messages",
        "wire_payload_json",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.Text(),
        existing_nullable=False,
        postgresql_using="wire_payload_json::text",
    )


def downgrade() -> None:
    """Return wire payload storage to JSONB."""
    op.alter_column(
        "messages",
        "wire_payload_json",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        postgresql_using="wire_payload_json::jsonb",
    )
