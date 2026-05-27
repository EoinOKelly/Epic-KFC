"""create initial secure messaging schema

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260527_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial relay-oriented secure messaging schema."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_actor_user_id",
        "audit_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"], unique=False)
    op.create_index(
        "ix_audit_logs_resource_type_resource_id",
        "audit_logs",
        ["resource_type", "resource_id"],
        unique=False,
    )
    op.create_index("ix_audit_logs_success", "audit_logs", ["success"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_created_by",
        "conversations",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        "ix_conversations_deleted_at",
        "conversations",
        ["deleted_at"],
        unique=False,
    )

    op.create_table(
        "device_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("identity_key_public_b64", sa.Text(), nullable=False),
        sa.Column("identity_signing_public_b64", sa.Text(), nullable=False),
        sa.Column("signed_prekey_id", sa.Integer(), nullable=False),
        sa.Column("signed_prekey_public_b64", sa.Text(), nullable=False),
        sa.Column("signed_prekey_signature_b64", sa.Text(), nullable=False),
        sa.Column(
            "signed_prekey_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "device_id", name="uq_device_keys_user_id_device_id"),
    )
    op.create_index("ix_device_keys_revoked_at", "device_keys", ["revoked_at"], unique=False)
    op.create_index("ix_device_keys_user_id", "device_keys", ["user_id"], unique=False)
    op.create_index(
        "ix_device_keys_user_id_is_active",
        "device_keys",
        ["user_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "one_time_prekeys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("prekey_id", sa.Integer(), nullable=False),
        sa.Column("prekey_public_b64", sa.Text(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "device_id",
            "prekey_id",
            name="uq_one_time_prekeys_user_id_device_id_prekey_id",
        ),
    )
    op.create_index(
        "ix_one_time_prekeys_user_id_device_id",
        "one_time_prekeys",
        ["user_id", "device_id"],
        unique=False,
    )
    op.create_index(
        "ix_one_time_prekeys_user_id_device_id_used_at",
        "one_time_prekeys",
        ["user_id", "device_id", "used_at"],
        unique=False,
    )

    op.create_table(
        "refresh_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("jti", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_refresh_sessions_jti"),
        sa.UniqueConstraint(
            "refresh_token_hash",
            name="uq_refresh_sessions_refresh_token_hash",
        ),
    )
    op.create_index(
        "ix_refresh_sessions_expires_at",
        "refresh_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_refresh_sessions_revoked_at",
        "refresh_sessions",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_refresh_sessions_user_id",
        "refresh_sessions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "conversation_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "member_role",
            sa.String(length=30),
            server_default="member",
            nullable=False,
        ),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "user_id",
            name="uq_conversation_members_conversation_id_user_id",
        ),
    )
    op.create_index(
        "ix_conversation_members_conversation_id",
        "conversation_members",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_members_conversation_id_is_active",
        "conversation_members",
        ["conversation_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_members_revoked_at",
        "conversation_members",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_members_user_id",
        "conversation_members",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_device_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_device_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("wire_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("consumed_one_time_prekey_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_conversation_id",
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index("ix_messages_deleted_at", "messages", ["deleted_at"], unique=False)
    op.create_index(
        "ix_messages_recipient_user_id_device_id_created_at",
        "messages",
        ["recipient_user_id", "recipient_device_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_sender_user_id_created_at",
        "messages",
        ["sender_user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "blockchain_anchors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("digest", sa.String(length=128), nullable=False),
        sa.Column("transaction_hash", sa.String(length=255), nullable=True),
        sa.Column("contract_address", sa.String(length=255), nullable=True),
        sa.Column("chain", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "message_id IS NOT NULL OR conversation_id IS NOT NULL",
            name="ck_blockchain_anchors_message_or_conversation",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_blockchain_anchors_conversation_id",
        "blockchain_anchors",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_blockchain_anchors_digest",
        "blockchain_anchors",
        ["digest"],
        unique=False,
    )
    op.create_index(
        "ix_blockchain_anchors_message_id",
        "blockchain_anchors",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        "ix_blockchain_anchors_status",
        "blockchain_anchors",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_blockchain_anchors_transaction_hash",
        "blockchain_anchors",
        ["transaction_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the initial relay-oriented secure messaging schema."""
    op.drop_index(
        "ix_blockchain_anchors_transaction_hash",
        table_name="blockchain_anchors",
    )
    op.drop_index("ix_blockchain_anchors_status", table_name="blockchain_anchors")
    op.drop_index("ix_blockchain_anchors_message_id", table_name="blockchain_anchors")
    op.drop_index("ix_blockchain_anchors_digest", table_name="blockchain_anchors")
    op.drop_index(
        "ix_blockchain_anchors_conversation_id",
        table_name="blockchain_anchors",
    )
    op.drop_table("blockchain_anchors")

    op.drop_index("ix_messages_sender_user_id_created_at", table_name="messages")
    op.drop_index(
        "ix_messages_recipient_user_id_device_id_created_at",
        table_name="messages",
    )
    op.drop_index("ix_messages_deleted_at", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversation_members_user_id", table_name="conversation_members")
    op.drop_index("ix_conversation_members_revoked_at", table_name="conversation_members")
    op.drop_index(
        "ix_conversation_members_conversation_id_is_active",
        table_name="conversation_members",
    )
    op.drop_index(
        "ix_conversation_members_conversation_id",
        table_name="conversation_members",
    )
    op.drop_table("conversation_members")

    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_revoked_at", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_expires_at", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")

    op.drop_index(
        "ix_one_time_prekeys_user_id_device_id_used_at",
        table_name="one_time_prekeys",
    )
    op.drop_index(
        "ix_one_time_prekeys_user_id_device_id",
        table_name="one_time_prekeys",
    )
    op.drop_table("one_time_prekeys")

    op.drop_index("ix_device_keys_user_id_is_active", table_name="device_keys")
    op.drop_index("ix_device_keys_user_id", table_name="device_keys")
    op.drop_index("ix_device_keys_revoked_at", table_name="device_keys")
    op.drop_table("device_keys")

    op.drop_index("ix_conversations_deleted_at", table_name="conversations")
    op.drop_index("ix_conversations_created_by", table_name="conversations")
    op.drop_table("conversations")

    op.drop_index("ix_audit_logs_success", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
