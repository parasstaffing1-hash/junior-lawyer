from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.tools.contract_clause_extractor.models import (
    ClauseExtractRequest,
    ClauseExtractResponse,
    ClauseExtractSummary,
    ClauseSignal,
    ClauseType,
    ClauseTypesResponse,
    ExtractedClause,
    MatchBasis,
    SupportedClauseType,
)


DISCLAIMER = (
    "This deterministic utility identifies supported clause patterns from supplied text. "
    "It does not determine legal meaning, materiality, enforceability, risk, completeness, "
    "or whether a clause satisfies any jurisdiction-specific requirement."
)


class ContractClauseExtractorError(ValueError):
    pass


@dataclass(frozen=True)
class ClauseRule:
    headings: tuple[str, ...]
    body_patterns: tuple[str, ...]


RULES: dict[ClauseType, ClauseRule] = {
    ClauseType.CONFIDENTIALITY: ClauseRule(
        headings=("confidentiality", "confidential information", "non-disclosure", "nondisclosure"),
        body_patterns=(
            r"\bconfidential information\b",
            r"\bkeep(?:s|ing)?\b.{0,80}\bconfidential\b",
            r"\bnon[- ]disclosure\b",
            r"\bshall not disclose\b",
        ),
    ),
    ClauseType.TERMINATION: ClauseRule(
        headings=("termination", "termination rights", "termination for cause", "termination for convenience"),
        body_patterns=(
            r"\bterminat(?:e|es|ed|ing|ion)\b",
            r"\bnotice of termination\b",
            r"\bterminate this agreement\b",
            r"\bupon termination\b",
        ),
    ),
    ClauseType.INDEMNITY: ClauseRule(
        headings=("indemnity", "indemnification", "indemnities"),
        body_patterns=(
            r"\bindemnif(?:y|ies|ied|ication)\b",
            r"\bhold harmless\b",
            r"\bdefend(?:s|ed|ing)?\b.{0,80}\bclaims?\b",
        ),
    ),
    ClauseType.LIMITATION_OF_LIABILITY: ClauseRule(
        headings=("limitation of liability", "limitations of liability", "liability cap", "limited liability"),
        body_patterns=(
            r"\blimitation of liability\b",
            r"\bliabilit(?:y|ies)\b.{0,120}\b(?:limited|cap|maximum|aggregate)\b",
            r"\bnot be liable\b.{0,120}\b(?:indirect|consequential|special|punitive)\b",
            r"\baggregate liability\b",
        ),
    ),
    ClauseType.GOVERNING_LAW: ClauseRule(
        headings=("governing law", "applicable law", "choice of law"),
        body_patterns=(
            r"\bgoverned by(?: and construed in accordance with)? the laws? of\b",
            r"\bgoverning law\b",
            r"\blaws? of .{1,80} shall govern\b",
        ),
    ),
    ClauseType.DISPUTE_RESOLUTION: ClauseRule(
        headings=("dispute resolution", "arbitration", "jurisdiction", "disputes"),
        body_patterns=(
            r"\barbitrat(?:ion|e|ed)\b",
            r"\bexclusive jurisdiction\b",
            r"\bsubmit(?:s|ted)? to the jurisdiction\b",
            r"\bdispute(?:s)?\b.{0,100}\b(?:court|arbitration|mediation)\b",
        ),
    ),
    ClauseType.PAYMENT: ClauseRule(
        headings=("payment", "payment terms", "fees", "charges", "compensation"),
        body_patterns=(
            r"\bpayment terms\b",
            r"\b(?:invoice|invoices)\b.{0,100}\b(?:payable|payment|due)\b",
            r"\bshall pay\b",
            r"\bdue and payable\b",
        ),
    ),
    ClauseType.TERM_RENEWAL: ClauseRule(
        headings=("term", "term and renewal", "renewal", "duration"),
        body_patterns=(
            r"\binitial term\b",
            r"\brenew(?:al|ed|s)?\b",
            r"\bterm of this agreement\b",
            r"\bexpire(?:s|d|ation)?\b",
        ),
    ),
    ClauseType.INTELLECTUAL_PROPERTY: ClauseRule(
        headings=("intellectual property", "intellectual property rights", "ownership", "ip rights"),
        body_patterns=(
            r"\bintellectual property(?: rights)?\b",
            r"\bcopyrights?\b",
            r"\btrademarks?\b",
            r"\bpatents?\b",
            r"\bownership of .{0,80}(?:work product|deliverables|materials)\b",
        ),
    ),
    ClauseType.DATA_PROTECTION: ClauseRule(
        headings=("data protection", "privacy", "personal data", "data processing"),
        body_patterns=(
            r"\bpersonal data\b",
            r"\bdata protection\b",
            r"\bprivacy laws?\b",
            r"\bdata processor\b",
            r"\bdata controller\b",
        ),
    ),
    ClauseType.FORCE_MAJEURE: ClauseRule(
        headings=("force majeure", "events beyond control"),
        body_patterns=(
            r"\bforce majeure\b",
            r"\bbeyond (?:the )?reasonable control\b",
            r"\bacts? of god\b",
            r"\bwar,? riot,? (?:or )?civil unrest\b",
        ),
    ),
    ClauseType.NON_COMPETE: ClauseRule(
        headings=("non-compete", "non compete", "restrictive covenant", "non-solicitation", "non solicitation"),
        body_patterns=(
            r"\bnon[- ]compete\b",
            r"\bnon[- ]solicitation\b",
            r"\bshall not compete\b",
            r"\bshall not solicit\b",
        ),
    ),
    ClauseType.ASSIGNMENT: ClauseRule(
        headings=("assignment", "assignments"),
        body_patterns=(
            r"\bassign(?:ment|s|ed|ing)?\b.{0,100}\b(?:consent|agreement|rights|obligations)\b",
            r"\bmay not assign\b",
            r"\bshall not assign\b",
        ),
    ),
    ClauseType.NOTICES: ClauseRule(
        headings=("notices", "notice"),
        body_patterns=(
            r"\ball notices\b.{0,120}\b(?:writing|delivered|address)\b",
            r"\bnotice shall be\b",
            r"\bdeemed received\b",
        ),
    ),
    ClauseType.WARRANTIES: ClauseRule(
        headings=("warranties", "warranty", "warranty disclaimer"),
        body_patterns=(
            r"\bwarrant(?:y|ies|s|ed)\b",
            r"\bas is\b.{0,80}\bwarrant(?:y|ies)\b",
            r"\bdisclaims? all warranties\b",
        ),
    ),
    ClauseType.REPRESENTATIONS: ClauseRule(
        headings=("representations", "representations and warranties"),
        body_patterns=(
            r"\brepresents? and warrants?\b",
            r"\brepresentation(?:s)?\b",
            r"\bauthority to enter into\b",
        ),
    ),
    ClauseType.INSURANCE: ClauseRule(
        headings=("insurance", "insurance requirements"),
        body_patterns=(
            r"\bmaintain(?:s|ed|ing)? insurance\b",
            r"\binsurance coverage\b",
            r"\bcertificate of insurance\b",
        ),
    ),
    ClauseType.AUDIT: ClauseRule(
        headings=("audit", "audit rights", "records and audit"),
        body_patterns=(
            r"\baudit rights?\b",
            r"\bright to audit\b",
            r"\binspect(?:ion)? of (?:books|records)\b",
            r"\bbooks and records\b",
        ),
    ),
    ClauseType.COMPLIANCE: ClauseRule(
        headings=("compliance", "compliance with laws", "legal compliance"),
        body_patterns=(
            r"\bcomply with all applicable laws\b",
            r"\bcompliance with laws\b",
            r"\bapplicable laws and regulations\b",
        ),
    ),
}


COMPILED_BODY: dict[ClauseType, tuple[re.Pattern[str], ...]] = {
    clause_type: tuple(re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in rule.body_patterns)
    for clause_type, rule in RULES.items()
}

_NUMBER_PREFIX = re.compile(
    r"^\s*(?:(?:section|article|clause)\s+)?(?:\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])(?:[.)\-:]|\s+-)?\s+",
    re.IGNORECASE,
)
_SECTION_WORD_PREFIX = re.compile(r"^\s*(?:section|article|clause)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Section:
    start: int
    end: int
    heading: str | None
    normalized_heading: str | None
    text: str


def _normalize_heading(value: str) -> str:
    text = " ".join(value.strip().split())
    text = _NUMBER_PREFIX.sub("", text)
    text = _SECTION_WORD_PREFIX.sub("", text)
    text = text.strip(" .:-–—\t")
    return " ".join(text.split()).casefold()


def _looks_like_heading(line: str) -> bool:
    stripped = " ".join(line.strip().split())
    if not stripped or len(stripped) > 160:
        return False
    if stripped.endswith((".", "?", "!", ";")):
        return False
    words = stripped.split()
    if len(words) > 14:
        return False

    if re.match(r"^\s*(?:section|article|clause)\s+", stripped, re.IGNORECASE):
        return True
    if re.match(r"^\s*(?:\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])(?:[.)\-:]|\s+-)\s+", stripped, re.IGNORECASE):
        return True

    letters = [char for char in stripped if char.isalpha()]
    if letters:
        upper_ratio = sum(char.isupper() for char in letters) / len(letters)
        if upper_ratio >= 0.80 and len(words) <= 10:
            return True

    normalized = _normalize_heading(stripped)
    known_terms = {term.casefold() for rule in RULES.values() for term in rule.headings}
    if any(normalized == term or term in normalized for term in known_terms):
        return True

    if len(words) <= 8:
        title_like = sum(word[:1].isupper() for word in words if word[:1].isalpha())
        alpha_words = sum(1 for word in words if word[:1].isalpha())
        if alpha_words and title_like / alpha_words >= 0.80:
            return True
    return False


def _line_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        spans.append((offset, end, line))
        offset = end
    if offset < len(text):
        spans.append((offset, len(text), text[offset:]))
    if not spans and text:
        spans.append((0, len(text), text))
    return spans


def _sections(text: str) -> list[Section]:
    lines = _line_spans(text)
    heading_lines: list[tuple[int, int, str]] = []
    for start, end, line in lines:
        candidate = line.rstrip("\r\n")
        if _looks_like_heading(candidate):
            heading_lines.append((start, end, candidate.strip()))

    if not heading_lines:
        return []

    result: list[Section] = []
    for index, (start, _line_end, heading) in enumerate(heading_lines):
        end = heading_lines[index + 1][0] if index + 1 < len(heading_lines) else len(text)
        section_text = text[start:end].rstrip()
        if not section_text.strip():
            continue
        result.append(
            Section(
                start=start,
                end=start + len(section_text),
                heading=heading,
                normalized_heading=_normalize_heading(heading),
                text=section_text,
            )
        )
    return result


def _paragraphs(text: str) -> list[Section]:
    result: list[Section] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=(?:\r?\n){2,}|\Z)", text, re.DOTALL):
        raw = match.group(0)
        if not raw.strip():
            continue
        result.append(
            Section(
                start=match.start(),
                end=match.end(),
                heading=None,
                normalized_heading=None,
                text=raw,
            )
        )
    return result


def _heading_score(normalized_heading: str | None, rule: ClauseRule) -> tuple[float, list[ClauseSignal]]:
    if not normalized_heading:
        return 0.0, []
    signals: list[ClauseSignal] = []
    best = 0.0
    for term in rule.headings:
        normalized_term = term.casefold()
        if normalized_heading == normalized_term:
            best = max(best, 0.99)
            signals.append(ClauseSignal(kind="heading_exact", value=term))
        elif normalized_term in normalized_heading:
            best = max(best, 0.92)
            signals.append(ClauseSignal(kind="heading_contains", value=term))
    return best, signals


def _body_score(text: str, clause_type: ClauseType) -> tuple[float, list[ClauseSignal]]:
    hits: list[ClauseSignal] = []
    for pattern, raw_pattern in zip(COMPILED_BODY[clause_type], RULES[clause_type].body_patterns, strict=True):
        if pattern.search(text):
            hits.append(ClauseSignal(kind="body_pattern", value=raw_pattern))
    if not hits:
        return 0.0, []
    score = 0.60 if len(hits) == 1 else 0.72 if len(hits) == 2 else 0.82
    return score, hits


def _line_column(text: str, start: int) -> tuple[int, int]:
    line = text.count("\n", 0, start) + 1
    last_newline = text.rfind("\n", 0, start)
    column = start + 1 if last_newline == -1 else start - last_newline
    return line, column


def _classify(section: Section, clause_type: ClauseType, full_text: str, include_heading: bool) -> ExtractedClause | None:
    rule = RULES[clause_type]
    heading_score, heading_signals = _heading_score(section.normalized_heading, rule)
    body_for_matching = section.text
    if section.heading and body_for_matching.startswith(section.heading):
        body_for_matching = body_for_matching[len(section.heading):]
    body_score, body_signals = _body_score(body_for_matching, clause_type)

    if heading_score and body_score:
        confidence = min(0.995, max(heading_score, 0.94 + min(0.05, 0.01 * len(body_signals))))
        basis = MatchBasis.HEADING_AND_BODY
    elif heading_score:
        confidence = heading_score
        basis = MatchBasis.HEADING
    elif body_score:
        confidence = body_score
        basis = MatchBasis.BODY
    else:
        return None

    output_start = section.start
    output_text = section.text
    if section.heading and not include_heading:
        relative = section.text.find(section.heading)
        after = relative + len(section.heading)
        remainder = section.text[after:].lstrip("\r\n \t")
        removed = len(section.text[after:]) - len(remainder)
        output_start = section.start + after + removed
        output_text = remainder

    if not output_text.strip():
        output_text = section.text
        output_start = section.start
    output_end = output_start + len(output_text)
    line, column = _line_column(full_text, output_start)

    return ExtractedClause(
        clause_type=clause_type,
        confidence=round(confidence, 3),
        match_basis=basis,
        heading=section.heading,
        normalized_heading=section.normalized_heading,
        text=output_text,
        start=output_start,
        end=output_end,
        line=line,
        column=column,
        signals=heading_signals + body_signals,
    )


def list_supported_clause_types() -> ClauseTypesResponse:
    return ClauseTypesResponse(
        clause_types=[
            SupportedClauseType(
                clause_type=clause_type,
                heading_terms=list(rule.headings),
                body_pattern_count=len(rule.body_patterns),
            )
            for clause_type, rule in RULES.items()
        ],
        disclaimer=DISCLAIMER,
    )


def extract_contract_clauses(payload: ClauseExtractRequest) -> ClauseExtractResponse:
    text = payload.text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ContractClauseExtractorError("text must contain non-whitespace characters")

    options = payload.options
    clause_types = options.clause_types or list(ClauseType)
    detected_sections = _sections(text)
    warnings: list[str] = []

    if detected_sections:
        source_sections = detected_sections
    elif options.use_body_fallback:
        source_sections = _paragraphs(text)
        warnings.append("No clause headings were detected; body-pattern paragraph fallback was used.")
    else:
        source_sections = []
        warnings.append("No clause headings were detected and body fallback is disabled.")

    matches: list[ExtractedClause] = []
    for section in source_sections:
        for clause_type in clause_types:
            item = _classify(section, clause_type, text, options.include_heading_in_text)
            if item is None or item.confidence < options.minimum_confidence:
                continue
            # Paragraph fallback should never masquerade as a heading-based match.
            if section.heading is None and item.match_basis != MatchBasis.BODY:
                continue
            matches.append(item)

    matches.sort(key=lambda item: (item.start, -item.confidence, item.clause_type.value))

    if options.deduplicate:
        deduped: list[ExtractedClause] = []
        seen: set[tuple[ClauseType, int, int]] = set()
        for item in matches:
            key = (item.clause_type, item.start, item.end)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        matches = deduped

    if len(matches) > options.max_results:
        warnings.append(f"Result limit reached; returned the first {options.max_results} matches.")
        matches = matches[: options.max_results]

    if not matches:
        warnings.append("No supported clause pattern met the configured confidence threshold.")

    counts = Counter(item.clause_type.value for item in matches)
    basis_counts = Counter(item.match_basis.value for item in matches)
    summary = ClauseExtractSummary(
        sections_detected=len(detected_sections),
        clauses_returned=len(matches),
        clause_type_counts=dict(sorted(counts.items())),
        heading_based=basis_counts.get(MatchBasis.HEADING.value, 0),
        body_based=basis_counts.get(MatchBasis.BODY.value, 0),
        heading_and_body=basis_counts.get(MatchBasis.HEADING_AND_BODY.value, 0),
    )
    return ClauseExtractResponse(
        matches=matches,
        summary=summary,
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
