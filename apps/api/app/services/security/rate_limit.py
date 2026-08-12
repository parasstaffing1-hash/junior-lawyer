"""Fixed-window request rate limiting.

Scope and honesty about it: counters live in this process's memory. With more
than one API replica the effective limit is per replica, not per cluster. That
is still worth having — it bounds credential stuffing and runaway clients
against any single replica — but it is not a substitute for a shared limiter at
the reverse proxy or a Redis-backed counter, and it must not be described as
one. Junior Lawyer has no Redis dependency, so the shared implementation is
deliberately left to the proxy layer.

Authentication endpoints get a much tighter budget than ordinary traffic
because they are the ones worth guessing against.
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

# Paths where a wrong guess is worth making repeatedly.
SENSITIVE_SUFFIXES = (
    "/security/auth/login",
    "/security/bootstrap",
    "/portal/auth/login",
    "/portal/auth/activate",
)


class FixedWindowCounter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._lock = Lock()

    def hit(self, key: tuple[str, str], *, limit: int, window: int) -> tuple[bool, int]:
        """Record a request. Returns (allowed, seconds until the window frees up)."""
        now = time.monotonic()
        cutoff = now - window
        with self._lock:
            timestamps = self._hits[key]
            # Drop expired entries so the dict does not grow without bound.
            timestamps[:] = [value for value in timestamps if value > cutoff]
            if len(timestamps) >= limit:
                return False, max(1, int(window - (now - timestamps[0])))
            timestamps.append(now)
            if not timestamps:
                del self._hits[key]
            return True, 0


_counter = FixedWindowCounter()


def client_key(request: Request) -> str:
    """Identify the caller.

    X-Forwarded-For is only trusted when the deployment says it sits behind a
    proxy; otherwise a client could spoof the header and evade the limit.
    """
    if settings.security_trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        sensitive = any(path.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)
        limit = (
            settings.rate_limit_auth_requests if sensitive else settings.rate_limit_requests
        )
        window = settings.rate_limit_window_seconds

        allowed, retry_after = _counter.hit(
            (client_key(request), "auth" if sensitive else "general"),
            limit=limit,
            window=window,
        )
        if not allowed:
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
