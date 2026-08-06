"""Stable ATS issue/strength construction and evidence validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from resume_analyzer.schemas import ATSCategory, ATSIssue, ATSStrength, PipelineReport

from .config import (
    CATEGORY_ORDER,
    ISSUE_DEFINITIONS,
    SEVERITY_ORDER,
    STRENGTH_TITLES,
)


def detect_language(text: str) -> str:
    arabic = sum("\u0600" <= char <= "\u06ff" for char in text)
    latin = sum(char.isascii() and char.isalpha() for char in text)
    if arabic and latin:
        total = arabic + latin
        if arabic / total >= 0.75:
            return "ar"
        if latin / total >= 0.75:
            return "en"
        return "mixed"
    if arabic:
        return "ar"
    if latin:
        return "en"
    return "unknown"


class EvidenceLookup:
    def __init__(self, report: PipelineReport) -> None:
        self._records = {item.id: item for item in report.evidence}
        self._by_path: dict[str, list[str]] = {}
        for item in report.evidence:
            self._by_path.setdefault(item.field_path, []).append(item.id)

    @property
    def known_ids(self) -> set[str]:
        return set(self._records)

    def paths(self, *paths: str) -> list[str]:
        output: list[str] = []
        for requested in paths:
            for path, values in self._by_path.items():
                if (
                    path == requested
                    or path.startswith(f"{requested}.")
                    or path.startswith(f"{requested}[")
                ):
                    output.extend(values)
        return list(dict.fromkeys(output))

    def pages(self, evidence_ids: list[str]) -> list[int]:
        return sorted(
            {
                item.source.page
                for evidence_id in evidence_ids
                if (item := self._records.get(evidence_id)) is not None
                and item.source.page is not None
            }
        )


@dataclass(frozen=True)
class IssueDraft:
    code: str
    evidence_ids: tuple[str, ...]
    source: str
    confidence: float = 0.9
    pages: tuple[int, ...] = ()


@dataclass(frozen=True)
class StrengthDraft:
    code: str
    category: ATSCategory
    evidence_ids: tuple[str, ...]
    source: str
    confidence: float = 0.9


@dataclass
class AnalyzerFindings:
    issues: list[IssueDraft] = field(default_factory=list)
    strengths: list[StrengthDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: AnalyzerFindings) -> None:
        self.issues.extend(other.issues)
        self.strengths.extend(other.strengths)
        self.warnings.extend(other.warnings)


class IssueBuilder:
    def __init__(self, report: PipelineReport, *, language: str) -> None:
        self.lookup = EvidenceLookup(report)
        self.language = language
        self.warnings: list[str] = []

    def build_issues(self, drafts: list[IssueDraft]) -> list[ATSIssue]:
        selected: dict[tuple[str, tuple[str, ...], tuple[int, ...]], IssueDraft] = {}
        for draft in drafts:
            definition = ISSUE_DEFINITIONS[draft.code]
            evidence_ids = tuple(
                sorted({value for value in draft.evidence_ids if value in self.lookup.known_ids})
            )
            if not evidence_ids:
                self.warnings.append(f"cannot_verify_evidence:{draft.code}")
                continue
            pages = tuple(sorted(set(draft.pages or tuple(self.lookup.pages(list(evidence_ids))))))
            key = (draft.code, evidence_ids, pages)
            current = selected.get(key)
            if current is None or draft.confidence > current.confidence:
                selected[key] = IssueDraft(
                    draft.code,
                    evidence_ids,
                    draft.source,
                    max(0.0, min(1.0, draft.confidence)),
                    pages,
                )

        ordered = sorted(
            selected.values(),
            key=lambda item: (
                CATEGORY_ORDER[ISSUE_DEFINITIONS[item.code].category],
                SEVERITY_ORDER[ISSUE_DEFINITIONS[item.code].severity],
                item.code,
                item.evidence_ids,
                item.pages,
            ),
        )
        output: list[ATSIssue] = []
        for draft in ordered:
            definition = ISSUE_DEFINITIONS[draft.code]
            localized = definition.ar if self.language == "ar" else definition.en
            material = "|".join((draft.code, *draft.evidence_ids, *(str(p) for p in draft.pages)))
            issue_id = f"ats-issue-{hashlib.sha256(material.encode()).hexdigest()[:12]}"
            output.append(
                ATSIssue(
                    issue_id=issue_id,
                    code=draft.code,
                    category=definition.category,
                    severity=definition.severity,
                    title=localized[0],
                    problem=localized[1],
                    suggestion=localized[2],
                    evidence_ids=list(draft.evidence_ids),
                    penalty=definition.penalty,
                    confidence=draft.confidence,
                    pages=list(draft.pages),
                    source=draft.source,
                )
            )
        return output

    def build_strengths(self, drafts: list[StrengthDraft]) -> list[ATSStrength]:
        output: list[ATSStrength] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for draft in sorted(drafts, key=lambda item: (CATEGORY_ORDER[item.category], item.code)):
            evidence_ids = tuple(
                sorted({value for value in draft.evidence_ids if value in self.lookup.known_ids})
            )
            key = (draft.code, evidence_ids)
            if not evidence_ids or key in seen:
                continue
            seen.add(key)
            titles = STRENGTH_TITLES[draft.code]
            output.append(
                ATSStrength(
                    code=draft.code,
                    category=draft.category,
                    title=titles[1] if self.language == "ar" else titles[0],
                    evidence_ids=list(evidence_ids),
                    confidence=max(0.0, min(1.0, draft.confidence)),
                    source=draft.source,
                )
            )
        return output
