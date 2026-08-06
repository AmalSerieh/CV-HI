"""Immutable internal contracts for normalized resumes and scored roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceRecord:
    """A traceable value copied from one exact input JSON path."""

    source: str
    path: str
    value: str
    normalized: str

    def to_public_dict(self) -> dict[str, str]:
        return {"source": self.source, "path": self.path, "value": self.value}


@dataclass(frozen=True)
class NormalizedResumeProfile:
    """Stable profile produced from varying upstream pipeline contracts."""

    summary: str = ""
    skills: tuple[str, ...] = ()
    original_skills: tuple[str, ...] = ()
    experience_titles: tuple[str, ...] = ()
    experience_companies: tuple[str, ...] = ()
    experience_bullets: tuple[str, ...] = ()
    project_names: tuple[str, ...] = ()
    project_descriptions: tuple[str, ...] = ()
    project_technologies: tuple[str, ...] = ()
    education: tuple[str, ...] = ()
    certifications: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    extracted_text: str = ""
    contact: tuple[tuple[str, str], ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    language: str = "unknown"

    def evidence_for(self, source: str) -> tuple[EvidenceRecord, ...]:
        return tuple(item for item in self.evidence if item.source == source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "skills": list(self.skills),
            "original_skills": list(self.original_skills),
            "experience_titles": list(self.experience_titles),
            "experience_companies": list(self.experience_companies),
            "experience_bullets": list(self.experience_bullets),
            "project_names": list(self.project_names),
            "project_descriptions": list(self.project_descriptions),
            "project_technologies": list(self.project_technologies),
            "education": list(self.education),
            "certifications": list(self.certifications),
            "languages": list(self.languages),
            "extracted_text": self.extracted_text,
            "contact": dict(self.contact),
            "metadata": dict(self.metadata),
            "evidence": [item.to_public_dict() for item in self.evidence],
            "language": self.language,
        }


@dataclass(frozen=True)
class RoleScore:
    """Internal finite score and its complete explanation."""

    role_id: str
    title_en: str
    title_ar: str
    confidence: float
    matched_signals: tuple[str, ...] = ()
    score_breakdown: tuple[tuple[str, float], ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "title_en": self.title_en,
            "title_ar": self.title_ar,
            "confidence": self.confidence,
            "matched_signals": list(self.matched_signals),
            "score_breakdown": dict(self.score_breakdown),
            "evidence": [item.to_public_dict() for item in self.evidence],
        }
