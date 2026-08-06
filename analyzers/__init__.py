"""Deprecated compatibility exports for capability-specific analyzers."""

import warnings

from resume_analyzer.ats import ATSAnalyzer, JobDescriptionMatcher
from resume_analyzer.recommendations import RecommendationEngine

from .ats_scorer import ATSScorer
from .job_matcher import JobMatcher

warnings.warn(
    "analyzers is deprecated; use resume_analyzer.ats or resume_analyzer.recommendations",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "ATSAnalyzer",
    "ATSScorer",
    "JobDescriptionMatcher",
    "JobMatcher",
    "RecommendationEngine",
]
