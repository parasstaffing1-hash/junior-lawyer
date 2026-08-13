from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging
import time
from uuid import uuid4

from fastapi import Request

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.ai import router as ai_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.billing import router as billing_router
from app.api.routes.case_lookup import router as case_lookup_router
from app.api.routes.client_money import router as client_money_router
from app.api.routes.collaboration import router as collaboration_router
from app.api.routes.portal import router as portal_router
from app.api.routes.contracts import router as contracts_router
from app.api.routes.contract_reviews import router as contract_reviews_router
from app.api.routes.crm import router as crm_router
from app.api.routes.documents import router as documents_router
from app.api.routes.drafting import router as drafting_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.experience import router as experience_router
from app.api.routes.health import router as health_router
from app.api.routes.language import router as language_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.legal_data import router as legal_data_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.matters import router as matters_router
from app.api.routes.operations import router as operations_router
from app.api.routes.research import router as research_router
from app.api.routes.remedies import router as remedies_router
from app.api.routes.security import router as security_router
from app.api.routes.search import router as search_router
from app.api.routes.system_health import router as system_health_router
from app.api.routes.tools import router as tools_router
from app.api.routes.qa import router as qa_router
from app.api.routes.release import router as release_router
from app.api.routes.procedure import router as procedure_router
from app.api.routes.deployment import router as deployment_router
from app.api.routes.validation import router as validation_router
from app.core.config import settings
from app.core.structured_logging import configure_structured_logging
from app.db.base import Base
from app.db.session import engine
from app.services.security.middleware import SecurityMiddleware
from app.services.security.rate_limit import RateLimitMiddleware

configure_structured_logging()
request_logger = logging.getLogger("junior_lawyer.http")

# Import models before create_all so SQLAlchemy metadata contains every table.
from app import models  # noqa: F401,E402


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Development convenience. Production deployments should run `alembic upgrade head`.
    if settings.app_env.casefold() == "development":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    _log_ai_configuration()
    yield


def _log_ai_configuration() -> None:
    """Say at startup whether a model is actually reachable.

    Misconfigured AI settings fail silently: the router simply blocks every
    run, which reads like a product decision rather than a missing key. One
    line at boot turns that into something you can see in the deploy log.
    """
    logger = logging.getLogger("junior_lawyer.ai")
    if not settings.ai_enabled:
        logger.info("ai_disabled", extra={"event": "ai.config", "reason": "AI_ENABLED is false"})
        return

    from app.services.ai.providers import ProviderRegistry

    registry = ProviderRegistry.from_settings(settings)
    if not registry.providers:
        missing = [
            name
            for name, value in (
                ("AI_REMOTE_BASE_URL", settings.ai_remote_base_url),
                ("AI_REMOTE_MODEL", settings.ai_remote_model),
                ("AI_REMOTE_API_KEY", settings.ai_remote_api_key),
            )
            if not value
        ]
        logger.warning(
            "ai_enabled_but_no_provider",
            extra={
                "event": "ai.config",
                # Names only. Never the values.
                "missing_settings": missing or ["AI_REMOTE_ENABLED / AI_LOCAL_ENABLED"],
            },
        )
        return

    logger.info(
        "ai_ready",
        extra={
            "event": "ai.config",
            "providers": sorted(registry.providers),
            "remote_model": settings.ai_remote_model,
            "spare_credentials": len(settings.ai_remote_fallback_api_keys),
        },
    )


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)



@app.middleware("http")
async def structured_request_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        latency = round((time.perf_counter() - started) * 1000)
        request_logger.exception("request_failed", extra={"request_id": request_id, "method": request.method, "path": request.url.path, "status_code": 500, "latency_ms": latency, "event": "http.request"})
        raise
    latency = round((time.perf_counter() - started) * 1000)
    response.headers["x-request-id"] = request_id
    request_logger.info("request_completed", extra={"request_id": request_id, "method": request.method, "path": request.url.path, "status_code": response.status_code, "latency_ms": latency, "event": "http.request"})
    return response

app.add_middleware(SecurityMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ai_router, prefix=settings.api_v1_prefix)
app.include_router(analytics_router, prefix=settings.api_v1_prefix)
app.include_router(billing_router, prefix=settings.api_v1_prefix)
app.include_router(case_lookup_router, prefix=settings.api_v1_prefix)
app.include_router(client_money_router, prefix=settings.api_v1_prefix)
app.include_router(collaboration_router, prefix=settings.api_v1_prefix)
app.include_router(portal_router, prefix=settings.api_v1_prefix)
app.include_router(contracts_router, prefix=settings.api_v1_prefix)
app.include_router(contract_reviews_router, prefix=settings.api_v1_prefix)
app.include_router(crm_router, prefix=settings.api_v1_prefix)
app.include_router(documents_router, prefix=settings.api_v1_prefix)
app.include_router(drafting_router, prefix=settings.api_v1_prefix)
app.include_router(evidence_router, prefix=settings.api_v1_prefix)
app.include_router(experience_router, prefix=settings.api_v1_prefix)
app.include_router(intelligence_router, prefix=settings.api_v1_prefix)
app.include_router(integrations_router, prefix=settings.api_v1_prefix)
app.include_router(knowledge_router, prefix=settings.api_v1_prefix)
app.include_router(legal_data_router, prefix=settings.api_v1_prefix)
app.include_router(jobs_router, prefix=settings.api_v1_prefix)
app.include_router(language_router, prefix=settings.api_v1_prefix)
app.include_router(matters_router, prefix=settings.api_v1_prefix)
app.include_router(operations_router, prefix=settings.api_v1_prefix)
app.include_router(research_router, prefix=settings.api_v1_prefix)
app.include_router(remedies_router, prefix=settings.api_v1_prefix)
app.include_router(search_router, prefix=settings.api_v1_prefix)
app.include_router(security_router, prefix=settings.api_v1_prefix)
app.include_router(system_health_router, prefix=settings.api_v1_prefix)
app.include_router(qa_router, prefix=settings.api_v1_prefix)
app.include_router(release_router, prefix=settings.api_v1_prefix)
app.include_router(procedure_router, prefix=settings.api_v1_prefix)
app.include_router(deployment_router, prefix=settings.api_v1_prefix)
app.include_router(validation_router, prefix=settings.api_v1_prefix)
app.include_router(tools_router, prefix=settings.api_v1_prefix)
