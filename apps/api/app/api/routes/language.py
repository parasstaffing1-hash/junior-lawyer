from fastapi import APIRouter

from app.schemas.language import LanguageAnalyzeRequest, LanguageAnalyzeResponse, LegalReference
from app.services.language.detector import detect_language
from app.services.language.normalizer import extract_legal_references, normalize_legal_text

router = APIRouter(prefix="/language", tags=["language"])


@router.post("/analyze", response_model=LanguageAnalyzeResponse)
async def analyze_language(payload: LanguageAnalyzeRequest) -> LanguageAnalyzeResponse:
    score = detect_language(payload.text)
    refs = extract_legal_references(payload.text)

    return LanguageAnalyzeResponse(
        language=score.language,
        devanagari_ratio=score.devanagari_ratio,
        latin_ratio=score.latin_ratio,
        normalized_text=normalize_legal_text(payload.text),
        legal_references=[
            LegalReference(
                raw=ref.raw,
                normalized_type=ref.normalized_type,
                number=ref.number,
                canonical=ref.canonical,
            )
            for ref in refs
        ],
    )
