"""Check that the async database connection can run a simple query."""

import asyncio
import sys

from sqlalchemy import text


async def check_database_connection() -> None:
    """Run a safe database connectivity check."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            raise RuntimeError("Unexpected database response.")


async def main() -> int:
    """Return a process exit code for the database connectivity check."""
    engine = None
    try:
        from app.db.session import engine as async_engine

        engine = async_engine
        await check_database_connection()
    except Exception as exc:
        print(f"Database connection failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            await engine.dispose()

    print("Database connection successful")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
