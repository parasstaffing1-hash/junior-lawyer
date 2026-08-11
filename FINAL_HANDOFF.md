# AI Junior Lawyer — Final Source Handoff

Version: `0.29.0-rc.1`  
Database revision: `20260808_0028`  
Architecture: India-first · Hindi/English/Hinglish · deterministic-first · local-first

## What this ZIP contains

This is the consolidated source tree, not a patch. It includes every module built across the project: matter/document management, bilingual OCR/extraction, facts/timeline/evidence, legal corpus/search/citations, contracts and redlining, legal drafting, procedure/deadlines/hearings, verified AI routing, firm security, CRM/intake, billing/client portal, client-money controls, collaboration/e-sign foundations, court operations, litigation evidence, firm knowledge, analytics, universal search, indexed search, background workers, system health/backups, QA/release engineering, production deployment, real integration boundaries, legal-data operations, UX/accessibility polish, release-candidate validation infrastructure, Case Lookup, and Legal Remedy Analysis.

## Core product rule

Routine work should use deterministic code, databases, local search, rules, templates, OCR, and local models wherever possible. Remote/paid AI is optional and explicitly permissioned. AI-generated legal content remains evidence-bounded and lawyer-reviewed.

## Quick local start

### API

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### Web

```bash
cd apps/web
npm install
cp .env.local.example .env.local   # Windows: copy .env.local.example .env.local
npm run dev
```

Web: `http://localhost:3000`

### Development services

```bash
cd infrastructure
docker compose up -d
```

## Production deployment

Use `infrastructure/production/README.md` and `DEPLOYMENT.md`. Production uses the dedicated migration service, PostgreSQL, S3-compatible object storage, workers, scheduler, reverse proxy/TLS, health checks, backups, and rollout evidence. Do not let every API replica run Alembic independently.

## Validation commands

```bash
cd apps/api
python -m pytest -q
python scripts/run_local_qa_gate.py
python scripts/run_security_baseline.py
python scripts/run_release_source_gate.py
```

For a real deployment also follow `VALIDATION_RUNBOOK.md`, `RELEASE_CANDIDATE.md`, and `PILOT_GUIDE.md` against representative PostgreSQL/S3 staging.

## Current source-gate status

The final polish build passes the consolidated source gate: backend regression, legal QA, security baseline, frontend static syntax, migration upgrade, downgrade, re-upgrade, and Alembic drift check. See `BUILD_VALIDATION_STATUS.md` for the exact result and snapshot hash.

## Case Lookup + Legal Remedies

`/cases` provides exact CNR and parsed case-number lookup through approved/user-assisted source adapters, normalized `CaseRecord` data, saved cases, source snapshots, and deterministic change detection. Protected official court interfaces are not bypassed.

The Case Workspace includes **Find Legal Remedies**. Remedy candidates come only from active verified rule packs and verified legal authorities. The engine exposes applicability, forum, limitation/deadline, maintainability, required evidence/documents, procedure, risks, and authorities. Missing verified coverage produces a research warning rather than an invented answer. Remedy memo and drafting actions reuse the existing evidence-bounded drafting/AI infrastructure.

## Before real-lawyer pilot

Do not treat this source-gate result as production certification. At minimum, complete a fresh representative staging validation campaign after the Case Lookup/Remedy feature change, including:

- live PostgreSQL + S3-compatible object storage deployment;
- authenticated ethical-wall/IDOR/security scenarios;
- bilingual end-to-end browser workflows;
- 1,000-page document and representative large-corpus tests;
- worker saturation/lease recovery;
- backup + isolated restore drill;
- accessibility/screen-reader/device checks;
- approved official-data/case-source connector validation;
- lawyer review of every active remedy rule pack, limitation rule, and authority;
- real-lawyer pilot sign-off.

## Important legal/data boundaries

- No CAPTCHA bypass is included.
- Court data that requires user verification remains user-assisted/approved-connector based.
- Unverified remedy templates must not be activated as authoritative legal rules.
- Limitation, maintainability, admissibility, tax treatment, client-money rules, and filings retain lawyer-review controls.
- Credentials and provider secrets belong in environment/secret-manager references, not source control or database configuration values.

## Handoff

The source tree is intentionally self-contained and all historical example packs, migrations, tests, deployment files, runbooks and validation tooling are included so the project can be continued without reconstructing earlier batches.
