from fastapi.testclient import TestClient

from app.main import app
from app.tools.contract_compare.models import (
    ContractChangeType,
    ContractClause,
    ContractCompareOptions,
    ContractCompareRequest,
)
from app.tools.contract_compare.service import compare_contracts

client = TestClient(app)


def _structured_request(**option_overrides) -> ContractCompareRequest:
    return ContractCompareRequest(
        original_clauses=[
            ContractClause(clause_id="1", title="Payment", text="Payment is due within 30 days."),
            ContractClause(clause_id="2", title="Term", text="The term is one year."),
        ],
        revised_clauses=[
            ContractClause(clause_id="1", title="Payment", text="Payment is due within 45 days."),
            ContractClause(clause_id="2", title="Term", text="The term is one year."),
        ],
        options=ContractCompareOptions(**option_overrides),
    )


def test_detects_modified_and_unchanged_structured_clauses() -> None:
    result = compare_contracts(_structured_request())
    assert result.summary.modified == 1
    assert result.summary.unchanged == 1
    assert result.summary.returned_changes == 1
    assert result.changes[0].change_type == ContractChangeType.MODIFIED
    assert "<del>30</del><ins>45</ins>" in result.changes[0].redline


def test_include_unchanged_returns_all_pairs() -> None:
    result = compare_contracts(_structured_request(include_unchanged=True))
    assert result.summary.returned_changes == 2
    assert {c.change_type for c in result.changes} == {
        ContractChangeType.MODIFIED,
        ContractChangeType.UNCHANGED,
    }


def test_detects_added_and_removed_clauses() -> None:
    request = ContractCompareRequest(
        original_clauses=[
            ContractClause(clause_id="1", title="Payment", text="Pay monthly."),
            ContractClause(clause_id="2", title="Old Warranty", text="Old warranty text."),
        ],
        revised_clauses=[
            ContractClause(clause_id="1", title="Payment", text="Pay monthly."),
            ContractClause(clause_id="3", title="Confidentiality", text="Keep information confidential."),
        ],
        options=ContractCompareOptions(similarity_threshold=0.9),
    )
    result = compare_contracts(request)
    assert result.summary.added == 1
    assert result.summary.removed == 1
    assert result.summary.unchanged == 1
    assert {c.change_type for c in result.changes} == {
        ContractChangeType.ADDED,
        ContractChangeType.REMOVED,
    }


def test_ignore_case_can_make_clause_unchanged() -> None:
    request = ContractCompareRequest(
        original_clauses=[ContractClause(clause_id="1", text="PAYMENT DUE")],
        revised_clauses=[ContractClause(clause_id="1", text="payment due")],
        options=ContractCompareOptions(ignore_case=True, include_unchanged=True),
    )
    result = compare_contracts(request)
    assert result.summary.unchanged == 1
    assert result.summary.modified == 0


def test_whitespace_normalization_can_make_clause_unchanged() -> None:
    request = ContractCompareRequest(
        original_clauses=[ContractClause(clause_id="1", text="Payment   is\n due")],
        revised_clauses=[ContractClause(clause_id="1", text="Payment is due")],
        options=ContractCompareOptions(normalize_whitespace=True, include_unchanged=True),
    )
    result = compare_contracts(request)
    assert result.summary.unchanged == 1


def test_plain_text_numbered_headings_are_split_and_aligned() -> None:
    request = ContractCompareRequest(
        original_text="1. Payment\nPayment within 30 days.\n\n2. Term\nOne year.",
        revised_text="1. Payment\nPayment within 60 days.\n\n2. Term\nOne year.",
    )
    result = compare_contracts(request)
    assert result.summary.original_clause_count == 2
    assert result.summary.revised_clause_count == 2
    assert result.summary.modified == 1
    assert result.summary.unchanged == 1


def test_plain_text_fallback_warns_about_automatic_splitting() -> None:
    request = ContractCompareRequest(
        original_text="First paragraph.\n\nSecond paragraph.",
        revised_text="First paragraph changed.\n\nSecond paragraph.",
    )
    result = compare_contracts(request)
    assert result.warnings
    assert "automatic plain-text clause splitting" in result.warnings[0]


def test_duplicate_structured_clause_ids_are_rejected_by_api() -> None:
    response = client.post(
        "/api/v1/tools/contract-compare/compare",
        json={
            "original_clauses": [
                {"clause_id": "1", "text": "A"},
                {"clause_id": "1", "text": "B"},
            ],
            "revised_clauses": [{"clause_id": "1", "text": "A"}],
        },
    )
    assert response.status_code == 422
    assert "duplicate clause_id" in response.json()["detail"]


def test_request_requires_exactly_one_source_per_side() -> None:
    response = client.post(
        "/api/v1/tools/contract-compare/compare",
        json={
            "original_text": "A",
            "original_clauses": [{"text": "A"}],
            "revised_text": "B",
        },
    )
    assert response.status_code == 422


def test_redline_escapes_html_from_source_text() -> None:
    request = ContractCompareRequest(
        original_clauses=[ContractClause(clause_id="1", text="Fee < 100")],
        revised_clauses=[ContractClause(clause_id="1", text="Fee < 200")],
    )
    result = compare_contracts(request)
    assert "&lt;" in result.changes[0].redline
    assert "< 200" not in result.changes[0].redline


def test_word_count_delta_is_reported() -> None:
    request = ContractCompareRequest(
        original_clauses=[ContractClause(clause_id="1", text="one two")],
        revised_clauses=[ContractClause(clause_id="1", text="one two three four")],
    )
    result = compare_contracts(request)
    assert result.summary.original_word_count == 2
    assert result.summary.revised_word_count == 4
    assert result.summary.word_count_delta == 2


def test_compare_api_returns_redline_and_summary() -> None:
    response = client.post(
        "/api/v1/tools/contract-compare/compare",
        json={
            "original_clauses": [{"clause_id": "1", "title": "Notice", "text": "30 days notice."}],
            "revised_clauses": [{"clause_id": "1", "title": "Notice", "text": "60 days notice."}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["modified"] == 1
    assert payload["changes"][0]["change_type"] == "modified"
    assert "Contract Comparison" in payload["redline_markdown"]
