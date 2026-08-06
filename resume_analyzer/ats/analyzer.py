"""Canonical ATS analyzer facade."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from resume_analyzer.schemas import ATSIssue, ATSResult, JobMatchResult, PipelineReport

from .config import PLACEHOLDER_PATTERNS, STANDARD_SECTION_KEYS
from .exceptions import InvalidJobDescriptionError
from .formatting import FormattingChecker
from .issue_builder import (
    AnalyzerFindings,
    EvidenceLookup,
    IssueBuilder,
    IssueDraft,
    StrengthDraft,
    detect_language,
)
from .job_match import JobDescriptionMatcher
from .scoring import ATSScoringPolicy
from .template import TemplateAnalyzer

_PLACEHOLDER_EMAIL = re.compile(
    r"(?i)^(?:email|name|student|candidate|yourname|user)@"
    r"(?:email|example|test|sample)\.(?:com|org|net|ca)$"
)
_PLACEHOLDER_PHONE = re.compile(r"^(?:1)?5555555555$")


class ATSAnalyzer:
    """Run deterministic compatibility and optional job matching without mutation."""

    def __init__(
        self,
        *,
        template_analyzer: TemplateAnalyzer | None = None,
        formatting_checker: FormattingChecker | None = None,
        scoring_policy: ATSScoringPolicy | None = None,
        job_matcher: JobDescriptionMatcher | None = None,
        max_job_description_characters: int = 50_000,
    ) -> None:
        self.template_analyzer = template_analyzer or TemplateAnalyzer()
        self.formatting_checker = formatting_checker or FormattingChecker()
        self.scoring_policy = scoring_policy or ATSScoringPolicy()
        self.job_matcher = job_matcher or JobDescriptionMatcher(
            max_characters=max_job_description_characters
        )

    def analyze(
        self,
        report: PipelineReport | Mapping[str, Any],
        *,
        job_description: str | None = None,
    ) -> ATSResult:
        canonical = (
            report if isinstance(report, PipelineReport) else PipelineReport.model_validate(report)
        )
        language = self._language(canonical)
        lookup = EvidenceLookup(canonical)
        findings = AnalyzerFindings()
        extraction_evidence = lookup.paths(
            "extraction.quality_score",
            "extraction.ocr_used",
            "extraction.ocr_usage",
            "extraction.warnings",
        )

        if canonical.extraction.status == "failed" or canonical.extraction.character_count == 0:
            evidence = extraction_evidence or lookup.paths("entities")
            builder = IssueBuilder(canonical, language=language)
            issues = builder.build_issues(
                [
                    IssueDraft(
                        "EMPTY_OR_UNREADABLE_TEXT",
                        tuple(evidence),
                        "ats_analyzer",
                        0.99,
                    )
                ]
            )
            return ATSResult(
                status="failed",
                language=language,
                issues=issues,
                warnings=list(dict.fromkeys(builder.warnings)),
                limitations=self._limitations(),
                interpretation=(
                    "ATS compatibility could not be evaluated because readable text was not "
                    "available. This is not a hiring prediction."
                ),
                parsing_integrity_context=self._parsing_integrity_context(canonical),
                job_match=self._job_match(canonical, job_description),
            )

        if canonical.extraction.word_count < 40:
            findings.issues.append(
                IssueDraft("LOW_TEXT_VOLUME", tuple(extraction_evidence), "ats_analyzer", 0.95)
            )
        if canonical.extraction.quality_score < 70:
            findings.issues.append(
                IssueDraft(
                    "LOW_EXTRACTION_QUALITY",
                    tuple(extraction_evidence),
                    "ats_analyzer",
                    0.92,
                )
            )
        elif canonical.extraction.quality_score >= 85:
            findings.strengths.append(
                StrengthDraft(
                    "TEXT_EXTRACTION_HEALTHY",
                    "extraction",
                    tuple(extraction_evidence),
                    "ats_analyzer",
                    0.96,
                )
            )
        self._ocr_findings(canonical, lookup, findings, extraction_evidence)
        if self._broken_ratio(canonical) >= 0.01:
            evidence = lookup.paths("extraction.sections") or extraction_evidence
            findings.issues.append(
                IssueDraft("BROKEN_CHARACTER_ENCODING", tuple(evidence), "ats_analyzer", 0.94)
            )

        self._structure_and_content(canonical, lookup, findings)
        findings.extend(self.template_analyzer.analyze(canonical))
        findings.extend(self.formatting_checker.analyze(canonical))
        builder = IssueBuilder(canonical, language=language)
        issues = builder.build_issues(findings.issues)
        strengths = builder.build_strengths(self._consistent_strengths(findings.strengths, issues))
        score, label, breakdown = self.scoring_policy.score(issues)
        warnings = list(dict.fromkeys((*findings.warnings, *builder.warnings)))
        status = (
            "partial"
            if any(value.startswith("cannot_verify") for value in warnings)
            else "complete"
        )
        return ATSResult(
            status=status,
            language=language,
            ats_compatibility_score=score,
            score_label=label,
            score_method=self.scoring_policy.method,
            score_breakdown=breakdown,
            issues=issues,
            strengths=strengths,
            job_match=self._job_match(canonical, job_description),
            warnings=warnings,
            limitations=self._limitations(),
            interpretation=self._score_interpretation(score),
            parsing_integrity_context=self._parsing_integrity_context(canonical),
        )

    @staticmethod
    def _score_interpretation(score: int) -> str:
        if score >= 85:
            detail = "The document is generally accessible to resume-parsing software."
        elif score >= 70:
            detail = "The document is readable, but some formatting may reduce reliability."
        elif score >= 50:
            detail = (
                "The document can be partially read by resume-parsing software, but its "
                "formatting may prevent reliable interpretation of some fields."
            )
        else:
            detail = (
                "The document has substantial extractability or formatting barriers for "
                "resume-parsing software."
            )
        return f"{detail} ATS compatibility is not a prediction of hiring probability."

    @staticmethod
    def _parsing_integrity_context(report: PipelineReport) -> str | None:
        quality = report.data_quality
        if quality.status in {"needs_review", "poor"}:
            if (
                quality.layout_reconstruction_quality is not None
                and quality.layout_reconstruction_quality < 80
            ):
                return (
                    "The document can be partially read by ATS software, but the complex "
                    "layout prevents reliable interpretation of several fields."
                )
            return (
                "ATS readability and parsing integrity are separate: some extracted fields "
                "still require review."
            )
        return None

    def _structure_and_content(
        self,
        report: PipelineReport,
        lookup: EvidenceLookup,
        findings: AnalyzerFindings,
    ) -> None:
        sections = report.extraction.sections
        active_sections = {
            key: section
            for key, section in sections.items()
            if key.casefold() != "contact_header" and section.content.strip()
        }
        keys = {key.casefold() for key in active_sections}
        if not report.entities.summary:
            findings.issues.append(
                IssueDraft(
                    "MISSING_SUMMARY",
                    tuple(lookup.paths("entities.summary")),
                    "ats_analyzer",
                    0.96,
                )
            )
        if report.entities.skills and "skills" not in keys:
            evidence = [
                *lookup.paths("entities.skills")[:4],
                *lookup.paths("extraction.section_order")[:1],
            ]
            findings.issues.append(
                IssueDraft("MISSING_SKILLS_SECTION", tuple(evidence), "ats_analyzer", 0.92)
            )
        elif report.entities.skills and "skills" in keys:
            findings.strengths.append(
                StrengthDraft(
                    "DEDICATED_SKILLS_SECTION",
                    "structure",
                    tuple(lookup.paths("entities.skills", "extraction.sections.skills")),
                    "ats_analyzer",
                    0.94,
                )
            )
        if not report.entities.experience:
            student_like = bool(report.entities.education and report.entities.projects)
            findings.issues.append(
                IssueDraft(
                    "STUDENT_EXPERIENCE_OPTIONAL" if student_like else "MISSING_EXPERIENCE",
                    tuple(
                        lookup.paths(
                            "entities.experience", "entities.education", "entities.projects"
                        )
                    ),
                    "ats_analyzer",
                    0.85 if student_like else 0.95,
                )
            )

        normalized_headings = {
            key: " ".join((section.heading or key).casefold().split())
            for key, section in active_sections.items()
        }
        duplicates = {
            value for value, count in Counter(normalized_headings.values()).items() if count > 1
        }
        if duplicates:
            evidence = [
                evidence_id
                for key, normalized in normalized_headings.items()
                if normalized in duplicates
                for evidence_id in lookup.paths(f"extraction.sections.{key}.heading")
            ]
            findings.issues.append(
                IssueDraft(
                    "DUPLICATE_SECTION_HEADING",
                    tuple(evidence[:8] or lookup.paths("extraction.sections")[:8]),
                    "ats_analyzer",
                    0.9,
                )
            )
        ambiguous = [key for key in active_sections if key.casefold() not in STANDARD_SECTION_KEYS]
        if ambiguous:
            evidence = [
                value
                for key in ambiguous
                for value in (
                    lookup.paths(f"extraction.sections.{key}.heading")
                    or lookup.paths(f"extraction.sections.{key}.content")
                )
            ]
            findings.issues.append(
                IssueDraft(
                    "AMBIGUOUS_SECTION_HEADING",
                    tuple(evidence[:8]),
                    "ats_analyzer",
                    0.75,
                )
            )
        if len(active_sections) > 12:
            findings.issues.append(
                IssueDraft(
                    "EXCESSIVE_SECTION_COUNT",
                    tuple(lookup.paths("extraction.sections")),
                    "ats_analyzer",
                    0.82,
                )
            )
        fragmented = [key for key, section in active_sections.items() if 0 < section.words < 3]
        if fragmented:
            evidence = [
                value
                for key in fragmented
                for value in lookup.paths(f"extraction.sections.{key}.content")
            ]
            findings.issues.append(
                IssueDraft("FRAGMENTED_SECTION", tuple(evidence[:8]), "ats_analyzer", 0.78)
            )

        for index, experience in enumerate(report.entities.experience):
            if not experience.job_title or not experience.company:
                findings.issues.append(
                    IssueDraft(
                        "EXPERIENCE_ENTRY_UNCLEAR",
                        tuple(lookup.paths(f"entities.experience[{index}]")),
                        "ats_analyzer",
                        0.88,
                    )
                )
        for index, project in enumerate(report.entities.projects):
            if not project.description:
                findings.issues.append(
                    IssueDraft(
                        "PROJECT_DESCRIPTION_MISSING",
                        tuple(lookup.paths(f"entities.projects[{index}]")),
                        "ats_analyzer",
                        0.82,
                    )
                )
        for index, education in enumerate(report.entities.education):
            if not education.degree or not education.institution:
                findings.issues.append(
                    IssueDraft(
                        "EDUCATION_ENTRY_UNCLEAR",
                        tuple(lookup.paths(f"entities.education[{index}]")),
                        "ats_analyzer",
                        0.82,
                    )
                )

        contact = report.entities.contact
        contact_header = sections.get("contact_header")
        contact_header_text = contact_header.content if contact_header else ""
        placeholder_contact = bool(
            any(re.search(pattern, contact_header_text) for pattern in PLACEHOLDER_PATTERNS)
            or (contact.email and _PLACEHOLDER_EMAIL.fullmatch(contact.email.strip()))
            or (contact.phone and _PLACEHOLDER_PHONE.fullmatch(re.sub(r"\D", "", contact.phone)))
        )
        for field, code in (
            ("name", "MISSING_NAME"),
            ("email", "MISSING_EMAIL"),
            ("phone", "MISSING_PHONE"),
        ):
            if not getattr(contact, field):
                findings.issues.append(
                    IssueDraft(
                        code,
                        tuple(lookup.paths(f"entities.contact.{field}")),
                        "ats_analyzer",
                        0.97,
                    )
                )
        accessible_sources = {"selectable_text", "annotation"}
        contact_sources = {
            field: (
                contact.source_types.get(field)
                or (
                    "ocr"
                    if report.extraction.ocr_used
                    or report.extraction.visual_metadata.contact_ocr_used
                    else "selectable_text"
                )
            )
            for field in ("email", "phone")
        }
        if (
            contact.email
            and contact.phone
            and not placeholder_contact
            and all(contact_sources[field] in accessible_sources for field in ("email", "phone"))
        ):
            findings.strengths.append(
                StrengthDraft(
                    "CONTACT_TEXT_ACCESSIBLE",
                    "contact",
                    tuple(lookup.paths("entities.contact.email", "entities.contact.phone")),
                    "ats_analyzer",
                    0.98,
                )
            )
        core = {"skills", "experience", "education"}
        if len(core & keys) >= 2:
            findings.strengths.append(
                StrengthDraft(
                    "CLEAR_SECTION_STRUCTURE",
                    "structure",
                    tuple(lookup.paths("extraction.sections")),
                    "ats_analyzer",
                    0.9,
                )
            )

    @staticmethod
    def _ocr_findings(
        report: PipelineReport,
        lookup: EvidenceLookup,
        findings: AnalyzerFindings,
        extraction_evidence: list[str],
    ) -> None:
        extraction = report.extraction
        usage = extraction.ocr_usage
        if not (extraction.ocr_used or usage.used):
            return

        scope = usage.scope if usage.used else "unknown"
        ocr_evidence = (
            lookup.paths("extraction.ocr_usage", "extraction.ocr_used") or extraction_evidence
        )
        if scope in {"full_document", "unknown"}:
            findings.issues.append(
                IssueDraft(
                    "OCR_REVIEW_REQUIRED",
                    tuple(ocr_evidence),
                    "ats_analyzer",
                    0.9,
                    tuple(usage.pages),
                )
            )
        elif scope in {"page", "mixed"}:
            findings.issues.append(
                IssueDraft(
                    "PAGE_OCR_REVIEW_REQUIRED",
                    tuple(ocr_evidence),
                    "ats_analyzer",
                    0.9,
                    tuple(usage.pages),
                )
            )

        contact = report.entities.contact
        ocr_core_count = sum(
            contact.source_types.get(field) == "ocr" for field in ("email", "phone")
        )
        visual = extraction.visual_metadata
        if not ocr_core_count and scope not in {"contact_header", "mixed"}:
            return
        contact_evidence = (
            lookup.paths("entities.contact.email", "entities.contact.phone")
            or lookup.paths("extraction.visual_metadata")
            or ocr_evidence
        )
        if visual.contact_ocr_status in {"failed", "unavailable"}:
            code = "CONTACT_OCR_FAILED"
        elif visual.contact_ocr_status == "partial":
            code = "CONTACT_PARTIAL_OCR_REVIEW_REQUIRED"
        elif ocr_core_count == 1:
            code = "CONTACT_MIXED_SOURCE_REVIEW_REQUIRED"
        else:
            code = "CONTACT_OCR_REVIEW_REQUIRED"
        findings.issues.append(
            IssueDraft(
                code,
                tuple(contact_evidence),
                "ats_analyzer",
                0.94,
                tuple(usage.pages),
            )
        )

    @staticmethod
    def _consistent_strengths(
        strengths: list[StrengthDraft],
        issues: list[ATSIssue],
    ) -> list[StrengthDraft]:
        issue_codes = {item.code for item in issues}
        blocked: set[str] = set()
        if issue_codes & {
            "CONTACT_OCR_REVIEW_REQUIRED",
            "CONTACT_MIXED_SOURCE_REVIEW_REQUIRED",
            "CONTACT_PARTIAL_OCR_REVIEW_REQUIRED",
            "CONTACT_OCR_FAILED",
            "IMAGE_ONLY_CONTACT_INFORMATION",
            "MISSING_EMAIL",
            "MISSING_PHONE",
        }:
            blocked.add("CONTACT_TEXT_ACCESSIBLE")
        if "MULTI_COLUMN_READING_ORDER_RISK" in issue_codes:
            blocked.update({"SINGLE_COLUMN_LAYOUT", "VERIFIED_COLUMN_READING_ORDER"})
        if "CONTENT_CRITICAL_TABLE" in issue_codes:
            blocked.add("TABLE_TEXT_EXTRACTED")
        return [item for item in strengths if item.code not in blocked]

    @staticmethod
    def _broken_ratio(report: PipelineReport) -> float:
        text = "\n".join(section.content for section in report.extraction.sections.values())
        if not text:
            return 0.0
        broken = sum(text.count(value) for value in ("�", "ï¿½", "Ã", "Â"))
        return broken / len(text)

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
            )
        )
        return detect_language(text)

    @staticmethod
    def _limitations() -> list[str]:
        return [
            "This is a deterministic project heuristic, not a certified commercial ATS score.",
            "Visual checks report cannot_verify when the extraction metadata is unavailable.",
            "Job-description matching is a separate lexical score and does not prove candidate skills.",
        ]

    def _job_match(self, report: PipelineReport, job_description: str | None):
        try:
            return self.job_matcher.match(report, job_description)
        except InvalidJobDescriptionError as exc:
            return JobMatchResult(status="failed", warnings=[str(exc)])
