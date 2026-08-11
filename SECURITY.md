# Security Operations Notes

## Production minimums

- Set `SECURITY_ENFORCE_AUTH=true`.
- Serve the application only over HTTPS.
- Set `SECURITY_COOKIE_SECURE=true`.
- Configure strong independent values for `SECURITY_BOOTSTRAP_SECRET`, `SECURITY_AUDIT_HMAC_KEY` and `SECURITY_PRIVACY_HASH_KEY`.
- Keep secrets outside source control and rotate them under a documented process.
- Restrict direct database access.
- Back up the primary database and document storage.
- Export security audit events to an external immutable or append-only destination for higher-assurance deployments.
- Use a dedicated identity provider / MFA system for production organizations that require enterprise authentication.

## Ethical walls

`ethical_wall` and `explicit` access modes require an explicit matter grant. Security administrators may administer the wall without inheriting content access. When changing a matter from organization access to a restricted mode, the service creates an explicit manage grant for the acting security administrator to prevent accidental administrative lockout.

## Remote AI

A remote AI call requires both:

1. Batch 9 request-level opt-in; and
2. Batch 10 authorization policy permission.

Matter/grant policy can deny remote AI even when organization defaults allow it. Highly confidential/ethical-wall matters can require MFA before remote AI is permitted.

## Session model

The raw session token is returned only as a cookie. The database stores its SHA-256 hash, not the bearer token. Server-side expiry/revocation therefore takes effect without waiting for a signed client token to expire.

## Passwords

The built-in password module uses Python `hashlib.scrypt` with a per-password random salt and configurable cost factors. It exists to keep local/development deployment dependency-light. A production deployment may delegate authentication to a dedicated identity provider while retaining this application's authorization rules.

## CSRF

Unsafe authenticated browser methods require the CSRF token. The Next.js API helper reads the CSRF cookie and sends `X-CSRF-Token` automatically for POST/PUT/PATCH/DELETE calls.

## Audit integrity

Security audit rows form a per-organization hash chain and may additionally be HMAC-protected. The verification endpoint detects divergence inside that stored chain. For threats involving privileged database administrators, replicate the audit stream outside the application database.

## Deletion

Deletion is a workflow, not an immediate destructive endpoint. Retention policies and active legal holds should be checked before execution. Production deletion workers should also account for object storage, derived indexes, backups and legally required retention.

## Batch 12 external client portal

The external client portal is a separate authentication boundary. It does not reuse the internal `jl_session` cookie, internal CSRF token, or internal user identity. Portal bearer tokens are opaque and only their SHA-256 hashes are persisted.

Portal users cannot enumerate internal resource IDs. Every external read is authorized through an active `client_portal_share` or the portal user's own request/message relationship. Sharing a legal document requires the internal actor to have document download permission; sharing a matter update requires matter work access. Ethical-wall client restrictions remain enforceable on internal billing/portal-management actions.

For production, run the public portal behind TLS, set secure cookies, rate-limit login/activation endpoints at the edge, monitor failed authentication, use a transactional email provider for invitations, and independently test authorization/IDOR behavior before exposing it to clients.

## Billing data

Issued invoice snapshots are immutable application records and carry content hashes. Treat payment/webhook integrations as separate future trust boundaries. Do not store payment-card credentials or banking secrets in billing metadata. Reconcile the application ledger with the firm's authoritative accounting/banking records under a documented process.

## Batch 20 background-worker boundary

Background workers are scoped to one organization UUID. Job creation uses the same matter/document access rules as interactive workflows, and matter-bound job history is permission-filtered before it reaches the UI. Worker execution reconstructs the initiating membership so permission changes can invalidate later execution rather than persisting a broad API-session capability indefinitely.

Treat job payloads, error text, worker logs and artifacts as potentially confidential. Production worker logs should go to the firm's protected logging system, and the database/storage used by workers should receive the same encryption, backup and access controls as the main legal workspace. The built-in queue is durable application infrastructure, not a compliance certification or distributed exactly-once guarantee; handlers should remain idempotent where possible.


## Batch 23 release-security gate

Release security tests are intended for Junior Lawyer environments that the operator is authorized to test. The built-in HTTP probe accepts only an explicit base URL and does not crawl, enumerate, brute-force, exploit or scan unrelated systems. Critical authorization, ethical-wall, IDOR, CSRF and prompt-boundary failures must hold the release rather than being averaged into an overall score.

Before exposing a production tenant, run authenticated fixture tests in isolated staging with realistic role/matter/client walls; include external portal IDOR checks, mutation/CSRF checks, file-upload abuse cases, rate controls at the edge, session expiry/revocation, remote-AI policy denial, and restricted-search/dashboard leakage. Store test evidence with the release run and retain a verified rollback point.

## Batch 24 production deployment notes

- Only the Caddy ingress should be exposed publicly in the supplied production Compose topology.
- Production API containers run as UID/GID 10001; `volume-init` only fixes ownership and exits.
- Alembic is owned by the one-shot migration container, guarded by a PostgreSQL advisory lock. Do not run migrations concurrently from API replicas.
- Document object storage uses a non-root MinIO/S3 application credential in the sample topology. For hardened deployments, replace the broad sample `readwrite` attachment with a bucket-specific least-privilege policy or an equivalent cloud IAM policy.
- `deployment_secret_references` stores only a secret-manager/environment reference. Never write the secret value into that table, rollout evidence, logs or release metadata.
- Interactive FastAPI docs are disabled by the production Compose configuration.
- Treat locally generated shared-volume artifacts and backup staging as single-host infrastructure. Multi-host deployments need externally shared/encrypted artifact and backup storage.
