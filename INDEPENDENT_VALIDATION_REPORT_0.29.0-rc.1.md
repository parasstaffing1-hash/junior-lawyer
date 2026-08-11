# AI Junior Lawyer 0.29.0-rc.1 — Independent Validation Report

Validation date: 8 August 2026  
Validator role: independent architecture, security, QA, DevOps, legal-tech, and release review

## A. Executive summary

The supplied SHA-256 matched its manifest and the source contains a broad FastAPI/Next.js legal-practice platform. A clean Python 3.12 install, 292 backend unit tests, deterministic legal QA, security baseline, TypeScript, clean npm install, dependency audit, and a real Next.js production build were executed. Several implementation claims remain supported only by unit/static tests rather than authenticated PostgreSQL end-to-end evidence.

The release is not safe for a controlled lawyer pilot. The mandatory PostgreSQL migration, authenticated multi-tenant/IDOR matrix, real production topology, backup/restore, upload abuse, realistic-volume performance, browser accessibility, and external sandbox integrations were not completed. The frontend lint gate fails, the backend originally could not be packaged, and the production build initially exposed four nullability defects.

## B. Final status

**NOT READY FOR PILOT**

## C. Critical blockers

1. No completed real-PostgreSQL zero-to-HEAD, downgrade/re-upgrade, schema-drift, constraint, locking, concurrency, UUID/JSONB, or `SKIP LOCKED` validation. Docker Desktop did not provide an engine and `psql` was unavailable.
2. No authenticated HTTP security matrix against two real organizations; confidentiality, IDOR, ethical-wall, portal, billing, export, AI, and background-job isolation are not independently proven end to end.
3. No production-style Caddy/TLS + Next.js + replicated FastAPI + PostgreSQL + MinIO + workers + scheduler boot.
4. No real staging database/object-store backup and restore drill.
5. No realistic-volume or concurrency benchmarks; no defensible p50/p95/p99, throughput, resource, error-rate, or queue-lag numbers.
6. No approved live/sandbox court, Google, Razorpay, or DocuSign credential exercise.

## D. High-severity defects

- The supplied backend `pyproject.toml` was not installable: setuptools aborted on multiple top-level packages (`app`, `alembic`). Fixed by explicitly including `app*`.
- The supplied frontend had no lockfile. A generated `package-lock.json` now supports a successful `npm ci`; absence from the supplied RC was a build-reproducibility and supply-chain defect.
- Production Next.js type checking found four nullable navigation-hook defects. Fixed with null-safe handling in app shell, reader, search, and sidebar.
- ESLint fails with 28 errors and 10 warnings, dominated by React effect/state violations; this gate remains unresolved.

## E. Medium defects

- Ruff fails with 1,456 findings: 807 `B008`, 190 import-order, 102 verbose Decimal construction, 84 legacy union annotations, 64 unused imports, and additional exception/timezone/async issues.
- Default Windows Turbopack build could not load a valid native SWC binding; the official Webpack production build passed. CI should use a supported/pinned build environment.
- Dependency ranges are broad and unpinned on the Python side; the clean install resolved current packages rather than a locked known-good set.
- SQLite migration cycle timed out and retained a lock, so even the fallback actual table count was unavailable.

## F. Low defects / polish

- Local QA emitted a PyMuPDF warning that the `fitz` API is deprecated.
- Frontend lint includes unused variables, an unescaped entity, an internal `window.location.href`, and stale hook-disable comments.
- Source includes intentional manual/mock integration modes; UI labels generally disclose them, but production policy must prohibit mock providers.

## G. Security findings

Passed only as deterministic/unit evidence: password/security crypto primitives, audit chain, portal policy helpers, integration SSRF host checks, AI prompt/output boundary, and one ethical-wall golden case. The security baseline ran 2/2 passing cases.

Not executed: invalid/brute-force login over HTTP, lockout timing, session expiry/idle/revocation/fixation, cookie inspection, CSRF, concurrent sessions, role escalation, cross-tenant direct-ID enumeration, search-before-ranking permission proof, hostile uploads, webhook replay/DNS rebinding, private-network SSRF, and secret leakage through runtime logs/snapshots. These omissions are release blocking.

## H. Legal-accuracy findings

The deterministic QA gate passed 17/17 golden probes across language, citation, deadline, evidence, security, drafting, search, OCR, case lookup, remedy, and contract categories. These fixtures verify expected shapes and selected rules, not broad Indian-law correctness, authority currency, jurisdictional coverage, or lawyer-grade maintainability analysis. No independent primary-source proposition audit was completed. The system must retain lawyer review and uncertainty labels.

## I. Case lookup findings

Parser/golden coverage passed exact CNR, typed number/year, Hindi case type, and snapshot-diff unit tests. No approved live official-source lookup, CAPTCHA-protected flow, saved court preference workflow, stale/cache refresh, full normalized record, or production UI exercise was performed.

## J. Legal remedy analysis findings

Unit and golden tests passed a verified-trigger/deadline case, source markers, insufficient-coverage behavior, and remedy engine primitives. No representative multi-jurisdiction primary-source audit, real fetched case, memo-to-draft provenance E2E, or English/Hindi/Hinglish lawyer review was executed. Remedy safety is therefore unproven for pilot use.

## K. Performance results

No product performance benchmark was completed. No numbers are asserted. Dependency download/build elapsed times are environment observations and are not product benchmarks.

## L. Accessibility results

Static accessibility unit checks are included in the 292 passing tests. No Axe/browser screen-reader, keyboard, mobile/tablet, contrast, reduced-motion, font-scaling, long-Hindi-text, or focus-flow campaign was completed. WCAG compliance is not claimed.

## M. Backup/restore results

Backup engine unit tests passed within the backend suite. No real PostgreSQL/object-store backup, SHA-256 restore verification, RPO/RTO measurement, or staging restore drill was performed.

## N. Production deployment results

Production Compose statically defines PostgreSQL, MinIO/init, volume init, migrate, API, worker, scheduler, web, and Caddy services. The topology was not booted because the Docker engine remained unavailable. TLS, port exposure, probes, migration lock, startup ordering, S3 OCR, rollback, and backups are unvalidated.

## O. Test summary

- Backend pytest: **292 run, 292 passed, 0 failed, 0 skipped**.
- Python compileall: passed.
- Backend Ruff: **1,456 findings; failed**.
- Deterministic golden legal QA: **17 run, 17 passed, 0 failed**.
- Security baseline: **2 run, 2 passed, 0 failed**.
- Frontend clean install: `npm ci` passed for 347 packages.
- Frontend production dependency audit: 0 reported vulnerabilities.
- TypeScript: passed after four fixes.
- ESLint: **38 findings (28 errors, 10 warnings); failed**.
- Next.js production build: passed using Next.js 16.3.0 Webpack; 31 routes generated/validated.
- Browser E2E cases: **0 run** (three Playwright spec files exist).
- Authenticated security cases: **0 run over HTTP**.
- Migration: graph has 28 files and head `20260808_0028`; real PostgreSQL not run; SQLite cycle timed out.
- ORM table count: **250**. Actual migrated table count: **not obtained**.
- External integrations: **0 exercised with approved credentials**.

## P. Production checklist

- [ ] Pin/lock backend dependencies and retain the frontend lockfile.
- [ ] Make Ruff and ESLint gates pass without blanket suppression.
- [ ] Run fresh PostgreSQL upgrade/downgrade/re-upgrade and compare all 250 ORM tables to migrated schema.
- [ ] Boot the production Compose topology with only Caddy public.
- [ ] Execute authenticated two-organization confidentiality matrix and portal enumeration tests.
- [ ] Complete hostile-upload, webhook, SSRF, prompt-injection, and secret-leak campaigns.
- [ ] Complete real PostgreSQL + object-store backup/restore drill.
- [ ] Run realistic-volume performance/stress tests and publish raw evidence.
- [ ] Run browser E2E and accessibility campaigns.
- [ ] Exercise approved sandbox integrations or mark them unavailable in-product.

## Q. Pilot checklist

- [ ] Close every critical blocker above.
- [ ] Obtain Indian-law domain review of remedy packs, limitation rules, forums, effective dates, and citations.
- [ ] Define supported jurisdictions/features and display unsupported-coverage warnings.
- [ ] Use synthetic/de-identified pilot data until confidentiality tests pass.
- [ ] Establish incident response, backup ownership, RPO/RTO, audit review, and rollback owners.
- [ ] Require lawyer confirmation for remedies, deadlines, conflicts, admissibility, authenticity, drafts, and exports.

## R. Files modified during validation

- `apps/api/pyproject.toml` — explicit setuptools application package discovery.
- `apps/web/package-lock.json` — generated reproducible npm dependency graph.
- `apps/web/tsconfig.json` — Next.js added generated type include during production build.
- `apps/web/components/app-shell.tsx` — null-safe pathname.
- `apps/web/components/document-reader.tsx` — null-safe search parameters.
- `apps/web/components/search-workspace.tsx` — null-safe search parameters.
- `apps/web/components/sidebar.tsx` — null-safe pathname.
- `INDEPENDENT_VALIDATION_REPORT_0.29.0-rc.1.md` — this report.

Generated dependency/build caches and disposable validation databases are not release source changes and are excluded from the release artifact.

## S. Final release artifact

The remediated source ZIP, checksum, and manifest are emitted alongside this report. The package excludes dependency and build-cache entries. Artifact integrity proves file identity only; it does not alter the **NOT READY FOR PILOT** decision.
