"""Deterministic content-format consistency checks."""

from __future__ import annotations

import re
from collections import Counter

from resume_analyzer.schemas import PipelineReport

from .issue_builder import AnalyzerFindings, EvidenceLookup, IssueDraft

_BULLET = re.compile(r"^\s*([•●▪◦*-])\s+")
_BROKEN_BULLET = re.compile(r"(?:�|ï¿½|\uf0b7|\uf0a7)")
_URL_LIKE = re.compile(r"(?i)\b(?:https?\s*:/?/?|www\.)\S+")
_VALID_URL = re.compile(r"(?i)^https://[^\s.]+(?:\.[^\s.]+)+\S*$")
_MAX_ISSUE_EVIDENCE = 8


def _normalized_content_line(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold()).strip()


def _date_style(value: str) -> str | None:
    normalized = value.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).strip()
    if not normalized:
        return None
    if re.search(r"\b\d{4}-\d{1,2}(?:-\d{1,2})?\b", normalized):
        return "iso"
    if re.search(r"\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b", normalized):
        return "numeric"
    if re.search(
        r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\b",
        normalized,
    ):
        return "named_month"
    if re.fullmatch(r"(?:19|20)\d{2}", normalized):
        return "year"
    return "other"


class FormattingChecker:
    def analyze(self, report: PipelineReport) -> AnalyzerFindings:
        findings = AnalyzerFindings()
        lookup = EvidenceLookup(report)
        blocks = list(report.extraction.layout_blocks)
        content_blocks = [
            (index, block)
            for index, block in enumerate(blocks)
            if block.text.strip() and not block.is_repeated_header_footer
        ]
        lines = [block.text for _, block in content_blocks]
        if not lines:
            lines = [
                line
                for key, section in report.extraction.sections.items()
                if key.casefold() != "contact_header"
                for line in section.content.splitlines()
                if line.strip()
            ]
        general_evidence = lookup.paths("extraction.sections") or lookup.paths("entities")
        layout_evidence = [
            evidence_id
            for index, _ in content_blocks
            for evidence_id in lookup.paths(f"extraction.layout_blocks[{index}].text")
        ]
        layout_evidence = (layout_evidence or general_evidence)[:_MAX_ISSUE_EVIDENCE]

        experience_dates = [
            value
            for item in report.entities.experience
            for value in (item.start_date, item.end_date)
            if value
        ]
        education_dates = [
            value
            for item in report.entities.education
            for value in (item.start_date, item.end_date)
            if value
        ]
        dates = experience_dates + education_dates
        styles = {_date_style(value) for value in dates} - {None, "other"}
        if len(styles) > 1 and len(dates) >= 3:
            evidence = lookup.paths("entities.experience", "entities.education")
            findings.issues.append(
                IssueDraft(
                    "INCONSISTENT_DATE_FORMATS",
                    tuple(evidence),
                    "formatting_checker",
                    0.88,
                )
            )

        bullets = [match.group(1) for line in lines if (match := _BULLET.match(line))]
        if len(set(bullets)) > 1:
            findings.issues.append(
                IssueDraft(
                    "INCONSISTENT_BULLET_STYLES",
                    tuple(layout_evidence),
                    "formatting_checker",
                    0.85,
                )
            )

        headings = [
            (key, section.heading)
            for key, section in report.extraction.sections.items()
            if key.casefold() != "contact_header"
            and section.heading
            and re.search(r"[A-Za-z]", section.heading)
        ]
        heading_styles = {
            "upper" if value.isupper() else "title" if value.istitle() else "mixed"
            for _, value in headings
        }
        if len(heading_styles) > 1 and len(headings) >= 3:
            evidence = [
                evidence_id
                for key, _ in headings
                for evidence_id in lookup.paths(f"extraction.sections.{key}.heading")
            ]
            findings.issues.append(
                IssueDraft(
                    "INCONSISTENT_HEADING_CASE",
                    tuple(evidence[:_MAX_ISSUE_EVIDENCE]),
                    "formatting_checker",
                    0.78,
                )
            )

        if any(re.search(r"\S {2,}\S", line) for line in lines):
            findings.issues.append(
                IssueDraft(
                    "DUPLICATE_WHITESPACE",
                    tuple(layout_evidence),
                    "formatting_checker",
                    0.82,
                )
            )
        if any(_BROKEN_BULLET.search(line) for line in lines):
            findings.issues.append(
                IssueDraft(
                    "BROKEN_BULLET_CHARACTERS",
                    tuple(layout_evidence),
                    "formatting_checker",
                    0.94,
                )
            )

        malformed = False
        for line in lines:
            for match in _URL_LIKE.findall(line):
                candidate = match.rstrip(".,);]")
                if not _VALID_URL.match(candidate):
                    malformed = True
                    break
            if malformed:
                break
        for value in (
            report.entities.contact.linkedin,
            report.entities.contact.github,
            report.entities.contact.portfolio,
        ):
            if value and not _VALID_URL.match(value):
                malformed = True
        if malformed:
            evidence = lookup.paths("entities.contact", "extraction.sections")
            findings.issues.append(
                IssueDraft("MALFORMED_LINK", tuple(evidence), "formatting_checker", 0.9)
            )

        current_labels = {
            value.casefold()
            for item in report.entities.experience
            for value in (item.end_date,)
            if value and value.casefold() in {"present", "current"}
        }
        if len(current_labels) > 1:
            findings.issues.append(
                IssueDraft(
                    "INCONSISTENT_CURRENT_LABEL",
                    tuple(lookup.paths("entities.experience")),
                    "formatting_checker",
                    0.9,
                )
            )

        if any(len(line.split()) > 80 for line in lines):
            findings.issues.append(
                IssueDraft(
                    "VERY_LONG_PARAGRAPH",
                    tuple(general_evidence),
                    "formatting_checker",
                    0.86,
                )
            )

        short_evidence: list[str] = []
        for index, experience in enumerate(report.entities.experience):
            bullets_for_role = (*experience.responsibilities, *experience.achievements)
            if any(0 < len(value.split()) < 4 for value in bullets_for_role):
                short_evidence.extend(lookup.paths(f"entities.experience[{index}]"))
        if short_evidence:
            findings.issues.append(
                IssueDraft(
                    "GENERIC_SHORT_BULLET",
                    tuple(short_evidence),
                    "formatting_checker",
                    0.82,
                )
            )

        normalized_lines = [
            _normalized_content_line(line) for line in lines if len(line.split()) >= 5
        ]
        duplicate_values = {
            value for value, count in Counter(normalized_lines).items() if value and count > 1
        }
        duplicate_ratio = report.extraction.visual_metadata.duplicate_ratio or 0.0
        if duplicate_values or duplicate_ratio >= 0.2:
            evidence = [
                evidence_id
                for index, block in content_blocks
                if _normalized_content_line(block.text) in duplicate_values
                for evidence_id in lookup.paths(f"extraction.layout_blocks[{index}].text")
            ]
            if duplicate_ratio >= 0.2:
                evidence.extend(lookup.paths("extraction.visual_metadata"))
            if not evidence:
                evidence = general_evidence
            findings.issues.append(
                IssueDraft(
                    "DUPLICATE_CONTENT",
                    tuple(evidence[:_MAX_ISSUE_EVIDENCE]),
                    "formatting_checker",
                    0.9,
                )
            )
        return findings
