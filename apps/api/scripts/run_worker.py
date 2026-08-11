#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
from uuid import uuid4

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.jobs import WorkerStatus
from app.services.jobs import service

STOP = False


def stop(*_):
    global STOP
    STOP = True


async def lease_loop(worker_id, job_id, seconds: float = float(settings.background_worker_heartbeat_seconds)):
    try:
        while True:
            await asyncio.sleep(seconds)
            async with AsyncSessionLocal() as lease_db:
                if not await service.renew_lease(lease_db,worker_id,job_id): return
    except asyncio.CancelledError:
        return


async def main() -> None:
    parser=argparse.ArgumentParser(description="Junior Lawyer durable background worker")
    parser.add_argument("--organization-id", default=os.getenv("BACKGROUND_WORKER_ORG_ID"), help="Organization UUID this worker is allowed to process")
    parser.add_argument("--queues", default="documents,search,evidence,analytics,operations,corpus,bundles,maintenance,default")
    parser.add_argument("--poll", type=float, default=settings.background_worker_poll_seconds)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-key", default=None)
    args=parser.parse_args()
    if not args.organization_id: parser.error("--organization-id or BACKGROUND_WORKER_ORG_ID is required")
    from uuid import UUID
    organization_id=UUID(str(args.organization_id))
    queues=[q.strip() for q in args.queues.split(",") if q.strip()]
    key=args.worker_key or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    signal.signal(signal.SIGINT,stop); signal.signal(signal.SIGTERM,stop)
    async with AsyncSessionLocal() as db:
        worker=await service.register_worker(db,organization_id,key,queues)
        print(f"Worker {key} online · queues={','.join(queues)}")
        while not STOP:
            await service.heartbeat(db,worker)
            job=await service.claim_next(db,worker,queues)
            if not job:
                if args.once: break
                await asyncio.sleep(args.poll); continue
            print(f"claim {job.id} · {job.kind} · attempt {job.attempt_count}/{job.max_attempts}")
            renew=asyncio.create_task(lease_loop(worker.id,job.id))
            try:
                await service.execute_claimed(db,worker,job)
            finally:
                renew.cancel(); await renew
            print(f"done  {job.id} · {job.status}")
            if args.once: break
        worker.status=WorkerStatus.OFFLINE; worker.current_job_id=None
        await db.commit()


if __name__ == "__main__": asyncio.run(main())
