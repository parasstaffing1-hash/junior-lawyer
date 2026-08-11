from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.security.context import reset_current_actor, set_current_actor
from app.services.security.service import authenticate_session, csrf_valid


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
AUTH_EXEMPT_PREFIXES = (f"{settings.api_v1_prefix}/portal", f"{settings.api_v1_prefix}/integrations/webhooks/")
AUTH_EXEMPT_PATHS = {
    f"{settings.api_v1_prefix}/security/auth/login",
    f"{settings.api_v1_prefix}/security/bootstrap",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        context_token = set_current_actor(None)
        try:
            if settings.security_enforce_auth and request.url.path.startswith(settings.api_v1_prefix):
                if request.url.path not in AUTH_EXEMPT_PATHS and not any(request.url.path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES):
                    raw_token = request.cookies.get(settings.security_session_cookie_name, "")
                    async with AsyncSessionLocal() as db:
                        authenticated = await authenticate_session(db, raw_token)
                        if not authenticated:
                            return self._secure(JSONResponse({"detail": "Authentication required"}, status_code=401))
                        actor, session = authenticated
                        request.state.actor = actor
                        request.state.session_id = session.id
                        reset_current_actor(context_token)
                        context_token = set_current_actor(actor)
                        if request.method.upper() not in SAFE_METHODS:
                            csrf = request.headers.get("x-csrf-token")
                            if not csrf_valid(session, csrf):
                                return self._secure(JSONResponse({"detail": "Invalid or missing CSRF token"}, status_code=403))
            response = await call_next(request)
            return self._secure(response)
        finally:
            reset_current_actor(context_token)

    @staticmethod
    def _secure(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        response.headers.setdefault("Cache-Control", "no-store")
        if settings.app_env.casefold() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.security_hsts_seconds}; includeSubDomains",
            )
        return response
