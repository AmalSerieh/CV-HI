"""Skill alias resolution layered on Unicode text normalization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from resume_analyzer.terminology import terminology_aliases

from .exceptions import InvalidCatalogError
from .text_utils import normalize_text, phrase_in_text, unique_normalized


class SkillAliasResolver:
    """Resolve exact skill aliases and match aliases inside source evidence."""

    def __init__(self, aliases: Mapping[str, str]) -> None:
        normalized: dict[str, str] = {}
        reverse: dict[str, list[str]] = {}
        merged_aliases = {**terminology_aliases(), **aliases}
        for alias, canonical in merged_aliases.items():
            if not isinstance(alias, str) or not isinstance(canonical, str):
                raise InvalidCatalogError("skill aliases must map strings to strings")
            alias_key = normalize_text(alias)
            canonical_value = normalize_text(canonical)
            if not alias_key or not canonical_value:
                raise InvalidCatalogError("skill aliases cannot be empty")
            normalized[alias_key] = canonical_value
            reverse.setdefault(canonical_value, []).append(alias_key)

        self._aliases = MappingProxyType(normalized)
        self._reverse = MappingProxyType(
            {key: tuple(unique_normalized(value)) for key, value in reverse.items()}
        )

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> SkillAliasResolver:
        source = Path(path) if path else Path(__file__).parent / "data" / "skill_aliases.json"
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidCatalogError(f"cannot load skill aliases from {source}: {exc}") from exc
        aliases = payload.get("aliases") if isinstance(payload, dict) else None
        if not isinstance(aliases, dict):
            raise InvalidCatalogError("skill_aliases.json must contain an 'aliases' object")
        return cls(aliases)

    def canonicalize(self, value: str) -> str:
        normalized = normalize_text(value)
        return self._aliases.get(normalized, normalized)

    def variants(self, canonical: str) -> tuple[str, ...]:
        normalized = self.canonicalize(canonical)
        return unique_normalized((normalized, *self._reverse.get(normalized, ())))

    def signal_matches(self, signal: str, evidence_text: str) -> bool:
        return any(phrase_in_text(variant, evidence_text) for variant in self.variants(signal))


def normalize_skill_values(
    values: list[str] | tuple[str, ...],
    resolver: SkillAliasResolver,
) -> tuple[str, ...]:
    return unique_normalized(tuple(resolver.canonicalize(value) for value in values))
