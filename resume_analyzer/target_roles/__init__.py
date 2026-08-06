"""Deterministic target-role suggestion public API."""

from .config import ScoringConfig
from .integration import attach_target_role
from .pipeline_adapter import PipelineAdapter
from .target_role_suggester import TargetRoleSuggester, suggest_target_roles

__all__ = [
    "PipelineAdapter",
    "ScoringConfig",
    "TargetRoleSuggester",
    "attach_target_role",
    "suggest_target_roles",
]
