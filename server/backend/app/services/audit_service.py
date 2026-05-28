"""Security audit logging service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories import audit_log_repository


MAX_USER_AGENT_LENGTH = 512
MAX_DETAIL_STRING_LENGTH = 200

SAFE_DETAIL_KEYS = {
    "device_id",
    "prekey_count",
    "target_device_id",
    "one_time_prekey_included",
    "reason",
}


async def record_audit_event(
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
    """Strictly create an audit event with sanitized metadata."""
    return await audit_log_repository.create_event(
        db,
        actor_user_id=actor_user_id,
        event_type=event_type,
        success=success,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=_truncate_user_agent(user_agent),
        details=_sanitize_details(details),
    )


async def record_audit_event_best_effort(
    db: AsyncSession,
    actor_user_id: UUID | None,
    event_type: str,
    success: bool,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog | None:
    """Create and commit an audit event without exposing audit DB failures."""
    try:
        event = await record_audit_event(
            db,
            actor_user_id=actor_user_id,
            event_type=event_type,
            success=success,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        await db.commit()
        return event
    except SQLAlchemyError:
        await db.rollback()
        return None


def _truncate_user_agent(user_agent: str | None) -> str | None:
    """Limit user-agent length before storage."""
    if user_agent is None:
        return None
    return user_agent[:MAX_USER_AGENT_LENGTH]


def _sanitize_details(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep only small, explicitly allowed audit metadata."""
    if not details:
        return None

    sanitized: dict[str, Any] = {}
    for key, value in details.items():
        if key not in SAFE_DETAIL_KEYS:
            continue
        safe_value = _sanitize_detail_value(value)
        if safe_value is not None:
            sanitized[key] = safe_value

    return sanitized or None


def _sanitize_detail_value(value: Any) -> str | int | bool:
    """Return a JSON-safe primitive detail value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value[:MAX_DETAIL_STRING_LENGTH]
    if isinstance(value, UUID):
        return str(value)
    return str(value)[:MAX_DETAIL_STRING_LENGTH]
