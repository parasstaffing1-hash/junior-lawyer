# Production deployment · Batch 24

Batch 24 converts the prior development topology into an explicit production foundation with PostgreSQL, S3-compatible object storage, TLS ingress, horizontally scalable API/worker containers, one-shot advisory-lock migrations, readiness probes and recorded rollouts.

The application still requires an independent infrastructure/security review before real privileged legal data is entrusted to it. Container images should be pinned by digest; secrets belong in an approved secret manager; backups must be encrypted/off-site; and real staging load/security gates should pass before production rollout.

See `infrastructure/production/README.md` for the deployment sequence.

## RC1 staging validation

After a successful staging rollout, create a Batch-28 validation campaign and record the required scenario evidence. Do not promote the same build to a controlled lawyer pilot solely because health probes and migrations passed. RC1 additionally requires authenticated permission testing, backup/isolated restore proof, representative load/large-document evidence, bilingual E2E and pilot-readiness review.
