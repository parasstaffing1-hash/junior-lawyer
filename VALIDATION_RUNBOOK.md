# RC1 Production Validation Runbook

## 1. Build/source gate

From `apps/api`:

```bash
python scripts/run_rc_local_gate.py --output ../../rc-local-gate.json
```

This must pass but intentionally reports `staging_validated=false` and `rc_ready=false`.

## 2. Representative staging

Deploy the Batch-24 production topology using PostgreSQL and S3-compatible object storage. Use a staging hostname and non-production credentials. Authentication must be enforced, secure cookies enabled, remote AI disabled unless the test explicitly needs it, and source/legal-data feeds must use controlled test manifests.

Record CPU, RAM, storage, PostgreSQL version, worker counts, object-storage topology, network placement and application build hash in the validation evidence.

## 3. Generate non-client fixtures

Example:

```bash
python scripts/generate_validation_fixtures.py \
  --output-dir ../../validation-output \
  --documents 100000 \
  --pages-per-document 1 \
  --pdf-pages 1000 \
  --seed 28
```

The generated material is synthetic and contains no client data. Do not use production client documents for performance testing unless the firm's privacy/security process explicitly approves a de-identified dataset.

## 4. Browser E2E

Install web dependencies and Playwright browsers in staging CI:

```bash
cd apps/web
npm ci
npx playwright install --with-deps chromium
JL_E2E_BASE_URL=https://staging.example.test \
JL_E2E_EMAIL='...' \
JL_E2E_PASSWORD='...' \
JL_E2E_ORG_SLUG='...' \
npm run test:e2e
```

Use a synthetic/de-identified large document ID through `JL_E2E_LARGE_DOCUMENT_ID` for the document-reader test.

Credentials belong in CI secret storage and must not be checked into the repository or attached to validation evidence.

## 5. Authenticated security matrix

Edit a copy of `validation_examples/authenticated-security-cases.json` with explicit staging fixture IDs. Provide session/CSRF values through environment variables only:

```bash
JL_VALIDATION_COOKIE='jl_session=...' \
JL_VALIDATION_CSRF='...' \
python scripts/run_authenticated_security_matrix.py \
  --base-url https://staging.example.test \
  --cases ../../validation_examples/authenticated-security-cases.json \
  --output ../../authenticated-security-report.json
```

Critical target: zero ethical-wall/IDOR/session/CSRF/client-portal boundary failures. The runner is bounded to the supplied host and case list; it is not a scanner or brute-force tool.

## 6. Load and search

Use `scripts/run_http_load.py` for bounded HTTP scenarios. For 100k-search validation, first ingest/index the synthetic corpus, then record the exact query workload, p50/p95/p99, success/error rates, hardware and index size. Do not infer a production capacity claim from local laptop results.

## 7. Workers

Queue synthetic OCR/search/evidence jobs until the planned staging saturation level is reached. Confirm leases renew, crashed workers release work after lease expiry, retries/backoff behave as configured, dead letters are explainable, and `lost_jobs=0`.

## 8. Backup/restore

Run a full database + application/object-storage backup using the System Health/Backup subsystem. Restore into an isolated target only. Verify database integrity, object/file hashes and restore manifests; record observed RPO/RTO and confirm the live staging environment was not overwritten.

## 9. Accessibility

Perform keyboard-only navigation on login, matters, search, document reader, drafting, contracts, calendar, validation and portal surfaces. Run at least one screen-reader pass on representative English and Hindi workflows. Record blocking issues as zero before passing the scenario. Automated tooling can supplement but not replace manual assistive-technology testing.

## 10. Record results

Create an RC campaign in `/validation`, submit scenario results/evidence through `/api/v1/validation`, complete pilot-readiness checks and record reviewer sign-off. Re-evaluate the campaign. The RC manifest remains `HELD` until every required dependency is present.

## 11. Failure handling

Any critical failure holds the candidate. Fix the defect, rerun the affected scenario plus the local source gate, create new evidence hashes and re-evaluate. Do not waive ethical-wall leakage, IDOR, destructive restore behavior, missing artifact integrity or uncontrolled production credentials.
