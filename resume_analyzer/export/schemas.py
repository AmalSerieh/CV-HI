"""Public contracts for review decisions and semantic final-resume data."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from resume_analyzer.schemas.pipeline_schema import StrictModel


class ReviewDecision(str, Enum):
    """An explicit user resolution for one validated proposal."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ResumeReviewState(StrictModel):
    """Temporary decisions that live for the same TTL as an analysis."""

    version: Literal[1] = 1
    summary: ReviewDecision = ReviewDecision.PENDING
    experience_bullets: dict[str, ReviewDecision] = Field(default_factory=dict)
    skills: ReviewDecision = ReviewDecision.PENDING


class ReviewUpdate(StrictModel):
    """Transactional partial update accepted by the review API."""

    summary: ReviewDecision | None = None
    experience_bullets: dict[str, ReviewDecision] | None = None
    skills: ReviewDecision | None = None


class TemplateSelection(StrictModel):
    template_id: str = Field(min_length=1, max_length=40)


class FinalContact(StrictModel):
    name: str | None = None
    job_title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class FinalExperience(StrictModel):
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


class FinalEducation(StrictModel):
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


class FinalSkillGroup(StrictModel):
    group: str = Field(min_length=1, max_length=80)
    items: list[str] = Field(default_factory=list)


class FinalProject(StrictModel):
    name: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class FinalLanguage(StrictModel):
    language: str = Field(min_length=1)
    proficiency: str | None = None
    cefr: str | None = None


class FinalCertification(StrictModel):
    name: str = Field(min_length=1)
    issuer: str | None = None
    date: str | None = None
    credential_id: str | None = None
    url: str | None = None


class FinalResume(StrictModel):
    """Only semantic information intended to appear in the exported resume."""

    contact: FinalContact = Field(default_factory=FinalContact)
    summary: str = ""
    experience: list[FinalExperience] = Field(default_factory=list)
    education: list[FinalEducation] = Field(default_factory=list)
    skills: list[FinalSkillGroup] = Field(default_factory=list)
    projects: list[FinalProject] = Field(default_factory=list)
    languages: list[FinalLanguage] = Field(default_factory=list)
    certifications: list[FinalCertification] = Field(default_factory=list)


class TextReviewItem(StrictModel):
    id: str
    original: str
    proposed: str | None = None
    decision: ReviewDecision
    final: str
    proposal_status: str
    can_accept: bool = False


class ExperienceBulletReviewItem(TextReviewItem):
    experience_index: int = Field(ge=0)
    bullet_index: int = Field(ge=0)
    bullet_kind: Literal["responsibility", "achievement"]
    job_title: str | None = None
    company: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SkillsReviewItem(StrictModel):
    id: Literal["skills"] = "skills"
    original: list[FinalSkillGroup] = Field(default_factory=list)
    proposed: list[FinalSkillGroup] | None = None
    decision: ReviewDecision
    final: list[FinalSkillGroup] = Field(default_factory=list)
    proposal_status: str
    can_accept: bool = False


class ResumeReviewPayload(StrictModel):
    summary: TextReviewItem
    experience_bullets: list[ExperienceBulletReviewItem] = Field(default_factory=list)
    skills: SkillsReviewItem
    final_resume: FinalResume
