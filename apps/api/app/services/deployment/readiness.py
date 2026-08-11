from __future__ import annotations

from urllib.parse import urlparse


def _is_https(value: str) -> bool:
    try:
        return urlparse(value).scheme.casefold() == "https"
    except Exception:
        return False


def evaluate_runtime_readiness(settings) -> dict:
    """Deterministic production readiness checklist; never reads secret values into output."""
    checks: list[dict] = []

    def add(key: str, passed: bool, message: str, *, critical: bool = True) -> None:
        checks.append({"key": key, "passed": bool(passed), "critical": critical, "message": message})

    add("production_env", str(settings.app_env).casefold() == "production", "APP_ENV must be production")
    add("debug_disabled", not bool(settings.debug), "DEBUG must be false")
    add("postgresql", str(settings.database_url).startswith("postgresql+asyncpg://"), "Production database must use PostgreSQL + asyncpg")
    add("auth_enforced", bool(settings.security_enforce_auth), "Internal authentication enforcement must be enabled")
    add("secure_cookie", bool(settings.security_cookie_secure), "Internal session cookie must be Secure")
    add("audit_hmac", bool(settings.security_audit_hmac_key), "Security audit HMAC key must be configured")
    add("privacy_hash", bool(settings.security_privacy_hash_key), "Privacy hash key must be configured")
    add("background_jobs", bool(settings.background_jobs_enabled), "Background jobs should be enabled for production")
    add("structured_logs", bool(settings.structured_logging_enabled), "Structured logging should be enabled")
    add("https_origins", bool(settings.frontend_origins) and all(_is_https(str(x)) for x in settings.frontend_origins), "Every frontend origin must use HTTPS")
    add("storage_backend", str(settings.storage_backend).casefold() == "s3", "Production document storage should use S3-compatible object storage")
    add("storage_bucket", bool(settings.storage_s3_bucket) if str(settings.storage_backend).casefold() == "s3" else False, "Object-storage bucket must be configured")
    add("docs_disabled", not bool(settings.api_docs_enabled), "Interactive API docs should be disabled in production", critical=False)

    critical_failed = [row for row in checks if row["critical"] and not row["passed"]]
    return {
        "ready": not critical_failed,
        "checks": checks,
        "app_version": settings.app_version,
        "build_ref": settings.build_ref,
        "commit_ref": settings.commit_ref,
    }
