"""Async repository functions for security audit logs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def create_event(
    db: AsyncSession,
    actor_user_id: UUID | None,
    event_type: str,
    success: bool,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Create an audit event without committing the transaction."""
    event = AuditLog(
        actor_user_id=actor_user_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        success=success,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def list_by_event_type(
    db: AsyncSession,
    event_type: str,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    """Return audit events matching an event type, newest first."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.event_type == event_type)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_for_user(
    db: AsyncSession,
    actor_user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    """Return audit events for a user, newest first."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.actor_user_id == actor_user_id)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
