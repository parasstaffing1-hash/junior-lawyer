from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.models.contract import ContractRiskLevel, ContractType
from app.services.contracts.catalog import CONTRACT_DEFINITIONS, PAID_TYPES


@dataclass(frozen=True, slots=True)
class RiskFinding:
    rule_code: str
    title: str
    explanation: str
    level: ContractRiskLevel
    clause_type: str | None = None
    metadata: dict[str, Any] | None = None


REQUIRED_CLAUSE_TYPES = {
    ContractType.NDA.value: {"confidentiality", "term_termination", "governing_law", "dispute_resolution"},
    ContractType.EMPLOYMENT.value: {"appointment_scope", "fees_payment", "confidentiality", "term_termination", "governing_law"},
    ContractType.CONSULTING.value: {"appointment_scope", "fees_payment", "confidentiality", "ip", "liability", "term_termination"},
    ContractType.FREELANCE.value: {"appointment_scope", "fees_payment", "ip", "liability", "term_termination"},
    ContractType.VENDOR.value: {"appointment_scope", "fees_payment", "warranty", "liability", "term_termination"},
    ContractType.SERVICES.value: {"appointment_scope", "fees_payment", "liability", "term_termination"},
    ContractType.SAAS.value: {"appointment_scope", "fees_payment", "data_protection", "liability", "term_termination"},
    ContractType.SOFTWARE_DEVELOPMENT.value: {"appointment_scope", "fees_payment", "acceptance", "ip", "liability", "term_termination"},
}


def _empty(value: object) -> bool:
    return value is None or value == "" or value == []


def evaluate_contract(
    *,
    contract_type: str,
    party_a_name: str,
    party_b_name: str,
    governing_state: str | None,
    questionnaire: dict[str, Any],
    clause_types: Iterable[str],
    modified_clause_types: Iterable[str] = (),
) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    clause_set = set(clause_types)
    modified_set = set(modified_clause_types)
    definition = CONTRACT_DEFINITIONS[contract_type]

    if _empty(party_a_name) or _empty(party_b_name):
        findings.append(RiskFinding("parties.missing", "Party details incomplete", "Both contracting parties must be identified before the draft is treated as complete.", ContractRiskLevel.HIGH))

    for key in definition.get("required_fields", []):
        if _empty(questionnaire.get(key)):
            findings.append(RiskFinding(f"required.{key}", "Required commercial term missing", f"The required field '{key}' has not been completed.", ContractRiskLevel.HIGH, metadata={"field": key}))

    if _empty(questionnaire.get("effective_date")):
        findings.append(RiskFinding("effective_date.missing", "Effective date missing", "The agreement does not yet contain a completed effective date.", ContractRiskLevel.HIGH))

    for address_key, party_label in (("party_a_address", "Party A"), ("party_b_address", "Party B")):
        if _empty(questionnaire.get(address_key)):
            findings.append(RiskFinding(f"{address_key}.missing", f"{party_label} address incomplete", "Complete the notice/identity address before signature.", ContractRiskLevel.MEDIUM, "notices"))

    if not governing_state:
        findings.append(RiskFinding("governing_state.missing", "Governing State / UT not set", "The draft does not identify the intended State or Union Territory for its governing-law and forum language.", ContractRiskLevel.MEDIUM, "governing_law"))

    if _empty(questionnaire.get("dispute_mode")):
        findings.append(RiskFinding("dispute_mode.missing", "Dispute mechanism not selected", "Select arbitration or courts so the dispute-resolution clause is not left ambiguous.", ContractRiskLevel.MEDIUM, "dispute_resolution"))

    if questionnaire.get("dispute_mode") == "arbitration" and _empty(questionnaire.get("arbitration_city")):
        findings.append(RiskFinding("arbitration_city.missing", "Arbitration seat/venue needs review", "An arbitration route is selected but no arbitration city has been entered.", ContractRiskLevel.MEDIUM, "dispute_resolution"))

    required_clauses = REQUIRED_CLAUSE_TYPES.get(contract_type, set())
    for clause_type in sorted(required_clauses - clause_set):
        findings.append(RiskFinding(f"clause.missing.{clause_type}", "Expected clause missing", f"The deterministic playbook expects a '{clause_type}' clause for this contract type.", ContractRiskLevel.HIGH, clause_type))

    if contract_type in PAID_TYPES:
        if _empty(questionnaire.get("fee_amount")) and _empty(questionnaire.get("monthly_salary")):
            findings.append(RiskFinding("commercial.value_missing", "Commercial value missing", "The contract does not contain a clear fee or compensation value.", ContractRiskLevel.HIGH, "fees_payment"))
        if _empty(questionnaire.get("payment_schedule")) and contract_type != ContractType.EMPLOYMENT.value:
            findings.append(RiskFinding("commercial.payment_missing", "Payment schedule missing", "Payment timing should be completed before signature.", ContractRiskLevel.HIGH, "fees_payment"))

    notice_days = questionnaire.get("notice_days")
    try:
        if notice_days is not None and int(notice_days) < 7:
            findings.append(RiskFinding("termination.short_notice", "Very short termination notice", "The selected notice period is less than seven days. Confirm that this is intentional and appropriate for the transaction.", ContractRiskLevel.MEDIUM, "term_termination", {"notice_days": int(notice_days)}))
    except (TypeError, ValueError):
        findings.append(RiskFinding("termination.notice_invalid", "Termination notice is invalid", "The notice period should be a valid number of days.", ContractRiskLevel.MEDIUM, "term_termination"))

    if contract_type == ContractType.SAAS.value and questionnaire.get("data_processing") is True and "data_protection" not in clause_set:
        findings.append(RiskFinding("saas.data_clause_missing", "Personal-data clause missing", "The questionnaire indicates personal-data processing but the data-protection clause is absent.", ContractRiskLevel.HIGH, "data_protection"))

    if contract_type in {ContractType.FREELANCE.value, ContractType.CONSULTING.value, ContractType.SOFTWARE_DEVELOPMENT.value} and "ip" not in clause_set:
        findings.append(RiskFinding("ip.missing", "IP position missing", "This type of engagement commonly creates deliverables; the draft has no IP clause.", ContractRiskLevel.HIGH, "ip"))

    for clause_type in sorted(modified_set):
        findings.append(RiskFinding(f"modified.{clause_type}", "Clause modified from approved library", f"The '{clause_type}' clause differs from the selected library text and should receive lawyer review.", ContractRiskLevel.LOW, clause_type))

    return findings


def health_score(findings: Iterable[RiskFinding]) -> int:
    deductions = {
        ContractRiskLevel.HIGH: 14,
        ContractRiskLevel.MEDIUM: 7,
        ContractRiskLevel.LOW: 2,
    }
    score = 100 - sum(deductions[item.level] for item in findings)
    return max(0, min(100, score))
