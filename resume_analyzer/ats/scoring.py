"""Explainable bounded ATS compatibility scoring."""

from __future__ import annotations

from resume_analyzer.schemas import ATSIssue, ATSScoreBreakdown

from .config import (
    CATEGORY_PENALTY_CAPS,
    CATEGORY_WEIGHTS,
    ISSUE_TO_SCORE_CATEGORY,
    SCORE_LABELS,
)


class ATSScoringPolicy:
    method = "deterministic_ats_compatibility_v1"

    def score(self, issues: list[ATSIssue]) -> tuple[int, str, ATSScoreBreakdown]:
        deductions = {name: 0 for name in CATEGORY_WEIGHTS}
        for issue in issues:
            if issue.category == "job_match":
                continue
            score_category = ISSUE_TO_SCORE_CATEGORY[issue.category]
            deductions[score_category] = min(
                CATEGORY_PENALTY_CAPS[score_category],
                deductions[score_category] + issue.penalty,
            )
        contributions = {
            name: max(0, maximum - deductions[name]) for name, maximum in CATEGORY_WEIGHTS.items()
        }
        breakdown = ATSScoreBreakdown(**contributions)
        score = breakdown.total()
        label = next(label for threshold, label in SCORE_LABELS if score >= threshold)
        return score, label, breakdown
