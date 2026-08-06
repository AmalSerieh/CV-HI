"""Reject unsupported AI claims against the canonical evidence registry."""

from __future__ import annotations

import re
from dataclasses import dataclass

from resume_analyzer.schemas import AIRecommendation, PipelineReport

_INJECTION = re.compile(
    r"(?i)\b(?:ignore (?:all |the )?(?:previous|prior) instructions?|system prompt|developer message|reveal (?:the )?prompt|call (?:a )?tool)\b"
)
_NUMBER = re.compile(r"(?<![\w.-])(?:[$€£]?\d[\d,.]*%?)(?![\w.-])")
_ADD_ACTION = re.compile(r"(?i)\b(?:add|include|list|mention|insert|expand[^.;:]{0,30}\bwith)\b")
_MISSING_CLAIM = re.compile(
    r"(?i)\b(?:missing|lacks?|does not (?:include|list|mention)|doesn't (?:include|list|mention))\b"
)
_FACT_PATTERNS = [
    re.compile(
        r"(?i)\b(?:worked|working|employed|experience|role|position)\s+(?:at|with|for|as)\s+([A-Z][\w&.+-]*(?:\s+[A-Z][\w&.+-]*){0,4})"
    ),
    re.compile(
        r"(?i)\b(?:degree|certification|certified)\s+(?:in|from|as)\s+([A-Z][\w&.+#/-]*(?:\s+[A-Z][\w&.+#/-]*){0,5})"
    ),
    re.compile(
        r"(?i)\b(?:used|using|built with|proficient in|expert in)\s+([A-Z][\w.+#/-]*(?:\s+[A-Z][\w.+#/-]*){0,4})"
    ),
]


@dataclass(frozen=True)
class EvidenceValidationResult:
    accepted: tuple[AIRecommendation, ...]
    rejected: tuple[tuple[str, str], ...]


class EvidenceValidator:
    def validate(
        self,
        recommendations: list[AIRecommendation],
        report: PipelineReport,
    ) -> EvidenceValidationResult:
        evidence = {item.id: item for item in report.evidence}
        accepted: list[AIRecommendation] = []
        rejected: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        for recommendation in recommendations:
            reason = self._reason(recommendation, evidence, seen_ids, report)
            if reason:
                rejected.append((recommendation.id, reason))
            else:
                accepted.append(recommendation)
                seen_ids.add(recommendation.id)
        return EvidenceValidationResult(tuple(accepted), tuple(rejected))

    def _reason(
        self,
        recommendation,
        evidence,
        seen_ids: set[str],
        report: PipelineReport,
    ) -> str | None:
        if recommendation.id in seen_ids:
            return "duplicate_recommendation_id"
        unknown = [item for item in recommendation.evidence_ids if item not in evidence]
        if unknown:
            return f"unknown_evidence_ids:{','.join(sorted(unknown))}"
        combined = " ".join(
            (recommendation.title, recommendation.problem, recommendation.suggestion)
        )
        if _INJECTION.search(combined):
            return "prompt_injection_content"
        trusted_ats_issue = next(
            (
                item
                for item in report.ats.issues
                if recommendation.severity == item.severity
                and " ".join(recommendation.title.split()) == " ".join(item.title.split())
                and " ".join(recommendation.problem.split()) == " ".join(item.problem.split())
                and " ".join(recommendation.suggestion.split()) == " ".join(item.suggestion.split())
                and set(recommendation.evidence_ids).issubset(item.evidence_ids)
            ),
            None,
        )
        if trusted_ats_issue is not None:
            cited_missing = [
                evidence[item]
                for item in recommendation.evidence_ids
                if evidence[item].kind == "missing"
            ]
            if bool(cited_missing) != recommendation.conditional:
                return "ats_focus_conditional_mismatch"
            return None
        if _MISSING_CLAIM.search(combined) and not any(
            evidence[item].kind == "missing" for item in recommendation.evidence_ids
        ):
            return "missing_claim_without_missing_evidence"
        cited_missing = [
            evidence[item]
            for item in recommendation.evidence_ids
            if evidence[item].kind == "missing"
        ]
        if cited_missing and not recommendation.conditional:
            return "missing_evidence_requires_conditional_recommendation"
        if (
            any(
                item.field_path
                in {
                    "entities.contact.linkedin",
                    "entities.contact.github",
                    "entities.contact.portfolio",
                }
                for item in cited_missing
            )
            and recommendation.severity != "low"
        ):
            return "optional_social_link_requires_low_severity"

        # A response can cite a present skill while incoherently recommending
        # that it be added. Formal evidence IDs do not make that claim valid.
        suggestion = " ".join(recommendation.suggestion.casefold().split())
        if _ADD_ACTION.search(suggestion):
            for item in report.entities.skills:
                skill = " ".join(item.value.casefold().split())
                if len(skill) >= 2 and re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", suggestion):
                    return f"contradictory_existing_skill:{skill}"

        referenced_values = " ".join(
            str(evidence[item].value or "") for item in recommendation.evidence_ids
        ).casefold()
        for number in _NUMBER.findall(recommendation.problem):
            if number.casefold() not in referenced_values:
                return f"unsupported_numeric_claim:{number}"
        for pattern in _FACT_PATTERNS:
            for match in pattern.finditer(recommendation.problem):
                claim = " ".join(match.group(1).split()).casefold().rstrip(".,;:")
                if claim and claim not in referenced_values:
                    return f"unsupported_named_claim:{claim}"
        return None
