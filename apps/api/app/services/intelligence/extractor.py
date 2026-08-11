from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from app.models.intelligence import FactType, StatementKind
from app.services.documents.metadata import extract_entities
from app.models.document_entity import EntityType
from app.services.language.normalizer import normalize_document_text


@dataclass(frozen=True, slots=True)
class FactCandidate:
    fact_key: str
    fact_type: FactType
    category: str
    label: str
    value_text: str
    normalized_value: str
    confidence: float
    quote: str
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EventCandidate:
    event_key: str
    event_type: str
    event_date: date
    title: str
    description: str
    confidence: float
    quote: str
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StatementCandidate:
    kind: StatementKind
    speaker_role: str | None
    raw_text: str
    normalized_text: str
    confidence: float
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntelligenceExtraction:
    facts: tuple[FactCandidate, ...]
    events: tuple[EventCandidate, ...]
    statements: tuple[StatementCandidate, ...]


# Each event type deliberately needs multiple legal/action cues. This keeps the chronology useful
# and avoids turning every calendar date in a pleading into a timeline event.
EVENT_RULES: tuple[tuple[str, str, tuple[str, ...], float], ...] = (
    (
        "agreement_execution",
        "Agreement executed",
        (
            "agreement executed", "contract executed", "agreement was executed", "entered into agreement",
            "executed the agreement", "agreement dated", "समझौता निष्पादित", "अनुबंध निष्पादित",
            "समझौता किया गया", "agreement kiya gaya", "agreement execute", "samjhauta kiya",
        ),
        0.96,
    ),
    (
        "notice",
        "Notice issued / served",
        (
            "legal notice", "notice issued", "notice served", "notice was sent", "notice sent",
            "demand notice", "notice", "नोटिस जारी", "नोटिस भेजा", "नोटिस तामील", "कानूनी नोटिस",
            "notice bheja", "notice jari",
        ),
        0.93,
    ),
    (
        "payment",
        "Payment",
        (
            "payment made", "payment of", "paid a sum", "paid rs", "paid inr", "paid ₹", "amount paid",
            "transferred a sum", "payment was made", "भुगतान किया", "राशि अदा", "राशि जमा",
            "भुगतान प्राप्त", "payment kiya", "paise diye", "rashi jama",
        ),
        0.94,
    ),
    (
        "filing",
        "Filing",
        (
            "petition filed", "suit filed", "appeal filed", "application filed", "complaint filed",
            "was instituted", "was filed", "याचिका दायर", "वाद दायर", "अपील दायर", "आवेदन दायर",
            "शिकायत दायर", "yachika dair", "case file kiya",
        ),
        0.91,
    ),
    (
        "order",
        "Court order",
        (
            "order dated", "order passed", "court ordered", "ordered that", "आदेश दिनांक",
            "आदेश पारित", "न्यायालय ने आदेश", "order pass hua",
        ),
        0.92,
    ),
    (
        "judgment",
        "Judgment",
        (
            "judgment dated", "judgment delivered", "judgment pronounced", "decision pronounced",
            "निर्णय दिनांक", "निर्णय सुनाया", "फैसला सुनाया", "judgment sunaya",
        ),
        0.93,
    ),
    (
        "hearing",
        "Hearing",
        (
            "hearing on", "listed on", "listed for hearing", "next date", "next hearing",
            "सुनवाई", "अगली तारीख", "hearing date", "agli tareekh",
        ),
        0.88,
    ),
    (
        "fir_registration",
        "FIR registered",
        (
            "fir registered", "fir was registered", "fir lodged", "first information report registered",
            "एफआईआर दर्ज", "प्राथमिकी दर्ज", "f.i.r. registered", "fir darj",
        ),
        0.97,
    ),
    (
        "arrest",
        "Arrest",
        (
            "was arrested", "arrested on", "taken into custody", "गिरफ्तार किया", "गिरफ्तारी हुई",
            "गिरफ्तार हुआ", "arrest hua",
        ),
        0.96,
    ),
    (
        "termination",
        "Termination",
        (
            "terminated on", "termination dated", "services terminated", "employment terminated",
            "agreement terminated", "सेवा समाप्त", "सेवाएं समाप्त", "अनुबंध समाप्त",
            "नियुक्ति समाप्त", "terminate kiya",
        ),
        0.96,
    ),
    (
        "possession",
        "Possession",
        (
            "possession handed over", "possession delivered", "took possession", "given possession",
            "कब्जा सौंपा", "कब्जा दिया", "कब्जा लिया", "possession diya", "kabza diya",
        ),
        0.93,
    ),
    (
        "registration",
        "Registration",
        (
            "deed registered", "agreement registered", "registered deed", "registration completed",
            "विलेख पंजीकृत", "दस्तावेज पंजीकृत", "रजिस्ट्री हुई", "registry hui",
        ),
        0.93,
    ),
    (
        "delivery",
        "Delivery",
        (
            "goods delivered", "delivered on", "delivery made", "माल सुपुर्द", "सामान दिया",
            "delivery ki", "maal diya",
        ),
        0.89,
    ),
)

STATEMENT_RULES: tuple[tuple[StatementKind, tuple[str, ...], float], ...] = (
    (
        StatementKind.ADMISSION,
        (
            "admits that", "admitted that", "admits having", "it is admitted", "has admitted",
            "स्वीकार करता है कि", "स्वीकार किया कि", "यह स्वीकार है", "कबूल किया कि",
            "sweekar karta hai", "maan liya ki", "admit karta hai",
        ),
        0.95,
    ),
    (
        StatementKind.DENIAL,
        (
            "denies that", "denied that", "specifically denies", "is denied", "has denied",
            "इंकार करता है", "इनकार करता है", "नकारता है", "अस्वीकार करता है", "से इंकार",
            "inkar karta hai", "deny karta hai",
        ),
        0.94,
    ),
    (
        StatementKind.CLAIM,
        (
            "submits that", "submitted that", "states that", "stated that", "alleges that",
            "asserts that", "contends that", "pleads that", "avers that", "claims that",
            "निवेदन करता है कि", "कहता है कि", "कथन है कि", "आरोप लगाता है", "दावा करता है कि",
            "kahta hai ki", "dawa karta hai", "submit karta hai",
        ),
        0.88,
    ),
)

SPEAKER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("petitioner", ("petitioner", "याचिकाकर्ता", "applicant", "आवेदक")),
    ("respondent", ("respondent", "प्रतिवादी")),
    ("plaintiff", ("plaintiff", "वादी")),
    ("defendant", ("defendant", "प्रतिवादी")),
    ("complainant", ("complainant", "शिकायतकर्ता")),
    ("accused", ("accused", "अभियुक्त", "आरोपी")),
)

CONTRACT_AMOUNT_CUES = (
    "total consideration", "sale consideration", "contract value", "purchase price", "agreed price",
    "total contract price", "प्रतिफल", "कुल कीमत", "विक्रय मूल्य", "समझौता राशि", "अनुबंध राशि",
    "contract amount", "total amount",
)

CLAIM_AMOUNT_CUES = (
    "claim amount", "claimed a sum", "claims a sum", "amount claimed", "demanded a sum",
    "दावा राशि", "राशि का दावा", "मांग की राशि",
)

PAYMENT_AMOUNT_CUES = (
    "payment", "paid", "transferred", "भुगतान", "अदा", "जमा", "pay kiya", "paise diye",
)

MONEY_RE = re.compile(
    r"(?:(?P<prefix>₹|rs\.?|inr|रु\.?|रुपये|रुपए)\s*)?"
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>crores?|cr\.?|lakhs?|lacs?|lakh|thousand|करोड़|करोड़|लाख|हजार)?"
    r"\s*(?P<suffix>rupees|रुपये|रुपए)?",
    re.IGNORECASE,
)

# Standalone numbers are not money. At least currency marker, a money unit, or strong amount context is needed.
MONEY_UNITS = {
    "crore": Decimal("10000000"), "crores": Decimal("10000000"), "cr": Decimal("10000000"), "cr.": Decimal("10000000"),
    "lakh": Decimal("100000"), "lakhs": Decimal("100000"), "lac": Decimal("100000"), "lacs": Decimal("100000"),
    "thousand": Decimal("1000"), "करोड़": Decimal("10000000"), "करोड़": Decimal("10000000"),
    "लाख": Decimal("100000"), "हजार": Decimal("1000"),
}

EVENT_SINGLE_VALUE_KEYS = {
    "agreement_execution",
    "fir_registration",
    "arrest",
    "termination",
    "possession",
    "registration",
}


def _normalize_space(value: str) -> str:
    return " ".join(value.split()).strip()


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    start = 0
    # Legal documents often use line-separated numbered paragraphs, so newline is an intentional boundary.
    for match in re.finditer(r"(?<=[.!?।])\s+|\n+", text):
        chunk = text[start:match.start()].strip()
        if chunk:
            left_trim = len(text[start:match.start()]) - len(text[start:match.start()].lstrip())
            s = start + left_trim
            spans.append((chunk, s, s + len(chunk)))
        start = match.end()
    tail = text[start:].strip()
    if tail:
        left_trim = len(text[start:]) - len(text[start:].lstrip())
        s = start + left_trim
        spans.append((tail, s, s + len(tail)))
    return spans


def _stable_excerpt_key(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text.casefold())
    normalized = _normalize_space(normalized)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _contains_any(text: str, cues: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return any(cue.casefold() in folded for cue in cues)


def _event_rule(sentence: str) -> tuple[str, str, float] | None:
    for event_type, title, cues, confidence in EVENT_RULES:
        if _contains_any(sentence, cues):
            return event_type, title, confidence
    return None


def _speaker_role(sentence: str) -> str | None:
    folded = sentence.casefold()
    # Prefer a role in the first half of the sentence, where the grammatical subject usually appears.
    prefix = folded[: max(80, len(folded) // 2)]
    for role, cues in SPEAKER_RULES:
        if any(cue.casefold() in prefix for cue in cues):
            return role
    return None


def _money_matches(sentence: str) -> list[tuple[str, Decimal, int, int]]:
    results: list[tuple[str, Decimal, int, int]] = []
    folded = sentence.casefold()
    for match in MONEY_RE.finditer(sentence):
        prefix = (match.group("prefix") or "").casefold().rstrip(".")
        unit = (match.group("unit") or "").casefold()
        suffix = (match.group("suffix") or "").casefold()
        if not prefix and not unit and not suffix:
            continue
        # Years/dates in a money-context sentence should not accidentally become rupee amounts.
        raw_number = match.group("number").replace(",", "")
        try:
            value = Decimal(raw_number)
        except InvalidOperation:
            continue
        multiplier = MONEY_UNITS.get(unit.rstrip("."), Decimal("1"))
        value *= multiplier
        if value <= 0:
            continue
        results.append((_normalize_space(match.group(0)), value, match.start(), match.end()))
    return results


def _money_category(sentence: str) -> tuple[str, str, float]:
    if _contains_any(sentence, CONTRACT_AMOUNT_CUES):
        return "contract_amount", "Contract / consideration amount", 0.94
    if _contains_any(sentence, CLAIM_AMOUNT_CUES):
        return "claim_amount", "Claim amount", 0.90
    if _contains_any(sentence, PAYMENT_AMOUNT_CUES):
        return "payment_amount", "Payment amount", 0.92
    return "money_amount", "Monetary amount", 0.78


def _decimal_to_rupees(value: Decimal) -> str:
    # Stable canonical form used for equality/contradiction checks.
    quantized = value.quantize(Decimal("0.01"))
    text = format(quantized, "f")
    if text.endswith(".00"):
        text = text[:-3]
    return text


def _date_candidates(sentence: str) -> list[tuple[date, str, int | None, int | None]]:
    result: list[tuple[date, str, int | None, int | None]] = []
    for entity in extract_entities(sentence):
        if entity.entity_type != EntityType.DATE or not entity.normalized_value:
            continue
        try:
            parsed = date.fromisoformat(entity.normalized_value)
        except ValueError:
            continue
        result.append((parsed, entity.raw_text, entity.start_char, entity.end_char))
    return result


def _event_fact_key(event_type: str, sentence: str) -> str:
    if event_type == "payment":
        amounts = _money_matches(sentence)
        if amounts:
            return f"payment_date:{_decimal_to_rupees(amounts[0][1])}"
        # No amount means repeat payments cannot safely be compared as one fact.
        return f"payment_date:{_stable_excerpt_key(sentence)}"
    if event_type in EVENT_SINGLE_VALUE_KEYS:
        return f"{event_type}_date"
    return f"{event_type}_date:{_stable_excerpt_key(sentence)}"


def extract_intelligence(text: str) -> IntelligenceExtraction:
    normalized_text = normalize_document_text(text)
    facts: list[FactCandidate] = []
    events: list[EventCandidate] = []
    statements: list[StatementCandidate] = []

    seen_facts: set[tuple[str, str, int | None]] = set()
    seen_events: set[str] = set()
    seen_statements: set[tuple[StatementKind, str]] = set()

    for sentence, sentence_start, sentence_end in _sentence_spans(normalized_text):
        compact = _normalize_space(sentence)
        if len(compact) < 4:
            continue

        dates = _date_candidates(compact)
        rule = _event_rule(compact)
        if rule and dates:
            event_type, title, base_confidence = rule
            for event_date, raw_date, local_start, local_end in dates:
                fact_key = _event_fact_key(event_type, compact)
                global_start = sentence_start + local_start if local_start is not None else sentence_start
                global_end = sentence_start + local_end if local_end is not None else sentence_end
                fact_identity = (fact_key, event_date.isoformat(), sentence_start)
                if fact_identity not in seen_facts:
                    seen_facts.add(fact_identity)
                    facts.append(
                        FactCandidate(
                            fact_key=fact_key,
                            fact_type=FactType.DATE,
                            category=f"{event_type}_date",
                            label=f"{title} date",
                            value_text=raw_date,
                            normalized_value=event_date.isoformat(),
                            confidence=base_confidence,
                            quote=compact,
                            start_char=global_start,
                            end_char=global_end,
                            metadata={"event_type": event_type},
                        )
                    )

                event_key = f"{event_type}:{event_date.isoformat()}:{_stable_excerpt_key(compact)}"
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    events.append(
                        EventCandidate(
                            event_key=event_key,
                            event_type=event_type,
                            event_date=event_date,
                            title=title,
                            description=compact,
                            confidence=base_confidence,
                            quote=compact,
                            start_char=sentence_start,
                            end_char=sentence_end,
                            metadata={},
                        )
                    )

        for raw_money, rupees, local_start, local_end in _money_matches(compact):
            category, label, confidence = _money_category(compact)
            normalized_amount = _decimal_to_rupees(rupees)
            # Only categories with semantic context get a shared key. Generic money stays source-specific.
            if category == "contract_amount":
                fact_key = "contract_amount"
            elif category == "claim_amount":
                fact_key = "claim_amount"
            elif category == "payment_amount":
                # Different payments can coexist, so sentence fingerprint avoids false contradictions.
                fact_key = f"payment_amount:{_stable_excerpt_key(compact)}"
            else:
                fact_key = f"money_amount:{_stable_excerpt_key(compact)}:{local_start}"

            identity = (fact_key, normalized_amount, sentence_start + local_start)
            if identity in seen_facts:
                continue
            seen_facts.add(identity)
            facts.append(
                FactCandidate(
                    fact_key=fact_key,
                    fact_type=FactType.MONEY,
                    category=category,
                    label=label,
                    value_text=raw_money,
                    normalized_value=normalized_amount,
                    confidence=confidence,
                    quote=compact,
                    start_char=sentence_start + local_start,
                    end_char=sentence_start + local_end,
                    metadata={"currency": "INR", "amount_rupees": normalized_amount},
                )
            )

        folded = compact.casefold()
        for kind, cues, confidence in STATEMENT_RULES:
            cue = next((cue for cue in cues if cue.casefold() in folded), None)
            if cue is None:
                continue
            normalized_statement = _normalize_space(compact).casefold()
            statement_key = (kind, normalized_statement)
            if statement_key in seen_statements:
                break
            seen_statements.add(statement_key)
            statements.append(
                StatementCandidate(
                    kind=kind,
                    speaker_role=_speaker_role(compact),
                    raw_text=compact,
                    normalized_text=normalized_statement,
                    confidence=confidence,
                    start_char=sentence_start,
                    end_char=sentence_end,
                    metadata={"matched_cue": cue},
                )
            )
            break

    return IntelligenceExtraction(
        facts=tuple(facts),
        events=tuple(events),
        statements=tuple(statements),
    )
