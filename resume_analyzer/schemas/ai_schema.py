"""Strict contracts for the recommendation subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .pipeline_schema import StrictModel

RecommendationArea = Literal[
    "contact",
    "summary",
    "skills",
    "education",
    "experience",
    "projects",
    "languages",
    "certifications",
    "target_role",
    "general",
]
RecommendationSeverity = Literal["low", "medium", "high", "critical", "good"]
RecommendationSource = Literal["ai", "hybrid", "fallback"]


class AIRecommendation(StrictModel):
    """One evidence-grounded, actionable recommendation."""

    id: str = Field(pattern=r"^rec-[a-z0-9][a-z0-9-]*$")
    area: RecommendationArea
    severity: RecommendationSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str = Field(min_length=1, max_length=160)
    problem: str = Field(min_length=1, max_length=1_000)
    suggestion: str = Field(min_length=1, max_length=2_000)
    evidence_ids: list[str] = Field(min_length=1)
    source: RecommendationSource
    conditional: bool = False

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence_ids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("Every recommendation must reference evidence_ids")
        return list(dict.fromkeys(cleaned))


class RecommendationBatch(StrictModel):
    """Validated recommendation output and its actual generation method."""

    schema_version: str = "1.0.0"
    provider: str
    model: str | None = None
    source: RecommendationSource
    recommendations: list[AIRecommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# Compatibility models retained for callers of the former AI schema. Resume
# rewriting remains a separate capability.
class SummaryRewrite(StrictModel):
    original: str
    rewritten: str
    evidence_ids: list[str] = Field(min_length=1)


class ExperienceBulletRewrite(StrictModel):
    original: str
    rewritten: str
    evidence_ids: list[str] = Field(min_length=1)


class AIRewrites(StrictModel):
    summary: SummaryRewrite | None = None
    experience_bullets: list[ExperienceBulletRewrite] = Field(default_factory=list)


class AIModelResponse(RecommendationBatch):
    """Backward-compatible name for callers that used the old response model."""

    grounded: Literal[True] = True
    rewrites: AIRewrites = Field(default_factory=AIRewrites)
