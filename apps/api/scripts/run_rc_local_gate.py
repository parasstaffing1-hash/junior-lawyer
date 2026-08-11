#!/usr/bin/env python3
"""Final dependency-light source gate for Batch 28 / RC1.

This proves source correctness and release-candidate invariants. It intentionally reports
`staging_validated=false`; only a real validation campaign can mark RC1 ready.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"


def run(command: list[str], cwd: Path) -> dict:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {"command": command, "passed": proc.returncode == 0, "returncode": proc.returncode, "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-12000:]}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", default=str(ROOT / "rc-local-gate.json")); args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="jl-rc-source-") as td:
        source_report = Path(td) / "source-gate.json"
        source = run([sys.executable, "scripts/run_release_source_gate.py", "--output", str(source_report)], API)
        validation = run([sys.executable, "-m", "pytest", "-q", "app/tests/test_validation_engine.py", "app/tests/test_validation_models.py"], API)
        docs = all((ROOT / name).exists() for name in ["RELEASE_CANDIDATE.md", "VALIDATION_RUNBOOK.md", "PILOT_GUIDE.md", "KNOWN_LIMITATIONS.md"])
        passed = source["passed"] and validation["passed"] and docs
        report = {
            "passed": passed,
            "source_gate": source["passed"],
            "validation_engine": validation["passed"],
            "release_candidate_docs": docs,
            "staging_validated": False,
            "rc_ready": False,
            "note": "Local/source validation cannot substitute for the staging, authenticated security, recovery, load and pilot-readiness evidence required by the RC campaign gate.",
            "stages": [source, validation],
        }
        raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode(); report["snapshot_hash"] = hashlib.sha256(raw).hexdigest()
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({k: report[k] for k in ["passed", "staging_validated", "rc_ready", "snapshot_hash"]}, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
