# Junior Lawyer production topology · Batch 24

This topology is a production **foundation**, not a substitute for your cloud/platform security review.

## Services

- `caddy` — only public ingress; automatic TLS for `APP_DOMAIN`.
- `web` — Next.js standalone container, not publicly exposed.
- `api` — FastAPI; scale horizontally with `docker compose up -d --scale api=2`.
- `worker` — organization-scoped background workers; scale independently.
- `scheduler` — organization-scoped maintenance scheduler.
- `migrate` — one-shot Alembic service with a PostgreSQL advisory lock.
- `postgres` — internal-only application database.
- `minio` — internal-only S3-compatible document object storage.

## Safe order

1. Create `.env.production` from `.env.production.example`; do not commit it.
2. Replace mutable container tags with approved immutable digests.
3. Verify off-site encrypted Batch-21 backups and a restore drill.
4. Run the Batch-23 release gate and approve the release.
5. Run `python apps/api/scripts/production_preflight.py` in the target environment.
6. Run `./deploy.sh` from this directory.
7. Verify `/health/live`, `/health/ready`, worker heartbeats, queue lag, object-storage access and database revision.
8. Record the rollout steps in `/deployment`; only mark traffic/postcheck passed after real verification.

## Zero-downtime migrations

The deployment service deliberately does not run migrations inside every API replica. `migrate` owns Alembic and takes a PostgreSQL advisory lock. For high-availability upgrades, write schema changes in expand/contract phases:

- **Expand:** add nullable columns/tables/indexes without removing old fields.
- Deploy code that can read old + new shapes.
- Backfill with background jobs if required.
- Switch reads/writes after verification.
- **Contract in a later release:** remove old fields only after rollback compatibility is no longer required.

A destructive migration in the same rollout as the application change defeats reliable rollback.

## Object storage

`STORAGE_BACKEND=s3` makes uploaded evidence/documents durable in S3-compatible storage. OCR/extraction materializes only the requested object into each API/worker container's cache. MinIO is included for self-hosting; AWS S3 or another compatible service can be used by changing the S3 endpoint/credentials. The sample creates a non-root application user; replace the broad built-in `readwrite` policy with a bucket-specific policy in a hardened deployment.

## Scaling

Example:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --scale api=3 --scale worker=6
```

Workers are still organization-scoped by design. Multi-tenant deployments should run worker sets for each organization or add a future trusted multi-tenant scheduler after a separate security review.

## Backups

The `backup_staging` volume is only working space for Batch-21 backup generation. A real production policy must copy verified artifacts to encrypted off-site storage with access controls and retention. Do not treat a Docker volume on the same server as disaster recovery.

## Batch 26 controlled legal-data drop

`docker-compose.prod.yml` mounts `${LEGAL_DATA_IMPORT_HOST_PATH:-./legal-imports}` read-only at `/data/legal-imports` in the API and worker containers. Only normalized, operator-approved JSON manifests belong there. Feed `import_path` values are relative to that root; path traversal is rejected. The scheduler does not crawl legal websites—it only enqueues due filesystem-drop feeds and integrity sweeps.
