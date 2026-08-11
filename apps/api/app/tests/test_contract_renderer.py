from uuid import uuid4

from docx import Document as WordDocument

from app.models.contract import Contract, ContractClause, ContractLanguage, ContractRiskProfile, ContractStatus, ContractType
from app.services.contracts.renderer import generate_docx, render_text, resolve_contract_storage_key


def test_render_text_replaces_known_values_and_flags_missing_values():
    text = render_text("Hello {{party_a_name}} — {{missing}}", {"party_a_name": "Alpha"})
    assert "Alpha" in text
    assert "[TO BE COMPLETED]" in text


def test_generate_real_bilingual_docx(tmp_path, monkeypatch):
    from app.services.contracts import renderer

    monkeypatch.setattr(renderer, "contract_storage_root", lambda: tmp_path)
    contract = Contract(
        id=uuid4(),
        title="Consulting Agreement",
        contract_type=ContractType.CONSULTING,
        language=ContractLanguage.BILINGUAL,
        status=ContractStatus.DRAFT,
        risk_profile=ContractRiskProfile.BALANCED,
        jurisdiction="India",
        governing_state="Delhi",
        party_a_name="Alpha Pvt Ltd",
        party_b_name="Beta Consulting",
        questionnaire_json={"scope_description": "Legal operations", "fee_amount": 100000, "payment_schedule": "Monthly", "notice_days": 30, "arbitration_city": "New Delhi"},
    )
    contract.clauses = [
        ContractClause(
            contract_id=contract.id,
            clause_code="appointment_scope.balanced",
            clause_type="appointment_scope",
            variant_key="balanced",
            title_en="Scope",
            title_hi="कार्य-क्षेत्र",
            body_en="{{party_b_name}} will provide {{scope_description}}.",
            body_hi="{{party_b_name}} {{scope_description}} प्रदान करेगा।",
            position=1,
        )
    ]
    filename, key, digest = generate_docx(contract, version_number=1)
    path = resolve_contract_storage_key(key)
    assert filename.endswith(".docx")
    assert path.exists()
    assert len(digest) == 64
    doc = WordDocument(path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "DRAFT — LAWYER REVIEW REQUIRED" in full_text
    assert "Beta Consulting" in full_text
    assert "कार्य-क्षेत्र" in full_text
