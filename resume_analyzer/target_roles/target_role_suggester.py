"""Public deterministic target-role suggestion service."""

from __future__ import annotations

from .config import ScoringConfig
from .contracts import NormalizedResumeProfile, RoleScore
from .normalizer import SkillAliasResolver
from .pipeline_adapter import PipelineAdapter
from .role_catalog import RoleCatalog
from .role_scorer import LexicalRoleScorer


class TargetRoleSuggester:
    """Suggest a primary role and alternatives without network or model access."""

    METHOD = "deterministic_weighted_matching"

    def __init__(
        self,
        *,
        catalog: RoleCatalog | None = None,
        aliases: SkillAliasResolver | None = None,
        config: ScoringConfig | None = None,
    ) -> None:
        self.aliases = aliases or SkillAliasResolver.from_json()
        self.catalog = catalog or RoleCatalog.load()
        self.config = config or ScoringConfig()
        self.adapter = PipelineAdapter(self.aliases)
        self.scorer = LexicalRoleScorer(self.catalog, self.aliases, self.config)

    def suggest(
        self,
        value: dict | NormalizedResumeProfile,
        *,
        top_k: int | None = None,
        minimum_confidence: float | None = None,
        language: str | None = None,
    ) -> dict:
        selected_top_k = self.config.top_k if top_k is None else top_k
        selected_minimum = (
            self.config.minimum_confidence if minimum_confidence is None else minimum_confidence
        )
        if selected_top_k < 1:
            raise ValueError("top_k must be at least 1")
        if not 0.0 <= selected_minimum <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1")

        profile = self.adapter.adapt(value, language=language)
        scored = sorted(
            self.scorer.score_all(profile),
            key=lambda item: (-item.confidence, item.role_id),
        )
        eligible = [
            item
            for item in scored
            if item.confidence >= selected_minimum
            and self._unique_evidence_count(item) >= self.config.minimum_unique_evidence
        ]

        if not eligible:
            return {
                "target_role": {
                    "primary": None,
                    "alternatives": [],
                    "insufficient_evidence": True,
                    "method": self.METHOD,
                    "language": profile.language,
                    "warnings": ["Not enough resume evidence to suggest a reliable target role."],
                }
            }

        selected = eligible[:selected_top_k]
        return {
            "target_role": {
                "primary": selected[0].to_dict(),
                "alternatives": [item.to_dict() for item in selected[1:]],
                "insufficient_evidence": False,
                "method": self.METHOD,
                "language": profile.language,
                "warnings": [],
            }
        }

    @staticmethod
    def _unique_evidence_count(score: RoleScore) -> int:
        return len({(item.path, item.normalized) for item in score.evidence})


def suggest_target_roles(
    pipeline_json: dict | NormalizedResumeProfile,
    *,
    top_k: int = 3,
    minimum_confidence: float = 0.20,
    language: str | None = None,
) -> dict:
    """Convenience API using the bundled catalog and lexical scorer."""

    return TargetRoleSuggester().suggest(
        pipeline_json,
        top_k=top_k,
        minimum_confidence=minimum_confidence,
        language=language,
    )
