from app.services.release.engine import (
    ReleaseGateInput,
    build_release_manifest,
    canonical_hash,
    decide_release_gate,
    evaluate_performance,
    evaluate_security_result,
    percentile,
    summarize_latencies,
)


def test_percentile_interpolates_and_handles_empty():
    assert percentile([], 0.95) == 0.0
    assert percentile([10], 0.95) == 10.0
    assert percentile([10, 20, 30, 40], 0.5) == 25.0


def test_summarize_latencies_is_deterministic():
    metrics = summarize_latencies([10, 20, 30, 40], success_count=3, failure_count=1, duration_seconds=2)
    assert metrics["total_requests"] == 4
    assert metrics["success_rate"] == 0.75
    assert metrics["error_rate"] == 0.25
    assert metrics["requests_per_second"] == 2.0
    assert metrics["p50_ms"] == 25.0


def test_performance_gate_catches_latency_and_errors():
    passed, reasons = evaluate_performance(
        {"p95_ms": 1500, "success_rate": 0.95, "error_rate": 0.05},
        max_p95_ms=1000,
        min_success_rate=0.99,
        max_error_rate=0.01,
    )
    assert not passed
    assert len(reasons) == 3


def test_performance_gate_passes_good_metrics():
    passed, reasons = evaluate_performance(
        {"p95_ms": 200, "success_rate": 1.0, "error_rate": 0.0},
        max_p95_ms=1000,
        min_success_rate=0.99,
        max_error_rate=0.01,
    )
    assert passed
    assert reasons == []


def test_security_evaluator_rejects_forbidden_leak():
    passed, reasons = evaluate_security_result(
        {"status_code": 200, "body": "Secret Acquisition Client XYZ", "headers": {}},
        {"status_in": [200], "forbidden_strings_absent": ["Secret Acquisition Client XYZ"]},
    )
    assert not passed
    assert "forbidden output leaked" in reasons[0]


def test_security_evaluator_checks_headers_and_json():
    passed, reasons = evaluate_security_result(
        {"status_code": 200, "body": "ok", "headers": {"X-Request-ID": "abc"}, "json": {"untrusted_sources": True}},
        {"status_in": [200], "required_headers": {"x-request-id": None}, "json_equals": {"untrusted_sources": True}},
    )
    assert passed
    assert reasons == []


def test_release_gate_requires_every_critical_control():
    base = ReleaseGateInput(
        backend_tests_passed=True,
        qa_passed=True,
        security_passed=True,
        load_passed=True,
        migration_passed=True,
        frontend_passed=True,
        critical_security_failures=0,
        rollback_ready=True,
        artifact_passed=True,
    )
    passed, reasons = decide_release_gate(base)
    assert passed and reasons == []

    missing_rollback = ReleaseGateInput(**{**base.__dict__, "rollback_ready": False})
    passed, reasons = decide_release_gate(missing_rollback)
    assert not passed
    assert "rollback point" in reasons[0]


def test_release_gate_zero_tolerance_security_failure():
    gate = ReleaseGateInput(
        backend_tests_passed=True,
        qa_passed=True,
        security_passed=True,
        load_passed=True,
        migration_passed=True,
        frontend_passed=True,
        critical_security_failures=1,
        rollback_ready=True,
        artifact_passed=True,
    )
    passed, reasons = decide_release_gate(gate)
    assert not passed
    assert any("critical security" in reason for reason in reasons)


def test_manifest_hash_is_stable_across_artifact_order():
    a = build_release_manifest(
        app_version="0.23.0",
        build_ref="abc",
        database_revision="rev",
        artifact_hashes=[{"kind": "zip", "filename": "b.zip", "sha256": "2"}, {"kind": "qa", "filename": "a.json", "sha256": "1"}],
        gates={"qa": True},
    )
    b = build_release_manifest(
        app_version="0.23.0",
        build_ref="abc",
        database_revision="rev",
        artifact_hashes=[{"kind": "qa", "filename": "a.json", "sha256": "1"}, {"kind": "zip", "filename": "b.zip", "sha256": "2"}],
        gates={"qa": True},
    )
    assert a["snapshot_hash"] == b["snapshot_hash"]
    assert canonical_hash(a) == canonical_hash(b)
