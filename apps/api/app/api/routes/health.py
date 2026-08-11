from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.services.documents.storage import check_storage_health

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/health/live")
async def health() -> dict[str, str | None]:
    return {
        "status": "ok",
        "service": "junior-lawyer-api",
        "version": settings.app_version,
        "build_ref": settings.build_ref,
        "commit_ref": settings.commit_ref,
    }


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    checks: dict[str, dict] = {}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["database"] = {"ready": True}
    except Exception as exc:
        checks["database"] = {"ready": False, "error": type(exc).__name__}

    storage = await asyncio.to_thread(check_storage_health)
    checks["storage"] = storage
    ready = all(bool(row.get("ready")) for row in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "version": settings.app_version, "checks": checks}
