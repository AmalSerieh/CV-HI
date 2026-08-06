"""Deterministic template and layout checks over canonical extraction metadata."""

from __future__ import annotations

import re

from resume_analyzer.schemas import PipelineReport

from .config import COPYRIGHT_PATTERNS, PLACEHOLDER_PATTERNS
from .issue_builder import (
    AnalyzerFindings,
    EvidenceLookup,
    IssueDraft,
    StrengthDraft,
)

_MAX_VISUAL_EVIDENCE = 8
_MAX_TEMPLATE_COPYRIGHT_EVIDENCE = 4
_REMOVED_REPEATED_FURNITURE = re.compile(r"^removed_repeated_header_footer_blocks:(?P<count>\d+)$")
_TEMPLATE_FIELD_LINE = re.compile(
    r"(?i)^\s*(?P<label>job title|company name)\s*:?\s*(?P<value>.*?)\s*$"
)
_TEMPLATE_FIELD_PLACEHOLDER_VALUE = re.compile(
    r"(?i)^(?:job title|company name|your (?:job title|company name)|"
    r"insert (?:text|value)|tbd|n/?a|none|-+)$"
)


def _contains_unresolved_placeholder(text: str) -> bool:
    if any(re.search(pattern, text) for pattern in PLACEHOLDER_PATTERNS):
        return True

    for line in text.splitlines():
        match = _TEMPLATE_FIELD_LINE.fullmatch(line)
        if match is None:
            continue
        value = match.group("value").strip()
        if not value or _TEMPLATE_FIELD_PLACEHOLDER_VALUE.fullmatch(value):
            return True
    return False


class TemplateAnalyzer:
    def analyze(self, report: PipelineReport) -> AnalyzerFindings:
        findings = AnalyzerFindings()
        lookup = EvidenceLookup(report)
        extraction = report.extraction
        visual = extraction.visual_metadata
        layout_evidence = lookup.paths("document.layout", "extraction.reading_order")
        visual_evidence = lookup.paths("extraction.visual_metadata") or layout_evidence

        if report.document.layout in {"two_column", "mixed"}:
            verified = extraction.reading_order == "column_wise" or any(
                "visual_order_reconstructed" in item for item in extraction.warnings
            )
            if report.document.layout == "mixed" or not verified:
                findings.issues.append(
                    IssueDraft(
                        "MULTI_COLUMN_READING_ORDER_RISK",
                        tuple(layout_evidence),
                        "template_analyzer",
                        0.9,
                    )
                )
            else:
                findings.strengths.append(
                    StrengthDraft(
                        "VERIFIED_COLUMN_READING_ORDER",
                        "layout",
                        tuple(layout_evidence),
                        "template_analyzer",
                        0.9,
                    )
                )
        elif report.document.layout == "single_column":
            findings.strengths.append(
                StrengthDraft(
                    "SINGLE_COLUMN_LAYOUT",
                    "layout",
                    tuple(layout_evidence),
                    "template_analyzer",
                    0.96,
                )
            )

        if (visual.text_box_count or 0) >= 3:
            findings.issues.append(
                IssueDraft(
                    "TEXT_BOX_READING_ORDER_RISK",
                    tuple(visual_evidence),
                    "template_analyzer",
                    0.92,
                )
            )
        if (visual.overlap_count or 0) > 0:
            findings.issues.append(
                IssueDraft(
                    "TEXT_OVERLAP_RISK",
                    tuple(visual_evidence),
                    "template_analyzer",
                    0.9,
                )
            )
        if (visual.small_font_count or 0) > 0:
            findings.issues.append(
                IssueDraft(
                    "VERY_SMALL_FONT",
                    tuple(visual_evidence),
                    "template_analyzer",
                    0.85,
                )
            )
        if len(visual.font_names) > 4 or len(visual.font_sizes) > 8:
            findings.issues.append(
                IssueDraft(
                    "EXCESSIVE_FONT_VARIATION",
                    tuple(visual_evidence),
                    "template_analyzer",
                    0.8,
                )
            )
        if visual.contrast_status.casefold() in {"poor", "low", "failed"}:
            findings.issues.append(
                IssueDraft(
                    "LOW_CONTRAST_TEXT",
                    tuple(visual_evidence),
                    "template_analyzer",
                    0.9,
                )
            )
        elif visual.has_color:
            findings.strengths.append(
                StrengthDraft(
                    "COLOR_NOT_PENALIZED",
                    "accessibility",
                    tuple(visual_evidence),
                    "template_analyzer",
                    0.85,
                )
            )

        image_only = [
            field
            for field in visual.image_only_contact_fields
            if field in {"email", "phone"}
            if report.entities.contact.source_types.get(field)
            not in {"ocr", "selectable_text", "annotation"}
        ]
        if image_only:
            evidence = lookup.paths("entities.contact") or visual_evidence
            findings.issues.append(
                IssueDraft(
                    "IMAGE_ONLY_CONTACT_INFORMATION",
                    tuple(evidence),
                    "template_analyzer",
                    0.92,
                )
            )
        elif visual.candidate_photo_detected:
            findings.warnings.append("candidate_photo_detected_not_scored_without_text_loss")

        table_blocks = [
            (index, block)
            for index, block in enumerate(extraction.layout_blocks)
            if block.block_type == "table"
        ]
        if table_blocks:
            evidence = []
            for index, _ in table_blocks:
                evidence.extend(lookup.paths(f"extraction.layout_blocks[{index}].text"))
            evidence = evidence[:_MAX_VISUAL_EVIDENCE]
            if extraction.reading_order in {"unknown", "mixed", "row_wise"}:
                findings.issues.append(
                    IssueDraft(
                        "CONTENT_CRITICAL_TABLE",
                        tuple(evidence or visual_evidence),
                        "template_analyzer",
                        0.75,
                    )
                )
            else:
                findings.strengths.append(
                    StrengthDraft(
                        "TABLE_TEXT_EXTRACTED",
                        "layout",
                        tuple(evidence or visual_evidence),
                        "template_analyzer",
                        0.8,
                    )
                )

        removed_repeated_count = max(
            (
                int(match.group("count"))
                for warning in extraction.warnings
                if (match := _REMOVED_REPEATED_FURNITURE.fullmatch(warning))
            ),
            default=0,
        )
        remaining_repeated_count = max(
            0,
            visual.repeated_header_footer_count - removed_repeated_count,
        )
        if remaining_repeated_count > 0:
            repeated_evidence = [
                evidence_id
                for index, block in enumerate(extraction.layout_blocks)
                if block.is_repeated_header_footer
                for evidence_id in lookup.paths(f"extraction.layout_blocks[{index}].text")
            ]
            evidence = list(
                dict.fromkeys(
                    (
                        *repeated_evidence,
                        *lookup.paths("extraction.visual_metadata"),
                    )
                )
            )[:_MAX_VISUAL_EVIDENCE]
            findings.issues.append(
                IssueDraft(
                    "REPEATED_PAGE_FURNITURE",
                    tuple(evidence or visual_evidence),
                    "template_analyzer",
                    0.88,
                )
            )

        section_texts = {
            key: value.content for key, value in extraction.sections.items() if value.content
        }
        placeholder_evidence: list[str] = []
        copyright_evidence: list[str] = []
        for key, text in section_texts.items():
            if _contains_unresolved_placeholder(text):
                placeholder_evidence.extend(lookup.paths(f"extraction.sections.{key}.content"))
            if any(re.search(pattern, text) for pattern in COPYRIGHT_PATTERNS):
                copyright_evidence.extend(lookup.paths(f"extraction.sections.{key}.content"))
        for index, block in enumerate(extraction.layout_blocks):
            if any(re.search(pattern, block.text) for pattern in COPYRIGHT_PATTERNS):
                copyright_evidence.extend(lookup.paths(f"extraction.layout_blocks[{index}].text"))
        if placeholder_evidence:
            findings.issues.append(
                IssueDraft(
                    "UNRESOLVED_TEMPLATE_CONTENT",
                    tuple(dict.fromkeys(placeholder_evidence))[:_MAX_VISUAL_EVIDENCE],
                    "template_analyzer",
                    0.98,
                )
            )
        if copyright_evidence:
            findings.issues.append(
                IssueDraft(
                    "TEMPLATE_COPYRIGHT_REMAINS",
                    tuple(dict.fromkeys(copyright_evidence))[:_MAX_TEMPLATE_COPYRIGHT_EVIDENCE],
                    "template_analyzer",
                    0.95,
                )
            )

        if visual.status in {"cannot_verify", "not_available"}:
            findings.warnings.append("cannot_verify_complete_visual_formatting_metadata")
        if visual.has_images and not image_only:
            findings.warnings.append("images_detected_without_verified_text_replacement")
        return findings
