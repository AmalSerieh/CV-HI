"""Evidence-preserving facade using the shared provider/client infrastructure."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.providers import AIProvider
from resume_analyzer.schemas import (
    BulletRewriteStats,
    ExperienceBulletRewriteResult,
    PipelineReport,
    RewriteNotice,
    RewriteResult,
    SkillGroup,
    SkillsSectionRewriteResult,
    SummaryRewriteResult,
)

from .bullets import BulletImprover
from .parser import RewriteResponseParser
from .prompts import RewritePromptBuilder
from .skills import SkillsSectionImprover
from .summary import SummaryGenerator
from .validator import RewriteValidator

_DISPLAY_ALIASES = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "node.js": "Node.js",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "aws": "AWS",
    "azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "git": "Git",
    "java": "Java",
    "c++": "C++",
    "c#": "C#",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "power bi": "Power BI",
}


class ResumeRewriter:
    """Generate proposed rewrites without mutating canonical candidate facts."""

    def __init__(
        self,
        provider: AIProvider | None = None,
        *,
        timeout_seconds: float = 20.0,
        retries: int = 1,
        retry_timeouts: bool = False,
        max_output_tokens: int = 256,
        summary_max_output_tokens: int | None = None,
        bullet_max_output_tokens: int | None = None,
        skills_max_output_tokens: int | None = None,
        client: AIClient | None = None,
        sections: tuple[str, ...] = ("summary", "experience", "skills"),
        output_language: str | None = None,
        max_prompt_characters: int = 12_000,
        max_response_characters: int = 50_000,
        max_summary_characters: int = 800,
        max_bullet_characters: int = 500,
        max_bullets: int = 5,
        absolute_max_bullets: int = 20,
        bullet_selection: tuple[int, ...] | None = None,
        rewrite_all_bullets: bool = False,
        skills_ai_max_items: int = 24,
    ) -> None:
        allowed = {"summary", "experience", "skills"}
        if not sections or set(sections) - allowed:
            raise ValueError("sections must contain summary, experience, and/or skills")
        if output_language not in {None, "en", "ar", "mixed"}:
            raise ValueError("output_language must be en, ar, mixed, or unset")
        if max_bullets <= 0 or absolute_max_bullets <= 0:
            raise ValueError("Bullet limits must be positive")
        token_limits = (
            max_output_tokens,
            summary_max_output_tokens or max_output_tokens,
            bullet_max_output_tokens or max_output_tokens,
            skills_max_output_tokens or max_output_tokens,
        )
        if any(value <= 0 for value in token_limits):
            raise ValueError("Output token limits must be positive")
        if client is not None and provider is not None and client.provider is not provider:
            raise ValueError("Rewrite client and provider must reference the same provider")
        self.provider = provider or (client.provider if client is not None else None)
        self.client = client or (
            AIClient(
                provider,
                timeout_seconds=timeout_seconds,
                retries=retries,
                retry_timeouts=retry_timeouts,
            )
            if provider is not None
            else None
        )
        self.sections = sections
        self.output_language = output_language
        self.max_bullets = max_bullets
        self.absolute_max_bullets = absolute_max_bullets
        self.bullet_selection = bullet_selection
        self.rewrite_all_bullets = rewrite_all_bullets
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.summary_max_output_tokens = summary_max_output_tokens or max_output_tokens
        self.bullet_max_output_tokens = bullet_max_output_tokens or max_output_tokens
        self.skills_max_output_tokens = skills_max_output_tokens or max_output_tokens
        builder = RewritePromptBuilder(max_characters=max_prompt_characters)
        parser = RewriteResponseParser(max_characters=max_response_characters)
        validator = RewriteValidator()
        self.validator = validator
        self.summary_generator = SummaryGenerator(
            prompt_builder=builder,
            parser=parser,
            validator=validator,
            max_characters=max_summary_characters,
        )
        self.bullet_improver = BulletImprover(
            prompt_builder=builder,
            parser=parser,
            validator=validator,
            max_characters=max_bullet_characters,
        )
        self.skills_improver = SkillsSectionImprover(
            prompt_builder=builder,
            parser=parser,
            validator=validator,
            max_ai_items=skills_ai_max_items,
        )

    def rewrite(self, report: PipelineReport | Mapping[str, Any]) -> RewriteResult:
        canonical = (
            report if isinstance(report, PipelineReport) else PipelineReport.model_validate(report)
        )
        language = self.output_language or self._language(canonical)
        if self.client is None or self.provider is None:
            return self._fallback(canonical, language, "AI rewriting provider is not configured.")

        summary = SummaryRewriteResult()
        skills = SkillsSectionRewriteResult()
        bullets: list[ExperienceBulletRewriteResult] = []
        rejected = []
        warnings: list[str] = []
        notices: list[RewriteNotice] = []
        completed_components: list[str] = []
        unchanged_components: list[str] = []
        rejected_components: list[str] = []
        skipped_components: list[str] = []

        if "summary" in self.sections:
            summary, rejection = self.summary_generator.improve(
                canonical,
                self.client,
                language=language,
                timeout_seconds=self.timeout_seconds,
                max_output_tokens=self.summary_max_output_tokens,
            )
            self._classify_component(
                "summary",
                summary.status,
                completed_components,
                unchanged_components,
                rejected_components,
            )
            if rejection:
                if rejection.code != "NO_MATERIAL_CHANGE":
                    rejected.append(rejection)
                notices.append(self._notice(rejection.code, "summary", rejection.message))

        eligible = self._eligible_bullets(canonical) if "experience" in self.sections else []
        selected, skipped = self._select_bullets(eligible)
        if skipped:
            start = len(selected)
            skipped_components.append(f"experience_bullets[{start}:]")
            notices.append(
                RewriteNotice(
                    code="BULLET_REWRITE_LIMIT_APPLIED",
                    component="experience_bullets",
                    message=(
                        f"Selected {len(selected)} of {len(eligible)} eligible bullets; "
                        f"{len(skipped)} were not run."
                    ),
                    severity="information",
                )
            )
        for experience_index, bullet_kind, bullet_index in selected:
            result, rejection = self.bullet_improver.improve(
                canonical,
                self.client,
                experience_index=experience_index,
                bullet_index=bullet_index,
                bullet_kind=bullet_kind,
                language=language,
                timeout_seconds=self.timeout_seconds,
                max_output_tokens=self.bullet_max_output_tokens,
            )
            bullets.append(result)
            if rejection:
                rejected.append(rejection)
                notices.append(self._notice(rejection.code, "experience_bullet", rejection.message))
        if selected:
            bullet_statuses = {item.status for item in bullets}
            if bullet_statuses & {"rejected", "unavailable"}:
                rejected_components.append("experience_bullets")
            if bullet_statuses & {"improved", "generated"}:
                completed_components.append("experience_bullets")
            elif bullet_statuses == {"unchanged"}:
                unchanged_components.append("experience_bullets")

        if "skills" in self.sections:
            skills, rejection = self.skills_improver.improve(
                canonical,
                self.client,
                language=language,
                timeout_seconds=self.timeout_seconds,
                max_output_tokens=self.skills_max_output_tokens,
            )
            self._classify_component(
                "skills_section",
                skills.status,
                completed_components,
                unchanged_components,
                rejected_components,
            )
            if rejection:
                rejected.append(rejection)
                if skills.method == "deterministic":
                    rejected_components.append("skills_section_ai")
                notices.append(self._notice(rejection.code, "skills_section", rejection.message))
            if skills.method == "deterministic":
                notices.append(
                    RewriteNotice(
                        code="SKILLS_DETERMINISTIC_FALLBACK_APPLIED",
                        component="skills_section",
                        message=skills.warnings[0],
                        severity="information",
                    )
                )

        status = "partial" if rejected_components or skipped_components else "complete"
        return RewriteResult(
            status=status,
            language=language,
            provider=self.provider.name,
            model=self.provider.model,
            summary=summary,
            experience_bullets=bullets,
            skills_section=skills,
            warnings=warnings,
            rejected_rewrites=rejected,
            notices=notices,
            completed_components=list(dict.fromkeys(completed_components)),
            unchanged_components=list(dict.fromkeys(unchanged_components)),
            rejected_components=list(dict.fromkeys(rejected_components)),
            skipped_components=skipped_components,
            bullet_stats=BulletRewriteStats(
                total_eligible=len(eligible),
                selected=len(selected),
                processed=len(bullets),
                skipped=len(skipped),
            ),
        )

    def _fallback(self, report: PipelineReport, language: str, reason: str) -> RewriteResult:
        summary_evidence = [
            item.id for item in report.evidence if item.field_path == "entities.summary"
        ]
        summary = SummaryRewriteResult(
            status="unavailable" if "summary" in self.sections else "not_run",
            original=report.entities.summary if "summary" in self.sections else "",
            improved=None,
            evidence_ids=summary_evidence if "summary" in self.sections else [],
            warnings=(
                ["No valid rewrite was generated; the original summary was preserved."]
                if "summary" in self.sections
                else []
            ),
        )
        bullets: list[ExperienceBulletRewriteResult] = []
        eligible = self._eligible_bullets(report) if "experience" in self.sections else []
        selected, skipped = self._select_bullets(eligible)
        for experience_index, bullet_kind, bullet_index in selected:
            experience = report.entities.experience[experience_index]
            values = (
                experience.responsibilities
                if bullet_kind == "responsibility"
                else experience.achievements
            )
            original = values[bullet_index]
            improved = re.sub(r"[ \t]+", " ", original).strip()
            if improved and improved[-1] not in ".!?؟":
                improved += "."
            bullets.append(
                ExperienceBulletRewriteResult(
                    experience_index=experience_index,
                    bullet_index=bullet_index,
                    bullet_kind=bullet_kind,
                    status="improved" if improved != original else "unchanged",
                    original=original,
                    improved=(improved if improved != original else None),
                    evidence_ids=experience.evidence_ids,
                    warnings=["Only safe whitespace and punctuation rules were applied."],
                )
            )

        skills = SkillsSectionRewriteResult()
        if "skills" in self.sections:
            original_items = [item.value for item in report.entities.skills]
            evidence_ids = list(
                dict.fromkeys(
                    evidence_id
                    for item in report.entities.skills
                    for evidence_id in item.evidence_ids
                )
            )
            groups: dict[str, list[str]] = {}
            seen: set[str] = set()
            removed: list[str] = []
            for value in original_items:
                key = self.validator.skill_key(value)
                if key in seen:
                    removed.append(value)
                    continue
                seen.add(key)
                display = _DISPLAY_ALIASES.get(key, value.strip())
                category = self._skill_category(key, language)
                groups.setdefault(category, []).append(display)
            skills = SkillsSectionRewriteResult(
                status=(
                    "improved"
                    if removed
                    or any(
                        _DISPLAY_ALIASES.get(self.validator.skill_key(value), value) != value
                        for value in original_items
                    )
                    else "unchanged"
                ),
                method="deterministic",
                original_items=original_items,
                improved_groups=[
                    SkillGroup(group=group, items=values) for group, values in groups.items()
                ],
                added_items=[],
                removed_duplicates=removed,
                evidence_ids=evidence_ids,
                warnings=["Only deterministic alias normalization and deduplication were applied."],
            )
        notices = [
            RewriteNotice(
                code="AI_PROVIDER_UNAVAILABLE",
                component="rewrites",
                message="The AI rewrite provider was unavailable; safe deterministic rules were used where possible.",
            )
        ]
        skipped_components: list[str] = []
        if skipped:
            skipped_components.append(f"experience_bullets[{len(selected)}:]")
            notices.append(
                RewriteNotice(
                    code="BULLET_REWRITE_LIMIT_APPLIED",
                    component="experience_bullets",
                    message=(
                        f"Selected {len(selected)} of {len(eligible)} eligible bullets; "
                        f"{len(skipped)} were not run."
                    ),
                    severity="information",
                )
            )
        return RewriteResult(
            status="fallback",
            language=language,
            provider="deterministic_safe_rules",
            model=None,
            summary=summary,
            experience_bullets=bullets,
            skills_section=skills,
            warnings=[reason],
            rejected_rewrites=[],
            notices=notices,
            completed_components=[
                name
                for name, value in (
                    ("experience_bullets", bullets),
                    ("skills_section", skills.improved_groups),
                )
                if value
            ],
            rejected_components=["summary"] if "summary" in self.sections else [],
            skipped_components=skipped_components,
            bullet_stats=BulletRewriteStats(
                total_eligible=len(eligible),
                selected=len(selected),
                processed=len(bullets),
                skipped=len(skipped),
            ),
        )

    @staticmethod
    def _classify_component(name, status, completed, unchanged, rejected) -> None:
        if status in {"improved", "generated"}:
            completed.append(name)
        elif status == "unchanged":
            unchanged.append(name)
        elif status in {"rejected", "unavailable"}:
            rejected.append(name)

    @staticmethod
    def _notice(code: str, component: str, message: str) -> RewriteNotice:
        supported = {
            "MODEL_OUTPUT_TRUNCATED",
            "NO_MATERIAL_CHANGE",
            "INVALID_MODEL_RESPONSE",
            "AI_PROVIDER_TIMEOUT",
            "AI_PROVIDER_UNAVAILABLE",
        }
        notice_code = code if code in supported else "INVALID_MODEL_RESPONSE"
        return RewriteNotice(
            code=notice_code,
            component=component,
            message=message,
            severity="information" if code == "NO_MATERIAL_CHANGE" else "warning",
        )

    def _eligible_bullets(self, report: PipelineReport) -> list[tuple[int, str, int]]:
        values: list[tuple[int, str, int]] = []
        for experience_index, experience in enumerate(report.entities.experience):
            for bullet_kind, bullets in (
                ("responsibility", experience.responsibilities),
                ("achievement", experience.achievements),
            ):
                for bullet_index, bullet in enumerate(bullets):
                    if (
                        bullet.strip()
                        and len(bullet.strip()) >= 8
                        and self.validator.incomplete_text_reason(bullet) is None
                    ):
                        values.append((experience_index, bullet_kind, bullet_index))
        return values

    def _select_bullets(self, eligible):
        if self.bullet_selection is not None:
            selected = [
                eligible[index] for index in self.bullet_selection if 0 <= index < len(eligible)
            ][: self.absolute_max_bullets]
        elif self.rewrite_all_bullets:
            selected = eligible[: self.absolute_max_bullets]
        else:
            selected = eligible[: self.max_bullets]
        selected_set = set(selected)
        return selected, [item for item in eligible if item not in selected_set]

    @staticmethod
    def _skill_category(key: str, language: str) -> str:
        if key in {"sql", "postgresql", "mysql", "mongodb"}:
            return (
                "\u0642\u0648\u0627\u0639\u062f \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a"
                if language == "ar"
                else "Databases"
            )
        if key in {"aws", "azure", "docker", "kubernetes", "git"}:
            return (
                "\u0627\u0644\u0645\u0646\u0635\u0627\u062a \u0648\u0627\u0644\u0623\u062f\u0648\u0627\u062a"
                if language == "ar"
                else "Platforms & Tools"
            )
        if key in {
            "python",
            "javascript",
            "typescript",
            "java",
            "c++",
            "c#",
            "react",
            "node.js",
            "django",
            "flask",
            "fastapi",
            "pytorch",
            "tensorflow",
        }:
            return (
                "\u062a\u0642\u0646\u064a\u0627\u062a \u0627\u0644\u0628\u0631\u0645\u062c\u0629"
                if language == "ar"
                else "Programming"
            )
        return (
            "\u0645\u0647\u0627\u0631\u0627\u062a \u0623\u062e\u0631\u0649"
            if language == "ar"
            else "Other Skills"
        )

    @staticmethod
    def _language(report: PipelineReport) -> str:
        extracted_text = " ".join(
            value
            for section in report.extraction.sections.values()
            for value in (section.heading or "", section.content)
            if value
        )
        text = extracted_text or " ".join(
            (
                report.entities.summary,
                *(item.value for item in report.entities.skills),
                *(
                    bullet
                    for experience in report.entities.experience
                    for bullet in (*experience.responsibilities, *experience.achievements)
                ),
            )
        )
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
