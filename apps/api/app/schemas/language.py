from pydantic import BaseModel, Field


class LanguageAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


class LegalReference(BaseModel):
    raw: str
    normalized_type: str
    number: str
    canonical: str


class LanguageAnalyzeResponse(BaseModel):
    language: str
    devanagari_ratio: float
    latin_ratio: float
    normalized_text: str
    legal_references: list[LegalReference]
