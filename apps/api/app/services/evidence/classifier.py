from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.evidence import EvidenceKind


@dataclass(frozen=True, slots=True)
class Classification:
    kind: EvidenceKind
    confidence: float
    matched_terms: tuple[str, ...]


RULES: dict[EvidenceKind, tuple[str, ...]] = {
    EvidenceKind.COURT_ORDER: ("order", "judgment", "court order", "आदेश", "निर्णय", "न्यायालय"),
    EvidenceKind.COURT_FILING: ("petition", "plaint", "written statement", "affidavit", "application", "याचिका", "शपथपत्र", "प्रार्थना पत्र"),
    EvidenceKind.CONTRACT: ("agreement", "contract", "memorandum of understanding", "nda", "समझौता", "अनुबंध"),
    EvidenceKind.CORRESPONDENCE: ("email", "letter", "notice", "reply", "whatsapp", "ईमेल", "पत्र", "नोटिस", "उत्तर"),
    EvidenceKind.FINANCIAL: ("invoice", "bank statement", "payment", "receipt", "ledger", "₹", "inr", "भुगतान", "रसीद", "बैंक"),
    EvidenceKind.IDENTITY: ("aadhaar", "pan card", "passport", "identity", "पहचान", "आधार", "पासपोर्ट"),
    EvidenceKind.PROPERTY: ("sale deed", "gift deed", "lease deed", "property", "खसरा", "खतौनी", "विलेख", "संपत्ति"),
    EvidenceKind.WITNESS_STATEMENT: ("witness statement", "deposition", "cross examination", "pw-", "dw-", "गवाह", "बयान", "जिरह"),
    EvidenceKind.EXPERT: ("expert report", "forensic", "valuation report", "medical opinion", "विशेषज्ञ", "फोरेंसिक"),
    EvidenceKind.PHOTO_VIDEO: ("photograph", "photo", "video", "cctv", "तस्वीर", "वीडियो"),
    EvidenceKind.ELECTRONIC: ("metadata", "server log", "call detail", "cdr", "electronic record", "इलेक्ट्रॉनिक", "कॉल रिकॉर्ड"),
}


def _haystack(filename: str, text: str) -> str:
    return re.sub(r"\s+", " ", f"{filename} {text}".casefold())


def classify_evidence(filename: str, text: str) -> Classification:
    haystack = _haystack(filename, text[:30000])
    scores: list[tuple[int, EvidenceKind, tuple[str, ...]]] = []
    for kind, terms in RULES.items():
        matched = tuple(term for term in terms if term.casefold() in haystack)
        if matched:
            scores.append((len(matched), kind, matched))
    if not scores:
        return Classification(EvidenceKind.OTHER, 0.45, ())
    scores.sort(key=lambda x: (x[0], len("".join(x[2]))), reverse=True)
    count, kind, matched = scores[0]
    confidence = min(0.98, 0.58 + 0.09 * count)
    return Classification(kind, confidence, matched)


ISSUE_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "agreement": ("Existence and terms of agreement", ("agreement", "contract", "समझौता", "अनुबंध")),
    "payment": ("Payment / consideration", ("payment", "paid", "invoice", "receipt", "भुगतान", "रसीद")),
    "notice": ("Notice and service", ("notice", "served", "service", "नोटिस", "तामील")),
    "termination": ("Termination", ("termination", "terminated", "समाप्त", "सेवा समाप्त")),
    "property": ("Title / possession of property", ("property", "possession", "title", "संपत्ति", "कब्जा", "स्वामित्व")),
    "identity": ("Identity / capacity of parties", ("identity", "authorised", "director", "पहचान", "अधिकृत")),
    "electronic": ("Electronic record authenticity", ("electronic", "email", "whatsapp", "metadata", "इलेक्ट्रॉनिक", "ईमेल")),
}


def infer_issue_codes(text: str) -> list[tuple[str, str, tuple[str, ...]]]:
    haystack = text.casefold()
    found: list[tuple[str, str, tuple[str, ...]]] = []
    for code, (title, terms) in ISSUE_RULES.items():
        matched = tuple(term for term in terms if term.casefold() in haystack)
        if matched:
            found.append((code, title, matched))
    return found


WITNESS_PATTERNS = [
    re.compile(r"\b(?:PW|DW|CW|RW)[-\s]?\d+\s*[:.-]?\s*([A-Z][A-Za-z .'-]{2,80})", re.I),
    re.compile(r"\b(?:witness|deponent)\s+(?:Mr\.?|Ms\.?|Mrs\.?)?\s*([A-Z][A-Za-z .'-]{2,80})", re.I),
    re.compile(r"(?:गवाह|साक्षी)\s*[:.-]?\s*([\u0900-\u097F][\u0900-\u097F ]{2,60})"),
]


def discover_witness_names(text: str) -> list[str]:
    names: list[str] = []
    for pattern in WITNESS_PATTERNS:
        for match in pattern.finditer(text[:50000]):
            name = re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
            if 2 <= len(name) <= 100 and name.casefold() not in {n.casefold() for n in names}:
                names.append(name)
    return names[:50]
