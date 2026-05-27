"""Shared FastAPI dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db as _get_db


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for route dependencies."""
    async for session in _get_db():
        yield session
