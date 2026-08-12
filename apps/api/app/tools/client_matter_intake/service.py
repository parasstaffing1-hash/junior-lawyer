from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.tools.client_matter_intake.models import (
    ClientMatterIntakeRequest,
    ClientMatterIntakeResponse,
    ConsentDefinition,
    ConflictPartyInput,
    EvaluatedConsent,
    EvaluatedIntakeField,
    IntakeFieldDefinition,
    IntakeFieldType,
    IntakeSummary,
    IntakeTemplate,
    IntakeTemplateSummary,
    MatchCondition,
    NormalizedConflictParty,
)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^[+()0-9.\-\s]{7,30}$")
DISCLAIMER = (
    "This intake packet is generated from a deterministic template and is not legal advice, "
    "a conflicts clearance, or an engagement agreement. A law firm should verify identity, "
    "conflicts, consent, privacy, professional-responsibility, and jurisdiction-specific "
    "requirements before opening or accepting a matter."
)


class ClientMatterIntakeError(ValueError):
    pass


class IntakeTemplateNotFoundError(ClientMatterIntakeError):
    pass


class IntakeTemplateDateError(ClientMatterIntakeError):
    pass


class IntakeInputError(ClientMatterIntakeError):
    pass


@lru_cache(maxsize=1)
def _load_templates() -> dict[str, IntakeTemplate]:
    templates: dict[str, IntakeTemplate] = {}
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        template = IntakeTemplate.model_validate(payload)
        if template.id in templates:
            raise RuntimeError(f"duplicate client intake template id: {template.id}")
        templates[template.id] = template
    return templates


def clear_template_cache() -> None:
    _load_templates.cache_clear()


def list_templates(
    matter_type: str | None = None,
    client_type: str | None = None,
) -> list[IntakeTemplateSummary]:
    normalized_matter = matter_type.strip().lower() if matter_type else None
    normalized_client = client_type.strip().lower() if client_type else None
    summaries: list[IntakeTemplateSummary] = []
    for template in sorted(_load_templates().values(), key=lambda item: item.id):
        if normalized_matter and template.matter_type.lower() != normalized_matter:
            continue
        if normalized_client and template.client_type.lower() != normalized_client:
            continue
        summaries.append(
            IntakeTemplateSummary(
                id=template.id,
                version=template.version,
                title=template.title,
                matter_type=template.matter_type,
                client_type=template.client_type,
                jurisdiction=template.jurisdiction,
                effective_from=template.effective_from,
                effective_to=template.effective_to,
                sections=template.sections,
                fields=template.fields,
                consents=template.consents,
                source_note=template.source_note,
            )
        )
    return summaries


def _get_template(template_id: str) -> IntakeTemplate:
    try:
        return _load_templates()[template_id]
    except KeyError as exc:
        raise IntakeTemplateNotFoundError(
            f"client/matter intake template '{template_id}' was not found"
        ) from exc


def _validate_date(template: IntakeTemplate, intake_date: date) -> None:
    if intake_date < template.effective_from:
        raise IntakeTemplateDateError(
            f"template '{template.id}' is effective from {template.effective_from.isoformat()}"
        )
    if template.effective_to is not None and intake_date > template.effective_to:
        raise IntakeTemplateDateError(
            f"template '{template.id}' expired on {template.effective_to.isoformat()}"
        )


def _condition_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, bool):
        return {"yes" if value else "no", "true" if value else "false"}
    if isinstance(value, date):
        return {value.isoformat().lower()}
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    text = str(value).strip().lower()
    return {text} if text else set()


def _condition_matches(condition: MatchCondition, values: dict[str, Any]) -> bool:
    current = _condition_values(values.get(condition.field))
    allowed = {value.strip().lower() for value in condition.values if value.strip()}
    return bool(current & allowed)


def _all_match(conditions: list[MatchCondition], values: dict[str, Any]) -> bool:
    return all(_condition_matches(condition, values) for condition in conditions)


def _any_match(conditions: list[MatchCondition], values: dict[str, Any]) -> bool:
    return any(_condition_matches(condition, values) for condition in conditions)


def _is_applicable(definition: Any, values: dict[str, Any]) -> bool:
    if definition.applies_if_all and not _all_match(definition.applies_if_all, values):
        return False
    if definition.applies_if_any and not _any_match(definition.applies_if_any, values):
        return False
    return True


def _is_required(definition: IntakeFieldDefinition, values: dict[str, Any], applicable: bool) -> bool:
    if not applicable:
        return False
    if definition.required:
        return True
    if definition.required_if_all and _all_match(definition.required_if_all, values):
        return True
    if definition.required_if_any and _any_match(definition.required_if_any, values):
        return True
    return False


def _trim_string(value: Any) -> str:
    return str(value).strip()


def _normalize_field(definition: IntakeFieldDefinition, raw: Any) -> tuple[Any | None, list[str]]:
    messages: list[str] = []
    field_type = definition.field_type

    if raw is None:
        return None, messages

    if field_type in {IntakeFieldType.TEXT, IntakeFieldType.TEXTAREA, IntakeFieldType.EMAIL, IntakeFieldType.PHONE}:
        if not isinstance(raw, str):
            return None, ["Value must be a string."]
        value = raw.strip()
        if not value:
            return None, messages
        if len(value) > definition.max_length:
            messages.append(f"Value exceeds maximum length of {definition.max_length} characters.")
        if field_type == IntakeFieldType.EMAIL and not EMAIL_RE.fullmatch(value):
            messages.append("Value is not a valid email address shape.")
        if field_type == IntakeFieldType.PHONE and not PHONE_RE.fullmatch(value):
            messages.append("Value is not a valid phone-number shape.")
        if definition.pattern:
            try:
                matched = re.fullmatch(definition.pattern, value)
            except re.error as exc:
                raise RuntimeError(f"invalid regex in intake template field '{definition.key}'") from exc
            if matched is None:
                messages.append("Value does not match the configured field pattern.")
        return value, messages

    if field_type == IntakeFieldType.DATE:
        if isinstance(raw, date):
            return raw.isoformat(), messages
        if not isinstance(raw, str):
            return None, ["Date value must be an ISO date string (YYYY-MM-DD)."]
        try:
            return date.fromisoformat(raw.strip()).isoformat(), messages
        except ValueError:
            return None, ["Date value must be a valid ISO date (YYYY-MM-DD)."]

    if field_type == IntakeFieldType.NUMBER:
        if isinstance(raw, bool):
            return None, ["Numeric value cannot be boolean."]
        try:
            number = Decimal(str(raw).strip())
        except (InvalidOperation, ValueError):
            return None, ["Value must be a valid number."]
        if not number.is_finite():
            return None, ["Value must be a finite number."]
        normalized = format(number.normalize(), "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        if normalized in {"-0", ""}:
            normalized = "0"
        return normalized, messages

    if field_type == IntakeFieldType.BOOLEAN:
        if isinstance(raw, bool):
            return raw, messages
        if isinstance(raw, str):
            cleaned = raw.strip().lower()
            if cleaned in {"yes", "true", "1"}:
                return True, messages
            if cleaned in {"no", "false", "0"}:
                return False, messages
        if raw in {0, 1}:
            return bool(raw), messages
        return None, ["Value must be boolean or yes/no."]

    if field_type == IntakeFieldType.CHOICE:
        if not isinstance(raw, str):
            return None, ["Choice value must be a string."]
        cleaned = raw.strip()
        allowed = {item.lower(): item for item in definition.allowed_values}
        canonical = allowed.get(cleaned.lower())
        if canonical is None:
            return None, [f"Value must be one of: {', '.join(definition.allowed_values)}"]
        return canonical, messages

    if field_type == IntakeFieldType.MULTICHOICE:
        if not isinstance(raw, list):
            return None, ["Multi-choice value must be a list."]
        allowed = {item.lower(): item for item in definition.allowed_values}
        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, str):
                messages.append("Every multi-choice item must be a string.")
                continue
            cleaned = item.strip()
            canonical = allowed.get(cleaned.lower())
            if canonical is None:
                messages.append(f"Unsupported choice: {cleaned}")
                continue
            key = canonical.lower()
            if key not in seen:
                normalized.append(canonical)
                seen.add(key)
        return normalized or None, messages

    return None, ["Unsupported field type."]


def _pre_normalize_values(template: IntakeTemplate, raw_values: dict[str, Any]) -> dict[str, Any]:
    definitions = {field.key: field for field in template.fields}
    unknown = sorted(set(raw_values) - set(definitions))
    if unknown:
        raise IntakeInputError(f"unknown intake field(s): {', '.join(unknown)}")

    values: dict[str, Any] = {}
    for key, raw in raw_values.items():
        normalized, _ = _normalize_field(definitions[key], raw)
        if normalized is not None:
            values[key] = normalized
        else:
            # Keep the raw value for deterministic condition checks only when it can be
            # represented safely. Invalid field values will still be reported later.
            if isinstance(raw, (str, bool, int, float)):
                values[key] = raw
    return values


def _normalize_conflict_parties(parties: list[ConflictPartyInput]) -> list[NormalizedConflictParty]:
    normalized: list[NormalizedConflictParty] = []
    for party in parties:
        aliases: list[str] = []
        seen_aliases: set[str] = set()
        for alias in party.aliases:
            cleaned = alias.strip()
            if cleaned and cleaned.lower() not in seen_aliases:
                aliases.append(cleaned)
                seen_aliases.add(cleaned.lower())
        normalized.append(
            NormalizedConflictParty(
                name=party.name.strip(),
                role=party.role,
                organization=_trim_string(party.organization) if party.organization else None,
                aliases=aliases,
                notes=_trim_string(party.notes) if party.notes else None,
            )
        )
    return normalized


def _build_conflict_terms(
    template: IntakeTemplate,
    normalized_values: dict[str, Any],
    parties: list[NormalizedConflictParty],
) -> list[str]:
    candidates: list[str] = []
    for field in template.fields:
        if not field.include_in_conflict_terms:
            continue
        value = normalized_values.get(field.key)
        if isinstance(value, list):
            candidates.extend(str(item) for item in value)
        elif value is not None:
            candidates.append(str(value))

    for party in parties:
        candidates.append(party.name)
        if party.organization:
            candidates.append(party.organization)
        candidates.extend(party.aliases)

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = " ".join(candidate.split())
        key = cleaned.lower()
        if cleaned and key not in seen:
            result.append(cleaned)
            seen.add(key)
    return result


def _evaluate_consents(
    template: IntakeTemplate,
    request: ClientMatterIntakeRequest,
    condition_values: dict[str, Any],
) -> tuple[list[EvaluatedConsent], list[str]]:
    definitions = {consent.key: consent for consent in template.consents}
    supplied = {}
    for consent in request.consents:
        if consent.key not in definitions:
            raise IntakeInputError(f"unknown consent key: {consent.key}")
        if consent.key in supplied:
            raise IntakeInputError(f"duplicate consent key: {consent.key}")
        supplied[consent.key] = consent

    evaluated: list[EvaluatedConsent] = []
    missing: list[str] = []
    for definition in template.consents:
        applicable = _is_applicable(definition, condition_values)
        submitted = supplied.get(definition.key)
        accepted = bool(submitted.accepted) if submitted and applicable else False
        accepted_at = submitted.accepted_at if submitted and applicable and submitted.accepted else None
        if applicable and definition.required and not accepted:
            missing.append(definition.key)
        evaluated.append(
            EvaluatedConsent(
                key=definition.key,
                label=definition.label,
                text=definition.text,
                applicable=applicable,
                required=definition.required and applicable,
                accepted=accepted,
                accepted_at=accepted_at,
            )
        )
    return evaluated, missing


def _render_markdown(
    template: IntakeTemplate,
    intake_date: date,
    fields: list[EvaluatedIntakeField],
    parties: list[NormalizedConflictParty],
    consents: list[EvaluatedConsent],
) -> str:
    lines = [
        f"# {template.title}",
        "",
        f"Intake date: {intake_date.isoformat()}",
        f"Matter type: {template.matter_type}",
        f"Client type: {template.client_type}",
        "",
    ]
    section_titles = {section.key: section.title for section in template.sections}
    for section in template.sections:
        section_fields = [field for field in fields if field.section == section.key and field.applicable]
        if not section_fields:
            continue
        lines.extend([f"## {section.title}", "", "| Field | Value | Status |", "|---|---|---|"])
        for field in section_fields:
            value = field.normalized_value
            if isinstance(value, list):
                display = ", ".join(str(item) for item in value)
            elif isinstance(value, bool):
                display = "Yes" if value else "No"
            elif value is None:
                display = ""
            else:
                display = str(value)
            status = "Valid" if field.valid and field.provided else "Missing" if not field.provided else "Invalid"
            lines.append(
                f"| {field.label.replace('|', '\\|')} | {display.replace('|', '\\|')} | {status} |"
            )
        lines.append("")

    if parties:
        lines.extend(["## Conflict-check parties", "", "| Name | Role | Organization | Aliases |", "|---|---|---|---|"])
        for party in parties:
            lines.append(
                f"| {party.name.replace('|', '\\|')} | {party.role.value.replace('_', ' ').title()} | "
                f"{(party.organization or '').replace('|', '\\|')} | {', '.join(party.aliases).replace('|', '\\|')} |"
            )
        lines.append("")

    applicable_consents = [consent for consent in consents if consent.applicable]
    if applicable_consents:
        lines.extend(["## Consents / confirmations", "", "| Confirmation | Required | Accepted |", "|---|---|---|"])
        for consent in applicable_consents:
            lines.append(
                f"| {consent.label.replace('|', '\\|')} | {'Yes' if consent.required else 'No'} | {'Yes' if consent.accepted else 'No'} |"
            )
        lines.append("")

    # Silence a false-positive linter concern about the dictionary being unused when templates evolve.
    _ = section_titles
    return "\n".join(lines).rstrip()


def _audit_hash(response_payload: dict[str, Any]) -> str:
    canonical = json.dumps(response_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_intake(request: ClientMatterIntakeRequest) -> ClientMatterIntakeResponse:
    template = _get_template(request.template_id)
    _validate_date(template, request.intake_date)

    condition_values = _pre_normalize_values(template, request.values)
    evaluated_fields: list[EvaluatedIntakeField] = []
    normalized_values: dict[str, Any] = {}
    missing_required_fields: list[str] = []
    invalid_fields: list[str] = []

    for sequence, definition in enumerate(template.fields, start=1):
        applicable = _is_applicable(definition, condition_values)
        required = _is_required(definition, condition_values, applicable)
        raw = request.values.get(definition.key)
        normalized, messages = _normalize_field(definition, raw) if applicable else (None, [])
        provided = normalized is not None
        valid = not messages

        if applicable and provided and valid:
            normalized_values[definition.key] = normalized
        if required and (not provided or not valid):
            missing_required_fields.append(definition.key)
        if applicable and raw is not None and messages:
            invalid_fields.append(definition.key)

        evaluated_fields.append(
            EvaluatedIntakeField(
                sequence=sequence,
                key=definition.key,
                label=definition.label,
                section=definition.section,
                field_type=definition.field_type,
                applicable=applicable,
                required=required,
                provided=provided,
                valid=valid,
                normalized_value=normalized,
                validation_messages=messages,
                help_text=definition.help_text,
            )
        )

    normalized_parties = _normalize_conflict_parties(request.conflict_parties)
    conflict_terms = _build_conflict_terms(template, normalized_values, normalized_parties)
    consents, missing_consents = _evaluate_consents(template, request, condition_values)

    warnings: list[str] = []
    for requirement in template.conflict_requirements:
        if _is_applicable(requirement, condition_values) and len(normalized_parties) < requirement.min_parties:
            warnings.append(requirement.description)
    if normalized_parties:
        warnings.append(
            "Conflict-check terms were prepared only; no law-firm conflicts database was searched by this tool."
        )
    if invalid_fields:
        warnings.append(f"{len(invalid_fields)} supplied intake field(s) failed deterministic validation.")
    if missing_required_fields:
        warnings.append(f"{len(missing_required_fields)} required intake field(s) are missing or invalid.")
    if missing_consents:
        warnings.append(f"{len(missing_consents)} required consent/confirmation(s) are not accepted.")

    applicable_fields = [field for field in evaluated_fields if field.applicable]
    required_fields = [field for field in applicable_fields if field.required]
    valid_provided = [field for field in applicable_fields if field.provided and field.valid]
    valid_required = [field for field in required_fields if field.provided and field.valid]
    applicable_required_consents = [consent for consent in consents if consent.applicable and consent.required]
    accepted_required_consents = [consent for consent in applicable_required_consents if consent.accepted]

    completion_percent = (
        round(len(valid_provided) / len(applicable_fields) * 100, 2) if applicable_fields else 100.0
    )
    required_denominator = len(required_fields) + len(applicable_required_consents)
    required_numerator = len(valid_required) + len(accepted_required_consents)
    required_completion_percent = (
        round(required_numerator / required_denominator * 100, 2)
        if required_denominator
        else 100.0
    )
    ready_for_review = (
        not missing_required_fields
        and not invalid_fields
        and not missing_consents
        and not any(
            _is_applicable(requirement, condition_values)
            and len(normalized_parties) < requirement.min_parties
            for requirement in template.conflict_requirements
        )
    )

    summary = IntakeSummary(
        total_fields=len(evaluated_fields),
        applicable_fields=len(applicable_fields),
        required_fields=len(required_fields),
        valid_provided_fields=len(valid_provided),
        invalid_fields=len(invalid_fields),
        missing_required_fields=missing_required_fields,
        required_consents=len(applicable_required_consents),
        accepted_required_consents=len(accepted_required_consents),
        missing_required_consents=missing_consents,
        conflict_parties=len(normalized_parties),
        conflict_search_terms=len(conflict_terms),
        completion_percent=completion_percent,
        required_completion_percent=required_completion_percent,
        ready_for_review=ready_for_review,
    )

    markdown = _render_markdown(template, request.intake_date, evaluated_fields, normalized_parties, consents)
    audit_payload = {
        "template_id": template.id,
        "template_version": template.version,
        "intake_date": request.intake_date.isoformat(),
        "normalized_values": normalized_values,
        "conflict_parties": [party.model_dump(mode="json") for party in normalized_parties],
        "consents": [consent.model_dump(mode="json") for consent in consents],
    }

    return ClientMatterIntakeResponse(
        template_id=template.id,
        template_version=template.version,
        title=template.title,
        matter_type=template.matter_type,
        client_type=template.client_type,
        jurisdiction=template.jurisdiction,
        intake_date=request.intake_date,
        fields=evaluated_fields,
        normalized_values=normalized_values,
        conflict_parties=normalized_parties,
        conflict_search_terms=conflict_terms,
        consents=consents,
        summary=summary,
        warnings=warnings,
        markdown=markdown,
        audit_hash_sha256=_audit_hash(audit_payload),
        source_note=template.source_note,
        disclaimer=DISCLAIMER,
    )
