"""Shared test fixtures."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.config import settings
from app.core.rate_limit import GLOBAL_RATE_LIMITER
from app.db.base import Base


def _get_test_database_url() -> str:
    """Return a guarded test database URL or skip integration tests."""
    if not settings.test_database_url:
        pytest.skip("TEST_DATABASE_URL is not set.")

    if settings.database_url and settings.test_database_url == settings.database_url:
        raise RuntimeError("TEST_DATABASE_URL must not equal DATABASE_URL.")

    database_name = make_url(settings.test_database_url).database or ""
    if "test" not in database_name.lower():
        raise RuntimeError("TEST_DATABASE_URL database name must contain 'test'.")

    return settings.test_database_url


async def _cleanup_database(db: AsyncSession) -> None:
    """Delete data from all known tables in dependency-safe order."""
    for table in reversed(Base.metadata.sorted_tables):
        await db.execute(delete(table))
    await db.commit()


@pytest_asyncio.fixture
async def integration_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a clean AsyncSession for integration tests."""
    test_database_url = _get_test_database_url()
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with session_factory() as db:
            try:
                await _cleanup_database(db)
            except (OSError, SQLAlchemyError) as exc:
                pytest.skip(
                    f"Test database unavailable or not migrated: {exc.__class__.__name__}"
                )

            yield db
            await db.rollback()
            try:
                await _cleanup_database(db)
            except (OSError, SQLAlchemyError):
                await db.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clear_rate_limiter_state() -> AsyncGenerator[None, None]:
    """Keep in-memory rate-limit counters isolated between tests."""
    await GLOBAL_RATE_LIMITER.clear()
    yield
    await GLOBAL_RATE_LIMITER.clear()
