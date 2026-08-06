"""ATS contract re-exports; canonical definitions live with report schemas."""

from resume_analyzer.schemas.ats_schema import (
    ATSCategory,
    ATSIssue,
    ATSResult,
    ATSScoreBreakdown,
    ATSSeverity,
    ATSStrength,
    JobMatchResult,
    MissingKeywordSuggestion,
)

__all__ = [
    "ATSCategory",
    "ATSIssue",
    "ATSResult",
    "ATSScoreBreakdown",
    "ATSSeverity",
    "ATSStrength",
    "JobMatchResult",
    "MissingKeywordSuggestion",
]
