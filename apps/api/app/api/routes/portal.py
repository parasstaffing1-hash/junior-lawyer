from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.crm import Client
from app.schemas.portal import (
    PortalActivationRequest, PortalDashboard, PortalLoginRequest, PortalMessageCreate,
    PortalMessageRead, PortalRequestRead, PortalRequestUpdate, PortalSessionRead, PortalClientApprovalRead, PortalClientApprovalDecision,
)
from app.services.portal import service


router = APIRouter(prefix="/portal", tags=["client-portal"])


async def portal_auth(request: Request, db: AsyncSession = Depends(get_db)):
    authenticated = await service.authenticate(db, request.cookies.get(settings.portal_session_cookie_name, ""))
    if not authenticated: raise HTTPException(401, "Client portal authentication required")
    return authenticated


def _set_session_cookies(response: Response, raw_token: str, csrf: str) -> None:
    response.set_cookie(settings.portal_session_cookie_name, raw_token, httponly=True, secure=settings.security_cookie_secure, samesite=settings.security_cookie_samesite, path="/")
    response.set_cookie("jl_client_csrf", csrf, httponly=False, secure=settings.security_cookie_secure, samesite=settings.security_cookie_samesite, path="/")


def _csrf(request: Request, session) -> None:
    if not service.csrf_valid(session, request.headers.get("x-csrf-token")):
        raise HTTPException(403, "Invalid or missing client portal CSRF token")


@router.post("/activate", response_model=PortalSessionRead)
async def activate(payload: PortalActivationRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user, raw, csrf, session = await service.activate(db, payload.invite_token, payload.password, request)
    client = await db.get(Client, user.client_id)
    _set_session_cookies(response, raw, csrf)
    return PortalSessionRead(email=user.email, client_id=user.client_id, client_name=client.display_name if client else "Client", csrf_token=csrf, expires_at=session.expires_at)


@router.post("/login", response_model=PortalSessionRead)
async def login(payload: PortalLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user, raw, csrf, session = await service.login(db, organization_slug=payload.organization_slug, email=payload.email, password=payload.password, request=request)
    client = await db.get(Client, user.client_id)
    _set_session_cookies(response, raw, csrf)
    return PortalSessionRead(email=user.email, client_id=user.client_id, client_name=client.display_name if client else "Client", csrf_token=csrf, expires_at=session.expires_at)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, session = authenticated; _csrf(request, session); await service.logout(db, actor, session)
    response.delete_cookie(settings.portal_session_cookie_name, path="/"); response.delete_cookie("jl_client_csrf", path="/")


@router.get("/dashboard", response_model=PortalDashboard)
async def dashboard(authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, _ = authenticated
    data = await service.dashboard(db, actor)
    return PortalDashboard(**data)


@router.post("/messages", response_model=PortalMessageRead, status_code=201)
async def send_message(payload: PortalMessageCreate, request: Request, authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, session = authenticated; _csrf(request, session)
    return PortalMessageRead.model_validate(await service.client_message(db, actor, payload.matter_id, payload.body))


@router.patch("/requests/{request_id}", response_model=PortalRequestRead)
async def update_request(request_id: UUID, payload: PortalRequestUpdate, request: Request, authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, session = authenticated; _csrf(request, session)
    return PortalRequestRead.model_validate(await service.update_request(db, actor, request_id, payload.status))


@router.get("/shares/{share_id}/invoice")
async def invoice_share(share_id: UUID, authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, _ = authenticated; return await service.invoice_snapshot_for_share(db, actor, share_id)


@router.get("/shares/{share_id}/document")
async def document_share(share_id: UUID, authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, _ = authenticated; document, path = await service.document_path_for_share(db, actor, share_id)
    return FileResponse(path, media_type=document.mime_type, filename=document.filename)


@router.get("/approvals", response_model=list[PortalClientApprovalRead])
async def approvals(authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, _ = authenticated
    return [PortalClientApprovalRead.model_validate(r) for r in await service.list_client_approvals(db, actor)]


@router.post("/approvals/{approval_id}/respond", response_model=PortalClientApprovalRead)
async def respond_approval(approval_id: UUID, payload: PortalClientApprovalDecision, request: Request, authenticated=Depends(portal_auth), db: AsyncSession = Depends(get_db)):
    actor, session = authenticated; _csrf(request, session)
    return PortalClientApprovalRead.model_validate(await service.respond_client_approval(db, actor, approval_id, payload.status, payload.note))
