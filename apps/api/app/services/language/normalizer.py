import re
import unicodedata
from dataclasses import dataclass

from app.services.language.legal_dictionary import HINGLISH_TERM_MAP, LEGAL_TERM_MAP


WHITESPACE_RE = re.compile(r"\s+")
HORIZONTAL_WHITESPACE_RE = re.compile(r"[^\S\r\n]+")
EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Supports Section 420, Sec. 420, धारा 420, dhara 420 and article/rule equivalents.
REFERENCE_RE = re.compile(
    r"(?P<label>section|sec\.?|धारा|सेक्शन|dhara|dhaara|article|अनुच्छेद|anuched|anumched|"
    r"rule|नियम|niyam)\s*[-:]?\s*(?P<number>\d+[A-Za-z]?(?:\([0-9A-Za-z]+\))*)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class NormalizedReference:
    raw: str
    normalized_type: str
    number: str
    canonical: str


def normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_document_text(text: str) -> str:
    """Normalize Unicode while preserving document line boundaries for legal extraction."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = HORIZONTAL_WHITESPACE_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return EXCESS_BLANK_LINES_RE.sub("\n\n", text).strip()


def _canonical_label(label: str) -> str:
    cleaned = label.casefold().rstrip(".")
    if cleaned in {"sec", "section"}:
        return "section"
    if cleaned == "article":
        return "article"
    if cleaned == "rule":
        return "rule"
    if label in LEGAL_TERM_MAP:
        return LEGAL_TERM_MAP[label]
    if cleaned in HINGLISH_TERM_MAP:
        return HINGLISH_TERM_MAP[cleaned]
    return cleaned


def extract_legal_references(text: str) -> list[NormalizedReference]:
    normalized = normalize_unicode(text)
    references: list[NormalizedReference] = []

    for match in REFERENCE_RE.finditer(normalized):
        raw = match.group(0)
        ref_type = _canonical_label(match.group("label"))
        number = match.group("number").upper()
        references.append(
            NormalizedReference(
                raw=raw,
                normalized_type=ref_type,
                number=number,
                canonical=f"{ref_type}:{number}",
            )
        )

    return references


def normalize_legal_text(text: str) -> str:
    normalized = normalize_unicode(text)

    # Replace high-confidence Devanagari terms first.
    for source, target in sorted(LEGAL_TERM_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = re.sub(
            rf"(?<!\w){re.escape(source)}(?!\w)",
            target,
            normalized,
            flags=re.IGNORECASE,
        )

    # Replace high-confidence Hinglish tokens.
    for source, target in HINGLISH_TERM_MAP.items():
        normalized = re.sub(
            rf"\b{re.escape(source)}\b",
            target,
            normalized,
            flags=re.IGNORECASE,
        )

    return WHITESPACE_RE.sub(" ", normalized).strip()
