import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.tools.legal_notice.models import (
    LegalNoticeGenerationRequest,
    LegalNoticeGenerationResponse,
    LegalNoticeTemplate,
    LegalNoticeTemplateSummary,
    RenderedNoticeSection,
)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
DISCLAIMER = (
    "This output is generated from a deterministic template and is not legal advice. "
    "A qualified lawyer should verify the facts, governing law, required service method, "
    "notice period, forum, and wording before use."
)


class LegalNoticeError(ValueError):
    pass


class LegalNoticeTemplateNotFoundError(LegalNoticeError):
    pass


class LegalNoticeTemplateDateError(LegalNoticeError):
    pass


class LegalNoticeInputError(LegalNoticeError):
    pass


@lru_cache(maxsize=1)
def _load_templates() -> dict[str, LegalNoticeTemplate]:
    templates: dict[str, LegalNoticeTemplate] = {}
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        template = LegalNoticeTemplate.model_validate(payload)
        if template.id in templates:
            raise RuntimeError(f"duplicate legal notice template id: {template.id}")
        templates[template.id] = template
    return templates


def clear_template_cache() -> None:
    _load_templates.cache_clear()


def list_templates() -> list[LegalNoticeTemplateSummary]:
    return [
        LegalNoticeTemplateSummary(
            id=item.id,
            version=item.version,
            title=item.title,
            notice_type=item.notice_type,
            jurisdiction=item.jurisdiction,
            effective_from=item.effective_from,
            effective_to=item.effective_to,
            fields=item.fields,
            source_note=item.source_note,
        )
        for item in sorted(_load_templates().values(), key=lambda value: value.id)
    ]


def _get_template(template_id: str) -> LegalNoticeTemplate:
    try:
        return _load_templates()[template_id]
    except KeyError as exc:
        raise LegalNoticeTemplateNotFoundError(
            f"legal notice template '{template_id}' was not found"
        ) from exc


def _validate_effective_date(template: LegalNoticeTemplate, generation_date: date) -> None:
    if generation_date < template.effective_from:
        raise LegalNoticeTemplateDateError(
            f"template '{template.id}' is effective from {template.effective_from.isoformat()}"
        )
    if template.effective_to is not None and generation_date > template.effective_to:
        raise LegalNoticeTemplateDateError(
            f"template '{template.id}' expired on {template.effective_to.isoformat()}"
        )


def _validate_and_normalize_fields(
    template: LegalNoticeTemplate,
    supplied_fields: dict[str, str],
) -> dict[str, str]:
    definitions = {field.key: field for field in template.fields}
    unknown = sorted(set(supplied_fields) - set(definitions))
    if unknown:
        raise LegalNoticeInputError(f"unknown template field(s): {', '.join(unknown)}")

    normalized: dict[str, str] = {}
    for key, raw_value in supplied_fields.items():
        value = raw_value.strip()
        definition = definitions[key]
        if len(value) > definition.max_length:
            raise LegalNoticeInputError(
                f"field '{key}' exceeds maximum length of {definition.max_length}"
            )
        if value:
            normalized[key] = value

    missing = [field.key for field in template.fields if field.required and field.key not in normalized]
    if missing:
        raise LegalNoticeInputError(f"missing required field(s): {', '.join(missing)}")

    return normalized


def _render_text(template_text: str, values: dict[str, str]) -> str:
    missing_placeholders = sorted(
        key for key in set(PLACEHOLDER_RE.findall(template_text)) if key not in values
    )
    if missing_placeholders:
        raise LegalNoticeInputError(
            "cannot render template because field(s) are missing: "
            + ", ".join(missing_placeholders)
        )

    return PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template_text).strip()


def _should_include(section, values: dict[str, str]) -> bool:
    if section.include_if_all_present and not all(
        key in values for key in section.include_if_all_present
    ):
        return False
    if section.include_if_any_present and not any(
        key in values for key in section.include_if_any_present
    ):
        return False
    return True


def generate_legal_notice(
    request: LegalNoticeGenerationRequest,
) -> LegalNoticeGenerationResponse:
    template = _get_template(request.template_id)
    _validate_effective_date(template, request.generation_date)
    fields = _validate_and_normalize_fields(template, request.fields)

    values = dict(fields)
    values["generation_date"] = request.generation_date.isoformat()

    subject = _render_text(template.subject_template, values)
    rendered_sections: list[RenderedNoticeSection] = []
    warnings: list[str] = []

    for section in template.sections:
        if not _should_include(section, values):
            continue
        rendered_sections.append(
            RenderedNoticeSection(
                id=section.id,
                heading=section.heading,
                body=_render_text(section.body_template, values),
            )
        )

    optional_fields = [field for field in template.fields if not field.required]
    omitted_optional = [field.label for field in optional_fields if field.key not in fields]
    if omitted_optional:
        warnings.append("Optional fields omitted: " + ", ".join(omitted_optional))

    text_parts = [template.title.upper(), f"Date: {request.generation_date.isoformat()}", f"Subject: {subject}"]
    for section in rendered_sections:
        if section.heading:
            text_parts.append(section.heading)
        text_parts.append(section.body)

    return LegalNoticeGenerationResponse(
        template_id=template.id,
        template_version=template.version,
        title=template.title,
        notice_type=template.notice_type,
        jurisdiction=template.jurisdiction,
        generation_date=request.generation_date,
        subject=subject,
        sections=rendered_sections,
        rendered_text="\n\n".join(text_parts),
        fields_used=fields,
        warnings=warnings,
        source_note=template.source_note,
        disclaimer=DISCLAIMER,
    )
