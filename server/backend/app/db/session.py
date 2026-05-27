"""Async SQLAlchemy session setup."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import settings


if not settings.database_url:
    raise RuntimeError("DATABASE_URL must be set before database sessions can be used.")

if not settings.database_url.startswith("postgresql+asyncpg://"):
    raise RuntimeError("DATABASE_URL must use the postgresql+asyncpg scheme.")


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        yield session
