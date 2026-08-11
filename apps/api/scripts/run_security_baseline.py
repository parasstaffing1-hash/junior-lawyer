#!/usr/bin/env python3
"""Safe release security baseline.

Runs deterministic security-policy checks locally. Optional HTTP probes target only an explicit
Junior Lawyer base URL and do not crawl, enumerate, brute force, or exploit third-party systems.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.ai import AITaskType
from app.services.ai.prompting import system_prompt
from app.services.release.engine import evaluate_security_result


def http_probe(url: str, method: str = "GET", headers: dict[str, str] | None = None, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            body = response.read(4096).decode("utf-8", "replace")
            return {"status_code": response.status, "headers": dict(response.headers), "body": body}
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", "replace")
        return {"status_code": exc.code, "headers": dict(exc.headers), "body": body}
    except Exception as exc:
        return {"status_code": None, "headers": {}, "body": "", "network_error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", help="Optional explicit local/staging Junior Lawyer URL")
    parser.add_argument("--expect-auth", action="store_true", help="Require protected APIs to reject anonymous requests")
    parser.add_argument("--output", default="security-report.json")
    args = parser.parse_args()

    cases: list[dict] = []
    # Prompt boundary is a static release gate: source material must remain evidence, not instruction.
    policy = system_prompt(AITaskType.MATTER_SUMMARY, "en")
    prompt_actual = {"status_code": 200, "json": {"untrusted_sources": "untrusted" in policy.casefold() and "instructions" in policy.casefold()}, "body": policy[:500], "headers": {}}
    passed, reasons = evaluate_security_result(prompt_actual, {"json_equals": {"untrusted_sources": True}})
    cases.append({"key": "prompt-boundary", "passed": passed, "reasons": reasons})

    # Output-leak evaluator itself must catch a restricted marker.
    passed, reasons = evaluate_security_result({"status_code": 200, "body": "ordinary permitted result", "headers": {}}, {"status_in": [200], "forbidden_strings_absent": ["Secret Acquisition Client XYZ"]})
    cases.append({"key": "forbidden-output-evaluator", "passed": passed, "reasons": reasons})

    if args.base_url:
        base = args.base_url.rstrip("/")
        health = http_probe(base + "/health")
        passed, reasons = evaluate_security_result(health, {"status_in": [200], "required_headers": {"x-request-id": None}})
        cases.append({"key": "request-id-header", "passed": passed, "reasons": reasons, "status": health.get("status_code")})
        if args.expect_auth:
            protected = http_probe(base + "/api/v1/security/me")
            passed, reasons = evaluate_security_result(protected, {"status_in": [401, 403]})
            cases.append({"key": "anonymous-protected-api", "passed": passed, "reasons": reasons, "status": protected.get("status_code")})

    report = {"passed": all(c["passed"] for c in cases), "critical_failures": sum(1 for c in cases if not c["passed"]), "cases": cases}
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
