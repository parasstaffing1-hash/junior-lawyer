from __future__ import annotations

import asyncio
import json

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.services.deployment.readiness import evaluate_runtime_readiness
from app.services.documents.storage import check_storage_health


async def main() -> int:
    result = evaluate_runtime_readiness(settings)
    runtime_checks: list[dict] = []
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        runtime_checks.append({"key": "database_connectivity", "passed": True, "critical": True, "message": "Database SELECT 1 succeeded"})
    except Exception as exc:
        runtime_checks.append({"key": "database_connectivity", "passed": False, "critical": True, "message": f"Database connection failed: {type(exc).__name__}"})

    storage = await asyncio.to_thread(check_storage_health)
    runtime_checks.append({"key": "storage_connectivity", "passed": bool(storage.get("ready")), "critical": True, "message": f"Storage backend: {storage.get('backend', 'unknown')}" + (f" ({storage.get('error')})" if storage.get("error") else "")})
    result["checks"].extend(runtime_checks)
    result["ready"] = result["ready"] and all(row["passed"] for row in runtime_checks if row["critical"])
    print(json.dumps(result, indent=2, default=str))
    await engine.dispose()
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
