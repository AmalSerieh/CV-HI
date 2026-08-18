"""Resolve canonical data, validated proposals, and decisions into one FinalResume."""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict

from resume_analyzer.schemas import PipelineReport, SkillGroup

from .schemas import (
    ExperienceBulletReviewItem,
    FinalCertification,
    FinalContact,
    FinalEducation,
    FinalExperience,
    FinalLanguage,
    FinalProject,
    FinalResume,
    FinalSkillGroup,
    ResumeReviewPayload,
    ResumeReviewState,
    ReviewDecision,
    ReviewUpdate,
    SkillsReviewItem,
    TextReviewItem,
)

_VALID_PROPOSAL_STATUSES = {"improved", "generated"}


class ReviewStateError(ValueError):
    """The submitted or stored review state is incompatible with the report."""


def bullet_review_id(experience_index: int, bullet_kind: str, bullet_index: int) -> str:
    return f"experience-{experience_index}-{bullet_kind}-{bullet_index}"


class FinalResumeBuilder:
    """Single authority for original + proposal + decision -> final content."""

    def __init__(self, report: PipelineReport | dict) -> None:
        self.report = (
            report if isinstance(report, PipelineReport) else PipelineReport.model_validate(report)
        )

    def initial_state(self) -> ResumeReviewState:
        return ResumeReviewState(
            experience_bullets={
                item_id: ReviewDecision.PENDING for item_id in self._valid_bullet_proposals()
            }
        )

    def apply_update(self, state: ResumeReviewState, update: ReviewUpdate) -> ResumeReviewState:
        """Validate every requested decision before returning a new state."""

        self._ensure_state_compatible(state)
        candidate = state.model_copy(deep=True)
        valid_bullets = self._valid_bullet_proposals()

        if update.summary is not None:
            if not self._summary_proposal():
                raise ReviewStateError("The summary has no acceptable proposal.")
            candidate.summary = update.summary
        if update.skills is not None:
            if not self._skills_proposal():
                raise ReviewStateError("The skills section has no acceptable proposal.")
            candidate.skills = update.skills
        if update.experience_bullets is not None:
            unknown = sorted(set(update.experience_bullets) - set(valid_bullets))
            if unknown:
                raise ReviewStateError(f"Unknown or unavailable review item: {unknown[0]}")
            candidate.experience_bullets.update(update.experience_bullets)

        self._ensure_state_compatible(candidate)
        return candidate

    def build(self, state: ResumeReviewState | None = None) -> FinalResume:
        selected = state or self.initial_state()
        self._ensure_state_compatible(selected)
        entities = self.report.entities
        summary_proposal = self._summary_proposal()
        summary = entities.summary
        if selected.summary is ReviewDecision.ACCEPTED and summary_proposal:
            summary = summary_proposal

        bullet_proposals = self._valid_bullet_proposals()
        experience: list[FinalExperience] = []
        for experience_index, item in enumerate(entities.experience):
            responsibilities = self._final_bullets(
                experience_index,
                "responsibility",
                item.responsibilities,
                bullet_proposals,
                selected,
            )
            achievements = self._final_bullets(
                experience_index,
                "achievement",
                item.achievements,
                bullet_proposals,
                selected,
            )
            experience.append(
                FinalExperience(
                    job_title=item.job_title,
                    company=item.company,
                    location=item.location,
                    employment_type=item.employment_type,
                    volunteer=item.volunteer,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    current=item.current,
                    responsibilities=responsibilities,
                    achievements=achievements,
                    technologies=list(item.technologies),
                    metrics=list(item.metrics),
                )
            )

        original_skills = self._original_skill_groups()
        proposed_skills = self._skills_proposal()
        skills = original_skills
        if selected.skills is ReviewDecision.ACCEPTED and proposed_skills:
            skills = proposed_skills

        return FinalResume(
            contact=FinalContact(
                **entities.contact.model_dump(
                    include={
                        "name",
                        "job_title",
                        "email",
                        "phone",
                        "location",
                        "linkedin",
                        "github",
                        "portfolio",
                    }
                )
            ),
            summary=summary,
            experience=experience,
            education=[
                FinalEducation(
                    **item.model_dump(
                        include={
                            "degree",
                            "field",
                            "specialization",
                            "institution",
                            "location",
                            "start_date",
                            "end_date",
                            "graduation_year",
                            "gpa",
                            "honors",
                            "coursework",
                            "description",
                        }
                    )
                )
                for item in entities.education
            ],
            skills=skills,
            projects=[
                FinalProject(
                    **item.model_dump(
                        include={
                            "name",
                            "role",
                            "start_date",
                            "end_date",
                            "current",
                            "description",
                            "technologies",
                            "url",
                        }
                    )
                )
                for item in entities.projects
            ],
            languages=[
                FinalLanguage(**item.model_dump(include={"language", "proficiency", "cefr"}))
                for item in entities.languages
            ],
            certifications=[
                FinalCertification(
                    **item.model_dump(include={"name", "issuer", "date", "credential_id", "url"})
                )
                for item in entities.certifications
            ],
        )

    def review_payload(self, state: ResumeReviewState | None = None) -> ResumeReviewPayload:
        selected = state or self.initial_state()
        final_resume = self.build(selected)
        summary_proposal = self._summary_proposal()
        summary_status = self.report.rewrites.summary.status

        bullet_proposals = self._valid_bullet_proposals()
        bullet_items: list[ExperienceBulletReviewItem] = []
        for rewrite in self.report.rewrites.experience_bullets:
            item_id = bullet_review_id(
                rewrite.experience_index, rewrite.bullet_kind, rewrite.bullet_index
            )
            proposed = bullet_proposals.get(item_id)
            decision = selected.experience_bullets.get(item_id, ReviewDecision.PENDING)
            final = rewrite.original
            if decision is ReviewDecision.ACCEPTED and proposed:
                final = proposed
            experience = self.report.entities.experience[rewrite.experience_index]
            bullet_items.append(
                ExperienceBulletReviewItem(
                    id=item_id,
                    original=rewrite.original,
                    proposed=proposed,
                    decision=decision,
                    final=final,
                    proposal_status=rewrite.status,
                    can_accept=proposed is not None,
                    experience_index=rewrite.experience_index,
                    bullet_index=rewrite.bullet_index,
                    bullet_kind=rewrite.bullet_kind,
                    job_title=experience.job_title,
                    company=experience.company,
                    warnings=list(rewrite.warnings),
                )
            )

        original_skills = self._original_skill_groups()
        proposed_skills = self._skills_proposal()
        return ResumeReviewPayload(
            summary=TextReviewItem(
                id="summary",
                original=self.report.entities.summary,
                proposed=summary_proposal,
                decision=selected.summary,
                final=final_resume.summary,
                proposal_status=summary_status,
                can_accept=summary_proposal is not None,
            ),
            experience_bullets=bullet_items,
            skills=SkillsReviewItem(
                original=original_skills,
                proposed=proposed_skills,
                decision=selected.skills,
                final=final_resume.skills,
                proposal_status=self.report.rewrites.skills_section.status,
                can_accept=proposed_skills is not None,
            ),
            final_resume=final_resume,
        )

    def _summary_proposal(self) -> str | None:
        rewrite = self.report.rewrites.summary
        if rewrite.status in _VALID_PROPOSAL_STATUSES and rewrite.improved:
            return rewrite.improved
        return None

    def _valid_bullet_proposals(self) -> dict[str, str]:
        proposals: dict[str, str] = {}
        for item in self.report.rewrites.experience_bullets:
            if item.status not in _VALID_PROPOSAL_STATUSES or not item.improved:
                continue
            proposals[
                bullet_review_id(item.experience_index, item.bullet_kind, item.bullet_index)
            ] = item.improved
        return proposals

    def _skills_proposal(self) -> list[FinalSkillGroup] | None:
        rewrite = self.report.rewrites.skills_section
        if rewrite.status not in _VALID_PROPOSAL_STATUSES or not rewrite.improved_groups:
            return None
        if rewrite.added_items:
            return None

        original_keys = {
            self._skill_key(item.value) for item in self.report.entities.skills if item.value
        }
        proposed_items = [item for group in rewrite.improved_groups for item in group.items]
        proposed_keys = {self._skill_key(item) for item in proposed_items if item}
        if proposed_keys != original_keys:
            return None
        return [self._final_skill_group(group) for group in rewrite.improved_groups if group.items]

    def _original_skill_groups(self) -> list[FinalSkillGroup]:
        grouped: OrderedDict[str, list[str]] = OrderedDict()
        for item in self.report.entities.skills:
            label = self._category_label(item.category)
            grouped.setdefault(label, []).append(item.value)
        return [FinalSkillGroup(group=group, items=items) for group, items in grouped.items()]

    @staticmethod
    def _category_label(category: str | None) -> str:
        if not category:
            return "Skills"
        return category.replace("_", " ").strip().title()

    @staticmethod
    def _final_skill_group(group: SkillGroup) -> FinalSkillGroup:
        return FinalSkillGroup(group=group.group, items=list(group.items))

    @staticmethod
    def _skill_key(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold().replace("‑", "-")
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _final_bullets(
        experience_index: int,
        bullet_kind: str,
        originals: list[str],
        proposals: dict[str, str],
        state: ResumeReviewState,
    ) -> list[str]:
        output: list[str] = []
        for bullet_index, original in enumerate(originals):
            item_id = bullet_review_id(experience_index, bullet_kind, bullet_index)
            decision = state.experience_bullets.get(item_id, ReviewDecision.PENDING)
            proposal = proposals.get(item_id)
            output.append(
                proposal
                if decision is ReviewDecision.ACCEPTED and proposal is not None
                else original
            )
        return output

    def _ensure_state_compatible(self, state: ResumeReviewState) -> None:
        valid_bullets = set(self._valid_bullet_proposals())
        unknown = sorted(set(state.experience_bullets) - valid_bullets)
        if unknown:
            raise ReviewStateError(f"Unknown or unavailable review item: {unknown[0]}")
        if state.summary is ReviewDecision.ACCEPTED and not self._summary_proposal():
            raise ReviewStateError("The summary has no acceptable proposal.")
        if state.skills is ReviewDecision.ACCEPTED and not self._skills_proposal():
            raise ReviewStateError("The skills section has no acceptable proposal.")
