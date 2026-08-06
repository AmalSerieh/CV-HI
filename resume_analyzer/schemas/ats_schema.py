"""Strict canonical contracts for ATS analysis."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .pipeline_schema import StrictModel

ATSCategory = Literal[
    "extraction",
    "structure",
    "layout",
    "formatting",
    "content",
    "contact",
    "consistency",
    "accessibility",
    "job_match",
]
ATSSeverity = Literal["critical", "high", "medium", "low", "info"]
ATSStatus = Literal["complete", "partial", "failed", "not_run", "unavailable"]


class ATSIssue(StrictModel):
    issue_id: str = Field(pattern=r"^ats-issue-[a-f0-9]{12}$")
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    category: ATSCategory
    severity: ATSSeverity
    title: str = Field(min_length=1, max_length=200)
    problem: str = Field(min_length=1, max_length=1_500)
    suggestion: str = Field(min_length=1, max_length=2_000)
    evidence_ids: list[str] = Field(min_length=1)
    penalty: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    pages: list[int] = Field(default_factory=list)
    source: str = Field(min_length=1)

    @field_validator("evidence_ids", "pages")
    @classmethod
    def unique_values(cls, values: list):
        return list(dict.fromkeys(values))

    @field_validator("pages")
    @classmethod
    def valid_pages(cls, values: list[int]) -> list[int]:
        if any(value < 1 for value in values):
            raise ValueError("ATS issue pages must be positive")
        return values


class ATSStrength(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    category: ATSCategory
    title: str = Field(min_length=1, max_length=200)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(min_length=1)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))


class ATSScoreBreakdown(StrictModel):
    text_extractability: int = Field(default=0, ge=0, le=15)
    section_structure: int = Field(default=0, ge=0, le=20)
    layout_safety: int = Field(default=0, ge=0, le=20)
    formatting_consistency: int = Field(default=0, ge=0, le=15)
    content_clarity: int = Field(default=0, ge=0, le=15)
    contact_accessibility: int = Field(default=0, ge=0, le=5)
    consistency: int = Field(default=0, ge=0, le=10)

    def total(self) -> int:
        return sum(self.model_dump().values())


class MissingKeywordSuggestion(StrictModel):
    phrase: str = Field(min_length=1, max_length=120)
    normalized: str = Field(min_length=1, max_length=120)
    suggestion: str = Field(min_length=1, max_length=300)
    conditional: Literal[True] = True


class JobMatchResult(StrictModel):
    status: Literal["complete", "not_run", "cannot_verify", "failed"] = "not_run"
    match_score: int | None = Field(default=None, ge=0, le=100)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[MissingKeywordSuggestion] = Field(default_factory=list)
    transferable_signals: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    method: str = "deterministic_keyword_and_phrase_match_v1"

    @field_validator("matched_keywords", "transferable_signals", "evidence_ids")
    @classmethod
    def unique_lists(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def score_matches_status(self) -> JobMatchResult:
        if self.status == "complete" and self.match_score is None:
            raise ValueError("A complete job match requires match_score")
        if self.status != "complete" and self.match_score is not None:
            raise ValueError("Only a complete job match may include match_score")
        return self


class ATSResult(StrictModel):
    status: ATSStatus = "not_run"
    language: Literal["en", "ar", "mixed", "unknown"] = "unknown"
    ats_compatibility_score: int | None = Field(default=None, ge=0, le=100)
    score_label: Literal["excellent", "good", "fair", "poor", "unavailable"] = "unavailable"
    score_method: str = "deterministic_ats_compatibility_v1"
    score_breakdown: ATSScoreBreakdown = Field(default_factory=ATSScoreBreakdown)
    issues: list[ATSIssue] = Field(default_factory=list)
    strengths: list[ATSStrength] = Field(default_factory=list)
    job_match: JobMatchResult = Field(default_factory=JobMatchResult)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    interpretation: str = (
        "ATS compatibility was not evaluated. This score is not a hiring prediction."
    )
    parsing_integrity_context: str | None = None
    provider: str = "deterministic_rules"

    @model_validator(mode="after")
    def validate_result(self) -> ATSResult:
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("ATS issue IDs must be unique")
        issue_keys = [
            (item.code, tuple(item.evidence_ids), tuple(item.pages)) for item in self.issues
        ]
        if len(issue_keys) != len(set(issue_keys)):
            raise ValueError("Duplicate ATS issues are not allowed")
        if self.status in {"complete", "partial"}:
            if self.ats_compatibility_score is None:
                raise ValueError("Completed ATS analysis requires a compatibility score")
            if self.score_breakdown.total() != self.ats_compatibility_score:
                raise ValueError("ATS score must equal the score breakdown total")
            if self.score_label == "unavailable":
                raise ValueError("Completed ATS analysis requires a score label")
        elif self.ats_compatibility_score is not None:
            raise ValueError("Unavailable ATS analysis cannot expose a score")
        return self
