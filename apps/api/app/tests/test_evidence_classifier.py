from app.models.evidence import EvidenceKind
from app.services.evidence.classifier import classify_evidence, discover_witness_names, infer_issue_codes


def test_classifies_english_contract():
    result = classify_evidence("service-agreement.pdf", "This Agreement records the contract between the parties.")
    assert result.kind == EvidenceKind.CONTRACT
    assert result.confidence > 0.5


def test_classifies_hindi_financial_record():
    result = classify_evidence("रसीद.pdf", "भुगतान की रसीद और बैंक विवरण संलग्न है।")
    assert result.kind == EvidenceKind.FINANCIAL


def test_classifies_hindi_witness_statement():
    result = classify_evidence("बयान.pdf", "गवाह: राम कुमार ने अपना बयान दिया।")
    assert result.kind == EvidenceKind.WITNESS_STATEMENT


def test_infers_payment_and_notice_issues():
    found = {code for code, _, _ in infer_issue_codes("Payment was made after service of notice")}
    assert "payment" in found
    assert "notice" in found


def test_infers_hindi_property_issue():
    found = {code for code, _, _ in infer_issue_codes("संपत्ति पर कब्जा और स्वामित्व विवादित है")}
    assert "property" in found


def test_discovers_english_witness_marker():
    names = discover_witness_names("PW-1: Rajesh Kumar\nThe witness was examined.")
    assert any("Rajesh Kumar" in name for name in names)


def test_discovers_hindi_witness_marker():
    names = discover_witness_names("गवाह: राम कुमार\nउसने दस्तावेज की पहचान की।")
    assert any("राम कुमार" in name for name in names)
