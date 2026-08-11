# Release engineering

Batch 23 separates four different claims that should not be conflated:

1. **Source gate** — unit/regression tests, legal golden cases, static security controls, frontend syntax, and migration round-trip/drift pass.
2. **Staging performance gate** — representative hardware/data meet explicit p95, success-rate, and error-rate targets under measured concurrency.
3. **Artifact/rollback gate** — the exact artifact is SHA-256 recorded and a verified rollback point exists.
4. **Deployment approval** — an authorized manager explicitly approves the already-passing candidate.

A source gate cannot prove production throughput. A load test cannot prove legal accuracy. A deployment approval cannot override a failed critical security gate.

## Local source gate

```bash
cd apps/api
python scripts/run_release_source_gate.py
```

## Representative staging load

```bash
cd apps/api
python scripts/run_http_load.py \
  --base-url https://staging.example.invalid \
  --path /health \
  --requests 1000 \
  --concurrency 40 \
  --max-p95-ms 750 \
  --min-success-rate 0.999 \
  --max-error-rate 0.001
```

Use only infrastructure you are authorized to test. Search/upload/OCR scenarios should use isolated synthetic or de-identified staging data.

## Safe source artifact

```bash
cd apps/api
python scripts/build_release_artifact.py --version 0.25.0 --build-ref <commit>
```

The artifact builder excludes `.env`, runtime `data/`, local databases, caches, VCS metadata, `node_modules`, and build output by default.

## Batch 28 release-candidate gate

`0.28.0-rc.1` adds a second, deployment-specific validation gate under `/validation`. The Batch-23 source/release gate remains necessary, but RC1 cannot become pilot-ready until representative staging, authenticated security, recovery, scale, accessibility and pilot-readiness evidence is recorded and signed off. See `RELEASE_CANDIDATE.md` and `VALIDATION_RUNBOOK.md`.

## Batch 29 pre-release change

Case Lookup + Legal Remedy Analysis is a post-RC1 feature change. Current source version is `0.29.0-rc.1`, database revision `20260808_0028`. The source gate now downgrades to Batch 28 (`20260808_0027`) and re-upgrades to Batch 29. A fresh release-candidate validation campaign is mandatory; prior Batch-28 staging/sign-off evidence must not be used to label Batch 29 pilot-ready.
