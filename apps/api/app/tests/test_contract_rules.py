from app.models.contract import ContractRiskLevel, ContractType
from app.services.contracts.rules import evaluate_contract, health_score


def complete_consulting_questionnaire():
    return {
        "scope_description": "Finance process consulting",
        "fee_amount": 150000,
        "payment_schedule": "50% advance, 50% on delivery",
        "notice_days": 30,
        "governing_state": "Delhi",
        "dispute_mode": "arbitration",
        "arbitration_city": "New Delhi",
        "effective_date": "2026-08-08",
        "party_a_address": "New Delhi",
        "party_b_address": "Gurugram",
    }


def test_complete_consulting_contract_has_no_missing_required_high_risk():
    findings = evaluate_contract(
        contract_type=ContractType.CONSULTING.value,
        party_a_name="Alpha Pvt Ltd",
        party_b_name="Consultant",
        governing_state="Delhi",
        questionnaire=complete_consulting_questionnaire(),
        clause_types={"appointment_scope", "fees_payment", "confidentiality", "ip", "liability", "term_termination", "dispute_resolution", "governing_law"},
    )
    assert not [item for item in findings if item.level == ContractRiskLevel.HIGH]
    assert health_score(findings) >= 90


def test_missing_payment_and_liability_are_high_risk():
    q = complete_consulting_questionnaire()
    q["fee_amount"] = ""
    q["payment_schedule"] = ""
    findings = evaluate_contract(
        contract_type=ContractType.CONSULTING.value,
        party_a_name="Alpha",
        party_b_name="Beta",
        governing_state="Delhi",
        questionnaire=q,
        clause_types={"appointment_scope", "confidentiality", "ip", "term_termination"},
    )
    codes = {item.rule_code for item in findings if item.level == ContractRiskLevel.HIGH}
    assert "commercial.value_missing" in codes
    assert "commercial.payment_missing" in codes
    assert "clause.missing.liability" in codes
    assert health_score(findings) < 80


def test_short_notice_is_review_warning_not_automatic_legal_conclusion():
    q = complete_consulting_questionnaire()
    q["notice_days"] = 3
    findings = evaluate_contract(
        contract_type=ContractType.CONSULTING.value,
        party_a_name="Alpha",
        party_b_name="Beta",
        governing_state="Delhi",
        questionnaire=q,
        clause_types={"appointment_scope", "fees_payment", "confidentiality", "ip", "liability", "term_termination"},
    )
    warning = next(item for item in findings if item.rule_code == "termination.short_notice")
    assert warning.level == ContractRiskLevel.MEDIUM
    assert "Confirm" in warning.explanation


def test_modified_library_clause_creates_review_item():
    findings = evaluate_contract(
        contract_type=ContractType.NDA.value,
        party_a_name="Alpha",
        party_b_name="Beta",
        governing_state="Delhi",
        questionnaire={"purpose": "Due diligence", "confidentiality_term_months": 36, "notice_days": 30, "dispute_mode": "courts"},
        clause_types={"confidentiality", "term_termination", "governing_law", "dispute_resolution"},
        modified_clause_types={"confidentiality"},
    )
    finding = next(item for item in findings if item.rule_code == "modified.confidentiality")
    assert finding.level == ContractRiskLevel.LOW
