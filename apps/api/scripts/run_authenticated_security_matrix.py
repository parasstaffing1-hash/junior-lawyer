#!/usr/bin/env python3
"""Run a bounded authenticated security matrix against an explicit Junior Lawyer staging URL.

Cases are operator-authored JSON. The runner never crawls or discovers endpoints, never brute-forces,
and reads credentials only from environment variables. Cookie/CSRF values are excluded from reports.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.release.engine import evaluate_security_result


def request(base: str, case: dict, cookie: str | None, csrf: str | None) -> dict:
    path = str(case.get("path") or "/")
    target = urllib.parse.urljoin(base.rstrip("/") + "/", path.lstrip("/"))
    if urllib.parse.urlparse(target).netloc != urllib.parse.urlparse(base).netloc:
        return {"status_code": None, "headers": {}, "body": "", "network_error": "target escaped configured staging host"}
    method = str(case.get("method") or "GET").upper()
    headers = {str(k): str(v) for k, v in dict(case.get("headers") or {}).items()}
    if cookie:
        headers["Cookie"] = cookie
    if csrf and method not in {"GET", "HEAD", "OPTIONS"}:
        headers.setdefault("x-csrf-token", csrf)
    body = None
    if "json" in case:
        body = json.dumps(case["json"], separators=(",", ":")).encode()
        headers.setdefault("content-type", "application/json")
    req = urllib.request.Request(target, method=method, headers=headers, data=body)
    try:
        with urllib.request.urlopen(req, timeout=float(case.get("timeout", 10))) as response:
            raw = response.read(16384).decode("utf-8", "replace")
            try: parsed = json.loads(raw)
            except Exception: parsed = None
            return {"status_code": response.status, "headers": dict(response.headers), "body": raw, "json": parsed}
    except urllib.error.HTTPError as exc:
        raw = exc.read(16384).decode("utf-8", "replace")
        try: parsed = json.loads(raw)
        except Exception: parsed = None
        return {"status_code": exc.code, "headers": dict(exc.headers), "body": raw, "json": parsed}
    except Exception as exc:
        return {"status_code": None, "headers": {}, "body": "", "network_error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--cases", required=True, help="JSON array of explicit security probes")
    parser.add_argument("--cookie-env", default="JL_VALIDATION_COOKIE")
    parser.add_argument("--csrf-env", default="JL_VALIDATION_CSRF")
    parser.add_argument("--output", default="authenticated-security-report.json")
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        parser.error("--base-url must be an explicit http(s) URL")
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or len(cases) > 200:
        parser.error("case file must be a JSON array with at most 200 explicit probes")
    cookie = os.getenv(args.cookie_env)
    csrf = os.getenv(args.csrf_env)
    results = []
    for case in cases:
        actual = request(args.base_url, case, cookie, csrf)
        passed, reasons = evaluate_security_result(actual, dict(case.get("expected") or {}))
        results.append({"key": case.get("key"), "critical": bool(case.get("critical", True)), "passed": passed, "reasons": reasons, "status_code": actual.get("status_code"), "network_error": actual.get("network_error")})
    critical_failures = sum(1 for r in results if r["critical"] and not r["passed"])
    report = {"passed": all(r["passed"] for r in results), "critical_failures": critical_failures, "case_count": len(results), "results": results, "credentials_recorded": False}
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
