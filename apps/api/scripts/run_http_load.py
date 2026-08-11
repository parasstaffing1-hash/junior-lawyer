#!/usr/bin/env python3
"""Dependency-light HTTP load probe for Junior Lawyer staging environments.

This is deliberately bounded: it sends only the configured request to a base URL the operator
explicitly supplies. It is not a crawler or internet scanner.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.release.engine import evaluate_performance, summarize_latencies


def one_request(url: str, method: str, timeout: float, headers: dict[str, str], payload: bytes | None) -> tuple[bool, float, int | None, str | None]:
    started = time.perf_counter()
    request = urllib.request.Request(url, method=method, headers=headers, data=payload)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1024)
            status = int(response.status)
            ok = 200 <= status < 400
            return ok, (time.perf_counter() - started) * 1000, status, None
    except urllib.error.HTTPError as exc:
        try:
            exc.read(1024)
        except Exception:
            pass
        return False, (time.perf_counter() - started) * 1000, int(exc.code), str(exc)
    except Exception as exc:  # network/runtime failure is a load-test failure, not a crash
        return False, (time.perf_counter() - started) * 1000, None, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="Explicit Junior Lawyer staging base URL")
    parser.add_argument("--path", default="/health")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    parser.add_argument("--min-success-rate", type=float, default=0.99)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--header", action="append", default=[], help="Header as Name:Value; repeatable")
    parser.add_argument("--json-payload")
    parser.add_argument("--output", default="load-report.json")
    args = parser.parse_args()

    if args.requests < 1 or args.requests > 100000:
        parser.error("--requests must be between 1 and 100000")
    if args.concurrency < 1 or args.concurrency > 256:
        parser.error("--concurrency must be between 1 and 256")

    headers: dict[str, str] = {}
    for item in args.header:
        if ":" not in item:
            parser.error("--header values must be Name:Value")
        key, value = item.split(":", 1)
        headers[key.strip()] = value.strip()
    payload = None
    if args.json_payload is not None:
        payload = args.json_payload.encode("utf-8")
        headers.setdefault("content-type", "application/json")

    url = args.base_url.rstrip("/") + "/" + args.path.lstrip("/")
    latencies: list[float] = []
    errors: list[dict] = []
    success = 0
    failure = 0
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one_request, url, args.method.upper(), args.timeout, headers, payload) for _ in range(args.requests)]
        for future in as_completed(futures):
            ok, latency, status, error = future.result()
            latencies.append(latency)
            if ok:
                success += 1
            else:
                failure += 1
                if len(errors) < 25:
                    errors.append({"status": status, "error": error})
    duration = time.perf_counter() - started
    metrics = summarize_latencies(latencies, success_count=success, failure_count=failure, duration_seconds=duration)
    passed, reasons = evaluate_performance(metrics, max_p95_ms=args.max_p95_ms, min_success_rate=args.min_success_rate, max_error_rate=args.max_error_rate)
    report = {
        "passed": passed,
        "target": {"url": url, "method": args.method.upper(), "requests": args.requests, "concurrency": args.concurrency},
        "thresholds": {"max_p95_ms": args.max_p95_ms, "min_success_rate": args.min_success_rate, "max_error_rate": args.max_error_rate},
        "metrics": metrics,
        "reasons": reasons,
        "sample_errors": errors,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
