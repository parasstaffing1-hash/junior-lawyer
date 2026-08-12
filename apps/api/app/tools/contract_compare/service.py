from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.tools.contract_compare.models import (
    ClauseChange,
    ContractChangeType,
    ContractClause,
    ContractCompareRequest,
    ContractCompareResponse,
    ContractCompareSummary,
    DiffOperation,
    TokenDiff,
)


DISCLAIMER = (
    "This deterministic comparison highlights textual differences only. It does not determine legal "
    "meaning, materiality, enforceability, risk, privilege, or whether a change is acceptable. "
    "Review the source documents and generated redline before legal use."
)

_HEADING_RE = re.compile(
    r"^\s*(?P<num>(?:\d+(?:\.\d+)*|[A-Z]|[IVXLCDM]+)[\.)]?)\s+(?P<title>\S.*)$",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"\s+|[\w₹$€£%]+(?:['’.-][\w₹$€£%]+)*|[^\w\s]", re.UNICODE)


@dataclass(slots=True)
class _Clause:
    index: int
    clause_id: str
    title: str | None
    text: str


def _clean_text(value: str, normalize_whitespace: bool) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalize_whitespace:
        return value
    return " ".join(value.split())


def _comparison_text(value: str, *, ignore_case: bool, normalize_whitespace: bool) -> str:
    cleaned = _clean_text(value, normalize_whitespace)
    return cleaned.casefold() if ignore_case else cleaned


def _from_structured(clauses: list[ContractClause], normalize_whitespace: bool) -> list[_Clause]:
    result: list[_Clause] = []
    seen_ids: set[str] = set()
    for idx, clause in enumerate(clauses, start=1):
        clause_id = (clause.clause_id or f"clause-{idx}").strip()
        key = clause_id.casefold()
        if key in seen_ids:
            raise ValueError(f"duplicate clause_id: {clause_id}")
        seen_ids.add(key)
        title = " ".join(clause.title.split()) if clause.title else None
        result.append(
            _Clause(
                index=idx,
                clause_id=clause_id,
                title=title,
                text=_clean_text(clause.text, normalize_whitespace),
            )
        )
    return result


def _flush_plain_clause(
    result: list[_Clause],
    title: str | None,
    clause_id: str | None,
    body_lines: list[str],
    normalize_whitespace: bool,
) -> None:
    raw = "\n".join(body_lines).strip()
    if not raw and title:
        raw = title
    if not raw:
        return
    idx = len(result) + 1
    result.append(
        _Clause(
            index=idx,
            clause_id=clause_id or f"clause-{idx}",
            title=title,
            text=_clean_text(raw, normalize_whitespace),
        )
    )


def _parse_plain_text(text: str, normalize_whitespace: bool) -> tuple[list[_Clause], bool]:
    """Split obvious numbered headings; otherwise use non-empty paragraphs."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heading_positions = [i for i, line in enumerate(lines) if _HEADING_RE.match(line.strip())]
    if heading_positions:
        result: list[_Clause] = []
        current_title: str | None = None
        current_id: str | None = None
        body: list[str] = []
        preamble: list[str] = []
        for line in lines:
            match = _HEADING_RE.match(line.strip())
            if match:
                if current_id is None and preamble:
                    _flush_plain_clause(result, "Preamble", "preamble", preamble, normalize_whitespace)
                    preamble = []
                if current_id is not None:
                    _flush_plain_clause(result, current_title, current_id, body, normalize_whitespace)
                current_id = match.group("num").rstrip(".)")
                current_title = " ".join(match.group("title").split())
                body = [line.strip()]
            elif current_id is None:
                if line.strip():
                    preamble.append(line)
            else:
                if line.strip():
                    body.append(line)
        if current_id is not None:
            _flush_plain_clause(result, current_title, current_id, body, normalize_whitespace)
        elif preamble:
            _flush_plain_clause(result, None, None, preamble, normalize_whitespace)
        return result, True

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]
    return (
        [
            _Clause(
                index=i,
                clause_id=f"clause-{i}",
                title=None,
                text=_clean_text(part, normalize_whitespace),
            )
            for i, part in enumerate(paragraphs, start=1)
        ],
        False,
    )


def _load_source(
    text: str | None,
    clauses: list[ContractClause] | None,
    normalize_whitespace: bool,
) -> tuple[list[_Clause], bool]:
    if clauses is not None:
        return _from_structured(clauses, normalize_whitespace), True
    assert text is not None
    return _parse_plain_text(text, normalize_whitespace)


def _title_key(clause: _Clause) -> str | None:
    if not clause.title:
        return None
    return re.sub(r"\W+", " ", clause.title.casefold()).strip()


def _identity_key(clause: _Clause) -> str:
    return clause.clause_id.casefold().strip()


def _similarity(a: _Clause, b: _Clause, *, ignore_case: bool, normalize_whitespace: bool) -> float:
    a_title = _title_key(a) or ""
    b_title = _title_key(b) or ""
    a_text = _comparison_text(a.text, ignore_case=ignore_case, normalize_whitespace=normalize_whitespace)
    b_text = _comparison_text(b.text, ignore_case=ignore_case, normalize_whitespace=normalize_whitespace)
    text_score = SequenceMatcher(None, a_text, b_text, autojunk=False).ratio()
    if a_title and b_title:
        title_score = SequenceMatcher(None, a_title, b_title, autojunk=False).ratio()
        return min(1.0, 0.35 * title_score + 0.65 * text_score)
    return text_score


def _pair_clauses(
    original: list[_Clause],
    revised: list[_Clause],
    *,
    ignore_case: bool,
    normalize_whitespace: bool,
    similarity_threshold: float,
) -> tuple[list[tuple[_Clause, _Clause, float]], list[_Clause], list[_Clause]]:
    unmatched_o = {c.index: c for c in original}
    unmatched_r = {c.index: c for c in revised}
    pairs: list[tuple[_Clause, _Clause, float]] = []

    # First pair explicit/extracted clause identifiers exactly.
    r_by_id = {_identity_key(c): c for c in revised}
    for o in original:
        r = r_by_id.get(_identity_key(o))
        if r and r.index in unmatched_r:
            score = _similarity(o, r, ignore_case=ignore_case, normalize_whitespace=normalize_whitespace)
            pairs.append((o, r, score))
            unmatched_o.pop(o.index, None)
            unmatched_r.pop(r.index, None)

    # Then pair identical normalized titles.
    for o in list(unmatched_o.values()):
        key = _title_key(o)
        if not key:
            continue
        candidates = [r for r in unmatched_r.values() if _title_key(r) == key]
        if len(candidates) == 1:
            r = candidates[0]
            score = _similarity(o, r, ignore_case=ignore_case, normalize_whitespace=normalize_whitespace)
            pairs.append((o, r, score))
            unmatched_o.pop(o.index, None)
            unmatched_r.pop(r.index, None)

    # Finally greedily pair the most similar remaining clauses above threshold.
    scored: list[tuple[float, int, int]] = []
    for o in unmatched_o.values():
        for r in unmatched_r.values():
            score = _similarity(o, r, ignore_case=ignore_case, normalize_whitespace=normalize_whitespace)
            if score >= similarity_threshold:
                scored.append((score, o.index, r.index))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_o: set[int] = set()
    used_r: set[int] = set()
    for score, oi, ri in scored:
        if oi in used_o or ri in used_r or oi not in unmatched_o or ri not in unmatched_r:
            continue
        o = unmatched_o.pop(oi)
        r = unmatched_r.pop(ri)
        used_o.add(oi)
        used_r.add(ri)
        pairs.append((o, r, score))

    pairs.sort(key=lambda item: (item[1].index, item[0].index))
    return pairs, list(unmatched_o.values()), list(unmatched_r.values())


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _token_diff(original: str, revised: str, max_tokens: int) -> tuple[list[TokenDiff], bool]:
    old = _tokenize(original)
    new = _tokenize(revised)
    truncated = False
    if len(old) > max_tokens:
        old = old[:max_tokens]
        truncated = True
    if len(new) > max_tokens:
        new = new[:max_tokens]
        truncated = True

    matcher = SequenceMatcher(None, old, new, autojunk=False)
    output: list[TokenDiff] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_text = "".join(old[i1:i2])
        new_text = "".join(new[j1:j2])
        if tag == "equal":
            output.append(TokenDiff(operation=DiffOperation.EQUAL, original=old_text, revised=new_text))
        elif tag == "delete":
            output.append(TokenDiff(operation=DiffOperation.DELETE, original=old_text))
        elif tag == "insert":
            output.append(TokenDiff(operation=DiffOperation.INSERT, revised=new_text))
        else:
            output.append(TokenDiff(operation=DiffOperation.REPLACE, original=old_text, revised=new_text))
    return output, truncated


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _redline_from_tokens(tokens: list[TokenDiff]) -> str:
    chunks: list[str] = []
    for item in tokens:
        if item.operation == DiffOperation.EQUAL:
            chunks.append(_escape_html(item.revised))
        elif item.operation == DiffOperation.DELETE:
            chunks.append(f"<del>{_escape_html(item.original)}</del>")
        elif item.operation == DiffOperation.INSERT:
            chunks.append(f"<ins>{_escape_html(item.revised)}</ins>")
        else:
            chunks.append(f"<del>{_escape_html(item.original)}</del><ins>{_escape_html(item.revised)}</ins>")
    return "".join(chunks)


def _word_count(clauses: list[_Clause]) -> int:
    return sum(len(re.findall(r"\b\w+\b", clause.text, re.UNICODE)) for clause in clauses)


def _heading(change: ClauseChange) -> str:
    title = change.revised_title or change.original_title
    cid = change.revised_clause_id or change.original_clause_id
    if title:
        return f"{cid} — {title}" if cid else title
    return cid or "Clause"


def _build_markdown(changes: list[ClauseChange], summary: ContractCompareSummary) -> str:
    lines = [
        "# Contract Comparison",
        "",
        f"Added: {summary.added} | Removed: {summary.removed} | Modified: {summary.modified} | Unchanged: {summary.unchanged}",
        "",
    ]
    for change in changes:
        lines.append(f"## {_heading(change)} [{change.change_type.value.upper()}]")
        lines.append("")
        if change.change_type == ContractChangeType.ADDED:
            lines.append(f"<ins>{_escape_html(change.revised_text or '')}</ins>")
        elif change.change_type == ContractChangeType.REMOVED:
            lines.append(f"<del>{_escape_html(change.original_text or '')}</del>")
        elif change.change_type == ContractChangeType.UNCHANGED:
            lines.append(change.revised_text or change.original_text or "")
        else:
            lines.append(change.redline)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def compare_contracts(payload: ContractCompareRequest) -> ContractCompareResponse:
    options = payload.options
    original, original_structured = _load_source(payload.original_text, payload.original_clauses, options.normalize_whitespace)
    revised, revised_structured = _load_source(payload.revised_text, payload.revised_clauses, options.normalize_whitespace)

    pairs, removed, added = _pair_clauses(
        original,
        revised,
        ignore_case=options.ignore_case,
        normalize_whitespace=options.normalize_whitespace,
        similarity_threshold=options.similarity_threshold,
    )

    warnings: list[str] = []
    if not original_structured or not revised_structured:
        warnings.append(
            "At least one source used automatic plain-text clause splitting; provide structured clauses for more reliable clause alignment."
        )

    all_changes: list[ClauseChange] = []
    truncated_count = 0
    unchanged_count = 0
    modified_count = 0

    for o, r, score in pairs:
        old_cmp = _comparison_text(o.text, ignore_case=options.ignore_case, normalize_whitespace=options.normalize_whitespace)
        new_cmp = _comparison_text(r.text, ignore_case=options.ignore_case, normalize_whitespace=options.normalize_whitespace)
        if old_cmp == new_cmp:
            unchanged_count += 1
            all_changes.append(
                ClauseChange(
                    change_type=ContractChangeType.UNCHANGED,
                    original_index=o.index,
                    revised_index=r.index,
                    original_clause_id=o.clause_id,
                    revised_clause_id=r.clause_id,
                    original_title=o.title,
                    revised_title=r.title,
                    original_text=o.text,
                    revised_text=r.text,
                    similarity=1.0,
                    redline=r.text,
                )
            )
            continue

        modified_count += 1
        tokens, truncated = _token_diff(o.text, r.text, options.max_diff_tokens_per_clause)
        truncated_count += int(truncated)
        all_changes.append(
            ClauseChange(
                change_type=ContractChangeType.MODIFIED,
                original_index=o.index,
                revised_index=r.index,
                original_clause_id=o.clause_id,
                revised_clause_id=r.clause_id,
                original_title=o.title,
                revised_title=r.title,
                original_text=o.text,
                revised_text=r.text,
                similarity=round(score, 6),
                token_diff=tokens,
                redline=_redline_from_tokens(tokens),
            )
        )

    for o in removed:
        all_changes.append(
            ClauseChange(
                change_type=ContractChangeType.REMOVED,
                original_index=o.index,
                original_clause_id=o.clause_id,
                original_title=o.title,
                original_text=o.text,
                similarity=0.0,
                redline=f"<del>{_escape_html(o.text)}</del>",
            )
        )
    for r in added:
        all_changes.append(
            ClauseChange(
                change_type=ContractChangeType.ADDED,
                revised_index=r.index,
                revised_clause_id=r.clause_id,
                revised_title=r.title,
                revised_text=r.text,
                similarity=0.0,
                redline=f"<ins>{_escape_html(r.text)}</ins>",
            )
        )

    if truncated_count:
        warnings.append(
            f"Token-level diff was truncated for {truncated_count} clause(s) at the configured per-clause token limit."
        )

    order = {
        ContractChangeType.REMOVED: 0,
        ContractChangeType.MODIFIED: 1,
        ContractChangeType.UNCHANGED: 2,
        ContractChangeType.ADDED: 3,
    }
    all_changes.sort(
        key=lambda c: (
            c.revised_index if c.revised_index is not None else 10**9,
            c.original_index if c.original_index is not None else 10**9,
            order[c.change_type],
        )
    )

    returned = all_changes if options.include_unchanged else [
        c for c in all_changes if c.change_type != ContractChangeType.UNCHANGED
    ]
    original_words = _word_count(original)
    revised_words = _word_count(revised)
    summary = ContractCompareSummary(
        original_clause_count=len(original),
        revised_clause_count=len(revised),
        added=len(added),
        removed=len(removed),
        modified=modified_count,
        unchanged=unchanged_count,
        returned_changes=len(returned),
        original_word_count=original_words,
        revised_word_count=revised_words,
        word_count_delta=revised_words - original_words,
    )
    return ContractCompareResponse(
        summary=summary,
        changes=returned,
        redline_markdown=_build_markdown(returned, summary),
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
