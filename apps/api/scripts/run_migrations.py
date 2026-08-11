from __future__ import annotations

import asyncio
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

LOCK_KEY = 621240024  # Stable project-specific PostgreSQL advisory lock key.


async def main() -> int:
    if settings.app_env.casefold() == "production" and not settings.database_url.startswith("postgresql+asyncpg://"):
        print("Refusing production migration against a non-PostgreSQL database", file=sys.stderr)
        return 2

    if settings.database_url.startswith("postgresql+asyncpg://"):
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
                try:
                    result = subprocess.run(["alembic", "upgrade", "head"], check=False)
                    return int(result.returncode)
                finally:
                    await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        finally:
            await engine.dispose()

    return int(subprocess.run(["alembic", "upgrade", "head"], check=False).returncode)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
