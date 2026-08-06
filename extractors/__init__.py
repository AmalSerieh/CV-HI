"""Deprecated lazy compatibility exports for :mod:`resume_analyzer.extraction`."""

from __future__ import annotations

import warnings
from importlib import import_module
from typing import Any

warnings.warn(
    "Import extraction capabilities from resume_analyzer.extraction.",
    DeprecationWarning,
    stacklevel=2,
)


_EXPORTS = {
    "TextExtractor": ("resume_analyzer.extraction.text_extractor", "TextExtractor"),
    "TextCleaner": ("resume_analyzer.extraction.text_cleaner", "TextCleaner"),
    "ContactExtractor": ("resume_analyzer.extraction.contact_extractor", "ContactExtractor"),
    "SectionExtractor": ("resume_analyzer.extraction.section_extractor", "SectionExtractor"),
    "SkillsExtractor": ("resume_analyzer.extraction.skills_extractor", "SkillsExtractor"),
    "EducationExtractor": (
        "resume_analyzer.extraction.education_extractor",
        "EducationExtractor",
    ),
    "ExperienceExtractor": (
        "resume_analyzer.extraction.experience_extractor",
        "ExperienceExtractor",
    ),
    "ProjectsExtractor": ("resume_analyzer.extraction.projects_extractor", "ProjectsExtractor"),
    "LanguagesExtractor": (
        "resume_analyzer.extraction.languages_extractor",
        "LanguagesExtractor",
    ),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))


__all__ = sorted(_EXPORTS)
