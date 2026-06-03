"""Blockchain anchor routes for API v1."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_ip_rate_limit, enforce_user_rate_limit, get_current_user, get_db
from app.core import rate_limit
from app.models.user import User
from app.schemas.blockchain_anchor import (
    BlockchainAnchorResponse,
    BlockchainMessageAnchorCreateRequest,
    BlockchainVerifyRequest,
    BlockchainVerifyResponse,
)
from app.services import audit_service, blockchain_anchor_service
from app.services.blockchain_anchor_service import BlockchainAnchorNotFoundError


router = APIRouter(prefix="/blockchain", tags=["blockchain"])


@router.post("/anchors", response_model=BlockchainAnchorResponse)
async def create_blockchain_anchor(
    request: BlockchainMessageAnchorCreateRequest,
    response: Response,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BlockchainAnchorResponse:
    """Create a pending integrity anchor for an accessible encrypted message."""
    await enforce_user_rate_limit(
        current_user.id,
        "blockchain.anchor_create",
        rate_limit.BLOCKCHAIN_WRITE_RATE_LIMIT,
    )
    try:
        result = await blockchain_anchor_service.create_message_anchor(
            db,
            current_user,
            request,
        )
    except BlockchainAnchorNotFoundError as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=current_user.id,
            event_type="blockchain.anchor_create_denied",
            success=False,
            resource_type="message",
            resource_id=request.message_id,
            details={"reason": "not_found_or_inaccessible"},
        )
        raise _anchor_not_found_error() from exc

    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    await _record_audit_event(
        db,
        http_request,
        actor_user_id=current_user.id,
        event_type="blockchain.anchor_created" if result.created else "blockchain.anchor_reused",
        success=True,
        resource_type="blockchain_anchor",
        resource_id=result.anchor.id,
        details={"message_id": str(result.anchor.message_id)},
    )
    return BlockchainAnchorResponse.model_validate(result.anchor)


@router.get("/anchors/{anchor_id}", response_model=BlockchainAnchorResponse)
async def get_blockchain_anchor(
    anchor_id: UUID,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BlockchainAnchorResponse:
    """Return anchor status."""
    await enforce_ip_rate_limit(
        http_request,
        "blockchain.anchor_read",
        rate_limit.BLOCKCHAIN_READ_RATE_LIMIT,
    )
    try:
        anchor = await blockchain_anchor_service.get_anchor_public(
            db,
            anchor_id,
        )
    except BlockchainAnchorNotFoundError as exc:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=None,
            event_type="blockchain.anchor_fetch_denied",
            success=False,
            resource_type="blockchain_anchor",
            resource_id=anchor_id,
            details={"reason": "not_found"},
        )
        raise _anchor_not_found_error() from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=None,
        event_type="blockchain.anchor_fetched",
        success=True,
        resource_type="blockchain_anchor",
        resource_id=anchor.id,
    )
    return BlockchainAnchorResponse.model_validate(anchor)


@router.post("/verify", response_model=BlockchainVerifyResponse)
async def verify_blockchain_anchor(
    request: BlockchainVerifyRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BlockchainVerifyResponse:
    """Verify digest/root metadata against confirmed backend anchor records."""
    await enforce_ip_rate_limit(
        http_request,
        "blockchain.verify",
        rate_limit.BLOCKCHAIN_READ_RATE_LIMIT,
    )
    return await blockchain_anchor_service.verify_anchor_metadata(db, request)


def _anchor_not_found_error() -> HTTPException:
    """Return a safe not-found response for inaccessible anchors."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Anchor not found",
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
    actor_user_id: UUID | None,
    event_type: str,
    success: bool,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    """Record a blockchain audit event without changing route behavior."""
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
