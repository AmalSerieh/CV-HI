"""The one authoritative pipeline report contract.

All public pipeline return values and JSON exports validate through
``PipelineReport``. Legacy shapes are accepted only by the explicit migration
layer, never by this model.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .ai_schema import AIRecommendation
from .ats_schema import ATSResult
from .pipeline_schema import LayoutBlock, PageLayout, StrictModel
from .rewrite_schema import RewriteResult

SCHEMA_VERSION: Literal["2.1.0"] = "2.1.0"
ModuleState = Literal[
    "not_run",
    "complete",
    "partial",
    "degraded",
    "fallback",
    "failed",
    "unavailable",
]
ContactSourceType = Literal[
    "selectable_text",
    "annotation",
    "ocr",
    "image_only_unrecovered",
    "inferred",
    "missing",
]
OCRScope = Literal[
    "none",
    "contact_header",
    "page",
    "full_document",
    "mixed",
    "unknown",
]
ParsingDimensionName = Literal[
    "contact_integrity",
    "section_segmentation_integrity",
    "reading_order_integrity",
    "experience_integrity",
    "project_integrity",
    "education_integrity",
    "skills_integrity",
    "evidence_consistency",
    "entity_coherence",
    "confidence_coverage",
]


class SourceReference(StrictModel):
    extractor: str
    field_path: str
    page: int | None = Field(default=None, ge=1)
    block_id: str | None = None
    section: str | None = None
    column: str | None = None
    zone_id: str | None = None
    source_field: str | None = None


class EvidenceRecord(StrictModel):
    id: str = Field(pattern=r"^ev-[a-f0-9]{16}$")
    kind: Literal["present", "missing", "rejected", "layout", "quality", "rule"]
    field_path: str = Field(min_length=1)
    value: str | int | float | bool | None = None
    source: SourceReference
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    parent_evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: str | int | float | bool | None):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Evidence values must be finite")
        return value


class DocumentInfo(StrictModel):
    name: str
    extension: str
    path: str | None = None
    pages: int = Field(default=0, ge=0)
    size_bytes: int | None = Field(default=None, ge=0)
    layout: Literal["single_column", "two_column", "mixed", "unknown"] = "unknown"


class VisualMetadata(StrictModel):
    status: Literal["complete", "partial", "cannot_verify", "not_available"] = "not_available"
    source: str = "not_available"
    has_images: bool | None = None
    image_count: int | None = Field(default=None, ge=0)
    icon_count: int | None = Field(default=None, ge=0)
    candidate_photo_detected: bool | None = None
    decorative_image_count: int | None = Field(default=None, ge=0)
    image_only_contact_fields: list[str] = Field(default_factory=list)
    possible_image_only_contact: bool = False
    contact_readability: Literal[
        "readable", "partially_readable", "image_only", "unreadable", "unknown"
    ] = "unknown"
    contact_ocr_used: bool = False
    contact_ocr_status: Literal[
        "not_needed", "complete", "partial", "failed", "disabled", "unavailable", "unknown"
    ] = "unknown"
    contact_ocr_error: str | None = None
    text_box_count: int | None = Field(default=None, ge=0)
    drawing_count: int | None = Field(default=None, ge=0)
    shape_count: int | None = Field(default=None, ge=0)
    table_count: int | None = Field(default=None, ge=0)
    has_color: bool | None = None
    detected_color_count: int | None = Field(default=None, ge=0)
    contrast_status: str = "unknown"
    ats_color_risk: str = "unknown"
    font_sizes: list[float] = Field(default_factory=list)
    font_names: list[str] = Field(default_factory=list)
    small_font_count: int | None = Field(default=None, ge=0)
    overlap_count: int | None = Field(default=None, ge=0)
    hidden_text_count: int | None = Field(default=None, ge=0)
    white_text_count: int | None = Field(default=None, ge=0)
    duplicate_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    repeated_header_footer_count: int = Field(default=0, ge=0)


class OCRUsage(StrictModel):
    used: bool = False
    scope: OCRScope = "none"
    pages: list[int] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)

    @field_validator("pages", "fields")
    @classmethod
    def unique_values(cls, values: list):
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def scope_matches_usage(self) -> OCRUsage:
        if not self.used and self.scope != "none":
            raise ValueError("Unused OCR must have scope='none'")
        if self.used and self.scope == "none":
            raise ValueError("Used OCR requires an explicit or unknown scope")
        return self


class SectionRecord(StrictModel):
    key: str
    heading: str | None = None
    content: str = ""
    words: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    block_ids: list[str] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=list)
    mixed_content: bool = False
    item_groups: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ExtractionInfo(StrictModel):
    status: Literal["ok", "degraded", "failed"]
    quality_score: int = Field(ge=0, le=100)
    word_count: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)
    ocr_used: bool = False
    ocr_available: bool | None = None
    ocr_usage: OCRUsage = Field(default_factory=OCRUsage)
    engine: Literal["pymupdf", "pdfplumber", "ocr", "docx", "docx_ooxml", "mixed", "unknown"] = (
        "unknown"
    )
    reading_order: Literal["top_to_bottom", "row_wise", "column_wise", "mixed", "unknown"] = (
        "unknown"
    )
    links: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    layout_blocks: list[LayoutBlock] = Field(default_factory=list)
    page_layouts: list[PageLayout] = Field(default_factory=list)
    visual_metadata: VisualMetadata = Field(default_factory=VisualMetadata)
    section_order: list[str] = Field(default_factory=list)
    detected_headings: list[str] = Field(default_factory=list)
    evidence_ids: dict[str, list[str]] = Field(default_factory=dict)
    sections: dict[str, SectionRecord] = Field(default_factory=dict)


class ContactInfo(StrictModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    job_title: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    source_types: dict[str, ContactSourceType] = Field(default_factory=dict)
    evidence_ids: dict[str, list[str]] = Field(default_factory=dict)


class SkillItem(StrictModel):
    value: str = Field(min_length=1)
    normalized: str | None = None
    category: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    field_evidence_ids: dict[str, list[str]] = Field(default_factory=dict)


class EducationItem(StrictModel):
    degree: str | None = None
    field: str | None = None
    specialization: str | None = None
    institution: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    graduation_year: int | None = None
    gpa: str | None = None
    honors: list[str] = Field(default_factory=list)
    coursework: list[str] = Field(default_factory=list)
    description: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    field_evidence_ids: dict[str, list[str]] = Field(default_factory=dict)


class ExperienceItem(StrictModel):
    job_title: str | None = None
    company: str | None = None
    location: str | None = None
    employment_type: str | None = None
    volunteer: bool = False
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = False
    parsing_needs_review: bool = False
    content_needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    field_evidence_ids: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def synchronize_review_states(self) -> ExperienceItem:
        if self.needs_review and not (self.parsing_needs_review or self.content_needs_review):
            object.__setattr__(self, "parsing_needs_review", True)
        object.__setattr__(
            self,
            "needs_review",
            self.parsing_needs_review or self.content_needs_review,
        )
        object.__setattr__(
            self,
            "review_reasons",
            list(dict.fromkeys(self.review_reasons)),
        )
        return self


class ProjectItem(StrictModel):
    name: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    field_evidence_ids: dict[str, list[str]] = Field(default_factory=dict)


class LanguageItem(StrictModel):
    language: str = Field(min_length=1)
    proficiency: str | None = None
    cefr: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class CertificationItem(StrictModel):
    name: str = Field(min_length=1)
    issuer: str | None = None
    date: str | None = None
    credential_id: str | None = None
    url: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    field_evidence_ids: dict[str, list[str]] = Field(default_factory=dict)


class Entities(StrictModel):
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = ""
    skills: list[SkillItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)


class QualityIssue(StrictModel):
    code: str
    area: str
    severity: Literal["low", "medium", "high"]
    title: str = ""
    field_path: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    message: str
    explanation: str = ""
    suggested_action: str = ""
    dimensions: list[ParsingDimensionName] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class QualityInfo(StrictModel):
    status: Literal["good", "needs_review", "poor", "failed"]
    score: int = Field(ge=0, le=100)
    missing_sections: list[str] = Field(default_factory=list)
    issues: list[QualityIssue] = Field(default_factory=list)


class ParsingIntegrityDimensions(StrictModel):
    contact_integrity: int = Field(default=100, ge=0, le=100)
    section_segmentation_integrity: int = Field(default=100, ge=0, le=100)
    reading_order_integrity: int = Field(default=100, ge=0, le=100)
    experience_integrity: int = Field(default=100, ge=0, le=100)
    project_integrity: int = Field(default=100, ge=0, le=100)
    education_integrity: int = Field(default=100, ge=0, le=100)
    skills_integrity: int = Field(default=100, ge=0, le=100)
    evidence_consistency: int = Field(default=100, ge=0, le=100)
    entity_coherence: int = Field(default=100, ge=0, le=100)
    confidence_coverage: int = Field(default=100, ge=0, le=100)


class ParsingIntegrityDimensionDetail(StrictModel):
    score: int = Field(ge=0, le=100)
    weight: float = Field(gt=0.0, le=1.0)
    weighted_points: float = Field(ge=0.0, le=100.0)
    issue_codes: list[str] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)

    @field_validator("issue_codes", "explanations")
    @classmethod
    def unique_items(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_weighted_points(self) -> ParsingIntegrityDimensionDetail:
        if not math.isclose(
            self.weighted_points,
            self.score * self.weight,
            abs_tol=1e-9,
        ):
            raise ValueError("Dimension weighted points must equal score multiplied by weight")
        return self


class ParsingIntegrityAdjustment(StrictModel):
    code: str
    points: int = Field(ge=-100, le=100)
    trigger_dimension: ParsingDimensionName | None = None
    explanation: str


class ParsingIntegrityBreakdown(StrictModel):
    dimensions: dict[ParsingDimensionName, ParsingIntegrityDimensionDetail]
    weighted_subtotal: int = Field(ge=0, le=100)
    adjustments: list[ParsingIntegrityAdjustment] = Field(default_factory=list)
    total: int = Field(ge=0, le=100)
    rounding_rule: Literal["python_round_half_to_even"] = "python_round_half_to_even"

    @model_validator(mode="after")
    def validate_recomputation(self) -> ParsingIntegrityBreakdown:
        required = set(ParsingIntegrityDimensions.model_fields)
        if set(self.dimensions) != required:
            raise ValueError("Parsing breakdown must contain all integrity dimensions")
        if not math.isclose(
            sum(item.weight for item in self.dimensions.values()),
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("Parsing breakdown weights must sum to 1.0")
        expected_subtotal = round(
            sum(item.score * item.weight for item in self.dimensions.values())
        )
        if self.weighted_subtotal != expected_subtotal:
            raise ValueError("Parsing weighted subtotal does not match dimension scores")
        expected_total = max(
            0,
            min(
                100,
                self.weighted_subtotal + sum(adjustment.points for adjustment in self.adjustments),
            ),
        )
        if self.total != expected_total:
            raise ValueError("Parsing total does not match subtotal and adjustments")
        return self


class DataQualityInfo(StrictModel):
    status: Literal["not_run", "good", "needs_review", "poor"] = "not_run"
    score: int | None = Field(default=None, ge=0, le=100)
    parsing_integrity_score: int | None = Field(default=None, ge=0, le=100)
    text_extraction_quality: int | None = Field(default=None, ge=0, le=100)
    layout_reconstruction_quality: int | None = Field(default=None, ge=0, le=100)
    section_segmentation_quality: int | None = Field(default=None, ge=0, le=100)
    contact_readability: Literal[
        "readable", "partially_readable", "image_only", "unreadable", "unknown"
    ] = "unknown"
    dimensions: ParsingIntegrityDimensions = Field(default_factory=ParsingIntegrityDimensions)
    breakdown: ParsingIntegrityBreakdown | None = None
    fields_requiring_review: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    issues: list[QualityIssue] = Field(default_factory=list)
    interpretation: str = "Canonical parsing integrity was not evaluated."
    method: str = "deterministic_canonical_integrity_v2"

    @model_validator(mode="after")
    def synchronized_integrity_scores(self) -> DataQualityInfo:
        if (
            self.score is not None
            and self.parsing_integrity_score is not None
            and self.score != self.parsing_integrity_score
        ):
            raise ValueError("score must equal parsing_integrity_score")
        if self.score is None and self.parsing_integrity_score is not None:
            self.score = self.parsing_integrity_score
        elif self.parsing_integrity_score is None and self.score is not None:
            self.parsing_integrity_score = self.score
        if self.breakdown is not None:
            if self.parsing_integrity_score != self.breakdown.total:
                raise ValueError("Parsing score must equal parsing breakdown total")
            flat_dimensions = self.dimensions.model_dump()
            detailed_dimensions = {
                name: detail.score for name, detail in self.breakdown.dimensions.items()
            }
            if flat_dimensions != detailed_dimensions:
                raise ValueError("Flat and detailed parsing dimensions must match")
        return self


class TargetRoleEvidence(StrictModel):
    source: str
    path: str
    value: str


class TargetRoleScoreBreakdown(StrictModel):
    skills: float = 0.0
    experience_titles: float = 0.0
    experience_bullets: float = 0.0
    projects: float = 0.0
    summary: float = 0.0
    education_certifications: float = 0.0


class TargetRoleCandidate(StrictModel):
    role_id: str
    title_en: str
    title_ar: str
    confidence: float = Field(ge=0.0, le=1.0)
    matched_signals: list[str] = Field(default_factory=list)
    score_breakdown: TargetRoleScoreBreakdown
    evidence: list[TargetRoleEvidence] = Field(default_factory=list)


class TargetRoleInfo(StrictModel):
    primary: TargetRoleCandidate | None = None
    alternatives: list[TargetRoleCandidate] = Field(default_factory=list)
    insufficient_evidence: bool = True
    method: str = "deterministic_weighted_matching"
    language: Literal["en", "ar", "mixed", "unknown"] = "en"
    warnings: list[str] = Field(default_factory=list)


class OptionalModuleInfo(StrictModel):
    status: Literal["not_run", "unavailable", "complete", "failed"] = "not_run"
    provider: str | None = None
    message: str | None = None


class PipelineMessage(StrictModel):
    stage: str
    code: str
    message: str
    recoverable: bool = True


class ComponentStatus(StrictModel):
    status: ModuleState
    provider: str | None = None
    model: str | None = None
    detail: str | None = None


class ModuleStatus(StrictModel):
    extraction: ComponentStatus
    target_role: ComponentStatus
    recommendations: ComponentStatus
    ats: ComponentStatus = Field(default_factory=lambda: ComponentStatus(status="not_run"))
    rewrites: ComponentStatus = Field(default_factory=lambda: ComponentStatus(status="not_run"))


class PipelineReport(StrictModel):
    schema_version: Literal["2.1.0"] = SCHEMA_VERSION
    document: DocumentInfo
    extraction: ExtractionInfo
    entities: Entities
    quality: QualityInfo
    data_quality: DataQualityInfo = Field(default_factory=DataQualityInfo)
    evidence: list[EvidenceRecord]
    target_role: TargetRoleInfo | None = None
    recommendations: list[AIRecommendation] = Field(default_factory=list)
    ats: ATSResult = Field(default_factory=ATSResult)
    rewrites: RewriteResult = Field(default_factory=RewriteResult)
    warnings: list[PipelineMessage] = Field(default_factory=list)
    errors: list[PipelineMessage] = Field(default_factory=list)
    module_status: ModuleStatus

    @model_validator(mode="after")
    def references_known_evidence(self) -> PipelineReport:
        known = {item.id for item in self.evidence}
        if len(known) != len(self.evidence):
            raise ValueError("Evidence IDs must be unique")

        referenced: list[str] = []
        for recommendation in self.recommendations:
            referenced.extend(recommendation.evidence_ids)
        for quality_issue in self.quality.issues:
            referenced.extend(quality_issue.evidence_ids)
        for quality_issue in self.data_quality.issues:
            referenced.extend(quality_issue.evidence_ids)
        for ats_issue in self.ats.issues:
            referenced.extend(ats_issue.evidence_ids)
        for strength in self.ats.strengths:
            referenced.extend(strength.evidence_ids)
        referenced.extend(self.ats.job_match.evidence_ids)
        referenced.extend(self.rewrites.summary.evidence_ids)
        referenced.extend(self.rewrites.skills_section.evidence_ids)
        for bullet in self.rewrites.experience_bullets:
            referenced.extend(bullet.evidence_ids)
        for values in self.extraction.evidence_ids.values():
            referenced.extend(values)
        for values in self.entities.contact.evidence_ids.values():
            referenced.extend(values)
        for collection in (
            self.entities.skills,
            self.entities.education,
            self.entities.experience,
            self.entities.projects,
            self.entities.languages,
            self.entities.certifications,
        ):
            for item in collection:
                referenced.extend(item.evidence_ids)

        unknown = sorted(set(referenced) - known)
        if unknown:
            raise ValueError(f"Unknown evidence IDs referenced: {unknown}")
        if self.rewrites.summary.status != "not_run":
            if self.rewrites.summary.original != self.entities.summary:
                raise ValueError("Summary rewrite original must match canonical entities.summary")
        expected_skills = [item.value for item in self.entities.skills]
        if self.rewrites.skills_section.status != "not_run":
            if self.rewrites.skills_section.original_items != expected_skills:
                raise ValueError("Skills rewrite originals must match canonical entities.skills")
        for rewrite in self.rewrites.experience_bullets:
            if rewrite.experience_index >= len(self.entities.experience):
                raise ValueError("Experience rewrite index is out of range")
            experience = self.entities.experience[rewrite.experience_index]
            bullets = (
                experience.responsibilities
                if rewrite.bullet_kind == "responsibility"
                else experience.achievements
            )
            if rewrite.bullet_index >= len(bullets):
                raise ValueError("Experience bullet rewrite index is out of range")
            if rewrite.original != bullets[rewrite.bullet_index]:
                raise ValueError("Experience rewrite original must match canonical entities")
        return self

    def to_json_dict(self) -> dict[str, Any]:
        """Return a validated JSON-safe object and reject NaN/Infinity."""

        import json

        value = self.model_dump(mode="json")
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        return value


# Backward-compatible aliases for imports from the former report schema.
CandidateInfo = ContactInfo
PipelineError = PipelineMessage
ATSReport = ATSResult
