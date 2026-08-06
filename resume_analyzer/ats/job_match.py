"""Offline job-description matching kept separate from ATS compatibility."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from resume_analyzer.schemas import (
    JobMatchResult,
    MissingKeywordSuggestion,
    PipelineReport,
)

from .config import JOB_KEYWORD_ALIASES, JOB_STOPWORDS
from .exceptions import InvalidJobDescriptionError

_INJECTION = re.compile(
    r"(?i)\b(?:ignore (?:all |the )?(?:previous|prior) instructions?|system prompt|developer message|call (?:a )?tool|reveal (?:the )?prompt)\b"
)
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{2,}|[\u0600-\u06ff]{4,}")


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ـ", "")
    value = re.sub(r"[\u064b-\u065f\u0670]", "", value)
    value = value.translate(str.maketrans("أإآى", "اااي"))
    return re.sub(r"[^\w+#./-]+", " ", value).strip()


_ALIAS_TO_CANONICAL = {
    _normalize(alias): canonical
    for canonical, aliases in JOB_KEYWORD_ALIASES.items()
    for alias in aliases
}


class JobDescriptionMatcher:
    method = "deterministic_keyword_and_phrase_match_v1"

    def __init__(self, *, max_characters: int = 50_000) -> None:
        self.max_characters = max_characters

    def match(self, report: PipelineReport, job_description: str | None) -> JobMatchResult:
        if job_description is None or not job_description.strip():
            return JobMatchResult(status="not_run")
        if not isinstance(job_description, str):
            raise InvalidJobDescriptionError("Job description must be text")
        if len(job_description) > self.max_characters:
            raise InvalidJobDescriptionError(
                f"Job description exceeds {self.max_characters} characters"
            )

        jd_keywords = self._keywords(job_description)
        if not jd_keywords:
            return JobMatchResult(
                status="cannot_verify",
                warnings=["No stable job keywords could be identified."],
            )
        resume_keywords = self._resume_keywords(report)
        matched: list[str] = []
        missing: list[MissingKeywordSuggestion] = []
        evidence_ids: list[str] = []
        for canonical, original in jd_keywords:
            supported = resume_keywords.get(canonical)
            if supported:
                matched.append(original)
                evidence_ids.extend(supported)
            else:
                missing.append(
                    MissingKeywordSuggestion(
                        phrase=original,
                        normalized=canonical,
                        suggestion=(
                            f"Include “{original}” only if it accurately represents your experience."
                        ),
                        conditional=True,
                    )
                )
        score = round(100 * len(matched) / len(jd_keywords))
        warnings = []
        if _INJECTION.search(job_description):
            warnings.append(
                "Instruction-like job-description text was treated only as untrusted data."
            )
        transferable = [
            item.value
            for item in report.entities.skills
            if _normalize(item.value) not in {key for key, _ in jd_keywords}
        ][:10]
        return JobMatchResult(
            status="complete",
            match_score=score,
            matched_keywords=matched,
            missing_keywords=missing,
            transferable_signals=transferable,
            evidence_ids=list(dict.fromkeys(evidence_ids)),
            warnings=warnings,
            method=self.method,
        )

    def _keywords(self, text: str) -> list[tuple[str, str]]:
        normalized = _normalize(text)
        output: dict[str, str] = {}
        for canonical, aliases in JOB_KEYWORD_ALIASES.items():
            for alias in sorted(aliases, key=len, reverse=True):
                normalized_alias = _normalize(alias)
                if re.search(rf"(?<!\w){re.escape(normalized_alias)}(?!\w)", normalized):
                    match = re.search(re.escape(alias), text, re.IGNORECASE)
                    output.setdefault(canonical, match.group(0) if match else alias)
                    break

        tokens = _TOKEN.findall(text)
        counts = Counter(_normalize(value) for value in tokens)
        for original in tokens:
            normalized_token = _normalize(original)
            if (
                not normalized_token
                or normalized_token in JOB_STOPWORDS
                or _INJECTION.search(original)
            ):
                continue
            canonical = _ALIAS_TO_CANONICAL.get(normalized_token, normalized_token)
            technical_shape = (
                original.isupper()
                or any(char in original for char in "+#./")
                or any(char.isdigit() for char in original)
            )
            if technical_shape or counts[normalized_token] >= 2:
                output.setdefault(canonical, original)
            if len(output) >= 30:
                break
        return list(output.items())

    def _resume_keywords(self, report: PipelineReport) -> dict[str, list[str]]:
        output: dict[str, list[str]] = {}

        def add(text: str | None, evidence_ids: list[str]) -> None:
            if not text:
                return
            normalized_text = _normalize(text)
            for alias, canonical in _ALIAS_TO_CANONICAL.items():
                if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized_text):
                    output.setdefault(canonical, []).extend(evidence_ids)
            for token in _TOKEN.findall(text):
                normalized_token = _normalize(token)
                if normalized_token and normalized_token not in JOB_STOPWORDS:
                    canonical = _ALIAS_TO_CANONICAL.get(normalized_token, normalized_token)
                    output.setdefault(canonical, []).extend(evidence_ids)

        summary_evidence = [
            item.id for item in report.evidence if item.field_path == "entities.summary"
        ]
        add(report.entities.summary, summary_evidence)
        for skill in report.entities.skills:
            add(skill.value, skill.evidence_ids)
        for experience in report.entities.experience:
            for value in (
                experience.job_title,
                *experience.technologies,
                *experience.responsibilities,
                *experience.achievements,
            ):
                add(value, experience.evidence_ids)
        for project in report.entities.projects:
            for value in (project.name, project.description, *project.technologies):
                add(value, project.evidence_ids)
        return {key: list(dict.fromkeys(values)) for key, values in output.items()}
