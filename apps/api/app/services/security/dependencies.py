from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.security.context import ActorContext, get_current_actor
from app.services.security.service import authenticate_session


async def require_actor(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ActorContext:
    actor = getattr(request.state, "actor", None) or get_current_actor()
    if actor:
        return actor
    token = request.cookies.get(settings.security_session_cookie_name, "")
    authenticated = await authenticate_session(db, token)
    if not authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    actor, _ = authenticated
    return actor
