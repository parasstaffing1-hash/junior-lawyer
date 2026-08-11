# Final Release Status

**Candidate:** `0.29.0-rc.1`  
**Database revision:** `20260808_0028`  
**Feature state:** Source-complete / feature-frozen for pilot validation

## Source validation

The final consolidated source package is expected to pass:

- backend regression tests;
- deterministic legal golden QA;
- security baseline;
- frontend TS/TSX static syntax/transpile gate;
- full Alembic upgrade;
- downgrade to the previous database revision;
- re-upgrade to current head;
- Alembic schema-drift check.

The exact final run result and snapshot hash are recorded in `BUILD_VALIDATION_STATUS.md` after packaging preparation.

## What remains deployment-specific

Production readiness must be assessed on the target firm's representative staging environment. Source validation cannot prove live court-source availability, provider credentials, real PostgreSQL/S3 throughput, browser/device accessibility, recovery objectives, or the substantive completeness of jurisdiction-specific remedy packs.

## Feature freeze

Major feature development should stop here until a controlled lawyer pilot has completed. During pilot, changes should normally be limited to defects, security fixes, verified legal-data corrections, integration corrections, accessibility issues, and measured performance improvements.
