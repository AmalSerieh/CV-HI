"""Single source of truth for deterministic scoring configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

DEFAULT_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {
        "skills": 0.40,
        "experience_titles": 0.25,
        "experience_bullets": 0.15,
        "projects": 0.10,
        "summary": 0.05,
        "education_certifications": 0.05,
    }
)

DEFAULT_MATCH_CAPS: Mapping[str, float] = MappingProxyType(
    {
        "skills": 4.0,
        "experience_titles": 1.0,
        "experience_bullets": 3.0,
        "projects": 2.0,
        "summary": 2.0,
        "education_certifications": 2.0,
    }
)


@dataclass(frozen=True)
class ScoringConfig:
    """Configuration shared by the scorer and public suggestion service."""

    weights: Mapping[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS)
    match_caps: Mapping[str, float] = field(default_factory=lambda: DEFAULT_MATCH_CAPS)
    top_k: int = 3
    minimum_confidence: float = 0.20
    minimum_unique_evidence: int = 2

    def __post_init__(self) -> None:
        weights = MappingProxyType(dict(self.weights))
        caps = MappingProxyType(dict(self.match_caps))
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "match_caps", caps)

        if set(weights) != set(DEFAULT_WEIGHTS):
            raise ValueError("weights must define every supported scoring category")
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError("scoring weights must sum to 1.0")
        if any(value < 0.0 for value in weights.values()):
            raise ValueError("scoring weights cannot be negative")
        if set(caps) != set(weights) or any(value <= 0 for value in caps.values()):
            raise ValueError("match_caps must contain one positive cap per category")
        if self.top_k < 1:
            raise ValueError("top_k must be at least 1")
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")
        if self.minimum_unique_evidence < 1:
            raise ValueError("minimum_unique_evidence must be at least 1")
