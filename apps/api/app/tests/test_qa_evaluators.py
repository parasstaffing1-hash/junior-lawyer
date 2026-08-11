from app.services.qa.evaluators import canonical_hash, evaluate_probe, evaluate_release_gate, category_scores


def test_language_probe_hindi_reference():
    out = evaluate_probe(
        "language_normalization",
        {"text": "धारा 420 के अंतर्गत"},
        {"references": ["section:420"], "normalized_contains": ["section 420"]},
    )
    assert out.passed
    assert out.score == 1.0


def test_hinglish_reference_probe():
    out = evaluate_probe(
        "language_normalization",
        {"text": "dhara 138 cheque notice"},
        {"references": ["section:138"], "normalized_contains": ["section 138"]},
    )
    assert out.passed


def test_citation_parser_probe():
    out = evaluate_probe("citation_parser", {"text": "See 2024 INSC 321."}, {"citations": ["2024 INSC 321"], "reject_extra": True})
    assert out.passed


def test_deadline_probe():
    out = evaluate_probe(
        "deadline_calculator",
        {"trigger_date": "2026-08-08", "offset_days": 7, "day_basis": "calendar", "count_from_next_day": True, "adjustment": "none"},
        {"due_date": "2026-08-15"},
    )
    assert out.passed


def test_security_leak_is_critical_finding():
    out = evaluate_probe("forbidden_absent", {"actual": "Visible Secret Client"}, {"values": ["Secret Client"]})
    assert not out.passed
    assert out.findings[0]["code"] == "SECURITY_LEAK"


def test_provenance_coverage():
    out = evaluate_probe("provenance_complete", {"claims": [{"source_ids": ["S1"]}, {"source_ids": []}]}, {"min_coverage": 1.0})
    assert not out.passed
    assert out.score == 0.5


def test_rank_at_k():
    out = evaluate_probe("rank_at_k", {"ranked_ids": ["A", "B", "C"]}, {"relevant_ids": ["B"], "k": 2, "min_recall": 1.0})
    assert out.passed


def test_ocr_token_recall():
    out = evaluate_probe("ocr_text_quality", {"ocr_text": "न्यायालय में आवेदन प्रस्तुत"}, {"text": "न्यायालय में आवेदन प्रस्तुत", "min_token_recall": 1.0})
    assert out.passed


def test_gate_blocks_security_and_citation_failures():
    passed, reasons = evaluate_release_gate(
        overall_score=0.99,
        critical_failures=0,
        category_scores_map={"security": 0.5, "citation": 1.0},
        gate={"min_overall_score": 0.9, "max_critical_failures": 0, "require_security_zero_failures": True, "require_citation_zero_failures": True, "category_thresholds_json": {}},
    )
    assert not passed
    assert any("Security" in reason for reason in reasons)


def test_category_scores_are_weighted():
    scores = category_scores([
        {"category": "search", "score": 1.0, "weight": 3.0},
        {"category": "search", "score": 0.0, "weight": 1.0},
    ])
    assert scores["search"] == 0.75


def test_canonical_hash_is_stable_for_key_order():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
