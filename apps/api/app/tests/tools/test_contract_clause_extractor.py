from fastapi.testclient import TestClient

from app.main import app
from app.tools.contract_clause_extractor.models import (
    ClauseExtractRequest,
    ClauseExtractionOptions,
    ClauseType,
    MatchBasis,
)
from app.tools.contract_clause_extractor.service import extract_contract_clauses

client = TestClient(app)


SAMPLE = """1. Confidentiality
Each party shall keep all Confidential Information confidential and shall not disclose it except as permitted.

2. Payment Terms
The Customer shall pay each invoice within 30 days after receipt.

3. Limitation of Liability
Neither party shall be liable for indirect or consequential damages. Aggregate liability is limited to the fees paid.

4. Governing Law
This Agreement is governed by the laws of Example State.
"""


def test_extracts_heading_and_body_supported_clauses() -> None:
    result = extract_contract_clauses(ClauseExtractRequest(text=SAMPLE))
    kinds = [item.clause_type for item in result.matches]
    assert ClauseType.CONFIDENTIALITY in kinds
    assert ClauseType.PAYMENT in kinds
    assert ClauseType.LIMITATION_OF_LIABILITY in kinds
    assert ClauseType.GOVERNING_LAW in kinds


def test_heading_and_body_basis_has_high_confidence() -> None:
    result = extract_contract_clauses(ClauseExtractRequest(text=SAMPLE))
    confidentiality = next(item for item in result.matches if item.clause_type == ClauseType.CONFIDENTIALITY)
    assert confidentiality.match_basis == MatchBasis.HEADING_AND_BODY
    assert confidentiality.confidence >= 0.94
    assert confidentiality.normalized_heading == "confidentiality"


def test_exact_offsets_point_to_returned_text() -> None:
    result = extract_contract_clauses(ClauseExtractRequest(text=SAMPLE))
    payment = next(item for item in result.matches if item.clause_type == ClauseType.PAYMENT)
    normalized = SAMPLE.replace("\r\n", "\n").replace("\r", "\n")
    assert normalized[payment.start:payment.end] == payment.text
    assert payment.line >= 1
    assert payment.column >= 1


def test_can_filter_clause_types() -> None:
    request = ClauseExtractRequest(
        text=SAMPLE,
        options=ClauseExtractionOptions(clause_types=[ClauseType.PAYMENT]),
    )
    result = extract_contract_clauses(request)
    assert result.summary.clauses_returned == 1
    assert result.matches[0].clause_type == ClauseType.PAYMENT


def test_body_fallback_without_headings() -> None:
    text = (
        "Each party shall keep all Confidential Information confidential and shall not disclose it.\n\n"
        "The supplier shall maintain insurance coverage during the term."
    )
    result = extract_contract_clauses(ClauseExtractRequest(text=text))
    kinds = {item.clause_type for item in result.matches}
    assert ClauseType.CONFIDENTIALITY in kinds
    assert ClauseType.INSURANCE in kinds
    assert result.summary.sections_detected == 0
    assert any("fallback" in warning.lower() for warning in result.warnings)


def test_body_fallback_can_be_disabled() -> None:
    text = "Each party shall keep all Confidential Information confidential and shall not disclose it."
    result = extract_contract_clauses(
        ClauseExtractRequest(
            text=text,
            options=ClauseExtractionOptions(use_body_fallback=False),
        )
    )
    assert result.summary.clauses_returned == 0
    assert any("disabled" in warning.lower() for warning in result.warnings)


def test_minimum_confidence_filters_body_only_matches() -> None:
    text = "The parties agree that the term of this agreement begins today."
    result = extract_contract_clauses(
        ClauseExtractRequest(
            text=text,
            options=ClauseExtractionOptions(minimum_confidence=0.90),
        )
    )
    assert result.summary.clauses_returned == 0


def test_excluding_heading_adjusts_text_and_offset() -> None:
    result = extract_contract_clauses(
        ClauseExtractRequest(
            text=SAMPLE,
            options=ClauseExtractionOptions(
                clause_types=[ClauseType.CONFIDENTIALITY],
                include_heading_in_text=False,
            ),
        )
    )
    item = result.matches[0]
    assert not item.text.startswith("1. Confidentiality")
    normalized = SAMPLE.replace("\r\n", "\n").replace("\r", "\n")
    assert normalized[item.start:item.end] == item.text


def test_reports_supported_types() -> None:
    response = client.get("/api/v1/tools/contract-clauses/types")
    assert response.status_code == 200
    payload = response.json()
    values = {item["clause_type"] for item in payload["clause_types"]}
    assert "termination" in values
    assert "indemnity" in values
    assert "data_protection" in values


def test_extract_api() -> None:
    response = client.post(
        "/api/v1/tools/contract-clauses/extract",
        json={"text": SAMPLE, "options": {"clause_types": ["governing_law"]}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["clauses_returned"] == 1
    assert payload["matches"][0]["clause_type"] == "governing_law"


def test_result_limit_is_enforced() -> None:
    text = "\n\n".join(
        f"{i}. Confidentiality\nConfidential Information shall not be disclosed."
        for i in range(1, 8)
    )
    result = extract_contract_clauses(
        ClauseExtractRequest(
            text=text,
            options=ClauseExtractionOptions(
                clause_types=[ClauseType.CONFIDENTIALITY],
                max_results=3,
            ),
        )
    )
    assert len(result.matches) == 3
    assert any("Result limit" in warning for warning in result.warnings)


def test_generic_numbered_heading_delimits_clause() -> None:
    text = """1. Services
The provider will perform the services.
2. Termination
Either party may terminate this agreement on written notice.
3. Miscellaneous
Entire agreement language.
"""
    result = extract_contract_clauses(
        ClauseExtractRequest(
            text=text,
            options=ClauseExtractionOptions(clause_types=[ClauseType.TERMINATION]),
        )
    )
    assert len(result.matches) == 1
    assert "Miscellaneous" not in result.matches[0].text
