# AI Junior Lawyer — Complete Source · 0.29.0-rc.1

India-first, Hindi/English/Hinglish legal operating system built with a **deterministic-first, local-first** architecture. This consolidated source package contains the complete implementation through Case Lookup and Legal Remedy Analysis. Version `0.29.0-rc.1` passes the repository source/legal/security/migration gates; representative staging, provider, recovery and lawyer-pilot validation are still required before production use. Paid AI remains optional and is not required for the deterministic core.

## Batch 29 — Case Lookup + Legal Remedy Analysis

Case Lookup detects exact CNRs, typed case type/number/year queries and ambiguous case-number inputs, ranks saved matches using lawyer court/location preferences without silently discarding alternatives, normalizes official/user-assisted/cache data into one case record, saves source snapshots, and records deterministic changes between refreshes. The Case page shows court, parties/advocates, judge/bench, Acts/sections, status/stage, hearing history, orders/judgments, source freshness and “what changed since last time?”. Live protected court interfaces remain behind approved/user-assisted adapters; there is no CAPTCHA bypass.

Legal Remedy Analysis is integrated into the Case Workspace via **Find Legal Remedies**. It evaluates only active, verified remedy rule packs and displays applicability reasoning, verified authorities, forum, limitation/deadline status, maintainability checks, required documents/evidence, procedural steps, risks/conditions and relevant verified case/statute authorities. A verified/active rule is rejected unless it is itself verified and has verified authority. Missing legal coverage produces research prompts instead of an unsupported remedy conclusion. Detailed English/Hindi/bilingual remedy memos and source-backed drafting links are included.

Batch 29 adds **20 tables**, bringing the application to **250 ORM tables**. Latest migration: `20260808_0028_case_lookup_legal_remedy_analysis.py`. See `CASE_LOOKUP_REMEDIES.md`, `case_lookup_examples/`, and `remedy_examples/`.

## Historical Batch 28 release-candidate validation

Batch 28 adds `validation_campaigns`, `validation_scenarios`, `validation_scenario_runs`, `validation_evidence`, `release_candidate_manifests`, `pilot_readiness_checks`, `validation_signoffs`, and `validation_datasets`, bringing the application to **230 ORM tables**. Latest migration: `20260808_0027_release_candidate_validation.py`. See `RELEASE_CANDIDATE.md`, `VALIDATION_RUNBOOK.md`, `PILOT_GUIDE.md`, `KNOWN_LIMITATIONS.md`, and `BUILD_VALIDATION_STATUS.md`. A local/source gate is necessary but cannot by itself mark RC1 pilot-ready; representative staging evidence is mandatory.

## Historical Batch 27 UX/accessibility freeze

Batch 27 added `user_experience_preferences` and `user_onboarding_progress`, bringing that revision to 222 ORM tables. See `UX_ACCESSIBILITY.md` for the accessibility boundary and large-document reader details.


## Batch 26 — legal data operations and jurisdiction packs

Batch 26 makes legal data a governed production subsystem rather than a collection of ad-hoc imports. Official legal-source rows are bound to organization feeds using `manual_manifest`, read-only `filesystem_drop`, or approved Batch-25 `integration_push` modes. The worker never becomes a CAPTCHA bypass or arbitrary web crawler: each item must use an HTTPS URL on the feed's authoritative-domain allowlist, and declared SHA-256 values are verified before import.

Statutory changes are compared section-by-section. Before/after snapshots, hashes and amendment events are retained for review. An official `effective_from` date can close the prior recorded version; when no effective date is supplied, Junior Lawyer does **not invent one**. Research now supports `as_of_date` for retrieving statute versions whose recorded effective range covers a historical date.

Jurisdiction packs group required legal sources into versioned releases with source-freshness requirements. Activation is blocked when required source/feed integrity is not satisfied or pending amendment review remains. Corpus checkpoints record counts plus an aggregate SHA-256 so legal-data states can be compared across update runs.

The premium `/legal-data` manager workspace exposes feeds, amendment review, ingestion runs and jurisdiction packs. Background jobs `legal_data.feed_sync` and `legal_data.integrity_sweep` use the existing `corpus` queue. Production mounts an operator-controlled legal-data drop read-only at `/data/legal-imports`.

Batch 26 adds eleven tables: `legal_data_feeds`, `legal_data_ingestion_runs`, `legal_data_ingestion_items`, `legal_data_source_snapshots`, `legal_data_integrity_checks`, `statute_amendment_events`, `jurisdiction_packs`, `jurisdiction_pack_releases`, `jurisdiction_pack_sources`, `legal_data_alerts`, and `legal_corpus_checkpoints`. Batch 26 introduced the controlled legal-data subsystem; Batch 27 adds the two experience tables described above.

See `LEGAL_DATA.md` and `legal_data_examples/` for feed, manifest and jurisdiction-release examples.

Batch-26 verification in this build: **260 tests passed**, 2 existing async SQLite integration modules skipped because the sandbox lacks the already-declared async driver; the Batch-22 golden legal QA and Batch-23 security baseline passed; full migration upgrade/downgrade/re-upgrade passed with zero Alembic drift; the schema contains **220 application tables**; **64 TS/TSX source files** syntax-transpiled with zero errors; JSON/TOML/production-Compose parsing passed; and the complete dependency-light source release gate passed.

## Historical Batch 25 — Real Integrations

India-first, Hindi/English/Hinglish legal workspace built with a **deterministic-first, local-first** architecture. Batch 25 contains the complete Batches 1–24 legal operating system plus real provider boundaries for Google Workspace, Razorpay, DocuSign, signed generic webhooks and allowlisted official legal-data imports. Provider credentials remain outside the application database; paid AI remains optional.


## Batch 25 — real integrations and provider boundaries

Batch 25 adds organization-scoped integration connections with explicit capabilities, public configuration, external **secret references** and persistent provider health/delivery/resource-mapping records. The built-in secret resolver accepts `env://NAME`/`env:NAME`; raw credential values are rejected from non-secret configuration. Vault/cloud-secret-manager support remains an adapter boundary rather than storing plaintext secrets in Junior Lawyer.

Google Workspace integration supports an OAuth authorization helper, refresh-token access-token exchange, Gmail message sending and Google Calendar event creation. The current runtime expects the refresh token to be provisioned into an external secret store/environment reference; the application does not persist OAuth refresh tokens returned by a callback. A live Google health probe refreshes a token without sending mail or creating a calendar event.

Razorpay integration creates Payment Links and verifies inbound webhook signatures over the **raw request body**. Provider event IDs are stored for idempotency, and verified payment-link events can update mapped local payment-intent state without copying full webhook bodies into logs.

DocuSign integration creates eSignature envelopes from an authorized, immutable Junior Lawyer document version. Document download permission is rechecked before the file is materialized from local/S3 storage. DocuSign Connect webhook HMAC verification updates the corresponding local envelope through an external-resource mapping. The initial adapter uses an externally provisioned access token; a full provider OAuth token-lifecycle implementation remains a later connector enhancement.

Generic outbound webhooks are HMAC-capable and are hardened against common SSRF misuse: only HTTPS targets on an explicit per-connection `allowed_hosts` allowlist are accepted, while localhost and private/loopback/link-local/reserved IP targets are rejected. Inbound generic/provider webhooks bypass browser-session CSRF only at the dedicated callback prefix and must pass the endpoint's provider-specific HMAC verification before being processed. Raw webhook bodies are represented by SHA-256 plus minimized normalized metadata rather than persisted as privileged payload logs.

The official legal-data connector is deliberately an **import boundary**, not a court scraper. It accepts normalized statute/judgment payloads only when the supplied source URL belongs to the connection's authoritative-domain allowlist, optionally verifies a supplied payload SHA-256, and then routes into the existing corpus importer. It performs no CAPTCHA bypass and no arbitrary network fetch.

The premium `/integrations` workspace shows connection state, health checks and the connector catalog, and lets managers create connection profiles using secret references. `Ctrl/Cmd + K` includes an **Integrations** command. Runtime provider operations are exposed through the authenticated API for Gmail, Calendar, Razorpay Payment Links, DocuSign envelopes, generic outbound webhooks and normalized official legal imports.

Batch 25 adds ten tables: `integration_connections`, `integration_secret_references`, `integration_oauth_states`, `integration_accounts`, `integration_sync_runs`, `integration_resource_mappings`, `integration_webhook_endpoints`, `integration_webhook_events`, `integration_delivery_attempts`, and `integration_health_checks`. The complete application contains **209 ORM tables**. Latest migration: `20260808_0024_real_integrations_provider_webhooks.py`.

See `INTEGRATIONS.md` and `integration_examples/` for configuration examples and provider/security boundaries. Live provider tests require operator-supplied credentials and are intentionally not executed by the dependency-light build suite.

Batch-25 verification in this build: **249 tests passed**, 2 existing async SQLite integration modules skipped because the sandbox lacks the already-declared async driver; the Batch-22 golden legal QA gate passed; the security baseline passed; full Batch 1→25 migration reached **209 application tables**, Batch 25→24 downgrade returned to 199, re-upgrade passed with zero Alembic drift; **62 TS/TSX source files** syntax-transpiled with zero errors; and the complete dependency-light source release gate passed. Live Google/Razorpay/DocuSign mutations were not executed because the build contains no real provider credentials.


## Batch 24 — production deployment topology

Batch 24 converts the release-gated codebase into an explicit production deployment foundation. It adds a hardened non-root API image, Next.js standalone production image, Caddy TLS ingress, internal PostgreSQL, S3-compatible object storage with a non-root application credential, one-shot volume initialization, advisory-lock Alembic migrations, horizontally scalable API/worker services, organization-scoped schedulers, liveness/readiness probes, production configuration preflight, recorded deployment environments/change windows/rollouts and secret **references** (never secret values).

Production source documents can use `STORAGE_BACKEND=s3`; OCR/extraction materializes only the needed object into a local worker/API cache. Batch-21 application-file backups now stream S3 document objects into the verified backup ZIP as well, avoiding a backup blind spot after switching from local source storage. Locally generated artifacts remain on a shared Docker volume in the single-host Compose topology; multi-host deployments should replace that with an external shared artifact-storage adapter before horizontal expansion across hosts.

`infrastructure/production/docker-compose.prod.yml` exposes only Caddy on ports 80/443. Database, MinIO, API, web and workers stay on the internal network. The dedicated `migrate` service takes a PostgreSQL advisory lock and runs before API/workers, so every replica does not race to run Alembic. `infrastructure/production/README.md` documents expand/contract migrations, backup verification, image-digest pinning, scaling and the production rollout order.

The premium `/deployment` workspace shows runtime preflight, environment/service topology, recorded rollouts and secret-manager references. A production rollout can only be created for a Batch-23 release that is already approved and has a verified ready rollback point; environments can require an approved change window. Deployment records are control/evidence records—the application does not shell into infrastructure or silently deploy itself.

Batch 24 adds six tables: `deployment_environments`, `deployment_service_profiles`, `deployment_change_windows`, `deployment_rollouts`, `deployment_rollout_steps`, and `deployment_secret_references`. The complete application now contains **199 ORM tables**. Latest migration: `20260808_0023_production_deployment_topology.py`.

Batch-24 verification in this build: **236 tests passed**, 2 existing async SQLite integration modules skipped because the sandbox lacks the already-declared async driver; full Batch 1→24 migration reached 199 application tables, Batch 24→23 downgrade returned to 193, re-upgrade passed with zero Alembic drift; the Batch-23 source release gate passed against Batch 24; 60 TS/TSX source files syntax-transpiled with zero errors; production Compose/static topology checks passed. Docker itself is not available in this build sandbox, so live container startup/TLS/MinIO behavior must still be verified on staging before production.


## Batch 23 — release engineering, load/stress and security gates

Batch 23 turns Batch 22's legal-accuracy gate into a production release pipeline. Release candidates now persist an explainable stage graph across backend regression tests, legal QA, migration round-trip/drift, frontend static/build checks, representative staging load tests, security probes, artifact integrity and rollback proof. A release is held when any required control fails; critical security failures cannot be averaged away by strong performance elsewhere. Deployment approval is a separate manager decision and does not deploy automatically.

The built-in performance layer stores versioned scenarios with concurrency/request counts and explicit p95/success/error thresholds. `apps/api/scripts/run_http_load.py` is a bounded dependency-light staging probe: it sends only the exact request and base URL supplied by the operator. The starter thresholds are examples, not performance claims; real firms should replace them with measured SLOs on representative hardware/data.

The security suite provides explicit authorization, ethical-wall, IDOR, CSRF, session/header, upload, rate-control and prompt-injection test categories. `run_security_baseline.py` executes dependency-light deterministic policy tests and can optionally probe an explicit Junior Lawyer staging URL. It does not crawl, brute force or scan third-party systems. Authenticated fixture tests should be run in an isolated staging tenant before production.

`apps/api/scripts/run_release_source_gate.py` runs the source-level CI gate: backend tests, the Batch-22 golden legal QA suite, deterministic security baseline, TypeScript/TSX syntax transpilation, full Alembic upgrade, downgrade to Batch 22, re-upgrade and schema-drift check. It intentionally reports `production_load_verified=false`; source tests cannot prove live throughput. The repository also includes `.github/workflows/release-gate.yml`, a production-release checklist, performance example, and separate frontend production-build CI job.

Artifacts may be registered by SHA-256 and size. The release gate additionally requires the artifact stage to pass plus a verified rollback point before deployment approval becomes eligible. Rollback points can reference a release artifact and/or a verified Batch-21 backup/restore run, preserving the distinction between "tests passed" and "we can safely reverse this deployment."

The premium `/release` workspace shows candidate stages, load scenarios, critical security cases, release history, hold reasons and approval controls. `Ctrl/Cmd + K` includes a **Release engineering** command.

Batch 23 adds ten tables: `release_pipelines`, `release_runs`, `release_stage_runs`, `performance_scenarios`, `performance_runs`, `security_test_cases`, `security_test_runs`, `release_artifacts`, `rollback_points`, and `deployment_approvals`. The complete application now contains **193 ORM tables**. Latest migration: `20260808_0022_release_engineering_load_security_testing.py`.

Batch-23 verification in the build sandbox: **230 tests passed**, 2 existing async SQLite integration modules skipped because the already-declared `aiosqlite` package is unavailable; the dependency-light source release gate passed; full Batch 1→23 migration reached 193 tables, Batch 23→22 downgrade returned to 183, re-upgrade passed with zero Alembic drift; frontend TS/TSX syntax gate passed. A live production-scale load result is intentionally not claimed from this sandbox.

## Batch 22 — testing, legal accuracy evaluation and release quality gates

Batch 22 adds a persistent evaluation system rather than relying only on ordinary unit tests. A firm can maintain versioned evaluation suites and golden cases across OCR, extraction, language normalization, search, citations, drafting provenance, contract review, deadlines, security and evidence. Each case stores its deterministic evaluator, exact input/expected snapshots, weight, criticality and SHA-256 source fingerprint.

The seeded `core-release` suite currently contains 13 dependency-light bilingual legal cases, including Hindi/Hinglish section normalization, SCC/INSC citation parsing, calendar/business-day deadlines, Hindi/English evidence classification, ethical-wall leakage prevention, drafting-source coverage, top-k search relevance, captured Hindi OCR token recall and contract-review output shape. These are a starting baseline, not a substitute for a firm's own representative golden matters.

Release gates are explicit and explainable. The default gate requires at least 95% weighted overall score, zero critical failures, zero security failures, zero citation failures, and 100% scores for selected critical categories. A critical security/citation regression therefore cannot be hidden behind high average accuracy in easier tests. Every run stores case-level actual/expected output, duration, findings, category metrics, app/build reference and a reproducible SHA-256 snapshot hash.

The premium `/qa` workspace shows release readiness, category scores, critical findings, golden-case definitions and immutable run history. `Ctrl/Cmd + K` includes a **Quality assurance** command. The local `apps/api/scripts/run_local_qa_gate.py` runner executes the built-in golden cases without a database and exits non-zero on gate failure, making it suitable as a dependency-light CI smoke gate. Organization-specific suites and run history use the authenticated API/database.

Batch 22 adds nine tables: `evaluation_suites`, `evaluation_cases`, `evaluation_runs`, `evaluation_case_runs`, `evaluation_metrics`, `release_quality_gates`, `release_quality_gate_runs`, `qa_findings`, and `evaluation_baselines`. The complete application now contains **183 ORM tables**. Latest migration: `20260808_0021_quality_assurance_legal_accuracy.py`.

Verification for Batch 22: **219 tests passed**, 2 existing async SQLite integration modules skipped because this sandbox lacks the already-declared `aiosqlite`; the 13 seeded golden cases all pass; Python compilation passed; Batch 21→22 migration, downgrade and re-upgrade passed with zero Alembic schema drift; **56 TS/TSX source files** syntax-transpiled with zero syntax errors.

Evaluation scores measure software behavior against curated expected outputs. They do **not** prove legal correctness in every matter, predict case outcomes, or replace lawyer review. Production firms should continuously add jurisdiction/practice-specific cases and separately validate statutory/rule updates.

## Batch 21 — observability, backup, recovery and system health

Batch 21 introduces a source-of-truth health layer across the API, database, local storage, workers, job queues, search index, OCR runtime, AI-provider configuration, court-tracker freshness, backup RPO and restore-verification freshness. Component status is persisted as `healthy`, `degraded`, `down` or `unknown`; the overall run uses the worst component status rather than hiding failures behind an average. Degraded/down checks can open or reopen deduplicated incidents, and later healthy checks can auto-resolve the corresponding system incident.

HTTP request logging is structured JSON with generated/propagated request IDs, method, path, status and latency. Request bodies, legal-document contents and API secrets are deliberately not logged.

Recovery objectives are organization-scoped and explicit: RPO minutes, RTO minutes, restore-verification age, maximum queue lag, worker-staleness threshold, slow-job threshold, minimum storage-free percentage and maximum database latency. These are operational targets, not compliance certifications.

Backup policies support database and application-file scope, simple scheduled recurrence (`FREQ=HOURLY|DAILY|WEEKLY;INTERVAL=n`), retention days/count, RPO/RTO metadata and destination/encryption metadata. The built-in local adapter performs a real SQLite backup through `sqlite3.Connection.backup`, or a PostgreSQL custom-format dump through `pg_dump`; document/draft/contract storage is archived as ZIP with manifest and SHA-256 artifacts. PostgreSQL Docker images now install `postgresql-client` so `pg_dump`/`pg_restore` are available.

The built-in local destination intentionally refuses external destinations or encryption modes that do not have a configured connector. **A backup on the same machine/volume is a development baseline, not disaster recovery.** Production deployments should use separate encrypted/off-site storage or an approved backup connector.

Restore drills in this batch are **verification-only**. They verify artifact SHA-256, run SQLite `PRAGMA quick_check`, use `pg_restore --list` for PostgreSQL dumps, test ZIP integrity and parse manifests. They never write restored data back into the live database. A successful drill still has an explicit manager review step.

Maintenance integrates with Batch 20's durable queue using the `maintenance` queue and three job kinds: `system.health_check`, `system.backup_run`, and `system.restore_verify`. The organization-scoped scheduler can enqueue due health/backup jobs without Celery. Run it from `apps/api` with:

```bash
python scripts/run_maintenance_scheduler.py \
  --organization-id <ORGANIZATION_UUID> \
  --poll 60
```

Workers should include the maintenance queue:

```bash
python scripts/run_worker.py \
  --organization-id <ORGANIZATION_UUID> \
  --queues documents,search,evidence,analytics,operations,corpus,bundles,maintenance,default
```

The premium `/system-health` workspace has Health, Backups and Recovery views: component status, open incidents, acknowledge/resolve actions, backup policies/runs, restore-verification history, recovery objectives and explicit restore-proof status. `Ctrl/Cmd + K` includes a **System health** command.

Batch 21 adds ten tables: `system_health_runs`, `system_health_components`, `system_incidents`, `system_incident_events`, `backup_policies`, `backup_runs`, `backup_artifacts`, `restore_drills`, `recovery_objectives`, and `system_metric_snapshots`. The complete application now contains **174 ORM tables**. Latest migration: `20260808_0020_observability_backup_disaster_recovery.py`.

Verification for Batch 21: **207 tests passed**, 2 existing async SQLite integration modules skipped because this sandbox lacks the already-declared `aiosqlite`; Python compilation passed; a real SQLite backup + isolated integrity verification passed; English/Hindi document ZIP backup verification passed; full migration upgrade/downgrade/re-upgrade passed with **zero Alembic schema drift**; **55 TS/TSX source files** syntax-transpiled with zero syntax errors.

The system-health layer is a strong operational foundation, not a claim of ISO/SOC/Bar-regulatory compliance or a guarantee of disaster recovery. Real production recovery should be tested against the firm's infrastructure, off-site backup provider, retention policy, encryption/key-management design and documented incident/recovery procedures.

## Batch 20 — durable background workers and large-scale processing

Batch 20 moves expensive deterministic work out of API request latency. Jobs live in PostgreSQL/SQLite rather than process memory, so an API restart does not erase queued work. Production PostgreSQL workers claim jobs with `FOR UPDATE SKIP LOCKED`; SQLite is intentionally a portable single-worker development fallback.

Core job states are `queued`, `leased`, `running`, `retry_wait`, `succeeded`, `failed`, `cancelled` and `dead_letter`. Every job records initiating membership, organization, matter/resource scope, payload/result snapshots, attempts, scheduling, lease/heartbeat state, progress, retry policy, errors and immutable event history. Retries use deterministic exponential backoff and exhausted jobs move to the dead-letter queue instead of disappearing.

Workers are **organization-scoped**. A worker must be launched with an explicit organization UUID, and queued matter/document jobs are permission-checked when created. Worker execution reconstructs the initiating membership and re-runs current permission checks where the underlying service requires them. Generic job listings also filter matter-bound work through the existing ethical-wall permission system.

Per-organization queues support enable/disable controls, maximum concurrency, claim-rate limits, default retry counts and lease duration. Long-running workers renew their lease through a separate heartbeat session. Expired leases are reclaimed; the abandoned attempt is retained for audit. Dependencies allow DAGs such as document extraction followed by matter intelligence and indexing. If a required dependency permanently fails, its dependent job dead-letters rather than waiting forever.

When `BACKGROUND_JOBS_ENABLED=true`, ordinary document upload stores the source file and returns it in `pending`, then queues deterministic processing. The processing DAG is:

```text
document.reprocess
       ↓
 ┌───────────────┐
 ↓               ↓
matter.intelligence_rebuild   search.document_reindex
```

OCR/extraction runs on the `documents` queue; intelligence/evidence work and indexing can therefore be handled by separate worker pools. Existing synchronous upload/reprocess remains available for simple development.

Registered job handlers include document reprocessing, incremental document indexing, full organization search-index rebuild, duplicate scanning, matter intelligence rebuild, evidence rebuild, analytics snapshot/risk refresh, court-operations due sweeps, citation resolution, and evidence bundle build/finalization. Bundle outputs can be registered as job artifacts with storage key and SHA-256.

The premium `/jobs` workspace shows active/succeeded/dead-letter metrics, filtered job history, progress, attempts, event logs, worker heartbeat health, and queue controls. `Ctrl/Cmd + K` also includes a **Background jobs** command.

Batch 20 adds seven tables: `background_queues`, `background_jobs`, `background_job_attempts`, `background_job_events`, `background_workers`, `background_job_dependencies`, and `background_job_artifacts`. The complete application now contains **164 ORM tables**. Latest migration: `20260808_0019_background_jobs_large_scale_processing.py`.

Verification for Batch 20: **194 tests passed**, 2 existing async SQLite integration modules skipped because the sandbox lacks the already-declared `aiosqlite`; complete migration upgrade/downgrade/re-upgrade and Alembic drift checks passed; 52 TS/TSX source files syntax-transpiled with zero errors.

Run a worker from `apps/api`:

```bash
python scripts/run_worker.py \
  --organization-id <ORGANIZATION_UUID> \
  --queues documents,search,evidence,analytics,operations,corpus,bundles,default
```

Cancellation is deliberately truthful: queued work cancels immediately; running handlers are currently cooperative at handler boundaries. If cancellation arrives after an irreversible handler has already completed its work, the completed output is preserved and the event log records that cancellation arrived too late.


## Batch 19 — indexed search and document intelligence performance

Batch 19 materializes searchable chunks into `search_index_entries`. Every entry carries organization/matter/client scope, stable source key, language, normalized text, source/content SHA-256, 64-bit SimHash, local vector, rank weight and navigation metadata. Security predicates are applied in SQL **before ranking**, so restricted matter/client content does not enter the ranked candidate set.

Production PostgreSQL migrations enable `pg_trgm`, a GIN `to_tsvector('simple', normalized_text)` index, and trigram GIN indexes for normalized body/title preselection. SQLite remains the portable local-development fallback. Final ranking combines deterministic BM25-style lexical relevance, exact-title/type boosts and a local vector score. The default vector is a zero-cost deterministic feature hash; an already-downloaded local sentence-transformers model can optionally be configured without contacting a paid embedding API.

Document ingestion/reprocessing now incrementally replaces only that document's page chunks. Full organization/corpus rebuild remains available for maintenance and upgrades. Stale organization rows are tombstoned rather than silently surviving a rebuild.

Duplicate intelligence uses normalized SHA-256 for exact duplicates and a bounded near-duplicate pipeline: 64-bit SimHash → four locality-sensitive hash bands → Hamming threshold → token-shingle Jaccard confirmation. This avoids a naive full-corpus all-pairs comparison. The premium `/search` workspace now exposes index health, chunk count, duplicate-pair count, rebuild controls and duplicate scanning.

Batch 19 adds six tables: `search_index_entries`, `search_index_jobs`, `search_index_cursors`, `search_duplicate_relations`, `search_index_health_snapshots`, and `search_performance_preferences`. The complete application now contains **157 ORM tables**. Latest migration: `20260808_0018_search_index_document_intelligence_.py`.

Verification for Batch 19: **188 tests passed**, 2 existing async SQLite integration modules skipped because the sandbox lacks the already-declared `aiosqlite`; full migration upgrade/downgrade/re-upgrade and Alembic drift check passed; 51 TS/TSX source files syntax-transpiled with zero errors. A CPU-only indexing primitive benchmark is included at `apps/api/scripts/benchmark_search_primitives.py`; this is intentionally not presented as a claim of end-to-end 100k-document throughput because database/storage hardware materially affects that result.


## Batch 18 — firm-wide search and universal command center

Batch 18 adds one permission-aware search surface across the entire Junior Lawyer workspace. Security filtering happens **before ranking**, so restricted ethical-wall matters, clients, documents and related operational records never enter the candidate pool and therefore cannot leak through titles, snippets, counts or recent items.

Search supports English, Hindi and common Hinglish legal terminology using the deterministic normalization/query-expansion layer already used by legal research. The global `Ctrl/Cmd + K` command palette and `/search` workspace cover matters, clients, document page text, facts, evidence, witnesses, contracts, drafts, deadlines, hearings, tasks, invoices, statutes/sections, judgments/paragraphs, approved firm precedents and permitted client communications.

The command center also includes recent permitted items, saved searches, scope filters, navigation/create commands and deterministic BM25-style ranking. Public legal corpus results can be included alongside organization data without sending queries or documents to a paid model.

Batch 18 adds three persistence tables: `search_preferences`, `saved_searches`, and `recent_items`. The complete application now contains **151 ORM tables**. Latest migration: `20260808_0017_universal_search_command_center.py`.

Verification for Batch 18: **175 tests passed**, 2 existing async SQLite tests skipped because the build sandbox does not contain the already-declared `aiosqlite` dependency; full migration upgrade/downgrade/re-upgrade and Alembic drift check passed; 50 TS/TSX source files syntax-transpiled with zero errors.


## Batch 17 — law firm analytics, quality and supervision intelligence

Batch 17 uses the structured records already created by Junior Lawyer rather than sending firm data to a model. Its default analytics path uses **zero paid LLM calls**. Scores are management signals, not predictions of case outcomes or hidden ratings of lawyer competence.

### Explainable matter health

Every visible active matter receives a deterministic 0–100 attention score. The default penalties are deliberately transparent and configurable:

```text
overdue task                 -12 each (category capped)
high-priority open task       -4 each
reviewed deadline due in 7d   -8 each
open factual contradiction   -10 each
open high drafting finding    -8 each
unreviewed court change       -6 each
open evidence gap             -7 each
```

Each category is capped at 30 penalty points so one noisy signal cannot drive the entire score to zero. The API/UI returns the exact count, weight and penalty behind every score. Firms can change the weights/thresholds in analytics preferences. These values are **operational heuristics**, not legal conclusions.

### Confidentiality-aware aggregation

Analytics always begins with the existing Batch-10 security layer. Matter-level metrics use `visible_matter_ids`; client metrics use `visible_client_ids`; finance and payment calculations exclude records connected to matters the actor cannot see. Ethical-wall matters therefore do not become visible merely because a partner opens Analytics.

Team/supervision views are restricted to owner/admin/partner roles. Financial analytics are restricted to owner/admin/partner/billing roles, and an organization can additionally hide financial analytics from partners.

### Partner command center

The premium `/analytics` workspace provides:

```text
Overview
Matter health
Team workload
Client operating health
Supervision signals
Snapshot / goal history
```

Core KPIs include active matters, average matter health, matters needing attention, overdue work, hearings/deadlines in the next seven days, draft health, contract health, high review findings, approved precedent count/reuse and permitted financial metrics.

### Workload is not a performance rating

The workload score is intentionally simple and disclosed:

```text
open tasks × 3
+ overdue tasks × 14
+ high/urgent tasks × 7
= workload pressure (0–100 cap)
```

It exists to surface capacity pressure and supervision needs. It is explicitly **not** a lawyer-quality, productivity, compensation or disciplinary score.

### Collections analytics without fake profitability

Batch 17 reports permitted receivables information including:

```text
outstanding amount
overdue amount
invoices issued in rolling window
cleared collections in rolling window
collection rate
ageing: current / 1–30 / 31–60 / 61–90 / 90+
```

It does **not** call this profit or matter profitability because the current project does not yet maintain complete payroll, overhead and cost-allocation data. This avoids presenting a misleading profitability number.

### Client operating-health signals

For users allowed to see financial analytics, the client view combines permitted receivables, visible active matters, open portal requests and last recorded communication. It can flag overdue balances, multiple open portal requests or long communication gaps. These are operational review prompts, not legal/client-risk classifications.

### Deterministic supervision signals

Partner/admin/owner users can rebuild threshold-driven signals such as:

```text
Matter health below configured threshold
Member workload pressure above configured threshold
Client overdue receivable above configured threshold
```

Signals can be acknowledged, resolved or dismissed. When a deterministic condition no longer exists, an open signal can auto-resolve on rebuild.

### Immutable snapshots and goals

A manual/daily/weekly/monthly analytics snapshot stores period metadata, organization metrics, matter health, member workload, client health and a deterministic SHA-256 payload hash. This creates a reproducible management history without altering the underlying legal records.

Firm goals can track transparent organization-scope metrics such as matter health, overdue tasks, draft health, precedent reuse, collection rate or overdue receivables. Goal progress supports `at_least`, `at_most` and `exact` comparisons.

### Batch 17 database additions

Batch 17 adds 10 tables:

```text
analytics_metric_definitions
analytics_preferences
analytics_snapshots
analytics_metric_values
matter_health_snapshots
member_performance_snapshots
client_health_snapshots
analytics_risk_signals
analytics_goals
analytics_goal_progress
```

The complete application now contains **148 ORM tables**.

Latest migration:

```text
20260808_0016_law_firm_analytics_quality_supervision.py
```

### Batch 17 API highlights

```text
GET   /api/v1/analytics/dashboard
GET   /api/v1/analytics/matter-health
GET   /api/v1/analytics/team
GET   /api/v1/analytics/clients
GET   /api/v1/analytics/finance
GET   /api/v1/analytics/quality
GET   /api/v1/analytics/preferences
PATCH /api/v1/analytics/preferences
POST  /api/v1/analytics/metrics/seed
GET   /api/v1/analytics/metrics
POST  /api/v1/analytics/risks/rebuild
GET   /api/v1/analytics/risks
PATCH /api/v1/analytics/risks/{id}
POST  /api/v1/analytics/snapshots
GET   /api/v1/analytics/snapshots
POST  /api/v1/analytics/goals
GET   /api/v1/analytics/goals
```

Example policy/goal payloads are in `analytics_examples/`.

### Batch 17 verification status

```text
169 tests passed
2 existing async SQLite integration modules skipped in the build sandbox
148-table ORM schema creation passed
Alembic 0015 → 0016 upgrade passed
Alembic 0016 → 0015 downgrade passed
Re-upgrade passed
Alembic schema drift check passed
Python compile pass
48 TypeScript/TSX source files syntax-transpile passed
```

The two skipped async tests require `aiosqlite`, which remains declared in project dependencies but is unavailable in the execution sandbox.

---

## Batch 16 — firm knowledge and precedent system

Batch 16 turns reviewed historical work product into reusable institutional memory **without training a model on client files**. Knowledge assets are explicit database records with provenance, versions, sanitization/review status, approval state and deterministic search text.

### Review-before-reuse boundary

Matter-derived work product is never organization-wide merely because it exists. The lifecycle is:

```text
Matter / draft / contract / research
              ↓
Knowledge draft
              ↓
Source provenance
              ↓
Sanitization review
              ↓
Partner/admin approval
              ↓
Approved firm precedent
```

If an asset is tied to a matter, approval requires `sanitization_status=reviewed` and at least one verified provenance source. The approving reviewer must also have access to the source matter, so an ethical wall is not bypassed by the knowledge-review role. Changing an approved matter-derived asset invalidates the approval and resets sanitization review.

The sanitization flag is a **human review control**, not an automatic guarantee that client-identifying information has been removed. Firms should define their own redaction/sanitization procedures before approving work product for broad reuse.

### Knowledge asset types

```text
pleading_section
contract_clause
argument
research_memo
authority_note
checklist
template
practice_note
```

Assets support English, Hindi and bilingual content, practice area, matter type, jurisdiction, outcome label, quality score, tags, annotations, collection membership, immutable SHA-256 fingerprints and version snapshots.

### Promote existing work product

Reviewed drafting and contract work can be promoted into the knowledge workflow without copy/paste:

```text
POST /api/v1/knowledge/promote/draft-section
POST /api/v1/knowledge/promote/contract-clause
```

The promoted asset keeps its source matter/source record and starts as a draft. It still requires sanitization and approval before becoming reusable firm-wide knowledge.

### Deterministic bilingual precedent search

Approved assets are searched locally using the existing legal normalization and BM25 engine. Narrow bilingual/Hinglish expansions allow queries such as:

```text
bail evidence
जमानत साक्ष्य
zamanat saboot
```

to converge on related approved precedent material. A conservative quality score is only a tie-breaker; it cannot make unrelated text rank as a match. No paid LLM call is required.

### Matter playbooks

Matter playbooks combine ordered steps with already-approved knowledge assets:

```text
Commercial injunction playbook
├── Intake / conflict checklist
├── Evidence-preservation step
├── Interim-relief argument precedent
├── Drafting precedent
├── Authority collection
└── Hearing preparation note
```

A playbook cannot be approved while it links to unapproved knowledge. This prevents a draft clause/argument from quietly becoming part of the firm's standard procedure.

### Curated authority collections

Research collections store selected judgments, optional paragraph-level references, propositions and notes. Approval is blocked until every item is explicitly marked verified. This creates reusable issue-specific authority sets without relying on a model to remember which cases are authoritative.

### Knowledge annotations and collections

Lawyers can attach notes, warnings, tips and outcome annotations to assets and group assets into practice-area collections. Immutable asset versions preserve the exact text/hash used at each revision.

### Batch 16 database additions

Batch 16 adds 11 tables:

```text
knowledge_collections
knowledge_assets
knowledge_asset_sources
knowledge_asset_versions
knowledge_tags
knowledge_asset_tags
knowledge_annotations
matter_playbooks
matter_playbook_items
research_collections
research_collection_items
```

The complete application now contains **138 ORM tables**.

Latest migration:

```text
20260808_0015_firm_knowledge_precedent_system.py
```

### Batch 16 API highlights

```text
GET/POST /api/v1/knowledge/collections
GET/POST /api/v1/knowledge/assets
GET       /api/v1/knowledge/assets/{id}
PATCH     /api/v1/knowledge/assets/{id}
POST      /api/v1/knowledge/assets/{id}/submit
POST      /api/v1/knowledge/assets/{id}/approve
GET       /api/v1/knowledge/assets/{id}/versions
GET/POST  /api/v1/knowledge/assets/{id}/annotations
GET       /api/v1/knowledge/search?q=...
POST      /api/v1/knowledge/promote/draft-section
POST      /api/v1/knowledge/promote/contract-clause
GET/POST  /api/v1/knowledge/playbooks
POST      /api/v1/knowledge/playbooks/{id}/items
POST      /api/v1/knowledge/playbooks/{id}/approve
GET/POST  /api/v1/knowledge/authority-collections
POST      /api/v1/knowledge/authority-collections/{id}/items
POST      /api/v1/knowledge/authority-collections/{id}/approve
```

Premium workspace:

```text
/knowledge
```

Tabs: Library, Review queue, Matter playbooks and Authority collections.

### Batch 16 verification status

```text
156 tests passed
2 existing async SQLite integration modules skipped in the build sandbox
138-table ORM schema creation passed
Alembic 0014 → 0015 upgrade passed
Alembic 0015 → 0014 downgrade passed
Re-upgrade passed
Alembic schema drift check passed
Python compile pass
45 TypeScript/TSX source files syntax-transpile passed
```

The two skipped async tests require `aiosqlite`, which remains declared in project dependencies but is unavailable in the execution sandbox.

## Batch 15 — evidence and litigation discovery intelligence

### Deterministic evidence register

Processed matter documents can be rebuilt into an evidence register without a paid LLM. The classifier uses filename/text rules in English and Hindi and records its confidence/matched terms. A lawyer can then review or reject the classification, assign strength, and separately record whether authenticity/admissibility have actually been checked. Those two fields are never auto-decided.

Supported evidence families include court filings/orders, contracts, correspondence, financial records, identity/property documents, electronic records, photos/video, witness statements, expert material, and other evidence.

### Issue-wise evidence mapping

Batch 15 introduces `LitigationIssue` records. Common issues such as agreement, payment, notice/service, termination, property title/possession, party identity/capacity and electronic-record authenticity can be suggested deterministically from matter facts and document text. Lawyers can create their own issues and manually map evidence as `supports`, `contradicts` or `context`.

### Evidence gaps

The engine creates explicit gaps when an issue has no mapped supporting evidence or when the Matter Intelligence engine still has an open contradiction. A gap is a review item, not a legal conclusion. It includes a suggested next action and stays open until a lawyer resolves/dismisses it.

### Witness and transaction graph

Common `PW-1` / `DW-1` / witness / `गवाह` markers can seed a witness register. The graph API combines:

```text
Litigation issue
      ↕
Evidence item
      ↕
Witness

Money/payment fact → supporting evidence document
```

Transaction nodes are sourced from structured money facts already extracted by Batch 3, preserving the original fact-source provenance rather than inventing transactions from a model.

### Witness preparation

Witness-preparation questions are deterministic foundation prompts linked to witnesses/evidence. The UI explicitly warns that they are counsel preparation aids, not scripts to coach testimony or alter recollection. Bespoke legal strategy can later use the verified AI layer if the lawyer chooses.

### Exhibits / annexures and bundles

Evidence items can receive proposed/marked/admitted/rejected exhibit labels (including annexure-style labels chosen by the firm/court). Hearing/trial/discovery bundles are ZIP exports containing source documents, an `INDEX.md`, `manifest.csv`, document hashes and a bundle SHA-256. Existing matter export policy is enforced at creation and download.

A draft bundle can be generated while review continues. **Finalization is blocked until every included evidence item is lawyer-reviewed.**

### Batch 15 database additions

Batch 15 adds 10 tables:

```text
litigation_issues
evidence_items
evidence_issue_links
evidence_witnesses
evidence_witness_links
evidence_gaps
evidence_bundles
evidence_bundle_items
evidence_exhibits
witness_prep_questions
```

The complete application now contains **127 ORM tables**.

Latest migration:

```text
20260808_0014_evidence_litigation_discovery.py
```

### Batch 15 API highlights

```text
GET/POST /api/v1/evidence/matters/{matter_id}/...
POST     /api/v1/evidence/matters/{matter_id}/rebuild
GET      /api/v1/evidence/matters/{matter_id}/dashboard
GET      /api/v1/evidence/matters/{matter_id}/graph
PATCH    /api/v1/evidence/items/{item_id}
POST     /api/v1/evidence/items/{item_id}/issues
POST     /api/v1/evidence/witnesses/{witness_id}/prep/generate
POST     /api/v1/evidence/matters/{matter_id}/bundles
POST     /api/v1/evidence/bundles/{bundle_id}/finalize
GET      /api/v1/evidence/bundles/{bundle_id}/download
```

Premium workspace:

```text
/evidence
```

Tabs: Evidence, Issues, Witnesses, Gaps, Bundles and Graph.

### Batch 15 verification status

```text
151 deterministic tests passed before final packaging
2 existing async SQLite integration modules skipped in the build sandbox
127-table ORM schema creation passed
Alembic 0013 → 0014 upgrade passed
Alembic 0014 → 0013 downgrade passed
Re-upgrade passed
Alembic schema drift check passed
Python compile pass
TypeScript/TSX syntax parse pass
```

The skipped async tests require `aiosqlite`, which remains declared in the project dependencies but is unavailable in the execution sandbox.

## Batch 14 — workflow automation and court operations

### Deterministic operations engine

Batch 14 adds a general workflow event layer so routine legal operations do not require an LLM. Court changes and reviewed-deadline events can trigger versioned workflow templates that create tasks and in-app notifications.

Built-in triggers include:

```text
court.new_order
court.hearing_date_changed
court.case_status_changed
deadline.due_soon
```

The built-in templates are seeded automatically on the first court snapshot/due sweep and can also be seeded explicitly through the API/UI.

### Court tracking and source boundaries

A matter can have a court tracker keyed by its case/CNR information and source type. Batch 14 supports:

```text
manual
ecourts_manual
official_import
mock
```

`ecourts_manual` means the legal team records/imports information obtained through a permitted official eCourts flow. The project does **not** implement CAPTCHA solving, CAPTCHA outsourcing, or access-control bypasses. Approved official connectors can later submit the same normalized snapshot payload without changing the comparison/workflow engine.

A court snapshot records:

- case status
- case stage
- next hearing date
- judge/bench
- order/proceeding count
- latest order date/reference
- source payload/provenance
- deterministic SHA-256 content hash

The first snapshot establishes a baseline. Later snapshots are compared field-by-field and may create:

```text
NEW_ORDER                high
HEARING_DATE_CHANGED     high
CASE_STATUS_CHANGED      medium
STAGE_CHANGED            medium
JUDGE_CHANGED            informational
```

A detected change is never treated as a substantive legal conclusion. It remains reviewable and should be confirmed against the underlying official record.

### Operational workflow path

```text
Court / deadline event
        ↓
Workflow event (deduplicated)
        ↓
Versioned workflow template
        ↓
Workflow run
        ↓
Task + in-app notification
        ↓
Due/overdue sweep
        ↓
Escalation
        ↓
Lawyer / partner action
```

The sweep engine only creates deadline events for **lawyer-reviewed** `MatterDeadline` records. It therefore does not convert an unverified limitation/date calculation into an operational deadline.

### Confidentiality behavior

Batch 14 reuses the Batch-10 matter-access layer throughout the operations service. Daily agenda, court trackers, change lists, task lists, dashboard counts, and partner supervision are filtered against visible matter IDs. An ethical-wall matter is therefore not leaked simply through aggregate operational counts.

Escalation does not automatically reveal a restricted matter to a partner. The triggering actor remains the default recipient; any future firm-wide assignment rules should continue to resolve matter access before notification delivery.

### Operations UI

New premium workspace:

```text
/operations
```

Tabs:

```text
Agenda
Court
Workflows
Supervision
```

The workspace includes:

- seven-day lawyer agenda
- open/overdue/high-priority metrics
- court tracker creation
- manual/approved snapshot entry
- deterministic court change comparison
- review controls
- workflow-template catalog
- due sweep
- task completion
- partner workload supervision
- explicit source-boundary warning

### Batch 14 database additions

Batch 14 adds 10 tables:

```text
workflow_templates
workflow_events
workflow_runs
workflow_tasks
workflow_notifications
workflow_escalations
court_case_trackers
court_case_snapshots
court_case_changes
operations_preferences
```

The complete application now contains **117 ORM tables**.

Latest migration:

```text
20260808_0013_workflow_automation_court_operations.py
```

### Batch 14 API highlights

```text
GET  /api/v1/operations/dashboard
GET  /api/v1/operations/agenda
GET  /api/v1/operations/supervision

POST /api/v1/operations/templates/seed
GET  /api/v1/operations/templates

GET   /api/v1/operations/tasks
POST  /api/v1/operations/tasks
PATCH /api/v1/operations/tasks/{task_id}
POST  /api/v1/operations/sweep

GET  /api/v1/operations/notifications
POST /api/v1/operations/notifications/process

GET  /api/v1/operations/court-sources
GET  /api/v1/operations/trackers
POST /api/v1/operations/trackers
POST /api/v1/operations/trackers/{tracker_id}/snapshots
GET  /api/v1/operations/trackers/{tracker_id}/snapshots
GET  /api/v1/operations/court-changes
POST /api/v1/operations/court-changes/{change_id}/review
```

### Scheduling note

The deterministic sweep is exposed as an authenticated operation rather than hidden inside the web server. For a single-process deployment it can be invoked by cron/systemd; for scaled deployments, use a durable job runner/queue and a properly scoped service identity. Approved court-source polling should submit normalized snapshots through the same service boundary.

### Batch 14 verification status

```text
142 deterministic tests passed before final packaging
2 existing async SQLite integration modules skipped in the build sandbox
117-table ORM schema creation passed
Alembic 0012 → 0013 upgrade passed
Alembic 0013 → 0012 downgrade passed
Re-upgrade passed
Alembic schema drift check passed
Python compile pass
TypeScript/TSX syntax-transpile pass
```

The skipped async tests require `aiosqlite`, which remains declared in the project dependencies but is unavailable in the execution sandbox.


## Batch 13 — client money and document collaboration

### Client-money control layer

Batch 13 introduces a separate ledger for money held on behalf of clients. It deliberately does **not** hard-code a jurisdiction-specific professional-accounting rule or claim regulatory certification. Instead it provides auditable accounting primitives that a firm can configure and review against its own obligations.

Core controls:

- separate client-money bank-control accounts
- balanced journal entries (debits must equal credits)
- client and optional matter allocation
- balances recomputed from posted journal lines rather than mutable balance fields
- receipt/deposit posting
- transfer-to-fees requests
- default four-eyes approval (`require_separate_approver=true`)
- invoice-linked transfer execution
- finance/client security-wall enforcement
- period reconciliation records
- different-user reconciliation review
- zero-difference requirement before a reconciliation can be locked
- SHA-256 event fingerprints and security audit events

Posting model:

```text
Client money received
  Dr  Bank control
  Cr  Client liability

Approved refund/disbursement/fee transfer
  Dr  Client liability
  Cr  Bank control
```

The receivables ledger from Batch 12 remains separate from this client-money subledger. An approved fee transfer can create the corresponding cleared invoice payment while preserving the separate client-money journal event.

### Payment-provider abstraction

The default code path still requires no paid payment API. Batch 13 includes:

- manual provider adapter
- deterministic mock/sandbox provider using `example.invalid` URLs
- provider-connection records
- payment intents
- provider-event/idempotency foundation
- public provider configuration only in the database
- environment-prefix pointer for secrets instead of storing provider secret keys in rows

`razorpay`, `stripe`, and other provider enum values are placeholders for explicit production connectors. The service returns `501` rather than pretending those integrations exist.

### Document collaboration

Every matter document can now have an independent version history without overwriting the original upload:

- immutable numbered document versions
- file SHA-256 per version
- change notes
- local version download
- document comments
- anchor JSON for later page/paragraph/coordinate comments
- comment resolution
- assigned internal review requests
- immutable approval decisions
- client approval requests tied to an exact document version
- client portal approval / request-changes / decline response
- manual/mock e-signature envelopes
- signer ordering and workflow states

The manual/mock e-sign flow is orchestration state only. It does not claim to provide a cryptographic or legally qualified electronic-signature service. External providers require an explicit production connector.

### Premium UI additions

New internal workspaces:

```text
/finance
/collaboration
```

`/finance` provides a calm client-money dashboard, account register, derived ledger, receipt posting and transfer approval queue. `/collaboration` provides matter/document selection, version history, snapshots/uploads and review comments.

The external `/portal` workspace now also displays explicit document-approval requests and records the client's response against the exact requested version.

### Batch 13 database additions

Batch 13 adds 16 tables:

```text
client_money_accounts
client_money_journal_entries
client_money_journal_lines
client_money_transfer_requests
client_money_reconciliations
client_money_reconciliation_items
payment_provider_connections
payment_intents
payment_provider_events

document_versions
document_comments
document_review_requests
document_approvals
client_document_approval_requests
esignature_envelopes
esignature_signers
```

The complete application now contains **107 ORM tables**.

Latest migration:

```text
20260808_0012_client_money_payments_collaboration.py
```

### Batch 13 API highlights

```text
GET/POST /api/v1/client-money/accounts
GET      /api/v1/client-money/accounts/{id}/balance
GET      /api/v1/client-money/accounts/{id}/entries
POST     /api/v1/client-money/deposits
GET/POST /api/v1/client-money/transfers
POST     /api/v1/client-money/transfers/{id}/decision
POST     /api/v1/client-money/transfers/{id}/execute
POST     /api/v1/client-money/reconciliations
POST     /api/v1/client-money/reconciliations/{id}/review
GET/POST /api/v1/client-money/providers
POST     /api/v1/client-money/payment-intents

GET/POST /api/v1/collaboration/documents/{id}/versions
POST     /api/v1/collaboration/documents/{id}/versions/snapshot
GET/POST /api/v1/collaboration/documents/{id}/comments
GET/POST /api/v1/collaboration/documents/{id}/reviews
POST     /api/v1/collaboration/documents/{id}/approvals
GET/POST /api/v1/collaboration/documents/{id}/client-approvals
POST     /api/v1/collaboration/documents/{id}/esign
POST     /api/v1/collaboration/esign/{id}/send

GET      /api/v1/portal/approvals
POST     /api/v1/portal/approvals/{id}/respond
```

### Batch 13 verification

The deterministic test suite, ORM schema build, migration upgrade/downgrade/re-upgrade, Alembic drift check, Python compilation and TypeScript/TSX syntax transpilation are all run before packaging. Async SQLite HTTP integration tests remain environment-skipped in the build sandbox because `aiosqlite` is not installed there; it remains declared in `pyproject.toml`.


## Batch 11 — client relationship and intake layer

Batch 11 adds an organization-scoped client operating layer without replacing the legal matter system with a generic sales CRM. It includes:

- lead / enquiry intake
- client register and contacts
- deterministic conflict screening with lawyer review
- masking of conflict candidates found in restricted matters
- onboarding gates
- privacy-conscious KYC verification records (masked/last-four identifiers only by default)
- engagement records
- guarded matter opening after conflict clearance or express override
- matter/client linking and team assignment
- client notes and communication log
- CRM tasks
- time-entry / billing foundation
- client-portal invitation foundation
- premium `/clients` workspace

Conflict matching is deliberately a screening aid, not a legal conclusion. A result with zero candidates remains pending until a lawyer clears it. Matter titles behind an ethical wall are used only for internal matching and are returned to unauthorized users as a generic restricted-match warning.

Client confidentiality now follows the same philosophy as matter confidentiality. A client can be organization-visible or placed behind an explicit/ethical-wall profile with membership grants. Conflict screening may compare against restricted client/contact names internally, but unauthorized reviewers receive only a masked restricted-relationship candidate.

In Batch 11, portal records were invitation/access foundations only. **Batch 12 now implements the external client portal as a separately isolated trust boundary**, with its own session/CSRF model and explicit-sharing rules.

The product now includes matter/document intelligence, legal research, contract drafting and review, redlining, litigation drafting, procedure/deadline/hearing workflows, verified opt-in AI reasoning, and organization/matter/client-level access control.

## Security architecture inherited from Batch 10

```text
Law firm organization
      ↓
Users + memberships + roles
      ↓
Organization security policy
      ↓
Matter security profile
      ↓
Organization access OR explicit-access wall
      ↓
Matter / document grants
      ↓
Remote-AI and export policy
      ↓
Server-side session + CSRF enforcement
      ↓
Append-only audit chain
      ↓
Retention / legal holds / deletion workflow
```

## Security capabilities added

### Organizations, users and roles

Built-in roles:

- Owner
- Admin
- Partner
- Lawyer
- Junior
- Paralegal
- Billing
- Read only

Roles establish a baseline only. Matter-level grants, deny rules, confidentiality walls, organization policies and document grants can further restrict access.

### Matter confidentiality

Every organization-owned matter can have a security profile:

- Internal
- Confidential
- Highly confidential
- Ethical wall

Access modes:

- `organization` — organization role establishes the baseline
- `explicit` — explicit matter grant is required

**Ethical-wall matters always require an explicit grant.** An owner/admin/partner can administer security policy without automatically receiving substantive matter access.

### Fine-grained matter grants

Explicit grants support:

- allow / deny
- view / work / manage
- remote-AI inherit / allow / deny
- export inherit / allow / deny

Deny rules take precedence over role defaults.

### Document grants

The security model contains independent document access grants for view/download/edit controls. The existing document service also enforces the parent matter boundary.

### Remote-AI policy

Remote generative AI remains opt-in at the request level from Batch 9. Batch 10 adds a second organizational security gate:

- organization default allow/deny
- matter override
- individual matter-grant override
- optional MFA requirement
- optional stricter MFA rule for highly confidential / ethical-wall matters

This means `allow_remote=true` on an AI request is not sufficient when firm policy forbids remote AI for that matter.

### Export policy

Contract/draft/redline/file export can be independently controlled by organization, matter and access grant policy.

### Authentication and sessions

The built-in first-party auth foundation uses:

- password hashes created with Python `hashlib.scrypt`
- independent random salt per password
- opaque high-entropy session tokens
- only the SHA-256 session-token hash is stored server-side
- server-side session expiry/revocation
- maximum concurrent-session policy
- account lockout after configurable failed attempts
- HttpOnly session cookie
- SameSite cookie support
- separate CSRF token and unsafe-method validation
- production secure-cookie switch

For enterprise deployment this can later be supplemented/replaced by SSO/OIDC/SAML and a dedicated MFA/identity provider while retaining the authorization layer.

### Audit chain

Security-sensitive events are written to an organization-scoped append-only audit chain with:

- monotonic organization sequence
- previous-entry hash
- entry hash
- optional HMAC signing key
- privacy-safe actor/request metadata
- chain verification endpoint

The chain detects database-level modification/reordering/removal in the recorded sequence. It is not a substitute for an externally immutable/WORM audit store, which is recommended for higher-assurance deployments.

### Retention, legal holds and deletion workflow

Batch 10 adds data structures and APIs for:

- retention policies
- legal holds
- deletion requests
- approval / denial / cancellation / execution state

A legal hold can block a deletion workflow instead of letting an ordinary user silently destroy matter data.

### Legacy matter adoption

Existing Batches 1–9 can contain matters created before organizations existed. Batch 10 keeps those records intact. A security administrator can explicitly adopt each legacy matter into the organization; the migration does not silently reassign confidential data.

## Premium security UI

New routes:

```text
/login
/security
```

The `/login` screen supports both normal sign-in and first-firm bootstrap.

The `/security` workspace contains:

- organization/security overview
- active-session metrics
- member/role management
- organization security-policy controls
- matter confidentiality and access mode
- matter-level AI/export policy
- ethical-wall controls
- explicit matter grants
- legacy-matter adoption
- append-only audit history
- audit-chain verification
- logout/session controls

The UI remains intentionally minimal and professional; security controls are separated from ordinary legal-work screens rather than turning every screen into an admin dashboard.

## Same-origin browser security

The Next.js app proxies `/backend/*` to FastAPI. Browser requests use same-origin cookies and the frontend API helper automatically attaches the CSRF token on unsafe methods. Server-rendered pages forward the incoming session cookie to the backend.

Example `.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=/backend/api/v1
API_INTERNAL_URL=http://localhost:8000
```

## Development vs production auth

For backwards-compatible local development, `.env.example` defaults to:

```dotenv
SECURITY_ENFORCE_AUTH=false
```

This preserves the old single-user development workflow while the security layer is being integrated.

For a real multi-user environment set at least:

```dotenv
SECURITY_ENFORCE_AUTH=true
SECURITY_COOKIE_SECURE=true
SECURITY_BOOTSTRAP_SECRET=<strong random secret>
SECURITY_AUDIT_HMAC_KEY=<strong random key>
SECURITY_PRIVACY_HASH_KEY=<strong random key>
```

Use HTTPS/TLS at the reverse proxy/load balancer. Do not expose a production instance with authentication enforcement disabled.

A template is provided at:

```text
security_examples/production.env.example
```

## First firm bootstrap

With authentication enabled and an empty database:

1. Open `/login`.
2. Choose **Create first firm**.
3. Enter the firm name, slug, owner name/email/password.
4. In production, provide the configured bootstrap secret.
5. The backend creates the organization, its first owner membership, default policy and a new authenticated session.

The production bootstrap endpoint refuses to operate without a configured bootstrap secret.

## API additions

Important security endpoints:

```text
POST  /api/v1/security/bootstrap
POST  /api/v1/security/auth/login
POST  /api/v1/security/auth/logout
GET   /api/v1/security/me
GET   /api/v1/security/overview

GET   /api/v1/security/members
POST  /api/v1/security/members
PATCH /api/v1/security/members/{membership_id}

GET   /api/v1/security/policy
PATCH /api/v1/security/policy

GET   /api/v1/security/legacy-matters
POST  /api/v1/security/matters/{matter_id}/adopt
GET   /api/v1/security/matters/{matter_id}/profile
PATCH /api/v1/security/matters/{matter_id}/profile
GET   /api/v1/security/matters/{matter_id}/access
GET   /api/v1/security/matters/{matter_id}/grants
POST  /api/v1/security/matters/{matter_id}/grants

GET   /api/v1/security/documents/{document_id}/grants
POST  /api/v1/security/documents/{document_id}/grants

GET   /api/v1/security/audit
GET   /api/v1/security/audit/verify

GET   /api/v1/security/retention
POST  /api/v1/security/retention
GET   /api/v1/security/legal-holds
POST  /api/v1/security/legal-holds
GET   /api/v1/security/deletions
POST  /api/v1/security/deletions
```

## Database

Batch 10 adds 13 tables:

```text
organizations
security_users
organization_memberships
organization_security_policies
user_sessions
matter_security_profiles
matter_access_grants
document_access_grants
audit_chain_heads
security_audit_entries
retention_policies
legal_holds
deletion_requests
```

Batch 11 adds 16 client/intake tables:

```text
crm_leads
clients
client_security_profiles
client_access_grants
client_contacts
conflict_checks
conflict_candidates
client_onboarding
client_kyc_records
engagements
matter_client_links
client_notes
crm_tasks
client_communications
time_entries
client_portal_access
```

The complete project contains **76 ORM tables**.

Latest migrations:

```text
20260808_0009_law_firm_security.py
20260808_0010_client_crm_legal_intake.py
```

## Run locally

### Backend

```bash
cd apps/api
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env          # Windows: copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API docs:

```text
http://localhost:8000/docs
```

### Frontend

```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

Open:

```text
http://localhost:3000/login
```

When `SECURITY_ENFORCE_AUTH=false`, existing development pages can still be used without a login.

## AI-cost boundary

The security layer uses no generative model. Existing deterministic document processing, matter intelligence, legal search, contract generation/review, redlining, procedure calculation and security/permissions continue to run without paid LLM calls. Batch 9 AI reasoning remains a separately routed, evidence-bounded and policy-controlled capability.

## Deployment note

The security architecture is a substantial application-security **foundation**, not a claim of compliance certification or a complete enterprise identity system. Before production use with real privileged client data, deploy behind TLS, use a managed secrets system, backups, database encryption controls, security monitoring, dependency/container scanning, a production-grade identity/MFA solution where required, and an external immutable audit destination where the threat model demands it. Perform independent security testing before relying on the system for confidential legal practice.


## Batch 12 — billing, accounting and external client portal

Batch 12 adds a deterministic finance layer and a separate client-facing trust boundary. It includes:

- organization billing profile and invoice numbering
- rate cards / lawyer-rate records
- hourly, fixed-fee, retainer, capped, contingency and custom fee-arrangement records
- billable expenses and receipt-document references
- invoice drafts with line-level Decimal arithmetic
- explicit CGST / SGST / IGST / cess fields (the software does **not** infer tax applicability or rates)
- invoice tax-review findings and human review gate
- immutable issue-time invoice snapshots + SHA-256 hashes
- source time-entry / expense locking once invoiced
- partial / full payments and outstanding balances
- client ledger entries and statements
- billing overview metrics
- external client activation and login
- separate opaque portal sessions and CSRF tokens
- explicit document / invoice / matter-update sharing
- portal requests and secure messages
- immutable issued-invoice snapshot viewing
- portal document download only after an active explicit share
- premium `/billing` and `/portal` workspaces

### Billing lifecycle

```text
Time entries / expenses / fee arrangement
              ↓
          Draft invoice
              ↓
       Explicit tax review
              ↓
         Issue + number
              ↓
 Immutable invoice snapshot
       + SHA-256 content hash
              ↓
      Ledger debit / payment
              ↓
 Partially paid / paid status
```

Draft invoices can be edited. Issued invoices are represented by an immutable snapshot; subsequent payments are recorded as separate financial events instead of rewriting the issued snapshot.

The billing engine deliberately does not decide whether GST applies or choose a tax rate. Tax components, place of supply, service code, reverse-charge data and supplier/client tax identifiers are explicit inputs and reviewable metadata. Production firms should configure their own verified tax policy and review invoices before issue.

### External portal trust boundary

The client portal does **not** reuse an internal lawyer session. It has its own:

```text
Client portal invitation
        ↓
Single-use activation token (hashed in DB)
        ↓
Portal identity + password
        ↓
Opaque portal session (hashed in DB)
        ↓
Separate CSRF token
        ↓
Explicitly shared records only
```

The portal does not enumerate internal matters, documents or invoices. A client sees only records linked to that portal access and explicitly shared by an authorized internal user. Invoice sharing uses the immutable issue-time snapshot, and document downloads require an active share with download permission.

Ethical-wall client restrictions continue to apply to internal billing/portal administrators. A billing-role user cannot use the portal-management endpoints to bypass an explicit client wall or obtain legal-document sharing permission.

### Batch 12 database additions

Batch 12 adds 15 tables:

```text
organization_billing_profiles
billing_rate_cards
billing_rates
fee_arrangements
billing_expenses
invoices
invoice_lines
invoice_versions
payments
client_ledger_entries

client_portal_users
client_portal_sessions
client_portal_shares
client_portal_messages
client_portal_requests
```

`client_portal_access` also gains hashed invitation-token and expiry fields.

The complete application now contains **91 ORM tables**.

Latest migration:

```text
20260808_0011_billing_accounting_client_portal.py
```

### Batch 12 API highlights

Internal authenticated billing/portal-management routes:

```text
GET/PUT /api/v1/billing/profile
GET      /api/v1/billing/overview
GET/POST /api/v1/billing/rate-cards
POST     /api/v1/billing/rate-cards/{id}/rates
GET/POST /api/v1/billing/fee-arrangements
GET/POST /api/v1/billing/expenses
GET/POST /api/v1/billing/invoices
POST     /api/v1/billing/invoices/{id}/review
POST     /api/v1/billing/invoices/{id}/issue
GET/POST /api/v1/billing/payments
GET      /api/v1/billing/clients/{client_id}/statement

POST /api/v1/billing/portal/access/{access_id}/activation-token
POST /api/v1/billing/portal/shares
POST /api/v1/billing/portal/requests
POST /api/v1/billing/portal/access/{access_id}/messages
```

External portal routes:

```text
POST  /api/v1/portal/activate
POST  /api/v1/portal/login
POST  /api/v1/portal/logout
GET   /api/v1/portal/dashboard
POST  /api/v1/portal/messages
PATCH /api/v1/portal/requests/{id}
GET   /api/v1/portal/shares/{id}/invoice
GET   /api/v1/portal/shares/{id}/document
```

### Verification status

```text
122 deterministic tests passed
2 existing async SQLite integration modules skipped in the build sandbox
91-table ORM schema creation passed
Alembic 0010 → 0011 upgrade passed
Alembic 0011 → 0010 downgrade passed
Re-upgrade passed
Alembic schema drift check passed
Python compile pass
TypeScript/TSX syntax-transpile pass
```

The skipped async tests require `aiosqlite`, which is already declared in project dependencies but is unavailable from the execution sandbox's package index.

### Finance and portal deployment note

This is an application billing/accounting foundation, not a substitute for tax/accounting review and not a banking or trust-account certification. Before production use, reconcile invoices/payments against the firm's accounting system, implement jurisdiction-specific tax controls, decide the firm's trust/client-money accounting requirements, and security-test the external portal independently.
## Historical Batch 28 · Release Candidate 1

Batch 28 RC1 (`0.28.0-rc.1`, database revision `20260808_0027`) predates the Batch-29 Case Lookup and Legal Remedy Analysis feature and is therefore superseded as release evidence. The RC validation framework remains in the codebase, but production/pilot validation must be rerun against `0.29.0-rc.1` / `20260808_0028`, including the new critical Case Lookup + Remedy scenario and lawyer-reviewed active remedy packs.
