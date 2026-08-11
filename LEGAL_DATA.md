# Legal Data Operations — Batch 26

Batch 26 treats legal-corpus maintenance as a controlled data operation rather than a web-scraping feature. Junior Lawyer accepts normalized manifests from approved official-source workflows, records source/hash integrity, versions statutory provisions, preserves amendment evidence, and makes jurisdiction-pack releases reviewable before activation.

## Safety boundary

The legal-data worker **does not fetch or crawl court/statute websites**. It consumes one of three feed modes:

- `manual_manifest` — a manager submits a normalized manifest through the authenticated API.
- `filesystem_drop` — an operator places normalized JSON manifests under `LEGAL_DATA_IMPORT_ROOT`; the organization-scoped worker processes them on schedule.
- `integration_push` — an approved Batch-25 connector submits normalized material to a bound feed.

Every manifest item must contain an HTTPS source URL whose hostname is explicitly allowed by the feed. When `source_sha256` or `manifest_sha256` is supplied, a mismatch blocks the item/run. The existing legal-source row must also be official and enabled.

Protected pages, CAPTCHAs, arbitrary URL fetching, credential harvesting, and access-control bypasses are intentionally out of scope.

## Statute versions and amendments

Statute sections are compared by canonical text hash. On a changed provision:

1. The previous active section snapshot is captured.
2. The incoming normalized section is imported as a new version when its version/effective identity differs.
3. An amendment event stores `before_json`, `after_json`, old/new hashes, section number and detected time.
4. The event remains reviewable by a firm manager.

If the official payload supplies `effective_from`, the previous active version can be closed at the preceding day. If no effective date is supplied, Junior Lawyer **does not invent one**. It records the textual change and leaves the effective-date question for authoritative review.

For a source that explicitly guarantees a complete section inventory, set `metadata.complete_sections=true` in the statute payload. Only then can omitted sections be recorded as removals; absence in an ordinary partial update is not treated as repeal/removal.

## Historical research

Corpus search supports an optional `as_of_date`:

```json
{
  "query": "termination notice",
  "scope": "statutes",
  "as_of_date": "2024-03-31",
  "limit": 20
}
```

Statute retrieval then selects versions whose recorded effective range includes that date. Without `as_of_date`, known expired provisions are excluded from the current search path.

## Filesystem feed

Production containers mount an operator-controlled directory read-only at `/data/legal-imports`.

Example environment:

```env
LEGAL_DATA_IMPORT_ROOT=/data/legal-imports
LEGAL_DATA_IMPORT_HOST_PATH=./legal-imports
LEGAL_DATA_MAX_MANIFEST_MB=50
LEGAL_DATA_STALE_SWEEP_MINUTES=60
```

A feed `import_path` is **relative** to `LEGAL_DATA_IMPORT_ROOT`, e.g. `india-code/central`. Path traversal outside the configured root is rejected.

The maintenance scheduler enqueues due `filesystem_drop` feeds. `manual_manifest` and `integration_push` feeds remain push-only and are never converted into background network crawlers.

## Integrity and freshness

Batch 26 records integrity checks for source state, domain allowlisting, declared hash verification and freshness. A periodic sweep can open/resolve alerts for stale feeds or disabled/non-official sources.

Each successful ingestion can write a corpus checkpoint containing counts of statutes, sections, judgments, paragraphs and citations plus a stable aggregate SHA-256 snapshot.

## Jurisdiction packs

A jurisdiction pack groups the legal sources required for a product/jurisdiction release, for example an India general-practice pack or a state-specific extension.

A release declares:

- version and optional effective dates;
- required/optional legal sources;
- the feed used to keep each source fresh;
- a maximum accepted source age;
- a stable release-manifest SHA-256.

Activation is blocked when a required source is disabled/non-official, a required feed is stale/missing, or a pending statutory amendment review exists for the pack's required legal sources.

This is a corpus-governance control, not a statement that the pack contains every law applicable to a real matter.

## API

Main routes:

```text
GET    /api/v1/legal-data/dashboard
GET    /api/v1/legal-data/feeds
POST   /api/v1/legal-data/feeds
PATCH  /api/v1/legal-data/feeds/{feed_id}
POST   /api/v1/legal-data/feeds/{feed_id}/ingest
POST   /api/v1/legal-data/feeds/{feed_id}/sync

GET    /api/v1/legal-data/runs
GET    /api/v1/legal-data/runs/{run_id}
GET    /api/v1/legal-data/amendments
PATCH  /api/v1/legal-data/amendments/{amendment_id}

POST   /api/v1/legal-data/integrity/sweep
GET    /api/v1/legal-data/integrity
GET    /api/v1/legal-data/alerts
PATCH  /api/v1/legal-data/alerts/{alert_id}
GET    /api/v1/legal-data/checkpoints

GET    /api/v1/legal-data/packs
POST   /api/v1/legal-data/packs
GET    /api/v1/legal-data/packs/{pack_id}/releases
POST   /api/v1/legal-data/packs/{pack_id}/releases
POST   /api/v1/legal-data/releases/{release_id}/activate
```

The Batch-25 official legal import endpoint accepts an optional `feed_id`; when supplied, the payload goes through this complete legal-data integrity/versioning pipeline rather than the legacy direct-import path.

## Background worker

Legal-data jobs use the existing `corpus` queue. Production's standard Batch-20 worker command already subscribes to it.

Relevant job kinds:

```text
legal_data.feed_sync
legal_data.integrity_sweep
```

## Admin UI

Open `/legal-data` to view:

- feed health and sync status;
- amendment review queue;
- ingestion runs;
- integrity alerts/checkpoints;
- jurisdiction packs and release state.

Access is limited to firm managers (owner/admin/partner) because corpus updates can change what the entire firm retrieves as legal authority.
