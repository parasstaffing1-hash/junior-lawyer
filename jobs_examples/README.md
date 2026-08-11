# Batch 20 background jobs

Start a worker from `apps/api` after the organization has been bootstrapped:

```bash
python scripts/run_worker.py \
  --organization-id 11111111-1111-1111-1111-111111111111 \
  --queues documents,search,evidence,analytics,operations,corpus,bundles,default
```

Production PostgreSQL workers claim rows with `FOR UPDATE SKIP LOCKED`. SQLite is intentionally a single-worker development fallback.

Set `BACKGROUND_JOBS_ENABLED=true` to make ordinary document uploads return after storage and queue the deterministic processing chain:

`document.reprocess -> matter.intelligence_rebuild -> search.document_reindex`

No Redis, Celery, paid queue service, or paid AI API is required for the default queue implementation.
