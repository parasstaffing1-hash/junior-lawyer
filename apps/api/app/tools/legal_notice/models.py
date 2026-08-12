from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FieldKind(str, Enum):
    TEXT = "text"
    MULTILINE = "multiline"
    DATE = "date"
    MONEY = "money"
    INTEGER = "integer"


class TemplateField(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    kind: FieldKind = FieldKind.TEXT
    required: bool = False
    max_length: int = Field(default=500, ge=1, le=10000)
    help_text: str | None = Field(default=None, max_length=500)


class TemplateSection(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$", min_length=1, max_length=80)
    heading: str | None = Field(default=None, max_length=200)
    body_template: str = Field(min_length=1, max_length=20000)
    include_if_all_present: list[str] = Field(default_factory=list)
    include_if_any_present: list[str] = Field(default_factory=list)


class LegalNoticeTemplate(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    notice_type: str = Field(min_length=1, max_length=120)
    jurisdiction: str = Field(min_length=1, max_length=160)
    effective_from: date
    effective_to: date | None = None
    fields: list[TemplateField]
    subject_template: str = Field(min_length=1, max_length=1000)
    sections: list[TemplateSection] = Field(min_length=1)
    source_note: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_template(self) -> "LegalNoticeTemplate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")

        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("template field keys must be unique")

        known = set(keys) | {"generation_date"}
        for section in self.sections:
            for key in section.include_if_all_present + section.include_if_any_present:
                if key not in known:
                    raise ValueError(
                        f"section '{section.id}' references unknown conditional field '{key}'"
                    )
        return self


class LegalNoticeGenerationRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=120)
    generation_date: date
    fields: dict[str, str] = Field(default_factory=dict)


class RenderedNoticeSection(BaseModel):
    id: str
    heading: str | None
    body: str


class LegalNoticeGenerationResponse(BaseModel):
    template_id: str
    template_version: str
    title: str
    notice_type: str
    jurisdiction: str
    generation_date: date
    subject: str
    sections: list[RenderedNoticeSection]
    rendered_text: str
    fields_used: dict[str, str]
    warnings: list[str]
    source_note: str
    disclaimer: str


class LegalNoticeTemplateSummary(BaseModel):
    id: str
    version: str
    title: str
    notice_type: str
    jurisdiction: str
    effective_from: date
    effective_to: date | None
    fields: list[TemplateField]
    source_note: str
