from __future__ import annotations

import calendar
import re
from collections import Counter
from datetime import date

from app.tools.key_dates_obligations.models import (
    DateKind,
    DateRelation,
    ExtractedDate,
    ExtractedObligation,
    ExtractionSignal,
    ExtractionSummary,
    ExtractRequest,
    ExtractResponse,
    Frequency,
    ObligationType,
    RelativeUnit,
    SupportedPatternsResponse,
)


DISCLAIMER = (
    "This deterministic utility identifies supported date expressions and obligation wording in supplied text. "
    "It does not determine legal effect, calculate jurisdiction-specific deadlines, resolve ambiguous dates, "
    "or decide whether an obligation is enforceable, satisfied, waived, material, or complete."
)


MONTHS = {name.casefold(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.casefold(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTH_PATTERN = "|".join(sorted((re.escape(x) for x in MONTHS), key=len, reverse=True))

ABSOLUTE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "iso",
        re.compile(r"(?<!\d)(?P<year>20\d{2}|19\d{2})-(?P<month>0?[1-9]|1[0-2])-(?P<day>0?[1-9]|[12]\d|3[01])(?!\d)"),
    ),
    (
        "day_month_year",
        re.compile(
            rf"(?<!\w)(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+(?P<month_name>{MONTH_PATTERN})\.?[,]?\s+(?P<year>20\d{{2}}|19\d{{2}})(?!\d)",
            re.IGNORECASE,
        ),
    ),
    (
        "month_day_year",
        re.compile(
            rf"(?<!\w)(?P<month_name>{MONTH_PATTERN})\.?\s+(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?[,]?\s+(?P<year>20\d{{2}}|19\d{{2}})(?!\d)",
            re.IGNORECASE,
        ),
    ),
)

RELATIVE_PATTERN = re.compile(
    r"\b(?P<relation>within|at least|no later than|not later than|by)\s+"
    r"(?P<value>\d{1,4})\s+"
    r"(?P<unit>business\s+days?|working\s+days?|days?|weeks?|months?|years?)\s+"
    r"(?P<direction>before|after|from)\s+"
    r"(?P<anchor>[^.;\n]{1,120})",
    re.IGNORECASE,
)

SIMPLE_RELATIVE_PATTERN = re.compile(
    r"\b(?P<value>\d{1,4})\s+"
    r"(?P<unit>business\s+days?|working\s+days?|days?|weeks?|months?|years?)\s+"
    r"(?P<direction>before|after|from)\s+"
    r"(?P<anchor>[^.;\n]{1,120})",
    re.IGNORECASE,
)

DATE_KIND_RULES: tuple[tuple[DateKind, tuple[str, ...]], ...] = (
    (DateKind.EFFECTIVE, ("effective", "effective date")),
    (DateKind.EXECUTION, ("executed", "execution", "signed", "signature date")),
    (DateKind.COMMENCEMENT, ("commence", "commencement", "start date", "begins", "begin on")),
    (DateKind.EXPIRY, ("expire", "expiry", "expiration", "end date", "ends on")),
    (DateKind.RENEWAL, ("renew", "renewal")),
    (DateKind.PAYMENT_DUE, ("payment", "invoice", "payable", "due")),
    (DateKind.NOTICE_DEADLINE, ("notice", "notify", "notification")),
    (DateKind.TERMINATION, ("terminate", "termination")),
    (DateKind.DELIVERY, ("deliver", "delivery", "ship", "shipment")),
    (DateKind.REPORTING, ("report", "reporting", "statement", "certificate")),
)

OBLIGATION_RULES: tuple[tuple[ObligationType, tuple[str, ...]], ...] = (
    (ObligationType.PAYMENT, ("pay", "payment", "invoice", "fee", "amount due")),
    (ObligationType.NOTICE, ("notice", "notify", "notification")),
    (ObligationType.DELIVERY, ("deliver", "delivery", "provide", "supply", "submit")),
    (ObligationType.REPORTING, ("report", "statement", "certificate", "records")),
    (ObligationType.INSURANCE, ("insurance", "insured", "coverage", "policy")),
    (ObligationType.CONFIDENTIALITY, ("confidential", "non-disclosure", "nondisclosure", "disclose")),
    (ObligationType.RENEWAL, ("renew", "renewal", "extend the term")),
    (ObligationType.AUDIT, ("audit", "inspect books", "inspect records")),
    (ObligationType.COMPLIANCE, ("comply", "compliance", "applicable law", "regulation")),
    (ObligationType.PERFORMANCE, ("perform", "services", "obligations", "complete", "maintain")),
)

OBLIGATION_MARKER = re.compile(
    r"\b(?P<marker>shall|must|is required to|are required to|agrees to|undertakes to|will)\b",
    re.IGNORECASE,
)


class KeyDatesObligationsError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_break = text.rfind("\n", 0, offset)
    column = offset + 1 if last_break < 0 else offset - last_break
    return line, column


def _context(text: str, start: int, end: int, chars: int) -> str:
    left = max(0, start - chars)
    right = min(len(text), end + chars)
    return " ".join(text[left:right].split())


def _parse_absolute(match: re.Match[str]) -> date | None:
    try:
        year = int(match.group("year"))
        day = int(match.group("day"))
        month_raw = match.groupdict().get("month")
        month_name = match.groupdict().get("month_name")
        month = int(month_raw) if month_raw else MONTHS[month_name.casefold().rstrip(".")]
        return date(year, month, day)
    except (ValueError, KeyError, AttributeError):
        return None


def _classify_date_near(
    text: str, start: int, end: int, chars: int
) -> tuple[str, DateKind, list[ExtractionSignal]]:
    left = max(0, start - chars)
    right = min(len(text), end + chars)
    raw_context = text[left:right]
    folded = raw_context.casefold()
    target_mid = ((start + end) / 2) - left
    candidates: list[tuple[float, int, DateKind, str]] = []
    priority = {
        DateKind.PAYMENT_DUE: 100,
        DateKind.NOTICE_DEADLINE: 95,
        DateKind.TERMINATION: 90,
        DateKind.RENEWAL: 85,
        DateKind.EXPIRY: 80,
        DateKind.EFFECTIVE: 75,
        DateKind.COMMENCEMENT: 70,
        DateKind.EXECUTION: 65,
        DateKind.DELIVERY: 60,
        DateKind.REPORTING: 55,
    }
    for kind, terms in DATE_KIND_RULES:
        for term in terms:
            needle = term.casefold()
            offset = 0
            while True:
                found = folded.find(needle, offset)
                if found < 0:
                    break
                term_mid = found + len(needle) / 2
                absolute_found = left + found
                absolute_term_end = absolute_found + len(needle)
                if absolute_term_end <= start:
                    side_rank = 0
                    distance = start - absolute_term_end
                elif absolute_found >= end:
                    side_rank = 2
                    distance = absolute_found - end
                else:
                    side_rank = 1
                    distance = abs(term_mid - target_mid)
                candidates.append((side_rank, distance, -priority[kind], kind, term))
                offset = found + 1

    context = " ".join(raw_context.split())
    if not candidates:
        return context, DateKind.OTHER, []
    _side, _distance, _priority, kind, term = min(candidates, key=lambda item: (item[0], item[1], item[2]))
    return context, kind, [ExtractionSignal(kind="nearest_keyword", value=term)]


def _relative_unit(raw: str) -> RelativeUnit:
    value = " ".join(raw.casefold().split())
    if value.startswith(("business", "working")):
        return RelativeUnit.BUSINESS_DAYS
    if value.startswith("day"):
        return RelativeUnit.DAYS
    if value.startswith("week"):
        return RelativeUnit.WEEKS
    if value.startswith("month"):
        return RelativeUnit.MONTHS
    return RelativeUnit.YEARS


def _relative_relation(raw: str) -> DateRelation:
    value = raw.casefold()
    if value == "before":
        return DateRelation.BEFORE
    if value == "after":
        return DateRelation.AFTER
    if value == "from":
        return DateRelation.FROM
    return DateRelation.WITHIN


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r"(?<=[.!?;])\s+|\n+", text):
        end = match.start()
        raw = text[start:end]
        if raw.strip():
            left_trim = len(raw) - len(raw.lstrip())
            right = len(raw.rstrip())
            spans.append((start + left_trim, start + right, raw.strip()))
        start = match.end()
    raw = text[start:]
    if raw.strip():
        left_trim = len(raw) - len(raw.lstrip())
        spans.append((start + left_trim, len(text.rstrip()), raw.strip()))
    return spans


def _classify_obligation(sentence: str) -> tuple[ObligationType, list[ExtractionSignal]]:
    folded = sentence.casefold()
    found: list[tuple[ObligationType, str]] = []
    for kind, terms in OBLIGATION_RULES:
        for term in terms:
            if term in folded:
                found.append((kind, term))
                break
    if not found:
        return ObligationType.OTHER, []
    priority = {
        ObligationType.PAYMENT: 100,
        ObligationType.NOTICE: 95,
        ObligationType.INSURANCE: 90,
        ObligationType.CONFIDENTIALITY: 85,
        ObligationType.REPORTING: 80,
        ObligationType.DELIVERY: 75,
        ObligationType.RENEWAL: 70,
        ObligationType.AUDIT: 65,
        ObligationType.COMPLIANCE: 60,
        ObligationType.PERFORMANCE: 50,
    }
    kind, term = max(found, key=lambda item: priority[item[0]])
    return kind, [ExtractionSignal(kind="keyword", value=term)]


def _frequency(sentence: str) -> Frequency:
    folded = sentence.casefold()
    if re.search(r"\b(each|every)\s+day\b|\bdaily\b", folded):
        return Frequency.DAILY
    if re.search(r"\b(each|every)\s+week\b|\bweekly\b", folded):
        return Frequency.WEEKLY
    if re.search(r"\b(each|every)\s+month\b|\bmonthly\b", folded):
        return Frequency.MONTHLY
    if re.search(r"\b(each|every)\s+quarter\b|\bquarterly\b", folded):
        return Frequency.QUARTERLY
    if re.search(r"\b(each|every)\s+year\b|\bannually\b|\bannual\b", folded):
        return Frequency.ANNUALLY
    if re.search(r"\bat all times\b|\bcontinuously\b|\bthroughout the term\b", folded):
        return Frequency.CONTINUOUS
    if re.search(r"\bupon\b|\bafter\b|\bbefore\b|\bwithin\s+\d+", folded):
        return Frequency.EVENT_BASED
    return Frequency.ONCE


def _deadline_expression(sentence: str) -> str | None:
    rel = RELATIVE_PATTERN.search(sentence) or SIMPLE_RELATIVE_PATTERN.search(sentence)
    if rel:
        return rel.group(0).strip()
    for _name, pattern in ABSOLUTE_PATTERNS:
        match = pattern.search(sentence)
        if match:
            return match.group(0)
    return None


def _actor_action(sentence: str, marker: re.Match[str]) -> tuple[str | None, str]:
    actor = sentence[: marker.start()].strip(" ,:;-\t") or None
    action = sentence[marker.end() :].strip(" ,:;-\t")
    return actor, action


def _dedup_dates(items: list[ExtractedDate]) -> list[ExtractedDate]:
    seen: set[tuple] = set()
    result: list[ExtractedDate] = []
    for item in items:
        key = (
            item.date_kind,
            item.raw_text.casefold(),
            item.normalized_date,
            item.relative_value,
            item.relative_unit,
            item.relation,
            (item.anchor or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedup_obligations(items: list[ExtractedObligation]) -> list[ExtractedObligation]:
    seen: set[tuple[str, str]] = set()
    result: list[ExtractedObligation] = []
    for item in items:
        key = (item.obligation_type.value, " ".join(item.text.casefold().split()))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def extract_key_dates_and_obligations(payload: ExtractRequest) -> ExtractResponse:
    text = _normalize_text(payload.text)
    options = payload.options
    warnings: list[str] = []
    dates: list[ExtractedDate] = []

    occupied: list[tuple[int, int]] = []
    for format_name, pattern in ABSOLUTE_PATTERNS:
        for match in pattern.finditer(text):
            parsed = _parse_absolute(match)
            if parsed is None:
                warnings.append(f"Ignored invalid calendar date expression: {match.group(0)}")
                continue
            context, kind, signals = _classify_date_near(
                text, match.start(), match.end(), options.context_chars
            )
            if kind == DateKind.OTHER and not options.include_other_dates:
                continue
            if options.date_kinds and kind not in options.date_kinds:
                continue
            line, column = _line_column(text, match.start())
            relation = DateRelation.ON
            prefix = text[max(0, match.start() - 12) : match.start()].casefold()
            if re.search(r"\bby\s*$", prefix):
                relation = DateRelation.BY
            dates.append(
                ExtractedDate(
                    date_kind=kind,
                    raw_text=match.group(0),
                    normalized_date=parsed,
                    relation=relation,
                    context=context,
                    start=match.start(),
                    end=match.end(),
                    line=line,
                    column=column,
                    signals=[ExtractionSignal(kind="date_format", value=format_name), *signals],
                )
            )
            occupied.append((match.start(), match.end()))

    relative_matches: list[re.Match[str]] = list(RELATIVE_PATTERN.finditer(text))
    # Add simple forms not already covered by the richer expression.
    for match in SIMPLE_RELATIVE_PATTERN.finditer(text):
        if any(start <= match.start() < end for start, end in [(m.start(), m.end()) for m in relative_matches]):
            continue
        relative_matches.append(match)

    for match in sorted(relative_matches, key=lambda m: m.start()):
        context, kind, signals = _classify_date_near(
            text, match.start(), match.end(), options.context_chars
        )
        if kind == DateKind.OTHER and not options.include_other_dates:
            continue
        if options.date_kinds and kind not in options.date_kinds:
            continue
        direction = match.group("direction")
        line, column = _line_column(text, match.start())
        dates.append(
            ExtractedDate(
                date_kind=kind,
                raw_text=match.group(0).strip(),
                relation=_relative_relation(direction),
                relative_value=int(match.group("value")),
                relative_unit=_relative_unit(match.group("unit")),
                anchor=match.group("anchor").strip(),
                context=context,
                start=match.start(),
                end=match.end(),
                line=line,
                column=column,
                signals=[ExtractionSignal(kind="relative_deadline", value=direction.casefold()), *signals],
            )
        )

    if options.deduplicate:
        dates = _dedup_dates(dates)
    dates.sort(key=lambda item: (item.start, item.end, item.date_kind.value))
    if len(dates) > options.max_dates:
        dates = dates[: options.max_dates]
        warnings.append(f"Date result limit reached ({options.max_dates}).")

    obligations: list[ExtractedObligation] = []
    for start, end, sentence in _sentence_spans(text):
        marker = OBLIGATION_MARKER.search(sentence)
        if not marker:
            continue
        kind, signals = _classify_obligation(sentence)
        if kind == ObligationType.OTHER and not options.include_other_obligations:
            continue
        if options.obligation_types and kind not in options.obligation_types:
            continue
        actor, action = _actor_action(sentence, marker)
        line, column = _line_column(text, start)
        obligations.append(
            ExtractedObligation(
                obligation_type=kind,
                actor=actor,
                action=action,
                frequency=_frequency(sentence),
                deadline_expression=_deadline_expression(sentence),
                text=sentence,
                start=start,
                end=end,
                line=line,
                column=column,
                signals=[ExtractionSignal(kind="obligation_marker", value=marker.group("marker")), *signals],
            )
        )

    if options.deduplicate:
        obligations = _dedup_obligations(obligations)
    if len(obligations) > options.max_obligations:
        obligations = obligations[: options.max_obligations]
        warnings.append(f"Obligation result limit reached ({options.max_obligations}).")

    if not dates:
        warnings.append("No supported key-date expressions matched the requested filters.")
    if not obligations:
        warnings.append("No supported obligation wording matched the requested filters.")

    date_counts = Counter(item.date_kind.value for item in dates)
    obligation_counts = Counter(item.obligation_type.value for item in obligations)
    return ExtractResponse(
        dates=dates,
        obligations=obligations,
        summary=ExtractionSummary(
            dates_returned=len(dates),
            obligations_returned=len(obligations),
            absolute_dates=sum(1 for item in dates if item.normalized_date is not None),
            relative_dates=sum(1 for item in dates if item.relative_value is not None),
            date_kind_counts=dict(sorted(date_counts.items())),
            obligation_type_counts=dict(sorted(obligation_counts.items())),
        ),
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )


def supported_patterns() -> SupportedPatternsResponse:
    return SupportedPatternsResponse(
        absolute_date_formats=[
            "YYYY-MM-DD",
            "D Month YYYY (for example 8 August 2026)",
            "Month D, YYYY (for example August 8, 2026)",
        ],
        relative_deadline_examples=[
            "within 30 days after receipt",
            "at least 60 days before expiry",
            "15 business days from invoice date",
        ],
        obligation_markers=["shall", "must", "is/are required to", "agrees to", "undertakes to", "will"],
        disclaimer=DISCLAIMER,
    )
