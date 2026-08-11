# Final Consolidated Build Validation Status

Date: 2026-08-08
Candidate: `0.29.0-rc.1`
Database revision: `20260808_0028`
Feature state: Complete source through Case Lookup + Legal Remedy Analysis

## Verified in this build environment

- **289 backend tests passed**; 2 pre-existing async SQLite integration tests are skipped because the sandbox lacks the already-declared async SQLite driver.
- **17/17 deterministic legal golden cases passed at 100%**, including Batch-29 CNR parsing, Hindi case-type parsing and verified-trigger remedy/deadline behavior.
- static security baseline passed.
- Python compilation passed.
- **85 TypeScript/TSX files** passed the dependency-light syntax/transpile gate with zero errors.
- full Alembic upgrade to Batch 29 passed.
- Batch 29 → Batch 28 downgrade returned the schema from **250 to 230 application tables**.
- Batch 28 → Batch 29 re-upgrade passed.
- Alembic drift check reports no pending schema operations.
- synthetic official-case example and unverified remedy-pack template validate against their Pydantic schemas.
- combined source/legal/security/frontend/migration gate passed; snapshot hash: `391cb351252c30f8861072ccedc86058dada208dcdd606f1d544724ace2dcb09`.

## Intentionally not claimed as verified

The final consolidated `0.29.0-rc.1` source includes Batch-29 functionality added after Batch-28 RC1, so the prior RC evidence is superseded. Before a real-lawyer pilot, a fresh `/validation` campaign must record representative staging evidence for the existing RC scenarios **plus** the new critical `case_lookup_remedy_e2e` scenario.

This sandbox does not prove:

- live District Court / High Court / Supreme Court case retrieval from protected official interfaces; these remain approved-connector or user-assisted flows where verification/CAPTCHA is required;
- correctness/completeness of any substantive India remedy rule pack, because the build deliberately ships only an **unverified template** rather than invented limitation/maintainability rules;
- live PostgreSQL + MinIO/S3 production topology after Batch-29 changes;
- authenticated E2E/ethical-wall penetration matrix on representative staging;
- new staging load/recovery/browser accessibility evidence after Batch 29.

An active remedy pack is an operational legal-data artifact and must be lawyer-reviewed with verified authority before activation. Missing verified coverage produces a warning/research prompt rather than an unsupported remedy conclusion.
