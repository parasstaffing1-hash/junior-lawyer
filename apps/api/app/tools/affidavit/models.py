from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class AffidavitFieldKind(str, Enum):
    TEXT = "text"
    MULTILINE = "multiline"
    DATE = "date"
    INTEGER = "integer"


class AffidavitTemplateField(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    kind: AffidavitFieldKind = AffidavitFieldKind.TEXT
    required: bool = False
    max_length: int = Field(default=500, ge=1, le=10000)
    help_text: str | None = Field(default=None, max_length=500)


class AffidavitTemplateSection(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$", min_length=1, max_length=80)
    heading: str | None = Field(default=None, max_length=200)
    body_template: str = Field(min_length=1, max_length=30000)
    include_if_all_present: list[str] = Field(default_factory=list)
    include_if_any_present: list[str] = Field(default_factory=list)


class AffidavitTemplate(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    affidavit_type: str = Field(min_length=1, max_length=120)
    jurisdiction: str = Field(min_length=1, max_length=160)
    effective_from: date
    effective_to: date | None = None
    fields: list[AffidavitTemplateField]
    sections: list[AffidavitTemplateSection] = Field(min_length=1)
    source_note: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_template(self) -> "AffidavitTemplate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")

        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("template field keys must be unique")

        built_ins = {
            "generation_date",
            "numbered_statements",
            "statement_count",
            "annexure_schedule",
            "annexure_count",
        }
        known = set(keys) | built_ins
        for section in self.sections:
            for key in section.include_if_all_present + section.include_if_any_present:
                if key not in known:
                    raise ValueError(
                        f"section '{section.id}' references unknown conditional field '{key}'"
                    )
        return self


class AffidavitStatement(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    source_reference: str | None = Field(default=None, max_length=500)


class AnnexureReference(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    document_date: date | None = None
    description: str | None = Field(default=None, max_length=1500)


class AffidavitGenerationRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=120)
    generation_date: date
    fields: dict[str, str] = Field(default_factory=dict)
    statements: list[AffidavitStatement] = Field(min_length=1, max_length=250)
    annexures: list[AnnexureReference] = Field(default_factory=list, max_length=100)


class RenderedAffidavitStatement(BaseModel):
    number: int
    text: str
    source_reference: str | None


class RenderedAffidavitSection(BaseModel):
    id: str
    heading: str | None
    body: str


class AffidavitGenerationResponse(BaseModel):
    template_id: str
    template_version: str
    title: str
    affidavit_type: str
    jurisdiction: str
    generation_date: date
    sections: list[RenderedAffidavitSection]
    statements: list[RenderedAffidavitStatement]
    annexures: list[AnnexureReference]
    rendered_text: str
    fields_used: dict[str, str]
    warnings: list[str]
    source_note: str
    disclaimer: str


class AffidavitTemplateSummary(BaseModel):
    id: str
    version: str
    title: str
    affidavit_type: str
    jurisdiction: str
    effective_from: date
    effective_to: date | None
    fields: list[AffidavitTemplateField]
    source_note: str
