"""Deprecated compatibility import for the canonical recommendation engine."""

import warnings

warnings.warn(
    "Import RecommendationEngine from resume_analyzer.recommendations.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.recommendations import RecommendationEngine  # noqa: E402

__all__ = ["RecommendationEngine"]
