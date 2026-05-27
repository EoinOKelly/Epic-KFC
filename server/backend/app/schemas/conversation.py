"""Conversation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ORMResponseModel, StrictRequestModel


class ConversationCreateRequest(StrictRequestModel):
    """Create a conversation container for future relay messages."""

    title: str | None = Field(default=None, max_length=120)
    member_ids: list[UUID] | None = Field(default=None, max_length=50)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        """Trim title and reject empty values."""
        if value is None:
            return None
        title = value.strip()
        if not title:
            raise ValueError("Title must not be empty.")
        return title

    @model_validator(mode="after")
    def validate_unique_members(self) -> Self:
        """Reject duplicate member IDs."""
        if self.member_ids is None:
            return self
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("member_ids must not contain duplicates.")
        return self


class ConversationResponse(ORMResponseModel):
    """Conversation response."""

    id: UUID
    created_by: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ConversationMemberResponse(ORMResponseModel):
    """Conversation membership response."""

    id: UUID
    conversation_id: UUID
    user_id: UUID
    member_role: str
    added_by: UUID | None
    added_at: datetime
    revoked_at: datetime | None
    is_active: bool
