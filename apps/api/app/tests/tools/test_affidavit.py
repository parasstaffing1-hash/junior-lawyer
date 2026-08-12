from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.tools.affidavit.models import (
    AffidavitGenerationRequest,
    AffidavitStatement,
    AnnexureReference,
)
from app.tools.affidavit.service import generate_affidavit, list_templates

client = TestClient(app)


def general_fields() -> dict[str, str]:
    return {
        "deponent_name": "Alex Example",
        "deponent_age": "42",
        "deponent_address": "10 Example Road, Sample City",
        "place": "Sample City",
        "verification_date": "2026-08-08",
    }


def test_affidavit_templates_are_discoverable() -> None:
    ids = {template.id for template in list_templates()}
    assert "demo-general-affidavit-v1" in ids
    assert "demo-supporting-affidavit-v1" in ids


def test_general_affidavit_numbers_statements_deterministically() -> None:
    result = generate_affidavit(
        AffidavitGenerationRequest(
            template_id="demo-general-affidavit-v1",
            generation_date=date(2026, 8, 8),
            fields=general_fields(),
            statements=[
                AffidavitStatement(text="I entered into the agreement on 1 July 2026."),
                AffidavitStatement(text="The attached invoice remains unpaid."),
            ],
        )
    )

    assert result.template_version == "1.0.0"
    assert result.statements[0].number == 1
    assert result.statements[1].number == 2
    assert "1. I entered into the agreement" in result.rendered_text
    assert "statements 1 through 2" in result.rendered_text


def test_statement_source_reference_is_rendered() -> None:
    result = generate_affidavit(
        AffidavitGenerationRequest(
            template_id="demo-general-affidavit-v1",
            generation_date=date(2026, 8, 8),
            fields=general_fields(),
            statements=[
                AffidavitStatement(
                    text="The invoice was issued on 2 July 2026.",
                    source_reference="Annexure A",
                )
            ],
        )
    )
    assert "[Reference: Annexure A]" in result.rendered_text
    assert result.statements[0].source_reference == "Annexure A"


def test_annexure_schedule_is_optional_and_rendered_when_supplied() -> None:
    result = generate_affidavit(
        AffidavitGenerationRequest(
            template_id="demo-general-affidavit-v1",
            generation_date=date(2026, 8, 8),
            fields=general_fields(),
            statements=[AffidavitStatement(text="I rely on the attached agreement.")],
            annexures=[
                AnnexureReference(
                    label="Annexure A",
                    title="Services Agreement",
                    document_date=date(2026, 7, 1),
                    description="Signed copy",
                )
            ],
        )
    )
    ids = {section.id for section in result.sections}
    assert "annexures" in ids
    assert "Annexure A: Services Agreement (2026-07-01) — Signed copy" in result.rendered_text


def test_no_annexure_section_when_none_supplied() -> None:
    result = generate_affidavit(
        AffidavitGenerationRequest(
            template_id="demo-general-affidavit-v1",
            generation_date=date(2026, 8, 8),
            fields=general_fields(),
            statements=[AffidavitStatement(text="A fact stated from personal knowledge.")],
        )
    )
    assert "annexures" not in {section.id for section in result.sections}
    assert "No annexures were supplied." in result.warnings


def test_duplicate_annexure_labels_return_422() -> None:
    response = client.post(
        "/api/v1/tools/affidavits/generate",
        json={
            "template_id": "demo-general-affidavit-v1",
            "generation_date": "2026-08-08",
            "fields": general_fields(),
            "statements": [{"text": "One statement."}],
            "annexures": [
                {"label": "Annexure A", "title": "First"},
                {"label": "annexure a", "title": "Second"},
            ],
        },
    )
    assert response.status_code == 422
    assert "duplicate annexure label" in response.json()["detail"]


def test_missing_required_field_returns_422() -> None:
    fields = general_fields()
    del fields["deponent_name"]
    response = client.post(
        "/api/v1/tools/affidavits/generate",
        json={
            "template_id": "demo-general-affidavit-v1",
            "generation_date": "2026-08-08",
            "fields": fields,
            "statements": [{"text": "One statement."}],
        },
    )
    assert response.status_code == 422
    assert "deponent_name" in response.json()["detail"]


def test_unknown_template_returns_404() -> None:
    response = client.post(
        "/api/v1/tools/affidavits/generate",
        json={
            "template_id": "not-real",
            "generation_date": "2026-08-08",
            "fields": {},
            "statements": [{"text": "One statement."}],
        },
    )
    assert response.status_code == 404


def test_template_list_endpoint() -> None:
    response = client.get("/api/v1/tools/affidavits/templates")
    assert response.status_code == 200
    assert len(response.json()) >= 2
    assert any(item["id"] == "demo-general-affidavit-v1" for item in response.json())
