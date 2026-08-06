"""Deterministic semantic-integrity checks for canonical extraction output."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any, Literal

from resume_analyzer.schemas import (
    DataQualityInfo,
    ExperienceItem,
    ParsingDimensionName,
    ParsingIntegrityAdjustment,
    ParsingIntegrityBreakdown,
    ParsingIntegrityDimensionDetail,
    ParsingIntegrityDimensions,
    PipelineReport,
    QualityIssue,
)
from resume_analyzer.terminology import is_known_technology

from .evidence_coherence import EvidenceCoherenceValidator


class CanonicalDataQualityAnalyzer:
    """Score parsing integrity independently from ATS compatibility.

    The score measures whether the canonical entities are coherent and traceable.
    Text recoverability is reported as a separate dimension and is intentionally
    not allowed to hide layout, segmentation, or evidence defects.
    """

    _INCOMPLETE = re.compile(r"(?i)(?:[,;:]|\b(?:and|or|with|including|و|أو|مع))\s*$")
    _ACTION_TITLE = re.compile(
        r"(?i)^(?:built|developed|developing|implemented|implementing|worked|working|"
        r"preparing|created|designed|supporting)\b"
    )
    _SENTENCE_COMPANY = re.compile(
        r"(?i)\b(?:i|we|they|responsible|worked|developed|built|helped|"
        r"where|using|with a team)\b"
    )
    _ORG_SUFFIX = re.compile(
        r"(?i)\b(?:inc|llc|ltd|limited|corp|company|group|gmbh|plc|labs?|"
        r"systems?|solutions?|technologies|partners?|bank|university|"
        r"شركة|مؤسسة|مجموعة|جامعة|بنك)\b"
    )
    _VAGUE_BULLET = re.compile(
        r"(?i)^(?:responsible for everything|worked with a team|"
        r"used many technologies|helped with .+ and other tasks|"
        r"did .+ sometimes)\W*$"
    )
    _VAGUE_PROJECT = re.compile(
        r"(?i)\b(?:many more things|various things|and technologies|" r"help(?:s|ed)? users)\b"
    )
    _UNSUPPORTED_METRIC = re.compile(
        r"(?i)\b(?:([2-9]\d{2,}|[1-9]\d{3,})\s*%|"
        r"(?:saved|generated|increased|reduced).{0,35}\b(?:millions?|billions?)\b)"
    )
    _DATE_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
    _GENERIC_SKILLS = {
        "planning",
        "operations",
        "account management",
        "accounting",
        "presentation",
    }
    _TECH_LOCATION_TERMS = {
        "business",
        "networks",
        "software",
        "artificial intelligence",
        "web",
        "python",
        "sql",
    }
    _DIMENSION_WEIGHTS: dict[ParsingDimensionName, float] = {
        "contact_integrity": 0.12,
        "section_segmentation_integrity": 0.12,
        "reading_order_integrity": 0.16,
        "experience_integrity": 0.14,
        "project_integrity": 0.08,
        "education_integrity": 0.08,
        "skills_integrity": 0.08,
        "evidence_consistency": 0.12,
        "entity_coherence": 0.06,
        "confidence_coverage": 0.04,
    }
    _AREA_DIMENSIONS: dict[str, ParsingDimensionName] = {
        "contact": "contact_integrity",
        "sections": "section_segmentation_integrity",
        "layout": "reading_order_integrity",
        "content_quality": "reading_order_integrity",
        "experience": "experience_integrity",
        "projects": "project_integrity",
        "education": "education_integrity",
        "skills": "skills_integrity",
        "evidence": "evidence_consistency",
        "entities": "entity_coherence",
    }
    _EXPERIENCE_CONTENT_CODES = {
        "truncated_experience_bullets",
        "duplicate_experience_bullets",
        "unsupported_experience_metric",
        "vague_experience_content",
    }

    def analyze(self, report: PipelineReport) -> DataQualityInfo:
        issues: list[QualityIssue] = []
        scores = {name: 100 for name in self._DIMENSION_WEIGHTS}

        def deduct(dimension: str, amount: int) -> None:
            scores[dimension] = max(0, scores[dimension] - amount)

        def add_issue(
            code: str,
            area: str,
            severity: Literal["low", "medium", "high"],
            title: str,
            field_path: str,
            message: str,
            explanation: str,
            suggested_action: str,
            *,
            evidence_ids: Iterable[str] = (),
            confidence: float = 0.9,
        ) -> None:
            key = (code, field_path)
            if any((item.code, item.field_path) == key for item in issues):
                return
            issues.append(
                QualityIssue(
                    code=code,
                    area=area,
                    severity=severity,
                    title=title,
                    field_path=field_path,
                    confidence=confidence,
                    message=message,
                    explanation=explanation,
                    suggested_action=suggested_action,
                    evidence_ids=list(dict.fromkeys(evidence_ids))[:12],
                )
            )

        self._contact_checks(report, deduct, add_issue)
        ambiguities = self._section_checks(report, deduct, add_issue)
        self._layout_checks(report, deduct, add_issue)
        self._experience_checks(report, deduct, add_issue)
        self._project_checks(report, deduct, add_issue)
        self._education_checks(report, deduct, add_issue)
        self._skill_checks(report, deduct, add_issue)
        self._evidence_checks(report, deduct, add_issue)
        self._confidence_checks(report, deduct, add_issue)
        semantic_issue_penalty = min(
            30,
            sum(
                5 if item.severity == "high" else 2 if item.severity == "medium" else 0
                for item in issues
                if item.area not in {"layout", "evidence"}
            ),
        )
        deduct("entity_coherence", semantic_issue_penalty)

        dimensions = ParsingIntegrityDimensions(**scores)
        weighted_subtotal = round(
            sum(scores[name] * weight for name, weight in self._DIMENSION_WEIGHTS.items())
        )
        parsing_score = weighted_subtotal
        weakest_dimension = min(scores.values())
        adjustments: list[ParsingIntegrityAdjustment] = []
        if weakest_dimension < 50:
            parsing_score = min(parsing_score, 79)
        elif weakest_dimension < 70:
            parsing_score = min(parsing_score, 89)
        if parsing_score != weighted_subtotal:
            trigger_dimension = next(
                name for name, score in scores.items() if score == weakest_dimension
            )
            cap = 79 if weakest_dimension < 50 else 89
            adjustments.append(
                ParsingIntegrityAdjustment(
                    code=f"weak_dimension_review_cap_{cap}",
                    points=parsing_score - weighted_subtotal,
                    trigger_dimension=trigger_dimension,
                    explanation=(
                        f"{trigger_dimension} scored {weakest_dimension}/100, so the "
                        f"overall parsing-integrity score is capped at {cap}."
                    ),
                )
            )
        status: Literal["good", "needs_review", "poor"] = (
            "good" if parsing_score >= 90 else "needs_review" if parsing_score >= 65 else "poor"
        )
        has_layout_risk = scores["reading_order_integrity"] < 80
        if status == "good":
            interpretation = (
                "Canonical entities are coherent and supported by the available source evidence."
            )
        elif has_layout_risk:
            interpretation = (
                "Text was recovered, but complex layout or weak source evidence makes some "
                "fields unreliable. Review the flagged fields before using them."
            )
        else:
            interpretation = (
                "Some canonical fields are ambiguous or weakly supported and require review."
            )

        issues = [
            item.model_copy(update={"dimensions": self._issue_dimensions(item)}) for item in issues
        ]
        review_fields = [
            item.field_path
            for item in issues
            if item.severity in {"medium", "high"} and item.field_path
        ]
        breakdown_dimensions = {
            name: ParsingIntegrityDimensionDetail(
                score=scores[name],
                weight=weight,
                weighted_points=scores[name] * weight,
                issue_codes=[item.code for item in issues if name in item.dimensions],
                explanations=self._dimension_explanations(name, scores[name], issues),
            )
            for name, weight in self._DIMENSION_WEIGHTS.items()
        }
        breakdown = ParsingIntegrityBreakdown(
            dimensions=breakdown_dimensions,
            weighted_subtotal=weighted_subtotal,
            adjustments=adjustments,
            total=parsing_score,
        )
        return DataQualityInfo(
            status=status,
            score=parsing_score,
            parsing_integrity_score=parsing_score,
            text_extraction_quality=report.extraction.quality_score,
            layout_reconstruction_quality=scores["reading_order_integrity"],
            section_segmentation_quality=scores["section_segmentation_integrity"],
            contact_readability=report.extraction.visual_metadata.contact_readability,
            dimensions=dimensions,
            breakdown=breakdown,
            fields_requiring_review=list(dict.fromkeys(review_fields)),
            ambiguities=ambiguities,
            issues=issues,
            interpretation=interpretation,
        )

    def annotate_experience_reviews(
        self,
        report: PipelineReport,
        quality: DataQualityInfo,
    ) -> list[ExperienceItem]:
        """Propagate content findings without converting them into parser failures."""

        annotated: list[ExperienceItem] = []
        for experience in report.entities.experience:
            evidence = set(experience.evidence_ids)
            matching = [
                issue
                for issue in quality.issues
                if issue.code in self._EXPERIENCE_CONTENT_CODES
                and evidence.intersection(issue.evidence_ids)
            ]
            severity_counts = Counter(issue.severity for issue in matching)
            content_needs_review = bool(
                severity_counts["high"] >= 1
                or severity_counts["medium"] >= 2
                or severity_counts["low"] >= 3
            )
            parsing_needs_review = bool(experience.parsing_needs_review)
            reasons = [f"{issue.code}: {issue.message}" for issue in matching]
            data = experience.model_dump(mode="python")
            data.update(
                parsing_needs_review=parsing_needs_review,
                content_needs_review=content_needs_review,
                needs_review=parsing_needs_review or content_needs_review,
                review_reasons=list(dict.fromkeys(reasons)),
            )
            annotated.append(ExperienceItem.model_validate(data))
        return annotated

    def _issue_dimensions(
        self,
        issue: QualityIssue,
    ) -> list[ParsingDimensionName]:
        dimensions: list[ParsingDimensionName] = []
        primary = self._AREA_DIMENSIONS.get(issue.area)
        if primary:
            dimensions.append(primary)
        if issue.code == "no_canonical_sections_recovered":
            dimensions.extend(["entity_coherence", "confidence_coverage"])
        if issue.code in {
            "calendar_value_extracted_as_phone",
            "template_remnant_detected",
            "evidence_cross_column",
            "evidence_section_mismatch",
            "low_confidence_entity_ratio",
        }:
            dimensions.append("entity_coherence")
        if issue.code == "low_confidence_entity_ratio":
            dimensions.append("confidence_coverage")
        if issue.area not in {"layout", "evidence"} and issue.severity in {
            "medium",
            "high",
        }:
            dimensions.append("entity_coherence")
        return list(dict.fromkeys(dimensions))

    @staticmethod
    def _dimension_explanations(
        dimension: ParsingDimensionName,
        score: int,
        issues: list[QualityIssue],
    ) -> list[str]:
        relevant = [item for item in issues if dimension in item.dimensions]
        if score == 100:
            return ["No deterministic integrity deductions were triggered."]
        codes = ", ".join(dict.fromkeys(item.code for item in relevant))
        if codes:
            return [
                f"Started at 100; deterministic checks deducted {100 - score} point(s).",
                f"Triggering checks: {codes}.",
            ]
        return [f"Started at 100; parser review-state checks deducted {100 - score} point(s)."]

    def _contact_checks(self, report, deduct, add_issue) -> None:
        visual = report.extraction.visual_metadata
        contact = report.entities.contact
        contact_evidence = self._path_evidence(report, "entities.contact")
        if visual.possible_image_only_contact:
            missing = [
                field for field in ("email", "phone", "linkedin") if not getattr(contact, field)
            ]
            penalty = 18 if len(missing) >= 2 else 12
            deduct("contact_integrity", penalty)
            add_issue(
                "image_only_contact_requires_review",
                "contact",
                "high" if len(missing) >= 2 else "medium",
                "Contact details may be embedded in an image",
                "entities.contact",
                "The header image may contain contact details that were not fully recovered.",
                "Image-only contact content is less reliable than searchable text and may be "
                "missed by parsers.",
                "Add email, phone, and profile links as selectable text in the header.",
                evidence_ids=contact_evidence,
                confidence=0.96,
            )
        if visual.contact_readability in {
            "partially_readable",
            "image_only",
            "unreadable",
        }:
            deduct("contact_integrity", 10)
            add_issue(
                "contact_readability_limited",
                "contact",
                "medium",
                "Contact readability is limited",
                "extraction.visual_metadata.contact_readability",
                f"Contact readability was classified as {visual.contact_readability}.",
                "Targeted OCR recovered only the text it could recognize with sufficient "
                "confidence.",
                "Verify the displayed contact fields and replace image text with real text.",
                evidence_ids=self._path_evidence(report, "extraction.visual_metadata"),
                confidence=0.95,
            )
        if contact.phone and self._looks_like_calendar_value(contact.phone):
            deduct("contact_integrity", 55)
            deduct("entity_coherence", 20)
            add_issue(
                "calendar_value_extracted_as_phone",
                "contact",
                "high",
                "A date-like value was extracted as a phone",
                "entities.contact.phone",
                "The phone value has the shape of a year or date range.",
                "Calendar values are not valid contact evidence, even when their digits match "
                "a phone regular expression.",
                "Remove the value and require a contact-region or phone-label match.",
                evidence_ids=self._path_evidence(report, "entities.contact.phone"),
                confidence=0.99,
            )

    def _section_checks(self, report, deduct, add_issue) -> list[str]:
        semantic_sections = [
            key
            for key, section in report.extraction.sections.items()
            if key not in {"contact_header", "additional_info"} and section.content.strip()
        ]
        semantic_entity_count = sum(
            len(collection)
            for collection in (
                report.entities.skills,
                report.entities.education,
                report.entities.experience,
                report.entities.projects,
                report.entities.languages,
                report.entities.certifications,
            )
        )
        if not semantic_sections and report.extraction.word_count >= 10:
            deduct("section_segmentation_integrity", 55)
            deduct("entity_coherence", 35 if semantic_entity_count == 0 else 20)
            deduct("confidence_coverage", 20)
            add_issue(
                "no_canonical_sections_recovered",
                "sections",
                "high",
                "No semantic resume sections were recovered",
                "extraction.sections",
                "Readable text was found, but no summary, skills, experience, project, "
                "education, language, or certification section could be reconstructed.",
                "Schema validity alone cannot establish parsing integrity when substantive "
                "resume content remains unclassified.",
                "Review OCR language/quality and provide selectable text with conventional "
                "section headings.",
                evidence_ids=self._path_evidence(report, "extraction.sections"),
                confidence=0.98,
            )
        raw_warnings = [
            *report.extraction.warnings,
            *(
                warning
                for section in report.extraction.sections.values()
                for warning in section.warnings
            ),
        ]
        ambiguities = list(
            dict.fromkeys(
                warning
                for warning in raw_warnings
                if "ambiguous_section_heading" in warning
                or "mixed_section_heading" in warning
                or "unmatched_heading" in warning
            )
        )
        ambiguous_count = sum("ambiguous_section_heading" in warning for warning in ambiguities)
        mixed_count = sum("mixed_section_heading" in warning for warning in ambiguities)
        unmatched_count = sum("unmatched_heading" in warning for warning in ambiguities)
        if ambiguous_count:
            deduct("section_segmentation_integrity", min(18, ambiguous_count * 6))
            add_issue(
                "ambiguous_section_headings",
                "sections",
                "medium",
                "Some section headings are non-standard",
                "extraction.sections",
                f"{ambiguous_count} heading(s) required conservative alias matching.",
                "Non-standard headings reduce confidence even when nearby content supports a "
                "likely section.",
                "Use conventional headings or review the affected section assignments.",
                evidence_ids=self._path_evidence(report, "extraction.sections"),
                confidence=0.9,
            )
        if mixed_count:
            deduct("section_segmentation_integrity", min(16, mixed_count * 8))
            add_issue(
                "mixed_section_content",
                "sections",
                "medium",
                "A heading combines different item types",
                "extraction.sections",
                f"{mixed_count} mixed section(s) required item-level classification.",
                "Certifications, courses, licenses, and interests cannot safely share one "
                "canonical entity type.",
                "Separate unrelated item types under conventional headings.",
                evidence_ids=self._path_evidence(report, "extraction.sections"),
                confidence=0.94,
            )
        if unmatched_count:
            deduct("section_segmentation_integrity", min(24, unmatched_count * 8))
        return ambiguities

    def _layout_checks(self, report, deduct, add_issue) -> None:
        pages = report.extraction.page_layouts
        high_risk = [page for page in pages if page.reading_order_risk == "high"]
        medium_risk = [page for page in pages if page.reading_order_risk == "medium"]
        if high_risk or medium_risk:
            deduct(
                "reading_order_integrity",
                min(36, len(high_risk) * 20 + len(medium_risk) * 8),
            )
            add_issue(
                "multi_column_reading_risk",
                "layout",
                "high" if high_risk else "medium",
                "Reading order requires column reconstruction",
                "extraction.page_layouts",
                "One or more pages have parallel text streams or uncertain reading order.",
                "A visually readable layout can still be interpreted in the wrong order by "
                "software.",
                "Use a single-column layout or verify all column-local fields.",
                evidence_ids=self._page_evidence(report, high_risk or medium_risk),
                confidence=0.97,
            )

        warning_map = {
            "TEMPLATE_REMNANT_DETECTED": (
                8,
                "template_remnant_detected",
                "content_quality",
                "Template-remnant text was detected",
                "Remove template instructions and provider residue from the document.",
            ),
            "SPARSE_TRAILING_PAGE": (
                10,
                "sparse_trailing_page",
                "layout",
                "The trailing page has little useful content",
                "Remove the extra page or rebalance content across pages.",
            ),
            "EXCESSIVE_WHITESPACE": (
                4,
                "excessive_whitespace",
                "layout",
                "A page contains excessive whitespace",
                "Tighten page breaks and spacing while keeping the document readable.",
            ),
            "EXCESSIVE_SMALL_TEXT": (
                8,
                "excessive_small_text",
                "layout",
                "A large proportion of text is very small",
                "Increase body text size and simplify the layout.",
            ),
            "TEMPLATE_DECORATION_OVERUSE": (
                4,
                "template_decoration_overuse",
                "layout",
                "Decorative shapes increase layout complexity",
                "Reduce decorative shapes that do not convey resume content.",
            ),
        }
        all_warnings = {warning for page in pages for warning in page.warnings} | set(
            report.extraction.warnings
        )
        for marker, (
            penalty,
            code,
            area,
            title,
            action,
        ) in warning_map.items():
            if not any(marker.casefold() in warning.casefold() for warning in all_warnings):
                continue
            deduct("reading_order_integrity", penalty)
            if marker == "TEMPLATE_REMNANT_DETECTED":
                deduct("entity_coherence", 4)
            add_issue(
                code,
                area,
                "medium",
                title,
                "extraction.page_layouts",
                title + ".",
                "The page-level layout model detected this risk from general geometry and "
                "content rules.",
                action,
                evidence_ids=self._path_evidence(report, "extraction"),
                confidence=0.95,
            )

    @staticmethod
    def _source_blocks_for_evidence(report: PipelineReport, evidence_ids: Iterable[str]):
        evidence = {item.id: item for item in report.evidence}
        blocks = {item.id: item for item in report.extraction.layout_blocks}
        output = []
        visited: set[str] = set()

        def visit(evidence_id: str) -> None:
            if evidence_id in visited:
                return
            visited.add(evidence_id)
            record = evidence.get(evidence_id)
            if record is None:
                return
            if record.parent_evidence_ids:
                for parent_id in record.parent_evidence_ids:
                    visit(parent_id)
                return
            block = blocks.get(record.source.block_id or "")
            if block is not None:
                output.append(block)

        for evidence_id in evidence_ids:
            visit(evidence_id)
        return output

    def _project_title_has_header_support(self, report, project) -> bool:
        evidence_ids = project.field_evidence_ids.get("name") or project.evidence_ids
        source_blocks = self._source_blocks_for_evidence(report, evidence_ids)
        section = report.extraction.sections.get("projects")
        ordered_ids = list(section.block_ids if section else [])
        all_blocks = {item.id: item for item in report.extraction.layout_blocks}
        normalized_name = re.sub(r"[.,;:\s]+$", "", project.name or "").casefold()
        for block in source_blocks:
            normalized_text = re.sub(r"[.,;:\s]+$", "", block.text).casefold()
            if normalized_text != normalized_name:
                continue
            if block.font_weight == "bold":
                return True
            try:
                index = ordered_ids.index(block.id)
            except ValueError:
                continue
            if index == 0:
                return True
            previous = all_blocks.get(ordered_ids[index - 1])
            following = (
                all_blocks.get(ordered_ids[index + 1])
                if index + 1 < len(ordered_ids)
                else None
            )
            if (
                previous
                and block.bbox
                and previous.bbox
                and block.bbox.top - previous.bbox.bottom >= 7.0
            ):
                return True
            if (
                following
                and block.bbox
                and following.bbox
                and abs(block.bbox.x0 - following.bbox.x0) >= 10.0
            ):
                return True
        return False

    def _experience_checks(self, report, deduct, add_issue) -> None:
        truncated: list[Any] = []
        duplicates: list[Any] = []
        sentence_companies: list[Any] = []
        suspicious_companies: list[Any] = []
        unsupported: list[Any] = []
        vague: list[Any] = []
        for experience in report.entities.experience:
            if experience.company and self._SENTENCE_COMPANY.search(experience.company):
                sentence_companies.append(experience)
            if experience.company and (
                (
                    re.fullmatch(r"[A-Z][A-Z0-9+./-]{1,9}s?", experience.company)
                    or is_known_technology(experience.company)
                )
                and not self._ORG_SUFFIX.search(experience.company)
            ):
                suspicious_companies.append(experience)
            seen: set[str] = set()
            bullets = [*experience.responsibilities, *experience.achievements]
            for bullet in bullets:
                if self._INCOMPLETE.search(bullet):
                    truncated.append(experience)
                key = self._normalized_sentence(bullet)
                if key in seen:
                    duplicates.append(experience)
                seen.add(key)
                if self._UNSUPPORTED_METRIC.search(bullet):
                    unsupported.append(experience)
                if self._VAGUE_BULLET.search(bullet):
                    vague.append(experience)

        self._entity_issue(
            report,
            truncated,
            deduct,
            add_issue,
            dimension="experience_integrity",
            penalty=min(21, len(truncated) * 7),
            code="truncated_experience_bullets",
            severity="high",
            title="An experience bullet may be incomplete",
            path="entities.experience",
            message=f"Detected {len(truncated)} responsibility line(s) ending in incomplete syntax.",
            explanation="A trailing conjunction or delimiter often indicates a broken wrapped line.",
            action="Join the continuation or rewrite the bullet as a complete statement.",
        )
        self._entity_issue(
            report,
            duplicates,
            deduct,
            add_issue,
            dimension="experience_integrity",
            penalty=min(12, len(duplicates) * 6),
            code="duplicate_experience_bullets",
            severity="medium",
            title="Duplicate experience bullets were detected",
            path="entities.experience",
            message=f"Detected {len(duplicates)} punctuation-normalized duplicate bullet(s).",
            explanation="Punctuation changes do not make two otherwise identical bullets unique.",
            action="Keep one copy of each responsibility or achievement.",
        )
        self._entity_issue(
            report,
            sentence_companies,
            deduct,
            add_issue,
            dimension="experience_integrity",
            penalty=min(32, len(sentence_companies) * 16),
            code="company_sentence_fragment",
            severity="high",
            title="A company value resembles prose",
            path="entities.experience",
            message=f"Detected {len(sentence_companies)} sentence-like company value(s).",
            explanation="Company evidence should belong to the same local title/date group.",
            action="Review the company field against the source block group.",
        )
        self._entity_issue(
            report,
            suspicious_companies,
            deduct,
            add_issue,
            dimension="experience_integrity",
            penalty=min(28, len(suspicious_companies) * 14),
            code="suspicious_company_type",
            severity="high",
            title="A company value has an incompatible lexical type",
            path="entities.experience",
            message=(
                f"Detected {len(suspicious_companies)} company value(s) that resemble "
                "standalone acronyms or technologies."
            ),
            explanation=(
                "An employer requires organization context and a coherent local "
                "title/company group."
            ),
            action="Use the supported organization block or leave company empty.",
        )
        self._entity_issue(
            report,
            unsupported,
            deduct,
            add_issue,
            dimension="experience_integrity",
            penalty=min(16, len(unsupported) * 8),
            code="unsupported_experience_metric",
            severity="medium",
            title="A large metric needs supporting context",
            path="entities.experience",
            message=f"Detected {len(unsupported)} unusually large or unqualified metric claim(s).",
            explanation="The text is preserved, but the parser cannot verify unsupported impact claims.",
            action="Add a measurable baseline, scope, and source for each metric.",
        )
        self._entity_issue(
            report,
            vague,
            deduct,
            add_issue,
            dimension="experience_integrity",
            penalty=min(18, len(vague) * 3),
            code="vague_experience_content",
            severity="low",
            title="Some experience bullets are vague",
            path="entities.experience",
            message=f"Detected {len(vague)} low-specificity experience bullet(s).",
            explanation="The bullets are valid extracted content but provide little role or impact detail.",
            action="Add concrete actions, technologies, scope, or outcomes.",
        )

    def _project_checks(self, report, deduct, add_issue) -> None:
        phantom = [
            item
            for item in report.entities.projects
            if item.name and (self._ACTION_TITLE.search(item.name) or len(item.name.split()) > 14)
        ]
        empty = [item for item in report.entities.projects if not item.description.strip()]
        technology_titles = [
            item
            for item in report.entities.projects
            if item.name
            and is_known_technology(item.name)
            and not self._project_title_has_header_support(report, item)
        ]
        vague = [
            item
            for item in report.entities.projects
            if item.description and self._VAGUE_PROJECT.search(item.description)
        ]
        self._entity_issue(
            report,
            phantom,
            deduct,
            add_issue,
            dimension="project_integrity",
            penalty=min(30, len(phantom) * 15),
            code="phantom_project_titles",
            severity="high",
            title="A project title resembles a description",
            path="entities.projects",
            message=f"Detected {len(phantom)} sentence-like project title(s).",
            explanation="Description sentences should not be promoted to project names.",
            action="Verify title and description boundaries.",
        )
        self._entity_issue(
            report,
            empty,
            deduct,
            add_issue,
            dimension="project_integrity",
            penalty=min(24, len(empty) * 12),
            code="empty_project_descriptions",
            severity="medium",
            title="A project has no extracted description",
            path="entities.projects",
            message=f"Detected {len(empty)} project(s) without a description.",
            explanation="A title alone may indicate a missed wrapped line or incorrect section boundary.",
            action="Verify the local project block and add a concise description.",
        )
        self._entity_issue(
            report,
            technology_titles,
            deduct,
            add_issue,
            dimension="project_integrity",
            penalty=min(30, len(technology_titles) * 15),
            code="technology_only_project_title",
            severity="high",
            title="A project title resembles a technology continuation",
            path="entities.projects",
            message=(
                f"Detected {len(technology_titles)} project title(s) that are tools "
                "without project-header evidence."
            ),
            explanation=(
                "A technology tail must remain attached to its parent stack unless "
                "layout evidence supports a new project header."
            ),
            action="Reconstruct the project boundary from section-local layout blocks.",
        )
        self._entity_issue(
            report,
            vague,
            deduct,
            add_issue,
            dimension="project_integrity",
            penalty=min(16, len(vague) * 8),
            code="vague_project_description",
            severity="low",
            title="A project description is low-specificity",
            path="entities.projects",
            message=f"Detected {len(vague)} vague project description(s).",
            explanation="The content was extracted correctly but lacks concrete scope or outcome.",
            action="State what was built, the technology used, and the result.",
        )

    def _education_checks(self, report, deduct, add_issue) -> None:
        date_conflicts: list[Any] = []
        implausible_locations: list[Any] = []
        for item in report.entities.education:
            start = self._first_year(item.start_date)
            end = self._first_year(item.end_date)
            if start and end and start > end:
                date_conflicts.append(item)
            location_parts = {
                part.strip().casefold() for part in (item.location or "").split(",") if part.strip()
            }
            if item.location and (
                len(location_parts & self._TECH_LOCATION_TERMS) >= 1 or len(location_parts) >= 4
            ):
                implausible_locations.append(item)
        self._entity_issue(
            report,
            date_conflicts,
            deduct,
            add_issue,
            dimension="education_integrity",
            penalty=min(36, len(date_conflicts) * 18),
            code="conflicting_education_dates",
            severity="high",
            title="Education dates are contradictory",
            path="entities.education",
            message=f"Detected {len(date_conflicts)} education date range(s) with start after end.",
            explanation="Date ranges must be directional and supported by the same education entry.",
            action="Review the source date range and correct start/end assignment.",
        )
        self._entity_issue(
            report,
            implausible_locations,
            deduct,
            add_issue,
            dimension="education_integrity",
            penalty=min(30, len(implausible_locations) * 15),
            code="implausible_education_location",
            severity="high",
            title="An education location resembles coursework",
            path="entities.education",
            message=f"Detected {len(implausible_locations)} non-geographic location value(s).",
            explanation="Comma-separated course or technology lists are not geographic evidence.",
            action="Leave location empty unless the source contains a city, region, or country.",
        )

    def _skill_checks(self, report, deduct, add_issue) -> None:
        malformed = [
            item
            for item in report.entities.skills
            if item.value.rstrip().endswith("&")
            or re.search(r"(?i)\b(?:aipowered|machinelearning|deeplearning)\b", item.value)
            or item.value.casefold() in {"programming", "backend", "frontend"}
        ]
        normalized = [
            (item.normalized or item.value).casefold().strip() for item in report.entities.skills
        ]
        duplicate_keys = {key for key, count in Counter(normalized).items() if count > 1}
        duplicates = [
            item
            for item, key in zip(report.entities.skills, normalized, strict=False)
            if key in duplicate_keys
        ]
        generic = [
            item
            for item in report.entities.skills
            if item.value.casefold() in self._GENERIC_SKILLS
            and item.category not in {"business_domain", "soft_skills", "methods"}
        ]
        self._entity_issue(
            report,
            malformed,
            deduct,
            add_issue,
            dimension="skills_integrity",
            penalty=min(30, len(malformed) * 10),
            code="malformed_skill_fragments",
            severity="high",
            title="Malformed skill fragments were detected",
            path="entities.skills",
            message=f"Detected {len(malformed)} malformed or heading-like skill value(s).",
            explanation="Truncated labels and broad headings are not canonical skills.",
            action="Reject the fragment or recover the complete source item.",
        )
        self._entity_issue(
            report,
            duplicates,
            deduct,
            add_issue,
            dimension="skills_integrity",
            penalty=min(24, len(duplicate_keys) * 12),
            code="duplicate_skill_aliases",
            severity="medium",
            title="Equivalent skills were emitted more than once",
            path="entities.skills",
            message=f"Detected {len(duplicate_keys)} duplicate normalized skill alias(es).",
            explanation="Case and product aliases should merge before canonical emission.",
            action="Merge aliases and preserve all source evidence on one skill.",
        )
        self._entity_issue(
            report,
            generic,
            deduct,
            add_issue,
            dimension="skills_integrity",
            penalty=min(15, len(generic) * 5),
            code="uncategorized_generic_skills",
            severity="medium",
            title="Generic skills lack explicit context",
            path="entities.skills",
            message=f"Detected {len(generic)} generic skill value(s) without explicit context.",
            explanation="Generic prose terms require dedicated-list or catalog evidence.",
            action="Review or categorize each generic skill using its source section.",
        )

    def _evidence_checks(self, report, deduct, add_issue) -> None:
        known = {item.id: item for item in report.evidence}
        entity_items = [
            *report.entities.skills,
            *report.entities.education,
            *report.entities.experience,
            *report.entities.projects,
            *report.entities.languages,
            *report.entities.certifications,
        ]
        referenced = [
            evidence_id
            for item in entity_items
            for evidence_id in getattr(item, "evidence_ids", [])
        ]
        missing = [value for value in referenced if value not in known]
        missing.extend(
            parent_id
            for item in report.evidence
            for parent_id in item.parent_evidence_ids
            if parent_id not in known
        )
        if missing:
            deduct("evidence_consistency", 55)
            add_issue(
                "unknown_entity_evidence",
                "evidence",
                "high",
                "An entity references unknown evidence",
                "entities",
                f"Detected {len(missing)} unknown entity evidence reference(s).",
                "A canonical field cannot be audited when its evidence record is missing.",
                "Rebuild the evidence registry before emitting the entity.",
                confidence=1.0,
            )

        source_records = [
            known[value]
            for value in dict.fromkeys(referenced)
            if value in known and known[value].kind in {"present", "layout"}
        ]

        def has_grounded_source(evidence_id: str, visited: set[str] | None = None) -> bool:
            visited = set() if visited is None else visited
            if evidence_id in visited:
                return False
            visited.add(evidence_id)
            record = known.get(evidence_id)
            if record is None:
                return False
            if record.source.page is not None and record.source.block_id:
                return True
            return any(
                has_grounded_source(parent_id, visited)
                for parent_id in record.parent_evidence_ids
            )

        ungrounded = [
            item for item in source_records if not has_grounded_source(item.id)
        ]
        ratio = len(ungrounded) / len(source_records) if source_records else 0.0
        if ratio >= 0.25:
            deduct("evidence_consistency", min(45, round(20 + ratio * 25)))
            add_issue(
                "entity_evidence_lacks_source_block",
                "evidence",
                "high" if ratio >= 0.75 else "medium",
                "Entity evidence lacks block-level provenance",
                "entities",
                f"{ratio:.0%} of entity evidence does not identify a source page and block.",
                "Derived snapshots are useful for compatibility but cannot prove section or "
                "column coherence.",
                "Attach each entity to its original layout block and section.",
                evidence_ids=[item.id for item in ungrounded[:20]],
                confidence=0.99,
            )

        coherence_findings = EvidenceCoherenceValidator().validate(report)
        for finding in coherence_findings:
            deduct("evidence_consistency", 18)
            if finding.code in {
                "evidence_cross_column",
                "evidence_section_mismatch",
            }:
                deduct("entity_coherence", 12)
            labels = {
                "evidence_section_mismatch": (
                    "Entity evidence belongs to another section",
                    "Attach the field only to blocks in its canonical section.",
                ),
                "evidence_cross_column": (
                    "Entity evidence spans parallel columns",
                    "Rebuild the entry from one coherent column-local group.",
                ),
                "evidence_page_mismatch": (
                    "Entity evidence belongs to another page",
                    "Attach the field to blocks on its section page.",
                ),
                "contact_evidence_outside_header": (
                    "Contact evidence is outside the contact region",
                    "Require page-one header proximity or an explicit contact label.",
                ),
            }
            title, action = labels[finding.code]
            add_issue(
                finding.code,
                "evidence",
                "high",
                title,
                finding.entity_path,
                finding.detail,
                "High-confidence entities require page, block, section, and column-local "
                "source evidence.",
                action,
                evidence_ids=finding.evidence_ids,
                confidence=finding.confidence,
            )

    def _confidence_checks(self, report, deduct, add_issue) -> None:
        items = [
            *report.entities.skills,
            *report.entities.education,
            *report.entities.experience,
            *report.entities.projects,
            *report.entities.languages,
            *report.entities.certifications,
        ]
        low = [item for item in items if item.confidence < 0.5]
        ratio = len(low) / len(items) if items else 0.0
        if ratio >= 0.25:
            deduct("confidence_coverage", min(40, round(ratio * 40)))
            self._entity_issue(
                report,
                low,
                deduct,
                add_issue,
                dimension="entity_coherence",
                penalty=min(12, round(ratio * 12)),
                code="low_confidence_entity_ratio",
                severity="medium",
                title="Many canonical entities have low confidence",
                path="entities",
                message=f"{ratio:.0%} of canonical entities have confidence below 0.50.",
                explanation="Ambiguous entities should remain visible but clearly require review.",
                action="Review the affected source blocks or provide a simpler layout.",
            )
        review_items = [
            item
            for item in items
            if (
                item.parsing_needs_review
                if isinstance(item, ExperienceItem)
                else getattr(item, "needs_review", False)
            )
        ]
        if review_items:
            deduct("entity_coherence", min(30, len(review_items) * 6))

    @staticmethod
    def _entity_issue(
        report: PipelineReport,
        items: list[Any],
        deduct,
        add_issue,
        *,
        dimension: str,
        penalty: int,
        code: str,
        severity: str,
        title: str,
        path: str,
        message: str,
        explanation: str,
        action: str,
    ) -> None:
        if not items:
            return
        deduct(dimension, penalty)
        evidence = [
            evidence_id for item in items for evidence_id in getattr(item, "evidence_ids", [])
        ]
        if not evidence:
            evidence = CanonicalDataQualityAnalyzer._path_evidence(report, path)
        add_issue(
            code,
            path.split(".", 1)[-1].split("[", 1)[0],
            severity,
            title,
            path,
            message,
            explanation,
            action,
            evidence_ids=evidence,
        )

    @staticmethod
    def _path_evidence(report: PipelineReport, prefix: str) -> list[str]:
        return [
            item.id
            for item in report.evidence
            if item.source.field_path == prefix
            or item.source.field_path.startswith(prefix + ".")
            or item.source.field_path.startswith(prefix + "[")
        ]

    @staticmethod
    def _page_evidence(report: PipelineReport, pages: Iterable[Any]) -> list[str]:
        page_numbers = {page.page for page in pages}
        return [
            item.id
            for item in report.evidence
            if item.source.page in page_numbers and item.kind == "layout"
        ]

    @classmethod
    def _looks_like_calendar_value(cls, value: str) -> bool:
        digits = re.sub(r"\D", "", value)
        return bool(
            re.fullmatch(r"(?:19|20)\d{2}", digits)
            or re.fullmatch(r"(?:19|20)\d{2}(?:19|20)\d{2}", digits)
            or re.fullmatch(r"(?:19|20)\d{4,6}", digits)
        )

    @classmethod
    def _first_year(cls, value: str | None) -> int | None:
        match = cls._DATE_YEAR.search(value or "")
        return int(match.group(1)) if match else None

    @staticmethod
    def _normalized_sentence(value: str) -> str:
        return re.sub(
            r"[.!?;:,]+$",
            "",
            re.sub(r"\s+", " ", value.casefold()),
        ).strip()
