"""Direct 1:1 message relay routes for API v1."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_user_rate_limit, get_current_user, get_db
from app.core import rate_limit
from app.models.user import User
from app.schemas.common import PaginationParams, SuccessResponse
from app.schemas.message import (
    DirectMessageCreateRequest,
    DirectMessageForwardRequest,
    MessageResponse,
)
from app.services import audit_service, message_service
from app.services.message_service import (
    InvalidDeviceError,
    InvalidPreKeyError,
    MessageAccessDeniedError,
    MessageNotFoundError,
    RecipientNotFoundError,
)


router = APIRouter(prefix="/messages", tags=["messages"])


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    request: DirectMessageCreateRequest,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Create a direct 1:1 encrypted relay message."""
    actor_user_id = current_user.id
    await enforce_user_rate_limit(
        actor_user_id,
        "messages.send",
        rate_limit.MESSAGE_SEND_RATE_LIMIT,
    )
    try:
        message = await message_service.send_message(db, current_user, request)
    except RecipientNotFoundError as exc:
        raise _not_found_error() from exc
    except (InvalidDeviceError, InvalidPreKeyError) as exc:
        raise _bad_request_error() from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=actor_user_id,
        event_type="message.sent",
        success=True,
        resource_type="message",
        resource_id=message.id,
    )
    return MessageResponse.model_validate(message)


@router.get("/received", response_model=list[MessageResponse])
async def list_received_messages(
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
) -> list[MessageResponse]:
    """List direct messages visible to the current user as recipient."""
    _ = http_request
    await enforce_user_rate_limit(
        current_user.id,
        "messages.list_received",
        rate_limit.MESSAGE_READ_RATE_LIMIT,
    )
    messages = await message_service.list_received_messages(
        db,
        current_user,
        pagination,
    )
    return [MessageResponse.model_validate(message) for message in messages]


@router.get("/sent", response_model=list[MessageResponse])
async def list_sent_messages(
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
) -> list[MessageResponse]:
    """List direct messages visible to the current user as sender."""
    _ = http_request
    await enforce_user_rate_limit(
        current_user.id,
        "messages.list_sent",
        rate_limit.MESSAGE_READ_RATE_LIMIT,
    )
    messages = await message_service.list_sent_messages(db, current_user, pagination)
    return [MessageResponse.model_validate(message) for message in messages]


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Return a direct message only if the current user can access it."""
    actor_user_id = current_user.id
    await enforce_user_rate_limit(
        actor_user_id,
        "messages.fetch",
        rate_limit.MESSAGE_READ_RATE_LIMIT,
    )
    try:
        message = await message_service.get_message_for_user(
            db,
            current_user,
            message_id,
        )
    except MessageNotFoundError as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=actor_user_id,
            event_type="message.fetch_denied",
            success=False,
            resource_type="message",
            resource_id=message_id,
            details={"reason": "not_found_or_inaccessible"},
        )
        raise _not_found_error() from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=actor_user_id,
        event_type="message.fetched",
        success=True,
        resource_type="message",
        resource_id=message.id,
    )
    return MessageResponse.model_validate(message)


@router.post(
    "/{message_id}/forward",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def forward_message(
    message_id: UUID,
    request: DirectMessageForwardRequest,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Forward a message by storing a newly encrypted opaque payload."""
    actor_user_id = current_user.id
    await enforce_user_rate_limit(
        actor_user_id,
        "messages.forward",
        rate_limit.MESSAGE_FORWARD_RATE_LIMIT,
    )
    try:
        message = await message_service.forward_message(
            db,
            current_user,
            message_id,
            request,
        )
    except (MessageNotFoundError, MessageAccessDeniedError) as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=actor_user_id,
            event_type="message.forward_denied",
            success=False,
            resource_type="message",
            resource_id=message_id,
            details={"reason": "not_found_or_inaccessible"},
        )
        raise _not_found_error() from exc
    except RecipientNotFoundError as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=actor_user_id,
            event_type="message.forward_denied",
            success=False,
            resource_type="message",
            resource_id=message_id,
            details={"reason": "invalid_recipient"},
        )
        raise _not_found_error() from exc
    except InvalidDeviceError as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=actor_user_id,
            event_type="message.forward_denied",
            success=False,
            resource_type="message",
            resource_id=message_id,
            details={"reason": "invalid_device"},
        )
        raise _bad_request_error() from exc
    except InvalidPreKeyError as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=actor_user_id,
            event_type="message.forward_denied",
            success=False,
            resource_type="message",
            resource_id=message_id,
            details={"reason": "invalid_prekey"},
        )
        raise _bad_request_error() from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=actor_user_id,
        event_type="message.forwarded",
        success=True,
        resource_type="message",
        resource_id=message.id,
    )
    return MessageResponse.model_validate(message)


@router.post("/{message_id}/revoke", response_model=MessageResponse)
async def revoke_message(
    message_id: UUID,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Revoke recipient access to a sender-owned message."""
    actor_user_id = current_user.id
    await enforce_user_rate_limit(
        actor_user_id,
        "messages.revoke",
        rate_limit.MESSAGE_READ_RATE_LIMIT,
    )
    try:
        message = await message_service.revoke_message_access(
            db,
            current_user,
            message_id,
        )
    except (MessageNotFoundError, MessageAccessDeniedError) as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=actor_user_id,
            event_type="message.revoke_denied",
            success=False,
            resource_type="message",
            resource_id=message_id,
            details={"reason": "not_found_or_inaccessible"},
        )
        raise _not_found_error() from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=actor_user_id,
        event_type="message.revoked",
        success=True,
        resource_type="message",
        resource_id=message.id,
    )
    return MessageResponse.model_validate(message)


@router.delete("/{message_id}", response_model=SuccessResponse)
async def delete_message(
    message_id: UUID,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    """Hide a direct message from the current user without hard deletion."""
    actor_user_id = current_user.id
    await enforce_user_rate_limit(
        actor_user_id,
        "messages.delete",
        rate_limit.MESSAGE_READ_RATE_LIMIT,
    )
    try:
        message = await message_service.delete_message_for_user(
            db,
            current_user,
            message_id,
        )
    except (MessageNotFoundError, MessageAccessDeniedError) as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=actor_user_id,
            event_type="message.delete_denied",
            success=False,
            resource_type="message",
            resource_id=message_id,
            details={"reason": "not_found_or_inaccessible"},
        )
        raise _not_found_error() from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=actor_user_id,
        event_type="message.deleted",
        success=True,
        resource_type="message",
        resource_id=message.id,
    )
    return SuccessResponse(message="Message deleted")


def _not_found_error() -> HTTPException:
    """Return a safe not-found response for inaccessible message resources."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Message not found",
    )


def _bad_request_error() -> HTTPException:
    """Return a safe bad-request response for invalid message inputs."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Message could not be processed",
    )


def _get_client_ip(request: Request) -> str | None:
    """Return the direct client IP when FastAPI provides it."""
    if request.client is None:
        return None
    return request.client.host


def _get_user_agent(request: Request) -> str | None:
    """Return the user-agent header without proxy-aware parsing."""
    return request.headers.get("user-agent")


async def _record_audit_event(
    db: AsyncSession,
    request: Request,
    actor_user_id: UUID,
    event_type: str,
    success: bool,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    """Record a message audit event without changing route behavior."""
    await audit_service.record_audit_event_best_effort(
        db,
        actor_user_id=actor_user_id,
        event_type=event_type,
        success=success,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
        details=details,
    )
