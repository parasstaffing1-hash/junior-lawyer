#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.system_health.scheduler import tick


async def main() -> None:
    parser = argparse.ArgumentParser(description="Junior Lawyer maintenance scheduler")
    parser.add_argument("--organization-id", default=os.getenv("BACKGROUND_WORKER_ORG_ID"))
    parser.add_argument("--poll", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.organization_id:
        parser.error("--organization-id or BACKGROUND_WORKER_ORG_ID is required")
    from uuid import UUID
    organization_id = UUID(str(args.organization_id))
    while True:
        async with AsyncSessionLocal() as db:
            result = await tick(db, organization_id)
            if result["queued_count"]:
                print(result)
        if args.once:
            return
        await asyncio.sleep(max(10.0, args.poll))


if __name__ == "__main__":
    asyncio.run(main())
