"""User discovery response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.common import ORMResponseModel


class UserDeviceSummary(ORMResponseModel):
    """Public-safe device summary for user discovery."""

    device_id: int = Field(gt=0)
    is_active: bool


class UserByUsernameResponse(ORMResponseModel):
    """Public-safe user lookup response for direct 1:1 messaging."""

    id: UUID
    username: str
    devices: list[UserDeviceSummary]
