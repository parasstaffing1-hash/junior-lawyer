# Production release checklist

- Backend regression tests pass.
- Batch 22 legal QA gate passes with zero critical security/citation failures.
- Alembic upgrade → previous revision downgrade → head re-upgrade passes with zero drift.
- Frontend production build passes in CI.
- Representative staging load test satisfies the firm's measured SLO thresholds.
- Security baseline and authenticated fixture tests pass with zero critical failures.
- A current database/files backup exists and restore verification is current.
- Release ZIP/container/image hashes are recorded in the immutable release manifest.
- A verified rollback point exists.
- Deployment approval is recorded by an authorized firm manager.
