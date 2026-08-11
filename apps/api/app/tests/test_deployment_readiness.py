from types import SimpleNamespace

from app.services.deployment.readiness import evaluate_runtime_readiness


def settings(**overrides):
    base = dict(
        app_env="production", debug=False, database_url="postgresql+asyncpg://u:p@db/app",
        security_enforce_auth=True, security_cookie_secure=True, security_audit_hmac_key="x",
        security_privacy_hash_key="y", background_jobs_enabled=True, structured_logging_enabled=True,
        frontend_origins=["https://law.example.com"], storage_backend="s3", storage_s3_bucket="documents",
        api_docs_enabled=False, app_version="0.26.0", build_ref="build-1", commit_ref="abc",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_production_readiness_passes_safe_profile():
    result = evaluate_runtime_readiness(settings())
    assert result["ready"] is True
    assert all(row["passed"] or not row["critical"] for row in result["checks"])


def test_production_readiness_rejects_sqlite_and_http():
    result = evaluate_runtime_readiness(settings(database_url="sqlite+aiosqlite:///x.db", frontend_origins=["http://localhost:3000"]))
    assert result["ready"] is False
    failed = {row["key"] for row in result["checks"] if not row["passed"]}
    assert {"postgresql", "https_origins"}.issubset(failed)
