from app.services.validation.engine import (
    PilotGateRow,
    ScenarioGateRow,
    build_candidate_manifest,
    evaluate_numeric_thresholds,
    evaluate_validation_gate,
    synthetic_fixture_manifest,
)


def test_numeric_thresholds_pass_and_fail():
    ok, reasons = evaluate_numeric_thresholds(
        {"p95_ms": 900, "success_rate": 0.999, "healthy": True},
        {"max": {"p95_ms": 1500}, "min": {"success_rate": 0.99}, "equals": {"healthy": True}},
    )
    assert ok is True
    assert reasons == []

    ok, reasons = evaluate_numeric_thresholds(
        {"p95_ms": 2000, "success_rate": 0.95, "healthy": False},
        {"max": {"p95_ms": 1500}, "min": {"success_rate": 0.99}, "equals": {"healthy": True}},
    )
    assert ok is False
    assert len(reasons) == 3


def test_release_candidate_gate_requires_critical_and_required_scenarios():
    scenarios = [
        ScenarioGateRow("security", "critical", "passed"),
        ScenarioGateRow("load", "required", "failed"),
        ScenarioGateRow("advisory", "advisory", "failed"),
    ]
    checks = [PilotGateRow("privacy", True, "passed")]
    ok, reasons = evaluate_validation_gate(
        scenarios,
        checks,
        release_approved=True,
        rollback_verified=True,
        staging_environment=True,
        artifact_integrity=True,
        minimum_signoffs=1,
        approval_signoffs=1,
    )
    assert ok is False
    assert any("load" in reason for reason in reasons)
    assert not any("advisory" in reason for reason in reasons)


def test_release_candidate_gate_is_strict_about_production_evidence():
    scenarios = [ScenarioGateRow("security", "critical", "passed")]
    checks = [PilotGateRow("privacy", True, "passed")]
    ok, reasons = evaluate_validation_gate(
        scenarios,
        checks,
        release_approved=False,
        rollback_verified=False,
        staging_environment=False,
        artifact_integrity=False,
        minimum_signoffs=2,
        approval_signoffs=1,
    )
    assert ok is False
    assert "underlying release run is not approved" in reasons
    assert "verified rollback point missing" in reasons
    assert "staging environment evidence missing" in reasons
    assert "release-candidate artifact integrity missing" in reasons
    assert any("1/2" in reason for reason in reasons)


def test_required_pilot_check_can_be_waived_by_policy_layer():
    scenarios = [ScenarioGateRow("security", "critical", "passed")]
    checks = [PilotGateRow("known_limitations", True, "waived")]
    ok, reasons = evaluate_validation_gate(
        scenarios,
        checks,
        release_approved=True,
        rollback_verified=True,
        staging_environment=True,
        artifact_integrity=True,
        minimum_signoffs=1,
        approval_signoffs=1,
    )
    assert ok is True
    assert reasons == []


def test_candidate_manifest_hash_is_stable_and_order_independent_for_datasets():
    kwargs = dict(
        candidate_version="0.28.0-rc.1",
        app_version="0.28.0-rc.1",
        database_revision="20260808_0027",
        artifact_sha256="a" * 64,
        campaign_hash="b" * 64,
        release_hash="c" * 64,
        validation_summary={"passed": True},
    )
    one = build_candidate_manifest(datasets=[{"kind": "large_pdf", "name": "B", "sha256": "2" * 64}, {"kind": "search_corpus", "name": "A", "sha256": "1" * 64}], **kwargs)
    two = build_candidate_manifest(datasets=[{"kind": "search_corpus", "name": "A", "sha256": "1" * 64}, {"kind": "large_pdf", "name": "B", "sha256": "2" * 64}], **kwargs)
    assert one["snapshot_hash"] == two["snapshot_hash"]


def test_synthetic_fixture_manifest_is_reproducible_and_bilingual():
    one = synthetic_fixture_manifest(seed=28, documents=100_000, pages_per_document=2, languages=["hi", "en", "hi"])
    two = synthetic_fixture_manifest(seed=28, documents=100_000, pages_per_document=2, languages=["en", "hi"])
    assert one == two
    assert one["documents"] == 100_000
    assert one["pages"] == 200_000
    assert one["languages"] == ["en", "hi"]
    assert len(one["sha256"]) == 64


def test_rejecting_signoff_holds_candidate_even_with_approval():
    scenarios = [ScenarioGateRow("security", "critical", "passed")]
    checks = [PilotGateRow("privacy", True, "passed")]
    ok, reasons = evaluate_validation_gate(
        scenarios, checks, release_approved=True, rollback_verified=True, staging_environment=True,
        artifact_integrity=True, minimum_signoffs=1, approval_signoffs=1, rejection_signoffs=1,
    )
    assert ok is False
    assert any("rejecting" in reason for reason in reasons)
