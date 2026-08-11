> **Batch 29 status:** This document describes the historical Batch-28 RC1 control plane. Case Lookup + Legal Remedy Analysis was added afterward, so RC1 is superseded. Current code is `0.29.0-rc.1` / `20260808_0028`; rerun all RC evidence before pilot use.

# AI Junior Lawyer — Release Candidate 1

Version: `0.28.0-rc.1`

Batch 28 freezes major product features and introduces the final production-validation control plane. Passing the local/source gates means the codebase is internally consistent; it does **not** by itself mean that a particular deployment is safe for real privileged client data.

RC1 becomes pilot-ready only when a recorded validation campaign has passed all critical and required scenarios, pilot-readiness checks, artifact/rollback requirements and manager sign-off against a representative staging deployment.

## Feature freeze

Major legal/product modules are frozen for RC1. Changes after this point should normally be limited to defects, security fixes, legal-data corrections, accessibility issues, deployment fixes and measured performance improvements. New feature requests should be deferred until after the controlled lawyer pilot unless they block safe use.

## Required validation classes

- PostgreSQL + S3-compatible staging topology
- English and Hindi end-to-end workflow
- authenticated ethical-wall / IDOR testing
- internal-session, CSRF and external-client-portal boundary testing
- full backup and isolated restore verification
- 1,000-page large-document workflow
- representative 100k-document indexed-search benchmark
- worker queue saturation / lease recovery
- keyboard and screen-reader pass
- legal-corpus hash/version integrity
- release artifact integrity and verified rollback point
- pilot-readiness checklist and human sign-off

## RC status language

Use these terms precisely:

- **Source gate passed** — deterministic tests and static release checks passed.
- **Staging validated** — the required scenarios were executed on representative staging infrastructure and evidence was recorded.
- **RC gate passed** — all critical/required scenarios, pilot checks, artifact/rollback requirements and sign-offs passed.
- **Pilot-ready** — RC gate passed and the firm has approved the controlled pilot runbook.
- **Production-ready** — should only be used after the pilot and production deployment/security/recovery evidence are reviewed for the target firm.

RC1 is lawyer-supervised software. It does not remove professional review obligations for filings, legal advice, limitation periods, admissibility, tax treatment, client-money rules or jurisdiction-specific practice.

## Superseded by Batch 29 feature change

Batch 28 RC1 evidence was created before Case Lookup + Legal Remedy Analysis. The current code version is `0.29.0-rc.1` at database revision `20260808_0028`. Treat prior RC1 evidence as historical only. A new validation campaign must include the `case_lookup_remedy_e2e` critical scenario and a required pilot check confirming that every active remedy rule pack has been lawyer-reviewed with verified authority.
