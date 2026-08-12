from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class ExistingTextPolicy(str, Enum):
    SKIP = "skip"
    FORCE = "force"
    ERROR = "error"


class OcrPagePlanStatus(str, Enum):
    OCR = "ocr"
    SKIP_EXISTING_TEXT = "skip_existing_text"
    SKIP_NOT_SELECTED = "skip_not_selected"


class OcrOptions(BaseModel):
    language: str = Field(default="eng", min_length=2, max_length=64)
    dpi: int = Field(default=300, ge=150, le=400)
    psm: int = Field(default=3, ge=1, le=13)
    page_numbers: list[int] | None = Field(default=None, max_length=500)
    existing_text_policy: ExistingTextPolicy = ExistingTextPolicy.SKIP
    existing_text_min_chars: int = Field(default=20, ge=0, le=10_000)
    timeout_per_page_seconds: int = Field(default=60, ge=5, le=180)

    @field_validator("language")
    @classmethod
    def validate_language_shape(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("language cannot be empty")
        parts = value.split("+")
        if any(not part.replace("_", "").replace("-", "").isalnum() for part in parts):
            raise ValueError("language must contain Tesseract language codes separated by '+'")
        return value

    @model_validator(mode="after")
    def validate_pages(self) -> "OcrOptions":
        if self.page_numbers is not None:
            if not self.page_numbers:
                raise ValueError("page_numbers cannot be empty; use null to consider every page")
            if any(number < 1 for number in self.page_numbers):
                raise ValueError("page_numbers are 1-based and must all be >= 1")
            if len(set(self.page_numbers)) != len(self.page_numbers):
                raise ValueError("page_numbers cannot contain duplicates")
        return self


class OcrPagePlan(BaseModel):
    page_number: int
    existing_text_chars: int
    status: OcrPagePlanStatus


class OcrAnalysisResponse(BaseModel):
    original_filename: str | None
    page_count: int
    selected_page_count: int
    pages_planned_for_ocr: int
    pages_with_existing_text: int
    pages: list[OcrPagePlan]
    tesseract_available: bool
    requested_languages: list[str]
    missing_languages: list[str]
    warnings: list[str]
    disclaimer: str


class OcrPageResult(BaseModel):
    page_number: int
    processed: bool
    skipped_reason: str | None = None
    word_count: int = 0
    mean_confidence: float | None = None
    extracted_text: str = ""


class OcrRunReport(BaseModel):
    original_filename: str | None
    page_count: int
    processed_page_count: int
    skipped_page_count: int
    total_word_count: int
    mean_confidence: float | None
    output_sha256: str
    pages: list[OcrPageResult]
    warnings: list[str]
    disclaimer: str
