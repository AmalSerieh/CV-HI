"""Deprecated compatibility exports for the canonical AI capabilities."""

import warnings

warnings.warn(
    "Import AI capabilities from resume_analyzer; top-level ai is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.recommendations import RecommendationEngine  # noqa: E402
from resume_analyzer.rewriting import ResumeRewriter  # noqa: E402
from resume_analyzer.target_roles import (  # noqa: E402
    TargetRoleSuggester,
    suggest_target_roles,
)

__all__ = [
    "RecommendationEngine",
    "ResumeRewriter",
    "TargetRoleSuggester",
    "suggest_target_roles",
]
