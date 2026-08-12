from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.tools.legal_notice.models import LegalNoticeGenerationRequest
from app.tools.legal_notice.service import generate_legal_notice, list_templates

client = TestClient(app)


def payment_fields() -> dict[str, str]:
    return {
        "sender_name": "Example Supplier Pvt Ltd",
        "sender_address": "1 Demo Street, Example City",
        "recipient_name": "Example Customer Pvt Ltd",
        "recipient_address": "2 Sample Road, Example City",
        "amount_due": "125000",
        "currency": "INR",
        "payment_due_date": "2026-07-15",
        "payment_deadline": "2026-08-22",
        "transaction_description": "Unpaid invoices for services supplied",
    }


def test_notice_templates_are_discoverable() -> None:
    ids = {template.id for template in list_templates()}
    assert "demo-payment-demand-v1" in ids
    assert "demo-breach-notice-v1" in ids


def test_payment_notice_renders_required_fields() -> None:
    result = generate_legal_notice(
        LegalNoticeGenerationRequest(
            template_id="demo-payment-demand-v1",
            generation_date=date(2026, 8, 8),
            fields=payment_fields(),
        )
    )

    assert result.template_version == "1.0.0"
    assert result.subject == "Demand for payment of INR 125000"
    assert "Example Supplier Pvt Ltd" in result.rendered_text
    assert "INR 125000" in result.rendered_text
    assert "2026-08-22" in result.rendered_text


def test_optional_section_is_omitted_when_field_missing() -> None:
    result = generate_legal_notice(
        LegalNoticeGenerationRequest(
            template_id="demo-payment-demand-v1",
            generation_date=date(2026, 8, 8),
            fields=payment_fields(),
        )
    )

    ids = {section.id for section in result.sections}
    assert "reference" not in ids
    assert "payment_instructions" not in ids
    assert "signature" not in ids
    assert any("Optional fields omitted" in warning for warning in result.warnings)


def test_optional_sections_render_when_values_are_present() -> None:
    fields = payment_fields() | {
        "contract_reference": "Services Agreement SA-101",
        "payment_instructions": "Pay to the account stated on Invoice INV-42.",
        "lawyer_name": "A. Example, Advocate",
    }
    result = generate_legal_notice(
        LegalNoticeGenerationRequest(
            template_id="demo-payment-demand-v1",
            generation_date=date(2026, 8, 8),
            fields=fields,
        )
    )

    ids = {section.id for section in result.sections}
    assert {"reference", "payment_instructions", "signature"}.issubset(ids)
    assert "Services Agreement SA-101" in result.rendered_text
    assert "A. Example, Advocate" in result.rendered_text


def test_missing_required_field_returns_422() -> None:
    fields = payment_fields()
    del fields["amount_due"]
    response = client.post(
        "/api/v1/tools/legal-notices/generate",
        json={
            "template_id": "demo-payment-demand-v1",
            "generation_date": "2026-08-08",
            "fields": fields,
        },
    )

    assert response.status_code == 422
    assert "amount_due" in response.json()["detail"]


def test_unknown_field_returns_422() -> None:
    response = client.post(
        "/api/v1/tools/legal-notices/generate",
        json={
            "template_id": "demo-payment-demand-v1",
            "generation_date": "2026-08-08",
            "fields": payment_fields() | {"made_up_field": "value"},
        },
    )

    assert response.status_code == 422
    assert "unknown template field" in response.json()["detail"]


def test_unknown_template_returns_404() -> None:
    response = client.post(
        "/api/v1/tools/legal-notices/generate",
        json={
            "template_id": "not-real",
            "generation_date": "2026-08-08",
            "fields": {},
        },
    )

    assert response.status_code == 404


def test_template_list_endpoint() -> None:
    response = client.get("/api/v1/tools/legal-notices/templates")
    assert response.status_code == 200
    assert len(response.json()) >= 2
    assert any(item["id"] == "demo-payment-demand-v1" for item in response.json())


def test_breach_notice_conditional_consequence() -> None:
    result = generate_legal_notice(
        LegalNoticeGenerationRequest(
            template_id="demo-breach-notice-v1",
            generation_date=date(2026, 8, 8),
            fields={
                "sender_name": "Example Company",
                "recipient_name": "Other Company",
                "agreement_name": "Supply Agreement",
                "agreement_date": "2026-01-10",
                "breach_description": "Delivery was not completed by the stated date",
                "cure_action": "Complete delivery of the outstanding items",
                "cure_deadline": "2026-08-20",
                "consequence_description": "exercise remedies stated in the agreement",
            },
        )
    )

    assert any(section.id == "consequence" for section in result.sections)
    assert "exercise remedies stated in the agreement" in result.rendered_text
