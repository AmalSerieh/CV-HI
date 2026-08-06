"""Explainable deterministic lexical role scoring."""

from __future__ import annotations

import math

from .config import ScoringConfig
from .contracts import EvidenceRecord, NormalizedResumeProfile, RoleScore
from .normalizer import SkillAliasResolver
from .role_catalog import RoleCatalog, RoleDefinition
from .text_utils import normalize_text


class LexicalRoleScorer:
    """Score every role using only evidence present in the normalized profile."""

    _SOURCES = {
        "skills": ("skills",),
        "experience_titles": ("experience.titles",),
        "experience_bullets": ("experience.bullets",),
        "projects": ("projects",),
        "summary": ("summary",),
        "education_certifications": ("education_certifications",),
    }

    def __init__(
        self,
        catalog: RoleCatalog,
        aliases: SkillAliasResolver,
        config: ScoringConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.aliases = aliases
        self.config = config or ScoringConfig()

    def score_all(self, profile: NormalizedResumeProfile) -> tuple[RoleScore, ...]:
        return tuple(self.score(profile, role) for role in self.catalog.roles)

    def score(self, profile: NormalizedResumeProfile, role: RoleDefinition) -> RoleScore:
        breakdown: list[tuple[str, float]] = []
        matched_signals: list[str] = []
        matched_evidence: list[EvidenceRecord] = []

        for category, weight in self.config.weights.items():
            candidates = tuple(
                item for item in profile.evidence if item.source in self._SOURCES[category]
            )
            signals = self._signals_for(role, category)
            category_total = 0.0
            for signal, strength in signals:
                matches = [
                    item for item in candidates if self.aliases.signal_matches(signal, item.value)
                ]
                if not matches:
                    continue
                category_total += strength
                matched_signals.append(self.aliases.canonicalize(signal))
                matched_evidence.extend(matches)
            normalized_category = min(
                1.0,
                category_total / self.config.match_caps[category],
            )
            contribution = round(weight * normalized_category, 4)
            breakdown.append((category, contribution))

        confidence = round(min(1.0, max(0.0, sum(value for _, value in breakdown))), 4)
        if not math.isfinite(confidence):
            confidence = 0.0
        return RoleScore(
            role_id=role.id,
            title_en=role.name_en,
            title_ar=role.name_ar,
            confidence=confidence,
            matched_signals=self._unique_signals(matched_signals),
            score_breakdown=tuple(breakdown),
            evidence=self._unique_evidence(matched_evidence),
        )

    def _signals_for(self, role: RoleDefinition, category: str) -> tuple[tuple[str, float], ...]:
        if category == "skills":
            values = [(item, 1.0) for item in role.required_signals]
            values += [(item, 0.65) for item in role.preferred_signals]
        elif category == "experience_titles":
            values = [(role.name_en, 1.0), (role.name_ar, 1.0)]
            values += [(item, 1.0) for item in role.aliases]
            values += [(item, 0.80) for item in role.experience_keywords]
        elif category == "experience_bullets":
            values = [(item, 0.90) for item in role.experience_keywords]
            values += [(item, 0.75) for item in role.required_signals]
            values += [(item, 0.50) for item in role.preferred_signals]
        elif category == "projects":
            values = [(item, 1.0) for item in role.project_keywords]
            values += [(item, 0.75) for item in role.required_signals]
            values += [(item, 0.50) for item in role.preferred_signals]
        elif category == "summary":
            values = [(role.name_en, 1.0), (role.name_ar, 1.0)]
            values += [(item, 0.90) for item in role.aliases]
            values += [(item, 0.60) for item in role.experience_keywords]
            values += [(item, 0.45) for item in role.required_signals]
        else:
            values = [(item, 1.0) for item in role.education_keywords]
            values += [(item, 1.0) for item in role.certification_keywords]
            values += [(item, 0.35) for item in role.required_signals]
        return self._unique_weighted_signals(values)

    @staticmethod
    def _unique_weighted_signals(values: list[tuple[str, float]]) -> tuple[tuple[str, float], ...]:
        output: dict[str, tuple[str, float]] = {}
        for signal, weight in values:
            key = normalize_text(signal)
            if key and (key not in output or weight > output[key][1]):
                output[key] = (signal, weight)
        return tuple(output.values())

    @staticmethod
    def _unique_signals(values: list[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            key = normalize_text(value)
            if key and key not in seen:
                seen.add(key)
                output.append(value)
        return tuple(output)

    @staticmethod
    def _unique_evidence(values: list[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
        seen: set[tuple[str, str, str]] = set()
        output: list[EvidenceRecord] = []
        for value in values:
            key = (value.source, value.path, value.normalized)
            if key not in seen:
                seen.add(key)
                output.append(value)
        return tuple(output)
