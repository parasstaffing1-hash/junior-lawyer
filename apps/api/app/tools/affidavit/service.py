import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.tools.affidavit.models import (
    AffidavitGenerationRequest,
    AffidavitGenerationResponse,
    AffidavitTemplate,
    AffidavitTemplateSummary,
    RenderedAffidavitSection,
    RenderedAffidavitStatement,
)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
DISCLAIMER = (
    "This affidavit is generated from a deterministic demonstration template and is not "
    "legal advice or a verification of truth. A qualified lawyer/notary/authorized officer "
    "should confirm the required form, oath/affirmation, attestation, exhibits, filing rules, "
    "and governing law before signing or filing it."
)


class AffidavitError(ValueError):
    pass


class AffidavitTemplateNotFoundError(AffidavitError):
    pass


class AffidavitTemplateDateError(AffidavitError):
    pass


class AffidavitInputError(AffidavitError):
    pass


@lru_cache(maxsize=1)
def _load_templates() -> dict[str, AffidavitTemplate]:
    templates: dict[str, AffidavitTemplate] = {}
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        template = AffidavitTemplate.model_validate(payload)
        if template.id in templates:
            raise RuntimeError(f"duplicate affidavit template id: {template.id}")
        templates[template.id] = template
    return templates


def clear_template_cache() -> None:
    _load_templates.cache_clear()


def list_templates() -> list[AffidavitTemplateSummary]:
    return [
        AffidavitTemplateSummary(
            id=item.id,
            version=item.version,
            title=item.title,
            affidavit_type=item.affidavit_type,
            jurisdiction=item.jurisdiction,
            effective_from=item.effective_from,
            effective_to=item.effective_to,
            fields=item.fields,
            source_note=item.source_note,
        )
        for item in sorted(_load_templates().values(), key=lambda value: value.id)
    ]


def _get_template(template_id: str) -> AffidavitTemplate:
    try:
        return _load_templates()[template_id]
    except KeyError as exc:
        raise AffidavitTemplateNotFoundError(
            f"affidavit template '{template_id}' was not found"
        ) from exc


def _validate_effective_date(template: AffidavitTemplate, generation_date: date) -> None:
    if generation_date < template.effective_from:
        raise AffidavitTemplateDateError(
            f"template '{template.id}' is effective from {template.effective_from.isoformat()}"
        )
    if template.effective_to is not None and generation_date > template.effective_to:
        raise AffidavitTemplateDateError(
            f"template '{template.id}' expired on {template.effective_to.isoformat()}"
        )


def _validate_and_normalize_fields(
    template: AffidavitTemplate,
    supplied_fields: dict[str, str],
) -> dict[str, str]:
    definitions = {field.key: field for field in template.fields}
    unknown = sorted(set(supplied_fields) - set(definitions))
    if unknown:
        raise AffidavitInputError(f"unknown template field(s): {', '.join(unknown)}")

    normalized: dict[str, str] = {}
    for key, raw_value in supplied_fields.items():
        value = raw_value.strip()
        definition = definitions[key]
        if len(value) > definition.max_length:
            raise AffidavitInputError(
                f"field '{key}' exceeds maximum length of {definition.max_length}"
            )
        if value:
            normalized[key] = value

    missing = [
        field.key
        for field in template.fields
        if field.required and field.key not in normalized
    ]
    if missing:
        raise AffidavitInputError(f"missing required field(s): {', '.join(missing)}")

    return normalized


def _render_numbered_statements(request: AffidavitGenerationRequest) -> tuple[str, list[RenderedAffidavitStatement]]:
    rendered: list[RenderedAffidavitStatement] = []
    lines: list[str] = []
    for number, statement in enumerate(request.statements, start=1):
        text = statement.text.strip()
        if not text:
            raise AffidavitInputError(f"statement {number} cannot be blank")
        rendered.append(
            RenderedAffidavitStatement(
                number=number,
                text=text,
                source_reference=statement.source_reference.strip()
                if statement.source_reference and statement.source_reference.strip()
                else None,
            )
        )
        suffix = ""
        if rendered[-1].source_reference:
            suffix = f" [Reference: {rendered[-1].source_reference}]"
        lines.append(f"{number}. {text}{suffix}")
    return "\n\n".join(lines), rendered


def _render_annexure_schedule(request: AffidavitGenerationRequest) -> str:
    lines: list[str] = []
    seen_labels: set[str] = set()
    for annexure in request.annexures:
        label = annexure.label.strip()
        normalized_label = label.casefold()
        if normalized_label in seen_labels:
            raise AffidavitInputError(f"duplicate annexure label: {label}")
        seen_labels.add(normalized_label)

        line = f"{label}: {annexure.title.strip()}"
        if annexure.document_date is not None:
            line += f" ({annexure.document_date.isoformat()})"
        if annexure.description and annexure.description.strip():
            line += f" — {annexure.description.strip()}"
        lines.append(line)
    return "\n".join(lines)


def _render_text(template_text: str, values: dict[str, str]) -> str:
    missing_placeholders = sorted(
        key for key in set(PLACEHOLDER_RE.findall(template_text)) if key not in values
    )
    if missing_placeholders:
        raise AffidavitInputError(
            "cannot render template because field(s) are missing: "
            + ", ".join(missing_placeholders)
        )
    return PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template_text).strip()


def _should_include(section, values: dict[str, str]) -> bool:
    if section.include_if_all_present and not all(
        values.get(key, "").strip() for key in section.include_if_all_present
    ):
        return False
    if section.include_if_any_present and not any(
        values.get(key, "").strip() for key in section.include_if_any_present
    ):
        return False
    return True


def generate_affidavit(request: AffidavitGenerationRequest) -> AffidavitGenerationResponse:
    template = _get_template(request.template_id)
    _validate_effective_date(template, request.generation_date)
    fields = _validate_and_normalize_fields(template, request.fields)

    numbered_text, rendered_statements = _render_numbered_statements(request)
    annexure_schedule = _render_annexure_schedule(request)

    values = dict(fields)
    values.update(
        {
            "generation_date": request.generation_date.isoformat(),
            "numbered_statements": numbered_text,
            "statement_count": str(len(rendered_statements)),
            "annexure_schedule": annexure_schedule,
            "annexure_count": str(len(request.annexures)),
        }
    )

    rendered_sections: list[RenderedAffidavitSection] = []
    for section in template.sections:
        if not _should_include(section, values):
            continue
        rendered_sections.append(
            RenderedAffidavitSection(
                id=section.id,
                heading=section.heading,
                body=_render_text(section.body_template, values),
            )
        )

    warnings: list[str] = []
    optional_fields = [field for field in template.fields if not field.required]
    omitted_optional = [field.label for field in optional_fields if field.key not in fields]
    if omitted_optional:
        warnings.append("Optional fields omitted: " + ", ".join(omitted_optional))
    if not request.annexures:
        warnings.append("No annexures were supplied.")

    text_parts = [template.title.upper()]
    for section in rendered_sections:
        if section.heading:
            text_parts.append(section.heading)
        text_parts.append(section.body)

    return AffidavitGenerationResponse(
        template_id=template.id,
        template_version=template.version,
        title=template.title,
        affidavit_type=template.affidavit_type,
        jurisdiction=template.jurisdiction,
        generation_date=request.generation_date,
        sections=rendered_sections,
        statements=rendered_statements,
        annexures=request.annexures,
        rendered_text="\n\n".join(text_parts),
        fields_used=fields,
        warnings=warnings,
        source_note=template.source_note,
        disclaimer=DISCLAIMER,
    )
