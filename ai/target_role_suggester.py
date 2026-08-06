"""Compatibility wrapper for deterministic target-role suggestion."""

from resume_analyzer.target_roles.target_role_suggester import (
    TargetRoleSuggester,
    suggest_target_roles,
)

__all__ = ["TargetRoleSuggester", "suggest_target_roles"]
