# Batch 22 QA examples

`core-golden-cases.json` mirrors the dependency-light release suite seeded by `POST /api/v1/qa/seed`. It is intentionally small: firms should add representative de-identified or synthetic golden matters, scanned Hindi/English documents, expected search rankings, contract-review cases, deadline examples and permission-leak cases relevant to their own practice.

Run the built-in local gate from `apps/api`:

```bash
python scripts/run_local_qa_gate.py
```

The command exits non-zero when the release gate fails and prints a SHA-256-stamped JSON report suitable for CI artifacts. It does not call a paid model or external service.

`release-gate.request.json` shows the default critical-gate posture. Security and citation failures are zero-tolerance by default; they cannot be averaged away by strong scores in easier categories.
