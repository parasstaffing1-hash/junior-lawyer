from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Junior Lawyer API"
    app_env: str = "development"
    debug: bool = True
    app_version: str = "0.29.0-rc.1"
    build_ref: str | None = None
    commit_ref: str | None = None
    api_docs_enabled: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./junior_lawyer.db"
    frontend_origins: list[str] | str = ["http://localhost:3000", "https://*.onrender.com", "https://junior-lawyer-web.onrender.com"]

    storage_root: Path = Path("./data/documents")
    storage_backend: str = "local"
    storage_s3_endpoint_url: str | None = None
    storage_s3_region: str = "us-east-1"
    storage_s3_bucket: str | None = None
    storage_s3_access_key: str | None = None
    storage_s3_secret_key: str | None = None
    storage_s3_secure: bool = True
    storage_gdrive_credentials_json: str | None = None
    storage_gdrive_root_folder_id: str | None = None
    storage_cache_root: Path = Path("./data/storage-cache")
    max_upload_mb: int = 75
    pdf_native_text_threshold: int = 45
    ocr_languages: str = "eng+hin"
    ocr_dpi: int = 180
    ocr_enabled: bool = True

    # Batch 20 · durable database-backed jobs. Disabled by default for simple local development.
    background_jobs_enabled: bool = False
    background_worker_poll_seconds: float = 1.0
    background_worker_heartbeat_seconds: int = 20

    # Batch 21 · local backup/restore verification foundation. Production deployments should
    # point this at encrypted, access-controlled storage or replace the local adapter.
    backup_root: Path = Path("./data/backups")
    system_health_history_limit: int = 90
    system_health_default_restore_verification_days: int = 30
    system_health_check_interval_minutes: int = 15
    structured_logging_enabled: bool = True

    # Batch 26 · legal-data operations. Scheduled ingestion consumes normalized manifests
    # from this controlled local drop or from an approved integration push; it never scrapes protected pages.
    legal_data_import_root: Path = Path("./data/legal-imports")
    legal_data_max_manifest_mb: int = 50
    legal_data_stale_sweep_minutes: int = 60

    # Batch 19 · optional local-only multilingual embeddings. The path must already exist locally.
    # When unset (default), search uses the deterministic zero-cost feature-hash vector.
    search_local_embedding_model_path: str | None = None

    # Batch 9 · AI is opt-in. Secrets live only in environment variables and are never persisted.
    ai_enabled: bool = False
    ai_local_enabled: bool = False
    ai_local_base_url: str = "http://localhost:11434/v1"
    ai_local_api_key: str | None = None
    ai_local_model: str = "local-legal-model"
    ai_remote_enabled: bool = False
    ai_remote_base_url: str | None = None
    ai_remote_api_key: str | None = None
    # Comma-separated spare credentials for the same endpoint. Free tiers meter
    # per key, so a second key turns a quota stall into a slower answer rather
    # than a failed one. Never logged; only the index of the key that served a
    # request is recorded.
    ai_remote_api_key_fallbacks: str | None = None
    ai_remote_model: str | None = None
    # Batch 33 · WhatsApp reminders via the Meta Cloud API. Outside a 24-hour
    # customer-service window Meta permits only a pre-approved template, and a
    # nightly digest is always outside it — so the template name is required,
    # not optional, and the sender refuses without it.
    whatsapp_enabled: bool = False
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_template_name: str | None = None
    whatsapp_template_language: str = "en"
    # Shared secret for the reminder cron endpoint, so a scheduler can trigger
    # the run without holding a user session.
    reminder_cron_token: str | None = None

    ai_default_max_sources: int = 12
    ai_default_max_input_tokens: int = 6000
    ai_default_max_output_tokens: int = 1200
    ai_request_timeout_seconds: int = 90

    # Batch 10 · security. Development remains open by default so prior batches still run locally.
    # Production deployments should set SECURITY_ENFORCE_AUTH=true and HTTPS cookie settings.
    security_enforce_auth: bool = False
    security_bootstrap_secret: str | None = None
    security_session_cookie_name: str = "jl_session"
    security_cookie_secure: bool = False
    security_cookie_samesite: str = "lax"
    security_session_touch_seconds: int = 60
    security_scrypt_n: int = 16384
    security_scrypt_r: int = 8
    security_scrypt_p: int = 5
    security_scrypt_dklen: int = 32
    security_audit_hmac_key: str | None = None
    security_privacy_hash_key: str | None = None
    security_hsts_seconds: int = 31536000
    # Only trust X-Forwarded-For when a proxy actually sets it; otherwise a
    # client can spoof the header and evade rate limiting.
    security_trust_forwarded_for: bool = False

    # Fixed-window rate limiting. Counters are per API process, so with multiple
    # replicas the effective limit is per replica; a shared limiter belongs at
    # the reverse proxy.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 300
    rate_limit_window_seconds: int = 60
    rate_limit_auth_requests: int = 10

    # Batch 12 · external client portal uses a separate session namespace/trust boundary.
    portal_session_cookie_name: str = "jl_client_session"
    portal_session_hours: int = 12
    portal_invite_hours: int = 168

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def ai_remote_fallback_api_keys(self) -> tuple[str, ...]:
        """Spare remote credentials, parsed from the comma-separated setting."""
        raw = self.ai_remote_api_key_fallbacks or ""
        return tuple(part.strip() for part in raw.split(",") if part.strip())

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("storage_root", "backup_root", "storage_cache_root", "legal_data_import_root", mode="before")
    @classmethod
    def parse_storage_root(cls, value: object) -> object:
        return Path(str(value)).expanduser()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
