import re
from dataclasses import dataclass

from app.services.language.legal_dictionary import HINGLISH_TERM_MAP


DEVANAGARI_START = ord("\u0900")
DEVANAGARI_END = ord("\u097f")
ROMAN_WORD_RE = re.compile(r"[A-Za-z]+")
COMMON_HINGLISH_MARKERS = {
    "hai", "hain", "me", "mein", "ka", "ki", "ke", "ko", "se", "aur",
    "kya", "kab", "kaise", "liye", "wala", "wali", "par", "karna", "karo",
}


@dataclass(frozen=True, slots=True)
class LanguageScore:
    language: str
    devanagari_ratio: float
    latin_ratio: float


def _looks_like_hinglish(text: str) -> bool:
    words = [word.casefold() for word in ROMAN_WORD_RE.findall(text)]
    legal_hits = sum(word in HINGLISH_TERM_MAP for word in words)
    common_hits = sum(word in COMMON_HINGLISH_MARKERS for word in words)
    return legal_hits >= 1 or common_hits >= 2


def detect_language(text: str) -> LanguageScore:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return LanguageScore("unknown", 0.0, 0.0)

    devanagari = sum(DEVANAGARI_START <= ord(char) <= DEVANAGARI_END for char in letters)
    latin = sum("a" <= char.lower() <= "z" for char in letters)
    total = len(letters)

    devanagari_ratio = devanagari / total
    latin_ratio = latin / total

    if devanagari_ratio >= 0.15 and latin_ratio >= 0.15:
        language = "mixed"
    elif devanagari_ratio >= 0.70:
        language = "hi"
    elif latin_ratio >= 0.70 and _looks_like_hinglish(text):
        language = "hinglish"
    elif latin_ratio >= 0.70:
        language = "en"
    else:
        language = "unknown"

    return LanguageScore(
        language=language,
        devanagari_ratio=round(devanagari_ratio, 4),
        latin_ratio=round(latin_ratio, 4),
    )
