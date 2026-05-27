"""Audit log response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.common import ORMResponseModel


class AuditLogResponse(ORMResponseModel):
    """Read-only audit log response for future restricted endpoints."""

    id: UUID
    actor_user_id: UUID | None
    event_type: str
    resource_type: str | None
    resource_id: UUID | None
    success: bool
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any] | None
    created_at: datetime
