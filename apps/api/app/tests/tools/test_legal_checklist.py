from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.legal_checklist.models import ChecklistItemInput, LegalChecklistRequest
from app.tools.legal_checklist.service import (
    LegalChecklistInputError,
    LegalChecklistTemplateDateError,
    LegalChecklistTemplateNotFoundError,
    evaluate_checklist,
    list_templates,
)

client = TestClient(app)


def base_request(**overrides):
    payload = dict(
        template_id="demo_civil_litigation_v1",
        assessment_date=date(2026, 8, 8),
        context={
            "has_written_contract": "no",
            "seeks_interim_relief": "no",
            "prior_notice_sent": "no",
        },
        items=[],
    )
    payload.update(overrides)
    return LegalChecklistRequest(**payload)


def test_template_listing_and_matter_filter() -> None:
    all_templates = list_templates()
    assert {item.id for item in all_templates} >= {
        "demo_civil_litigation_v1",
        "demo_contract_review_v1",
    }
    filtered = list_templates("contract_review")
    assert [item.id for item in filtered] == ["demo_contract_review_v1"]


def test_conditional_items_are_not_applicable_when_context_is_no() -> None:
    result = evaluate_checklist(base_request())
    by_key = {item.key: item for item in result.items}
    assert by_key["written_contract"].applicable is False
    assert by_key["written_contract"].status.value == "not_applicable"
    assert by_key["interim_relief_material"].applicable is False
    assert result.summary.applicable_items == 7


def test_conditional_requirement_is_elevated_to_required() -> None:
    result = evaluate_checklist(
        base_request(
            context={
                "has_written_contract": "YES",
                "seeks_interim_relief": "yes",
                "prior_notice_sent": "no",
            }
        )
    )
    by_key = {item.key: item for item in result.items}
    assert by_key["written_contract"].required is True
    assert by_key["interim_relief_material"].required is True
    assert "written_contract" in result.summary.outstanding_required_keys


def test_completion_and_required_progress_are_calculated() -> None:
    result = evaluate_checklist(
        base_request(
            items=[
                ChecklistItemInput(
                    key="client_identity",
                    status="present",
                    file_reference="client-id.pdf",
                ),
                ChecklistItemInput(key="authority_to_act", status="present", file_reference="loa.pdf"),
                ChecklistItemInput(key="facts_chronology", status="completed"),
                ChecklistItemInput(key="limitation_review", status="completed"),
                ChecklistItemInput(key="supporting_evidence", status="present", file_reference="evidence.pdf"),
            ]
        )
    )
    assert result.summary.required_items == 5
    assert result.summary.required_satisfied == 5
    assert result.summary.required_completion_percent == 100.0
    assert result.summary.required_outstanding == 0


def test_applicable_item_cannot_be_marked_not_applicable() -> None:
    with pytest.raises(LegalChecklistInputError, match="cannot be marked not_applicable"):
        evaluate_checklist(
            base_request(
                items=[ChecklistItemInput(key="client_identity", status="not_applicable")]
            )
        )


def test_non_applicable_supplied_status_is_normalized_with_warning() -> None:
    result = evaluate_checklist(
        base_request(
            items=[ChecklistItemInput(key="written_contract", status="present", file_reference="contract.pdf")]
        )
    )
    item = next(item for item in result.items if item.key == "written_contract")
    assert item.status.value == "not_applicable"
    assert any("normalized to not_applicable" in warning for warning in result.warnings)


def test_unknown_context_and_duplicate_item_keys_are_rejected() -> None:
    with pytest.raises(LegalChecklistInputError, match="unknown context"):
        evaluate_checklist(base_request(context={"unexpected": "yes"}))

    with pytest.raises(LegalChecklistInputError, match="duplicate checklist item key"):
        evaluate_checklist(
            base_request(
                items=[
                    ChecklistItemInput(key="client_identity", status="missing"),
                    ChecklistItemInput(key="client_identity", status="pending"),
                ]
            )
        )


def test_invalid_context_value_is_rejected() -> None:
    with pytest.raises(LegalChecklistInputError, match="must be one of"):
        evaluate_checklist(
            base_request(
                context={
                    "has_written_contract": "maybe",
                    "seeks_interim_relief": "no",
                    "prior_notice_sent": "no",
                }
            )
        )


def test_template_not_found_and_effective_date_errors() -> None:
    with pytest.raises(LegalChecklistTemplateNotFoundError):
        evaluate_checklist(base_request(template_id="missing"))
    with pytest.raises(LegalChecklistTemplateDateError):
        evaluate_checklist(base_request(assessment_date=date(2025, 12, 31)))


def test_markdown_is_export_ready() -> None:
    result = evaluate_checklist(base_request())
    assert "# Civil Litigation Matter Checklist (Demo)" in result.markdown
    assert "| # | Item | Category | Requirement | Status |" in result.markdown
    assert "Client identity / KYC material" in result.markdown


def test_api_lists_templates_and_evaluates() -> None:
    response = client.get("/api/v1/tools/legal-checklists/templates?matter_type=civil_litigation")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "demo_civil_litigation_v1"

    response = client.post(
        "/api/v1/tools/legal-checklists/evaluate",
        json={
            "template_id": "demo_civil_litigation_v1",
            "assessment_date": "2026-08-08",
            "context": {
                "has_written_contract": "no",
                "seeks_interim_relief": "no",
                "prior_notice_sent": "no"
            },
            "items": [
                {"key": "facts_chronology", "status": "completed"}
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["required_satisfied"] == 1
    assert payload["template_version"] == "1.0.0"


def test_api_returns_404_for_unknown_template() -> None:
    response = client.post(
        "/api/v1/tools/legal-checklists/evaluate",
        json={
            "template_id": "does_not_exist",
            "assessment_date": "2026-08-08",
            "context": {},
            "items": []
        },
    )
    assert response.status_code == 404
