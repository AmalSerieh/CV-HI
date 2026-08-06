"""Strict canonical contracts for proposed resume rewrites."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .pipeline_schema import StrictModel

RewriteLanguage = Literal["en", "ar", "mixed", "unknown"]
RewriteStatus = Literal["complete", "partial", "fallback", "unavailable", "failed", "not_run"]
SkillsRewriteMethod = Literal["not_run", "ai", "deterministic"]
ComponentRewriteStatus = Literal[
    "improved", "generated", "unchanged", "rejected", "unavailable", "not_run"
]
RewriteRejectionCode = Literal[
    "INVENTED_NUMBER",
    "CHANGED_NUMBER",
    "INVENTED_PERCENTAGE",
    "CHANGED_PERCENTAGE",
    "INVENTED_MONEY_VALUE",
    "CHANGED_MONEY_VALUE",
    "INVENTED_COMPANY",
    "INVENTED_TECHNOLOGY",
    "INVENTED_CERTIFICATION",
    "INVENTED_DEGREE",
    "CHANGED_DATE",
    "CHANGED_JOB_TITLE",
    "CHANGED_URL",
    "UNSUPPORTED_PROPER_NOUN",
    "UNKNOWN_EVIDENCE_ID",
    "ORIGINAL_TEXT_MISMATCH",
    "LANGUAGE_CHANGED",
    "PROMPT_INJECTION_OUTPUT",
    "UNSUPPORTED_FACTUAL_CLAIM",
    "INVALID_MODEL_RESPONSE",
    "MODEL_OUTPUT_TRUNCATED",
    "NO_MATERIAL_CHANGE",
    "AI_PROVIDER_TIMEOUT",
    "AI_PROVIDER_UNAVAILABLE",
    "EMPTY_IMPROVED_TEXT",
    "INVALID_INDEX",
]


class RewriteChange(StrictModel):
    type: Literal["clarity", "grammar", "conciseness", "tone", "organization", "deduplication"]
    description: str = Field(min_length=1, max_length=300)


class SummaryRewriteResult(StrictModel):
    status: ComponentRewriteStatus = "not_run"
    original: str = ""
    improved: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    changes: list[RewriteChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool = False
    generated_from_evidence: bool = False

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_text(self) -> SummaryRewriteResult:
        if self.status in {"improved", "generated"} and not self.improved:
            raise ValueError("An accepted summary rewrite cannot be empty")
        return self


class ExperienceBulletRewriteResult(StrictModel):
    experience_index: int = Field(ge=0)
    bullet_index: int = Field(ge=0)
    bullet_kind: Literal["responsibility", "achievement"] = "responsibility"
    status: ComponentRewriteStatus = "not_run"
    original: str
    improved: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    changes: list[RewriteChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool = False

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_text(self) -> ExperienceBulletRewriteResult:
        if self.status in {"improved", "generated"} and not self.improved:
            raise ValueError("An accepted bullet rewrite cannot be empty")
        return self


class SkillGroup(StrictModel):
    group: str = Field(min_length=1, max_length=80)
    items: list[str] = Field(default_factory=list)

    @field_validator("items")
    @classmethod
    def unique_items(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))


class SkillsSectionRewriteResult(StrictModel):
    status: ComponentRewriteStatus = "not_run"
    method: SkillsRewriteMethod = "not_run"
    original_items: list[str] = Field(default_factory=list)
    improved_groups: list[SkillGroup] = Field(default_factory=list)
    added_items: list[str] = Field(default_factory=list)
    removed_duplicates: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool = False

    @field_validator("original_items", "added_items", "removed_duplicates", "evidence_ids")
    @classmethod
    def unique_items(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))


class RejectedRewrite(StrictModel):
    component: Literal["summary", "experience_bullet", "skills_section"]
    code: RewriteRejectionCode
    message: str = Field(min_length=1, max_length=500)
    original: str | list[str]
    candidate: str | list[str] | None = None
    experience_index: int | None = Field(default=None, ge=0)
    bullet_index: int | None = Field(default=None, ge=0)


class RewriteNotice(StrictModel):
    code: Literal[
        "MODEL_OUTPUT_TRUNCATED",
        "NO_MATERIAL_CHANGE",
        "BULLET_REWRITE_LIMIT_APPLIED",
        "INVALID_MODEL_RESPONSE",
        "AI_PROVIDER_TIMEOUT",
        "AI_PROVIDER_UNAVAILABLE",
        "SKILLS_DETERMINISTIC_FALLBACK_APPLIED",
    ]
    component: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    severity: Literal["information", "warning"] = "warning"


class BulletRewriteStats(StrictModel):
    total_eligible: int = Field(default=0, ge=0)
    selected: int = Field(default=0, ge=0)
    processed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)


class RewriteResult(StrictModel):
    status: RewriteStatus = "not_run"
    language: RewriteLanguage = "unknown"
    provider: str | None = None
    model: str | None = None
    summary: SummaryRewriteResult = Field(default_factory=SummaryRewriteResult)
    experience_bullets: list[ExperienceBulletRewriteResult] = Field(default_factory=list)
    skills_section: SkillsSectionRewriteResult = Field(default_factory=SkillsSectionRewriteResult)
    warnings: list[str] = Field(default_factory=list)
    rejected_rewrites: list[RejectedRewrite] = Field(default_factory=list)
    notices: list[RewriteNotice] = Field(default_factory=list)
    completed_components: list[str] = Field(default_factory=list)
    unchanged_components: list[str] = Field(default_factory=list)
    rejected_components: list[str] = Field(default_factory=list)
    skipped_components: list[str] = Field(default_factory=list)
    bullet_stats: BulletRewriteStats = Field(default_factory=BulletRewriteStats)

    @model_validator(mode="after")
    def unique_bullets(self) -> RewriteResult:
        indices = [
            (item.experience_index, item.bullet_kind, item.bullet_index)
            for item in self.experience_bullets
        ]
        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate experience bullet rewrites are not allowed")
        return self
