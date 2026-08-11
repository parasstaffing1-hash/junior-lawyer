from app.services.language.detector import detect_language
from app.services.language.normalizer import extract_legal_references, normalize_legal_text


def test_detect_hindi() -> None:
    result = detect_language("याचिकाकर्ता ने न्यायालय में जमानत आवेदन दिया।")
    assert result.language == "hi"


def test_detect_english() -> None:
    result = detect_language("The petitioner filed a bail application before the court.")
    assert result.language == "en"


def test_detect_mixed() -> None:
    result = detect_language("Petitioner ने court में जमानत application file किया")
    assert result.language == "mixed"


def test_section_reference_english() -> None:
    refs = extract_legal_references("Application under Section 420")
    assert refs[0].canonical == "section:420"


def test_section_reference_hindi() -> None:
    refs = extract_legal_references("धारा 420 के अंतर्गत आवेदन")
    assert refs[0].canonical == "section:420"


def test_section_reference_hinglish() -> None:
    refs = extract_legal_references("dhara 420 me application")
    assert refs[0].canonical == "section:420"


def test_legal_text_normalization() -> None:
    normalized = normalize_legal_text("याचिकाकर्ता ने धारा 420 में जमानत मांगी")
    assert "petitioner" in normalized
    assert "section" in normalized
    assert "bail" in normalized


def test_detect_hinglish_roman_script() -> None:
    result = detect_language("dhara 420 me bail kab milti hai")
    assert result.language == "hinglish"
