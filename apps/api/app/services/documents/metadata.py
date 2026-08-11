from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.models.document_entity import EntityType
from app.services.language.normalizer import extract_legal_references, normalize_document_text


@dataclass(frozen=True, slots=True)
class ExtractedEntityData:
    entity_type: EntityType
    raw_text: str
    normalized_value: str | None
    confidence: float
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict = field(default_factory=dict)


CNR_RE = re.compile(r"\b(?P<cnr>[A-Z]{4}\d{12})\b", re.IGNORECASE)

CASE_NUMBER_PATTERNS = [
    re.compile(
        r"\b(?P<case>(?:W\.?P\.?\s*\(?C\)?|W\.?P\.?|C\.?S\.?\s*\(?OS\)?|CS\s*\(?COMM\)?|"
        r"CRL\.?\s*(?:A\.?|M\.?C\.?|REV\.?P\.?)?|FAO|RFA|RSA|ARB\.?\s*P\.?|O\.?M\.?P\.?|"
        r"SLP\s*\(?C(?:RL)?\)?|CIVIL\s+APPEAL|CRIMINAL\s+APPEAL|TRANSFER\s+PETITION|"
        r"CONTEMPT\s+PETITION|CASE)\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*[A-Z0-9./()\-]+"
        r"(?:\s+(?:OF|/)?\s*\d{4})?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<case>(?:वाद|मुकदमा|प्रकरण|अपील|याचिका)\s*(?:संख्या|सं\.?|नंबर)?\s*[:\-]?\s*"
        r"[0-9०-९./()\-]+(?:\s*(?:/|वर्ष)\s*[0-9०-९]{4})?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<case>(?:mukadma|mukadama|vad|yachika|appeal)\s*(?:sankhya|number|no\.?)\s*[:\-]?\s*"
        r"[0-9./()\-]+(?:\s*(?:/|of)\s*\d{4})?)\b",
        re.IGNORECASE,
    ),
]

NUMERIC_DATE_RE = re.compile(
    r"\b(?P<day>0?[1-9]|[12]\d|3[01])[-/.](?P<month>0?[1-9]|1[0-2])[-/.](?P<year>(?:19|20)\d{2})\b"
)
ENGLISH_DATE_RE = re.compile(
    r"\b(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"[,]?\s+(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
HINDI_MONTHS = {
    "जनवरी": 1,
    "फरवरी": 2,
    "मार्च": 3,
    "अप्रैल": 4,
    "मई": 5,
    "जून": 6,
    "जुलाई": 7,
    "अगस्त": 8,
    "सितंबर": 9,
    "सितम्बर": 9,
    "अक्टूबर": 10,
    "नवंबर": 11,
    "नवम्बर": 11,
    "दिसंबर": 12,
    "दिसम्बर": 12,
}
HINDI_DATE_RE = re.compile(
    rf"(?P<day>[0-9०-९]{{1,2}})\s+(?P<month>{'|'.join(map(re.escape, HINDI_MONTHS))})\s+"
    r"(?P<year>[0-9०-९]{4})"
)

CASE_TITLE_RE = re.compile(
    r"^(?P<left>[^\n]{2,140}?)\s+(?P<marker>v\.?|vs\.?|versus|बनाम|banam)\s+(?P<right>[^\n]{2,140}?)$",
    re.IGNORECASE | re.MULTILINE,
)

COURT_LINE_RE = re.compile(
    r"^(?P<court>[^\n]*(?:SUPREME\s+COURT|HIGH\s+COURT|DISTRICT\s+COURT|SESSIONS\s+COURT|"
    r"COURT\s+OF|TRIBUNAL|COMMISSION|न्यायालय|उच्च\s+न्यायालय|सर्वोच्च\s+न्यायालय)[^\n]*)$",
    re.IGNORECASE | re.MULTILINE,
)

JUDGE_RE = re.compile(
    r"^(?P<judge>[^\n]*(?:HON['’]?BLE\s+(?:MR\.?|MS\.?|MRS\.?)?\s*JUSTICE|JUSTICE\s+|"
    r"न्यायमूर्ति\s+|माननीय\s+न्यायमूर्ति\s+)[^\n]{2,120})$",
    re.IGNORECASE | re.MULTILINE,
)

ACT_RE = re.compile(
    r"\b(?P<act>(?:The\s+)?[A-Z][A-Za-z&(),.\-\s]{2,90}?\s+(?:Act|Code),?\s*(?:18|19|20)\d{2})\b"
    r"|(?P<hindi_act>(?:भारतीय|उत्तर\s+प्रदेश|मध्य\s+प्रदेश|राजस्थान|दिल्ली|महाराष्ट्र|केंद्रीय|केन्द्रीय)"
    r"[^\n,।]{1,90}?(?:अधिनियम|संहिता),?\s*[0-9०-९]{4})",
    re.IGNORECASE,
)

CITATION_PATTERNS = [
    re.compile(r"\(\d{4}\)\s*\d+\s*SCC\s*\d+", re.IGNORECASE),
    re.compile(r"\b\d{4}\s+SCC\s+OnLine\s+[A-Za-z]+\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bAIR\s+\d{4}\s+[A-Za-z]+\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b\d{4}\s+INSC\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b\d{4}:[A-Z]{2,12}:\d+\b"),
]

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _clean(value: str) -> str:
    return " ".join(value.split()).strip(" ,;:-")


def _dedupe(entities: list[ExtractedEntityData]) -> list[ExtractedEntityData]:
    seen: set[tuple[EntityType, str]] = set()
    result: list[ExtractedEntityData] = []
    for entity in entities:
        key = (entity.entity_type, (entity.normalized_value or entity.raw_text).casefold())
        if key in seen:
            continue
        seen.add(key)
        result.append(entity)
    return result


def _date_entity(raw: str, year: int, month: int, day: int, start: int, end: int) -> ExtractedEntityData | None:
    try:
        normalized = datetime(year, month, day).date().isoformat()
    except ValueError:
        return None
    return ExtractedEntityData(
        entity_type=EntityType.DATE,
        raw_text=raw,
        normalized_value=normalized,
        confidence=0.99,
        start_char=start,
        end_char=end,
    )


def extract_entities(text: str) -> list[ExtractedEntityData]:
    text = normalize_document_text(text)
    entities: list[ExtractedEntityData] = []

    for match in CNR_RE.finditer(text):
        value = match.group("cnr").upper()
        entities.append(
            ExtractedEntityData(
                EntityType.CNR_NUMBER,
                match.group(0),
                value,
                1.0,
                match.start(),
                match.end(),
            )
        )

    for pattern in CASE_NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            raw = _clean(match.group("case"))
            entities.append(
                ExtractedEntityData(
                    EntityType.CASE_NUMBER,
                    raw,
                    raw.upper(),
                    0.94,
                    match.start(),
                    match.end(),
                )
            )

    for match in NUMERIC_DATE_RE.finditer(text):
        entity = _date_entity(
            match.group(0),
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            match.start(),
            match.end(),
        )
        if entity:
            entities.append(entity)

    for match in ENGLISH_DATE_RE.finditer(text):
        month = datetime.strptime(match.group("month")[:3], "%b").month
        entity = _date_entity(
            match.group(0),
            int(match.group("year")),
            month,
            int(match.group("day")),
            match.start(),
            match.end(),
        )
        if entity:
            entities.append(entity)

    for match in HINDI_DATE_RE.finditer(text):
        day = int(match.group("day").translate(DEVANAGARI_DIGITS))
        year = int(match.group("year").translate(DEVANAGARI_DIGITS))
        entity = _date_entity(
            match.group(0),
            year,
            HINDI_MONTHS[match.group("month")],
            day,
            match.start(),
            match.end(),
        )
        if entity:
            entities.append(entity)

    for match in CASE_TITLE_RE.finditer(text):
        left = _clean(match.group("left"))
        right = _clean(match.group("right"))
        # Avoid interpreting very long prose lines as a case title.
        if not left or not right or len(left.split()) > 18 or len(right.split()) > 18:
            continue
        title = f"{left} v. {right}"
        entities.append(
            ExtractedEntityData(
                EntityType.CASE_TITLE,
                match.group(0),
                title,
                0.88,
                match.start(),
                match.end(),
                {"left_party": left, "right_party": right},
            )
        )
        entities.extend(
            [
                ExtractedEntityData(EntityType.PARTY, left, left, 0.86),
                ExtractedEntityData(EntityType.PARTY, right, right, 0.86),
            ]
        )

    for match in COURT_LINE_RE.finditer(text):
        court = _clean(match.group("court"))
        if 4 <= len(court) <= 220:
            entities.append(
                ExtractedEntityData(
                    EntityType.COURT,
                    court,
                    court,
                    0.88,
                    match.start(),
                    match.end(),
                )
            )

    for match in JUDGE_RE.finditer(text):
        judge = _clean(match.group("judge"))
        if 4 <= len(judge) <= 180:
            entities.append(
                ExtractedEntityData(
                    EntityType.JUDGE,
                    judge,
                    judge,
                    0.9,
                    match.start(),
                    match.end(),
                )
            )

    for match in ACT_RE.finditer(text):
        raw = _clean(match.group("act") or match.group("hindi_act") or "")
        if raw:
            entities.append(
                ExtractedEntityData(
                    EntityType.ACT,
                    raw,
                    raw,
                    0.88,
                    match.start(),
                    match.end(),
                )
            )

    for reference in extract_legal_references(text):
        start = text.casefold().find(reference.raw.casefold())
        entities.append(
            ExtractedEntityData(
                EntityType.STATUTE_REFERENCE,
                reference.raw,
                reference.canonical,
                0.99,
                start if start >= 0 else None,
                start + len(reference.raw) if start >= 0 else None,
                {"reference_type": reference.normalized_type, "number": reference.number},
            )
        )

    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(text):
            raw = _clean(match.group(0))
            entities.append(
                ExtractedEntityData(
                    EntityType.CITATION,
                    raw,
                    raw.upper(),
                    0.98,
                    match.start(),
                    match.end(),
                )
            )

    return _dedupe(entities)
