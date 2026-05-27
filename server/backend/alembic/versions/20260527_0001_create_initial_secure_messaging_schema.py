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
    """Create the initial secure messaging schema."""
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
        "user_key_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encryption_public_key", sa.Text(), nullable=False),
        sa.Column("signing_public_key", sa.Text(), nullable=False),
        sa.Column("key_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("key_algorithm", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "key_fingerprint",
            name="uq_user_key_bundles_key_fingerprint",
        ),
    )
    op.create_index(
        "ix_user_key_bundles_revoked_at",
        "user_key_bundles",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_key_bundles_user_id",
        "user_key_bundles",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_key_bundles_user_id_is_active",
        "user_key_bundles",
        ["user_id", "is_active"],
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
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_key_fingerprint", sa.String(length=128), nullable=False),
        sa.Column(
            "message_type",
            sa.String(length=30),
            server_default="direct",
            nullable=False,
            comment="Allowed: direct, forwarded, system. system is reserved.",
        ),
        sa.Column(
            "forwarded_from_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "encryption_scheme",
            sa.String(length=50),
            server_default="client_aes_gcm_v1",
            nullable=False,
        ),
        sa.Column(
            "algorithm",
            sa.String(length=50),
            server_default="AES-256-GCM",
            nullable=False,
        ),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("associated_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ciphertext_hash", sa.String(length=128), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "message_type IN ('direct', 'forwarded', 'system')",
            name="ck_messages_message_type",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["forwarded_from_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_ciphertext_hash",
        "messages",
        ["ciphertext_hash"],
        unique=True,
    )
    op.create_index(
        "ix_messages_conversation_id",
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_messages_conversation_id_sent_at",
        "messages",
        ["conversation_id", "sent_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_deleted_at",
        "messages",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_forwarded_from_message_id",
        "messages",
        ["forwarded_from_message_id"],
        unique=False,
    )
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"], unique=False)
    op.create_index(
        "ix_messages_sender_id_nonce",
        "messages",
        ["sender_id", "nonce"],
        unique=False,
    )
    op.create_index(
        "ix_messages_sender_key_fingerprint",
        "messages",
        ["sender_key_fingerprint"],
        unique=False,
    )
    op.create_index("ix_messages_sent_at", "messages", ["sent_at"], unique=False)

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

    op.create_table(
        "message_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_key_fingerprint", sa.String(length=128), nullable=False),
        sa.Column(
            "key_encryption_scheme",
            sa.String(length=100),
            server_default="public_key_encrypted_message_key_v1",
            nullable=False,
        ),
        sa.Column("encrypted_message_key", sa.Text(), nullable=False),
        sa.Column("access_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "recipient_id",
            name="uq_message_recipients_message_id_recipient_id",
        ),
    )
    op.create_index(
        "ix_message_recipients_access_revoked_at",
        "message_recipients",
        ["access_revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_message_recipients_deleted_at",
        "message_recipients",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_message_recipients_message_id",
        "message_recipients",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        "ix_message_recipients_recipient_id",
        "message_recipients",
        ["recipient_id"],
        unique=False,
    )
    op.create_index(
        "ix_message_recipients_recipient_key_fingerprint",
        "message_recipients",
        ["recipient_key_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the initial secure messaging schema."""
    op.drop_index(
        "ix_message_recipients_recipient_key_fingerprint",
        table_name="message_recipients",
    )
    op.drop_index("ix_message_recipients_recipient_id", table_name="message_recipients")
    op.drop_index("ix_message_recipients_message_id", table_name="message_recipients")
    op.drop_index("ix_message_recipients_deleted_at", table_name="message_recipients")
    op.drop_index(
        "ix_message_recipients_access_revoked_at",
        table_name="message_recipients",
    )
    op.drop_table("message_recipients")

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

    op.drop_index("ix_messages_sent_at", table_name="messages")
    op.drop_index("ix_messages_sender_key_fingerprint", table_name="messages")
    op.drop_index("ix_messages_sender_id_nonce", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_forwarded_from_message_id", table_name="messages")
    op.drop_index("ix_messages_deleted_at", table_name="messages")
    op.drop_index("ix_messages_conversation_id_sent_at", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_messages_ciphertext_hash", table_name="messages")
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

    op.drop_index(
        "ix_user_key_bundles_user_id_is_active",
        table_name="user_key_bundles",
    )
    op.drop_index("ix_user_key_bundles_user_id", table_name="user_key_bundles")
    op.drop_index("ix_user_key_bundles_revoked_at", table_name="user_key_bundles")
    op.drop_table("user_key_bundles")

    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_revoked_at", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_expires_at", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")

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
