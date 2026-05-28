"""API router for version 1 endpoints.

Feature routers will be included here in later steps.
"""

from fastapi import APIRouter

from app.api.v1 import auth, keys, messages


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(keys.router)
api_router.include_router(messages.router)
