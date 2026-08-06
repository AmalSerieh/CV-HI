"""Small Unicode-safe text helpers used by normalization and scoring."""

from __future__ import annotations

import re
import unicodedata

_ARABIC_DIACRITICS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_DASHES = re.compile("[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]")
_WHITESPACE = re.compile(r"\s+")
_ARABIC_CHAR = re.compile(r"[\u0600-\u06ff]")
_LATIN_CHAR = re.compile(r"[A-Za-z]")
_ARABIC_TRANSLATION: dict[int, str] = {
    ord("أ"): "ا",
    ord("إ"): "ا",
    ord("آ"): "ا",
    ord("ٱ"): "ا",
    ord("ى"): "ي",
}


def normalize_text(value: str | None) -> str:
    """Normalize English/Arabic text without translating or losing tech marks."""

    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("text values must be strings or null")

    text = unicodedata.normalize("NFKC", value)
    text = _DASHES.sub("-", text)
    text = text.replace("ـ", "")
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(_ARABIC_TRANSLATION)
    return _WHITESPACE.sub(" ", text.casefold()).strip()


def phrase_in_text(phrase: str, text: str) -> bool:
    """Match normalized phrases on word-like boundaries."""

    needle = normalize_text(phrase)
    haystack = normalize_text(text)
    if not needle or not haystack:
        return False
    pattern = rf"(?<!\w){re.escape(needle)}(?!\w)"
    return re.search(pattern, haystack, flags=re.UNICODE) is not None


def unique_normalized(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Return non-empty values de-duplicated by normalized spelling."""

    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(value.strip())
    return tuple(output)


def detect_language(values: list[str] | tuple[str, ...]) -> str:
    text = " ".join(value for value in values if isinstance(value, str))
    arabic = len(_ARABIC_CHAR.findall(text))
    latin = len(_LATIN_CHAR.findall(text))
    if arabic and latin:
        return "mixed"
    if arabic:
        return "ar"
    if latin:
        return "en"
    return "unknown"
