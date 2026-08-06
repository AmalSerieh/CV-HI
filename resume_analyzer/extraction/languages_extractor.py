from __future__ import annotations

import re
from typing import Any


class LanguagesExtractor:
    """Evidence-preserving language extraction with per-language proficiency."""

    LANGUAGE_NAMES = {
        "afrikaans", "albanian", "amharic", "arabic", "armenian",
        "azerbaijani", "basque", "belarusian", "bengali", "bosnian",
        "bulgarian", "burmese", "catalan", "cebuano", "chinese",
        "mandarin", "cantonese", "croatian", "czech", "danish",
        "dutch", "english", "estonian", "farsi", "persian", "filipino",
        "finnish", "french", "georgian", "german", "greek", "gujarati",
        "haitian creole", "hausa", "hebrew", "hindi", "hungarian",
        "icelandic", "igbo", "indonesian", "irish", "italian", "japanese",
        "javanese", "kannada", "kazakh", "khmer", "korean", "kurdish",
        "lao", "latvian", "lithuanian", "macedonian", "malay", "malayalam",
        "maltese", "marathi", "mongolian", "nepali", "norwegian", "odia",
        "pashto", "polish", "portuguese", "punjabi", "romanian", "russian",
        "serbian", "sinhala", "slovak", "slovenian", "somali", "spanish",
        "swahili", "swedish", "tamil", "telugu", "thai", "turkish",
        "ukrainian", "urdu", "uzbek", "vietnamese", "welsh", "xhosa",
        "yoruba", "zulu",
    }

    CEFR_MAP = {
        "A1": ("Beginner", 1),
        "A2": ("Elementary", 2),
        "B1": ("Intermediate", 3),
        "B2": ("Upper Intermediate", 4),
        "C1": ("Advanced", 5),
        "C2": ("Proficient", 6),
    }

    WORD_LEVELS = {
        "native": ("Native", 7, None),
        "mother tongue": ("Native", 7, None),
        "bilingual": ("Bilingual", 7, None),
        "fluent": ("Fluent", 6, None),
        "professional": ("Professional", 5, None),
        "advanced": ("Advanced", 5, None),
        "upper intermediate": ("Upper Intermediate", 4, None),
        "intermediate": ("Intermediate", 3, None),
        "elementary": ("Elementary", 2, None),
        "basic": ("Basic", 1, None),
        "beginner": ("Beginner", 1, None),
    }

    PAIR_RE = re.compile(
        r"(?ix)\b"
        r"(?P<language>[A-Za-z][A-Za-z .'-]{1,28}?)"
        r"\s*(?:[-–—:|]|\()\s*"
        r"(?P<level>A1|A2|B1|B2|C1|C2|native|mother\s+tongue|"
        r"bilingual|fluent|professional|advanced|upper\s+intermediate|"
        r"intermediate|elementary|basic|beginner)\s*\)?"
    )

    def _sections(self, payload: dict) -> dict:
        sections = payload.get("sections", {}) if isinstance(payload, dict) else {}
        return sections if isinstance(sections, dict) else {}

    def _section_text(self, sections: dict, name: str) -> str:
        section = sections.get(name, {})
        if isinstance(section, dict):
            return str(section.get("content") or "")
        return str(section or "")

    def _candidate_texts(self, payload: dict) -> list[tuple[str, str]]:
        sections = self._sections(payload)
        output: list[tuple[str, str]] = []
        language_text = self._section_text(sections, "languages")
        if language_text:
            output.append(("languages", language_text))

        # Visual DOCX templates can temporarily misattribute a row. Scan the
        # complete text only as a fallback and retain source evidence.
        full_text = str(
            payload.get("cleaned_text")
            or payload.get("text")
            or payload.get("raw_text")
            or ""
        )
        if full_text and full_text != language_text:
            output.append(("document_fallback", full_text))
        return output

    def _canonical_language(self, value: str) -> str | None:
        clean = re.sub(r"\s+", " ", value.strip())
        # Remove common prefixes accidentally captured from a preceding pair.
        clean = re.sub(
            r"(?i)^(?:and|or|languages?|proficiency|skills?)\s+",
            "",
            clean,
        ).strip()
        lowered = clean.casefold()
        if lowered not in self.LANGUAGE_NAMES:
            # When regex starts too early, keep the last 1-2 words if they form
            # a known language name.
            words = lowered.split()
            for width in (2, 1):
                tail = " ".join(words[-width:])
                if tail in self.LANGUAGE_NAMES:
                    lowered = tail
                    break
            else:
                return None
        return " ".join(word.capitalize() for word in lowered.split())

    def _level(self, raw: str) -> tuple[str, int, str | None]:
        clean = re.sub(r"\s+", " ", raw.strip()).upper()
        if clean in self.CEFR_MAP:
            label, rank = self.CEFR_MAP[clean]
            return label, rank, clean
        label, rank, cefr = self.WORD_LEVELS.get(
            clean.casefold(),
            ("Unspecified", 0, None),
        )
        return label, rank, cefr

    def extract(self, payload: dict) -> dict:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        raw_language_text = ""

        for source_section, text in self._candidate_texts(payload):
            for line in text.splitlines():
                matches = list(self.PAIR_RE.finditer(line))
                if not matches:
                    continue
                if not raw_language_text:
                    raw_language_text = line.strip()
                for match in matches:
                    language = self._canonical_language(match.group("language"))
                    if not language:
                        continue
                    key = language.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    proficiency, rank, cefr = self._level(match.group("level"))
                    records.append({
                        "language": language,
                        "proficiency": proficiency,
                        "proficiency_rank": rank,
                        "cefr": cefr,
                        "test_score": None,
                        "evidence": line.strip(),
                        "source_section": source_section,
                        "confidence": 96 if source_section == "languages" else 82,
                    })

            if records and source_section == "languages":
                break

        count = len(records)
        if not count:
            return {
                "languages": [],
                "count": 0,
                "has_languages": False,
                "native_languages": [],
                "fluent_languages": [],
                "language_score": 0,
                "recommendations": [],
                "raw_languages_text": raw_language_text,
                "spacy_available": False,
                "mode": "pairwise_rule_extraction",
                "status": "not_present",
                "applicable": False,
            }

        explicit_levels = sum(bool(item.get("cefr") or item.get("proficiency") != "Unspecified") for item in records)
        score = min(100, 55 + count * 10 + explicit_levels * 3)
        native = [item["language"] for item in records if item["proficiency_rank"] >= 7]
        fluent = [item["language"] for item in records if item["proficiency_rank"] >= 5]

        return {
            "languages": records,
            "count": count,
            "has_languages": True,
            "native_languages": native,
            "fluent_languages": fluent,
            "language_score": score,
            "recommendations": [{
                "severity": "good",
                "type": "complete",
                "message": "Languages section looks complete.",
            }],
            "raw_languages_text": raw_language_text,
            "spacy_available": False,
            "mode": "pairwise_language_level_extraction",
            "status": "present",
            "applicable": True,
        }

    def extract_languages(self, payload: dict) -> dict:
        return self.extract(payload)
