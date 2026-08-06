"""Deprecated import path for the optional model registry."""

from __future__ import annotations

import warnings

from resume_analyzer.ai.model_registry import ModelRegistry, OptionalModelDependencyError

warnings.warn(
    "models1.model_registry is deprecated; use resume_analyzer.ai.model_registry",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ModelRegistry", "OptionalModelDependencyError"]
