"""Public key relay routes for API v1."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_user_rate_limit, get_current_user, get_db
from app.core import rate_limit
from app.models.user import User
from app.repositories import device_key_repository, one_time_prekey_repository
from app.schemas.device_key import (
    DeviceKeyResponse,
    DeviceKeyUploadRequest,
    PreKeyBundleResponse,
)
from app.schemas.one_time_prekey import (
    OneTimePreKeyBatchUploadRequest,
    OneTimePreKeyResponse,
)
from app.services import audit_service


router = APIRouter(prefix="/keys", tags=["keys"])


@router.put(
    "/devices/{device_id}",
    response_model=DeviceKeyResponse,
)
async def upsert_device_key(
    device_id: Annotated[int, Path(gt=0)],
    request: DeviceKeyUploadRequest,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceKeyResponse:
    """Register or update public device key material for the current user."""
    await enforce_user_rate_limit(
        current_user.id,
        "keys.device_upsert",
        rate_limit.DEVICE_KEY_UPLOAD_RATE_LIMIT,
    )
    if device_id != request.device_id:
        raise _device_id_mismatch_error()

    try:
        device_key = await device_key_repository.create_or_update_device_key(
            db,
            current_user.id,
            request,
        )
        await db.commit()
        await db.refresh(device_key)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device key could not be saved",
        ) from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=current_user.id,
        event_type="keys.device_upserted",
        success=True,
        resource_type="device_key",
        resource_id=device_key.id,
        details={"device_id": device_key.device_id},
    )
    return DeviceKeyResponse.model_validate(device_key)


@router.post(
    "/devices/{device_id}/one-time-prekeys",
    response_model=list[OneTimePreKeyResponse],
)
async def upload_one_time_prekeys(
    device_id: Annotated[int, Path(gt=0)],
    request: OneTimePreKeyBatchUploadRequest,
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OneTimePreKeyResponse]:
    """Upload public one-time prekeys for the current user's device."""
    await enforce_user_rate_limit(
        current_user.id,
        "keys.one_time_prekey_upload",
        rate_limit.ONE_TIME_PREKEY_UPLOAD_RATE_LIMIT,
    )
    if any(prekey.device_id != device_id for prekey in request.prekeys):
        raise _device_id_mismatch_error()

    try:
        prekeys = await one_time_prekey_repository.create_batch(
            db,
            current_user.id,
            device_id,
            request.prekeys,
        )
        await db.commit()
        for prekey in prekeys:
            await db.refresh(prekey)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One-time prekey already exists",
        ) from exc

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=current_user.id,
        event_type="keys.one_time_prekeys_uploaded",
        success=True,
        details={"device_id": device_id, "prekey_count": len(prekeys)},
    )
    return [OneTimePreKeyResponse.model_validate(prekey) for prekey in prekeys]


@router.get(
    "/users/{user_id}/devices/{device_id}/prekey-bundle",
    response_model=PreKeyBundleResponse,
)
async def get_prekey_bundle(
    user_id: UUID,
    device_id: Annotated[int, Path(gt=0)],
    http_request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreKeyBundleResponse:
    """Return public prekey bundle material for session setup."""
    await enforce_user_rate_limit(
        current_user.id,
        "keys.prekey_bundle_fetch",
        rate_limit.PREKEY_BUNDLE_FETCH_RATE_LIMIT,
    )
    device_key = await device_key_repository.get_active_by_user_and_device(
        db,
        user_id,
        device_id,
    )
    if device_key is None:
        await _record_audit_event(
            db,
            http_request,
            actor_user_id=current_user.id,
            event_type="keys.prekey_bundle_missing",
            success=False,
            resource_type="user",
            resource_id=user_id,
            details={"target_device_id": device_id},
        )
        raise _target_device_not_found_error()

    one_time_prekey = await one_time_prekey_repository.get_unused_for_device(
        db,
        user_id,
        device_id,
        for_update=True,
    )
    if one_time_prekey is not None:
        await one_time_prekey_repository.mark_used(db, one_time_prekey)
        await db.commit()
        await db.refresh(one_time_prekey)

    await _record_audit_event(
        db,
        http_request,
        actor_user_id=current_user.id,
        event_type="keys.prekey_bundle_fetched",
        success=True,
        resource_type="device_key",
        resource_id=device_key.id,
        details={
            "target_device_id": device_id,
            "one_time_prekey_included": one_time_prekey is not None,
        },
    )
    return PreKeyBundleResponse(
        registration_id=device_key.registration_id,
        device_id=device_key.device_id,
        identity_key_public_b64=device_key.identity_key_public_b64,
        identity_signing_public_b64=device_key.identity_signing_public_b64,
        signed_prekey_id=device_key.signed_prekey_id,
        signed_prekey_public_b64=device_key.signed_prekey_public_b64,
        signed_prekey_signature_b64=device_key.signed_prekey_signature_b64,
        one_time_prekey_id=one_time_prekey.prekey_id
        if one_time_prekey is not None
        else None,
        one_time_prekey_public_b64=one_time_prekey.prekey_public_b64
        if one_time_prekey is not None
        else None,
    )


def _device_id_mismatch_error() -> HTTPException:
    """Return a safe path/body device ID mismatch error."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Path device_id must match request device_id",
    )


def _target_device_not_found_error() -> HTTPException:
    """Return a safe target device lookup error."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Target device not found",
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
    """Record a key relay audit event without changing route behavior."""
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
