import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.tools.legal_checklist.models import (
    ChecklistItemInput,
    ChecklistSummary,
    ChecklistTemplateSummary,
    EvaluatedChecklistItem,
    ItemStatus,
    LegalChecklistRequest,
    LegalChecklistResponse,
    LegalChecklistTemplate,
    MatchCondition,
    RequirementLevel,
)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DISCLAIMER = (
    "This checklist is generated from a deterministic template and is not legal advice. "
    "A qualified lawyer should verify the applicable law, court rules, filing requirements, "
    "document currency, and matter-specific requirements before relying on it."
)


class LegalChecklistError(ValueError):
    pass


class LegalChecklistTemplateNotFoundError(LegalChecklistError):
    pass


class LegalChecklistTemplateDateError(LegalChecklistError):
    pass


class LegalChecklistInputError(LegalChecklistError):
    pass


@lru_cache(maxsize=1)
def _load_templates() -> dict[str, LegalChecklistTemplate]:
    templates: dict[str, LegalChecklistTemplate] = {}
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        template = LegalChecklistTemplate.model_validate(payload)
        if template.id in templates:
            raise RuntimeError(f"duplicate legal checklist template id: {template.id}")
        templates[template.id] = template
    return templates


def clear_template_cache() -> None:
    _load_templates.cache_clear()


def list_templates(matter_type: str | None = None) -> list[ChecklistTemplateSummary]:
    normalized_filter = matter_type.strip().lower() if matter_type else None
    summaries: list[ChecklistTemplateSummary] = []
    for template in sorted(_load_templates().values(), key=lambda item: item.id):
        if normalized_filter and template.matter_type.lower() != normalized_filter:
            continue
        summaries.append(
            ChecklistTemplateSummary(
                id=template.id,
                version=template.version,
                title=template.title,
                matter_type=template.matter_type,
                jurisdiction=template.jurisdiction,
                effective_from=template.effective_from,
                effective_to=template.effective_to,
                context_fields=template.context_fields,
                item_count=len(template.items),
                source_note=template.source_note,
            )
        )
    return summaries


def _get_template(template_id: str) -> LegalChecklistTemplate:
    try:
        return _load_templates()[template_id]
    except KeyError as exc:
        raise LegalChecklistTemplateNotFoundError(
            f"legal checklist template '{template_id}' was not found"
        ) from exc


def _validate_date(template: LegalChecklistTemplate, request: LegalChecklistRequest) -> None:
    if request.assessment_date < template.effective_from:
        raise LegalChecklistTemplateDateError(
            f"template '{template.id}' is effective from {template.effective_from.isoformat()}"
        )
    if template.effective_to is not None and request.assessment_date > template.effective_to:
        raise LegalChecklistTemplateDateError(
            f"template '{template.id}' expired on {template.effective_to.isoformat()}"
        )


def _normalize_context(template: LegalChecklistTemplate, raw: dict[str, str]) -> dict[str, str]:
    definitions = {field.key: field for field in template.context_fields}
    unknown = sorted(set(raw) - set(definitions))
    if unknown:
        raise LegalChecklistInputError(f"unknown context field(s): {', '.join(unknown)}")

    normalized: dict[str, str] = {}
    for key, value in raw.items():
        cleaned = value.strip()
        if not cleaned:
            continue
        definition = definitions[key]
        if definition.allowed_values:
            allowed = {item.lower(): item for item in definition.allowed_values}
            if cleaned.lower() not in allowed:
                raise LegalChecklistInputError(
                    f"context field '{key}' must be one of: {', '.join(definition.allowed_values)}"
                )
            cleaned = allowed[cleaned.lower()]
        normalized[key] = cleaned

    missing = [field.key for field in template.context_fields if field.required and field.key not in normalized]
    if missing:
        raise LegalChecklistInputError(f"missing required context field(s): {', '.join(missing)}")
    return normalized


def _condition_matches(condition: MatchCondition, context: dict[str, str]) -> bool:
    current = context.get(condition.field)
    if current is None:
        return False
    allowed = {value.strip().lower() for value in condition.values}
    return current.strip().lower() in allowed


def _all_match(conditions: list[MatchCondition], context: dict[str, str]) -> bool:
    return all(_condition_matches(condition, context) for condition in conditions)


def _any_match(conditions: list[MatchCondition], context: dict[str, str]) -> bool:
    return any(_condition_matches(condition, context) for condition in conditions)


def _is_applicable(item, context: dict[str, str]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if item.applies_if_all and not _all_match(item.applies_if_all, context):
        reasons.append("Not applicable because all applicability conditions were not met.")
        return False, reasons
    if item.applies_if_any and not _any_match(item.applies_if_any, context):
        reasons.append("Not applicable because none of the applicability conditions were met.")
        return False, reasons
    if item.applies_if_all or item.applies_if_any:
        reasons.append("Applicable because configured matter conditions were met.")
    else:
        reasons.append("Applicable to all matters using this checklist template.")
    return True, reasons


def _effective_requirement(item, context: dict[str, str]) -> tuple[RequirementLevel, list[str]]:
    reasons: list[str] = []
    conditional_required = False
    if item.required_if_all and _all_match(item.required_if_all, context):
        conditional_required = True
        reasons.append("Requirement elevated to required because all required-if conditions were met.")
    if item.required_if_any and _any_match(item.required_if_any, context):
        conditional_required = True
        reasons.append("Requirement elevated to required because a required-if condition was met.")
    if conditional_required:
        return RequirementLevel.REQUIRED, reasons
    return item.requirement, reasons


def _normalize_item_inputs(template: LegalChecklistTemplate, inputs: list[ChecklistItemInput]) -> dict[str, ChecklistItemInput]:
    known = {item.key for item in template.items}
    seen: dict[str, ChecklistItemInput] = {}
    for item in inputs:
        if item.key not in known:
            raise LegalChecklistInputError(f"unknown checklist item key: {item.key}")
        if item.key in seen:
            raise LegalChecklistInputError(f"duplicate checklist item key: {item.key}")
        seen[item.key] = item
    return seen


def _default_status(requirement: RequirementLevel, applicable: bool) -> ItemStatus:
    if not applicable:
        return ItemStatus.NOT_APPLICABLE
    if requirement == RequirementLevel.OPTIONAL:
        return ItemStatus.PENDING
    return ItemStatus.MISSING


def _is_satisfied(status: ItemStatus, applicable: bool) -> bool:
    if not applicable:
        return True
    return status in {ItemStatus.PRESENT, ItemStatus.COMPLETED}


def _render_markdown(response_items: list[EvaluatedChecklistItem], title: str, matter_type: str, assessment_date) -> str:
    lines = [
        f"# {title}",
        "",
        f"Matter type: {matter_type}",
        f"Assessment date: {assessment_date.isoformat()}",
        "",
        "| # | Item | Category | Requirement | Status |",
        "|---:|---|---|---|---|",
    ]
    for item in response_items:
        requirement = "Not applicable" if not item.applicable else item.requirement.value.title()
        lines.append(
            f"| {item.sequence} | {item.title.replace('|', '\\|')} | "
            f"{item.category.replace('|', '\\|')} | {requirement} | {item.status.value.replace('_', ' ').title()} |"
        )
    return "\n".join(lines)


def evaluate_checklist(request: LegalChecklistRequest) -> LegalChecklistResponse:
    template = _get_template(request.template_id)
    _validate_date(template, request)
    context = _normalize_context(template, request.context)
    supplied = _normalize_item_inputs(template, request.items)

    evaluated: list[EvaluatedChecklistItem] = []
    warnings: list[str] = []

    for sequence, definition in enumerate(template.items, start=1):
        applicable, reasons = _is_applicable(definition, context)
        requirement, requirement_reasons = _effective_requirement(definition, context)
        reasons.extend(requirement_reasons)
        submitted = supplied.get(definition.key)

        if submitted is None:
            status = _default_status(requirement, applicable)
            file_reference = None
            document_date = None
            notes = None
        else:
            status = submitted.status
            file_reference = submitted.file_reference.strip() if submitted.file_reference else None
            document_date = submitted.document_date
            notes = submitted.notes.strip() if submitted.notes else None

        if not applicable and status != ItemStatus.NOT_APPLICABLE:
            warnings.append(
                f"Item '{definition.key}' is not applicable under the supplied context; status was normalized to not_applicable."
            )
            status = ItemStatus.NOT_APPLICABLE
        elif applicable and status == ItemStatus.NOT_APPLICABLE:
            raise LegalChecklistInputError(
                f"item '{definition.key}' is applicable and cannot be marked not_applicable"
            )

        if file_reference and status not in {ItemStatus.PRESENT, ItemStatus.COMPLETED}:
            warnings.append(
                f"Item '{definition.key}' has a file reference but status is '{status.value}'."
            )
        if definition.kind.value == "document" and status == ItemStatus.PRESENT and not file_reference:
            warnings.append(f"Document item '{definition.key}' is present but has no file reference.")

        required = applicable and requirement == RequirementLevel.REQUIRED
        satisfied = _is_satisfied(status, applicable)
        evaluated.append(
            EvaluatedChecklistItem(
                sequence=sequence,
                key=definition.key,
                title=definition.title,
                category=definition.category,
                kind=definition.kind,
                description=definition.description,
                applicable=applicable,
                requirement=requirement,
                required=required,
                status=status,
                satisfied=satisfied,
                file_reference=file_reference,
                document_date=document_date,
                notes=notes,
                evidence_hint=definition.evidence_hint,
                reasons=reasons,
            )
        )

    applicable_items = [item for item in evaluated if item.applicable]
    required_items = [item for item in applicable_items if item.required]
    recommended_items = [
        item for item in applicable_items if item.requirement == RequirementLevel.RECOMMENDED
    ]
    completed_applicable = [item for item in applicable_items if item.satisfied]
    required_satisfied = [item for item in required_items if item.satisfied]
    category_counts = dict(sorted(Counter(item.category for item in applicable_items).items()))

    completion_percent = (
        round(len(completed_applicable) / len(applicable_items) * 100, 2)
        if applicable_items
        else 100.0
    )
    required_completion_percent = (
        round(len(required_satisfied) / len(required_items) * 100, 2)
        if required_items
        else 100.0
    )
    outstanding_required = [item.key for item in required_items if not item.satisfied]

    if outstanding_required:
        warnings.append(
            f"{len(outstanding_required)} required checklist item(s) remain outstanding."
        )

    summary = ChecklistSummary(
        total_items=len(evaluated),
        applicable_items=len(applicable_items),
        required_items=len(required_items),
        required_satisfied=len(required_satisfied),
        required_outstanding=len(outstanding_required),
        recommended_items=len(recommended_items),
        completed_applicable_items=len(completed_applicable),
        completion_percent=completion_percent,
        required_completion_percent=required_completion_percent,
        category_counts=category_counts,
        outstanding_required_keys=outstanding_required,
    )

    return LegalChecklistResponse(
        template_id=template.id,
        template_version=template.version,
        title=template.title,
        matter_type=template.matter_type,
        jurisdiction=template.jurisdiction,
        assessment_date=request.assessment_date,
        context_used=context,
        items=evaluated,
        summary=summary,
        warnings=warnings,
        markdown=_render_markdown(evaluated, template.title, template.matter_type, request.assessment_date),
        source_note=template.source_note,
        disclaimer=DISCLAIMER,
    )
