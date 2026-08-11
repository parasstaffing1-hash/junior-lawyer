from app.models.contract import ContractType
from app.services.contracts.catalog import BUILTIN_CLAUSES, CONTRACT_DEFINITIONS, get_contract_catalog


def test_all_contract_types_have_playbooks():
    assert set(CONTRACT_DEFINITIONS) == {item.value for item in ContractType}
    assert len(get_contract_catalog()) == 8


def test_playbooks_have_questions_and_clauses():
    for definition in CONTRACT_DEFINITIONS.values():
        assert definition["questions"]
        assert definition["clauses"]
        keys = {item["key"] for item in definition["questions"]}
        assert "effective_date" in keys
        assert "governing_state" in keys
        assert "dispute_mode" in keys


def test_protective_variants_exist_for_material_risk_clauses():
    variants = {(item["clause_type"], item["variant_key"]) for item in BUILTIN_CLAUSES}
    for clause_type in ("term_termination", "liability", "indemnity"):
        assert (clause_type, "balanced") in variants
        assert (clause_type, "pro_party_a") in variants
        assert (clause_type, "pro_party_b") in variants


def test_every_clause_has_bilingual_rendering():
    assert len(BUILTIN_CLAUSES) >= 20
    for clause in BUILTIN_CLAUSES:
        assert clause["title_en"]
        assert clause["title_hi"]
        assert clause["body_en"]
        assert clause["body_hi"]
