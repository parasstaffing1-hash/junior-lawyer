from uuid import uuid4

from app.services.drafting.builder import build_findings, build_sections, health_score, safe_facts
from app.services.drafting.catalog import DRAFT_DEFINITIONS, get_draft_catalog


def base_context() -> dict:
    return {
        "matter_title": "ABC Pvt Ltd v XYZ Ltd",
        "client_name": "ABC Pvt Ltd",
        "court_name": "High Court of Delhi",
        "case_number": "CS(COMM) 123/2026",
        "facts": [],
        "safe_facts": [],
        "excluded_facts": [],
        "timeline": [],
        "documents": [],
        "statements": [],
        "contradictions": [],
    }


def test_catalog_contains_twelve_work_product_types():
    catalog = get_draft_catalog()
    assert len(catalog) == 12
    names = {item["draft_type"] for item in catalog}
    assert {"petition", "legal_notice", "hearing_note", "annexure_index"} <= names


def test_safe_facts_excludes_open_conflicting_fact_ids():
    one, two = uuid4(), uuid4()
    facts = [
        {"id": one, "status": "confirmed", "label": "Agreement date", "value": "12 Mar 2026"},
        {"id": two, "status": "confirmed", "label": "Payment", "value": "₹10,000"},
    ]
    safe, excluded = safe_facts(
        facts,
        [{"status": "open", "fact_ids": [str(one)]}],
    )
    assert [item["id"] for item in safe] == [two]
    assert [item["id"] for item in excluded] == [one]


def test_health_score_penalizes_only_open_findings():
    findings = [
        {"level": "high", "status": "open"},
        {"level": "medium", "status": "open"},
        {"level": "low", "status": "resolved"},
    ]
    assert health_score(findings) == 70


def test_petition_requires_counsel_ground_and_relief_when_missing():
    context = base_context()
    context["safe_facts"] = [{"id": uuid4(), "status": "confirmed"}]
    findings = build_findings(
        "petition", context, {}, [], [item["key"] for item in DRAFT_DEFINITIONS["petition"]["sections"]]
    )
    codes = {item["rule_code"] for item in findings}
    assert "grounds_need_lawyer" in codes
    assert "relief_missing" in codes
    assert "authorities_missing" in codes


def test_legal_notice_requires_recipient_and_demand():
    context = base_context()
    context["safe_facts"] = [{"id": uuid4(), "status": "confirmed"}]
    findings = build_findings(
        "legal_notice", context, {"sender_name": "ABC"}, [],
        [item["key"] for item in DRAFT_DEFINITIONS["legal_notice"]["sections"]],
    )
    codes = {item["rule_code"] for item in findings}
    assert "notice_recipient_missing" in codes
    assert "notice_demand_missing" in codes


def test_chronology_section_keeps_timeline_sources():
    event_id = uuid4()
    context = base_context()
    context["timeline"] = [{
        "id": event_id,
        "date": "2026-08-01",
        "title": "Order passed",
        "description": "Court directed filing of affidavit.",
        "source": {"locator": "order.pdf · p.2", "excerpt": "File affidavit"},
    }]
    sections, _ = build_sections(DRAFT_DEFINITIONS["chronology"], "chronology", context, {}, [])
    assert "Order passed" in sections[0]["body_en"]
    assert sections[0]["sources"][0]["source_id"] == event_id
    assert sections[0]["sources"][0]["locator"] == "order.pdf · p.2"


def test_annexure_index_is_deterministically_numbered():
    context = base_context()
    context["documents"] = [
        {"id": uuid4(), "name": "Agreement.pdf", "pages": 4},
        {"id": uuid4(), "name": "Notice.pdf", "pages": 2},
    ]
    sections, _ = build_sections(
        DRAFT_DEFINITIONS["annexure_index"], "annexure_index", context, {"annexure_prefix": "P"}, []
    )
    assert "Annexure P-1 — Agreement.pdf" in sections[0]["body_en"]
    assert "Annexure P-2 — Notice.pdf" in sections[0]["body_en"]
    assert len(sections[0]["sources"]) == 2


def test_fact_section_has_english_and_hindi_renderings_and_provenance():
    fact_id = uuid4()
    context = base_context()
    context["safe_facts"] = [{
        "id": fact_id,
        "label": "Agreement date",
        "value": "12 March 2026",
        "status": "confirmed",
        "source": {"locator": "agreement.pdf · p.1", "excerpt": "dated 12 March 2026"},
        "all_sources": [],
    }]
    sections, _ = build_sections(DRAFT_DEFINITIONS["case_synopsis"], "case_synopsis", context, {}, [])
    facts = next(item for item in sections if item["section_key"] == "material_facts")
    assert "Agreement date" in facts["body_en"]
    assert facts["body_hi"]
    assert facts["sources"][0]["source_id"] == fact_id


def test_deterministic_builder_never_invents_missing_petition_grounds():
    context = base_context()
    context["safe_facts"] = [{
        "id": uuid4(), "label": "Contract", "value": "Executed", "status": "confirmed", "source": {}, "all_sources": []
    }]
    sections, _ = build_sections(DRAFT_DEFINITIONS["petition"], "petition", context, {"relief_requested": "Allow petition"}, [])
    grounds = next(item for item in sections if item["section_key"] == "grounds")
    assert "require lawyer drafting" in grounds["body_en"]
    assert "कानूनी आधार गढ़ने" in grounds["body_hi"]


def test_hearing_note_surfaces_admissions_denials_and_conflicts():
    context = base_context()
    context["safe_facts"] = [{"id": uuid4(), "label": "Payment", "value": "₹1 lakh", "status": "confirmed", "source": {}, "all_sources": []}]
    context["statements"] = [{"id": uuid4(), "kind": "admission", "text": "Payment was received.", "locator": "reply.pdf · p.3"}]
    context["contradictions"] = [{"id": uuid4(), "label": "Agreement date", "severity": "high", "status": "open", "values": ["1 Jan", "2 Jan"], "fact_ids": []}]
    sections, _ = build_sections(DRAFT_DEFINITIONS["hearing_note"], "hearing_note", context, {}, [])
    by_key = {item["section_key"]: item for item in sections}
    assert "Admission" in by_key["statements"]["body_en"]
    assert "HIGH: Agreement date" in by_key["contradictions"]["body_en"]
