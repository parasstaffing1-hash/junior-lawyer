from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.client_matter_intake.models import (
    ClientMatterIntakeRequest,
    ConflictPartyInput,
    ConsentInput,
)
from app.tools.client_matter_intake.service import (
    IntakeInputError,
    IntakeTemplateDateError,
    IntakeTemplateNotFoundError,
    generate_intake,
    list_templates,
)

client = TestClient(app)


def base_request(**overrides) -> ClientMatterIntakeRequest:
    payload = dict(
        template_id="demo_general_matter_intake_v1",
        intake_date=date(2026, 8, 8),
        values={
            "client_name": "Asha Rao",
            "client_type": "Individual",
            "email": "asha@example.com",
            "phone": "+91 98765 43210",
            "matter_title": "Contract payment dispute",
            "matter_category": "Contract",
            "matter_summary": "Payment remains outstanding under the written agreement.",
            "urgency": "Time-sensitive",
            "has_opposing_parties": False,
        },
        conflict_parties=[],
        consents=[
            ConsentInput(key="accuracy_confirmation", accepted=True),
            ConsentInput(key="intake_processing_ack", accepted=True),
        ],
    )
    payload.update(overrides)
    return ClientMatterIntakeRequest(**payload)


def test_template_listing_and_filters() -> None:
    all_templates = list_templates()
    assert {item.id for item in all_templates} >= {
        "demo_general_matter_intake_v1",
        "demo_business_matter_intake_v1",
    }
    filtered = list_templates(client_type="business")
    assert [item.id for item in filtered] == ["demo_business_matter_intake_v1"]


def test_complete_general_intake_is_ready_for_review() -> None:
    result = generate_intake(base_request())
    assert result.summary.ready_for_review is True
    assert result.summary.required_completion_percent == 100.0
    assert result.normalized_values["client_name"] == "Asha Rao"
    assert result.normalized_values["has_opposing_parties"] is False
    assert len(result.audit_hash_sha256) == 64


def test_business_client_condition_makes_organization_required() -> None:
    values = dict(base_request().values)
    values["client_type"] = "Business"
    result = generate_intake(base_request(values=values))
    organization = next(field for field in result.fields if field.key == "organization_name")
    assert organization.applicable is True
    assert organization.required is True
    assert "organization_name" in result.summary.missing_required_fields
    assert result.summary.ready_for_review is False


def test_individual_client_hides_organization_field() -> None:
    result = generate_intake(base_request())
    organization = next(field for field in result.fields if field.key == "organization_name")
    assert organization.applicable is False
    assert organization.required is False
    assert organization.provided is False


def test_invalid_email_and_date_are_reported_not_silently_normalized() -> None:
    values = dict(base_request().values)
    values["email"] = "not-an-email"
    values["key_date"] = "2026-02-30"
    result = generate_intake(base_request(values=values))
    assert result.summary.invalid_fields == 2
    assert "email" in result.summary.missing_required_fields
    date_field = next(field for field in result.fields if field.key == "key_date")
    assert date_field.valid is False
    assert "valid ISO date" in date_field.validation_messages[0]


def test_choice_and_number_values_are_canonicalized() -> None:
    values = dict(base_request().values)
    values["matter_category"] = "contract"
    values["claim_amount"] = "00125000.5000"
    result = generate_intake(base_request(values=values))
    assert result.normalized_values["matter_category"] == "Contract"
    assert result.normalized_values["claim_amount"] == "125000.5"


def test_conflict_requirement_warns_when_party_missing() -> None:
    values = dict(base_request().values)
    values["has_opposing_parties"] = True
    result = generate_intake(base_request(values=values))
    assert result.summary.ready_for_review is False
    assert any("no conflict-check party" in warning for warning in result.warnings)


def test_conflict_terms_are_deduplicated_and_include_aliases() -> None:
    values = dict(base_request().values)
    values["has_opposing_parties"] = True
    # Pydantic correctly rejects duplicate aliases ignoring case before the service runs.
    with pytest.raises(ValueError, match="aliases must be unique"):
        ConflictPartyInput(
            name="Example Holdings Pvt Ltd",
            role="counterparty",
            organization="Example Holdings Pvt Ltd",
            aliases=["Example Holdings", "EXAMPLE HOLDINGS"],
        )

    parties = [
        ConflictPartyInput(
            name="Example Holdings Pvt Ltd",
            role="counterparty",
            organization="Example Group",
            aliases=["Example Holdings"],
        )
    ]
    result = generate_intake(base_request(values=values, conflict_parties=parties))
    assert result.conflict_search_terms == [
        "Asha Rao",
        "Example Holdings Pvt Ltd",
        "Example Group",
        "Example Holdings",
    ]
    assert any("no law-firm conflicts database" in warning for warning in result.warnings)


def test_required_consents_affect_readiness() -> None:
    result = generate_intake(base_request(consents=[]))
    assert result.summary.missing_required_consents == [
        "accuracy_confirmation",
        "intake_processing_ack",
    ]
    assert result.summary.ready_for_review is False
    assert result.summary.required_completion_percent < 100


def test_unknown_fields_and_duplicate_consents_are_rejected() -> None:
    values = dict(base_request().values)
    values["unexpected_field"] = "x"
    with pytest.raises(IntakeInputError, match="unknown intake field"):
        generate_intake(base_request(values=values))

    with pytest.raises(IntakeInputError, match="duplicate consent key"):
        generate_intake(
            base_request(
                consents=[
                    ConsentInput(key="accuracy_confirmation", accepted=True),
                    ConsentInput(key="accuracy_confirmation", accepted=False),
                ]
            )
        )


def test_template_errors_are_explicit() -> None:
    with pytest.raises(IntakeTemplateNotFoundError):
        generate_intake(base_request(template_id="missing"))
    with pytest.raises(IntakeTemplateDateError):
        generate_intake(base_request(intake_date=date(2025, 12, 31)))


def test_markdown_is_export_ready() -> None:
    result = generate_intake(base_request())
    assert "# General Client / Matter Intake (Demo)" in result.markdown
    assert "## Client details" in result.markdown
    assert "Contract payment dispute" in result.markdown
    assert "## Consents / confirmations" in result.markdown


def test_api_lists_templates_and_generates_intake() -> None:
    response = client.get("/api/v1/tools/client-intakes/templates?client_type=business")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "demo_business_matter_intake_v1"

    response = client.post(
        "/api/v1/tools/client-intakes/generate",
        json={
            "template_id": "demo_general_matter_intake_v1",
            "intake_date": "2026-08-08",
            "values": {
                "client_name": "Asha Rao",
                "client_type": "Individual",
                "email": "asha@example.com",
                "phone": "+91 98765 43210",
                "matter_title": "Contract payment dispute",
                "matter_category": "Contract",
                "matter_summary": "Outstanding payment.",
                "urgency": "Routine",
                "has_opposing_parties": False
            },
            "conflict_parties": [],
            "consents": [
                {"key": "accuracy_confirmation", "accepted": True},
                {"key": "intake_processing_ack", "accepted": True}
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["ready_for_review"] is True
    assert payload["template_version"] == "1.0.0"


def test_api_returns_404_for_unknown_template() -> None:
    response = client.post(
        "/api/v1/tools/client-intakes/generate",
        json={
            "template_id": "does_not_exist",
            "intake_date": "2026-08-08",
            "values": {},
            "conflict_parties": [],
            "consents": []
        },
    )
    assert response.status_code == 404
