from app.models.intelligence import StatementKind
from app.services.intelligence.extractor import extract_intelligence


def test_extracts_english_agreement_amount_and_admission():
    text = (
        "The parties executed the agreement on 12 March 2025. "
        "The total consideration was ₹10,00,000. "
        "The petitioner admits that payment was received."
    )
    result = extract_intelligence(text)

    assert any(
        fact.fact_key == "agreement_execution_date" and fact.normalized_value == "2025-03-12"
        for fact in result.facts
    )
    assert any(
        fact.fact_key == "contract_amount" and fact.normalized_value == "1000000"
        for fact in result.facts
    )
    assert any(
        statement.kind == StatementKind.ADMISSION and statement.speaker_role == "petitioner"
        for statement in result.statements
    )
    assert any(event.event_type == "agreement_execution" for event in result.events)


def test_extracts_hindi_agreement_and_denial():
    text = (
        "दिनांक 12 मार्च 2025 को समझौता निष्पादित किया गया। "
        "कुल प्रतिफल ₹10,00,000 था। "
        "प्रतिवादी इनकार करता है कि भुगतान प्राप्त हुआ।"
    )
    result = extract_intelligence(text)

    assert any(
        fact.fact_key == "agreement_execution_date" and fact.normalized_value == "2025-03-12"
        for fact in result.facts
    )
    assert any(fact.fact_key == "contract_amount" for fact in result.facts)
    assert any(
        statement.kind == StatementKind.DENIAL and statement.speaker_role in {"respondent", "defendant"}
        for statement in result.statements
    )


def test_repeatable_hearings_do_not_share_single_value_fact_key():
    result = extract_intelligence(
        "The matter was listed for hearing on 12 March 2025.\n"
        "The next hearing was fixed on 20 April 2025."
    )
    keys = [fact.fact_key for fact in result.facts if fact.category == "hearing_date"]
    assert len(keys) == 2
    assert len(set(keys)) == 2


def test_payment_date_key_uses_amount_to_reduce_false_conflicts():
    result = extract_intelligence(
        "Payment of ₹50,000 was made on 12 March 2025.\n"
        "Payment of ₹75,000 was made on 15 March 2025."
    )
    keys = {fact.fact_key for fact in result.facts if fact.category == "payment_date"}
    assert "payment_date:50000" in keys
    assert "payment_date:75000" in keys


def test_hinglish_statement_is_detected():
    result = extract_intelligence("Petitioner submit karta hai ki notice 12 March 2025 ko bheja gaya.")
    assert any(statement.kind == StatementKind.CLAIM for statement in result.statements)
    assert any(event.event_type == "notice" for event in result.events)


def test_plain_numbers_are_not_treated_as_money():
    result = extract_intelligence("The hearing was on 12 March 2025 in courtroom 14.")
    assert not any(fact.fact_type.value == "money" for fact in result.facts)
