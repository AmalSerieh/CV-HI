"""Extensible JSON role catalog loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .exceptions import InvalidCatalogError


@dataclass(frozen=True)
class RoleDefinition:
    id: str
    name_en: str
    name_ar: str
    aliases: tuple[str, ...]
    required_signals: tuple[str, ...]
    preferred_signals: tuple[str, ...]
    experience_keywords: tuple[str, ...]
    project_keywords: tuple[str, ...]
    education_keywords: tuple[str, ...] = ()
    certification_keywords: tuple[str, ...] = ()


class RoleCatalog:
    """Validated immutable collection of role definitions."""

    _REQUIRED_FIELDS = (
        "id",
        "name_en",
        "name_ar",
        "aliases",
        "required_signals",
        "preferred_signals",
        "experience_keywords",
        "project_keywords",
    )
    _LIST_FIELDS = (
        "aliases",
        "required_signals",
        "preferred_signals",
        "experience_keywords",
        "project_keywords",
        "education_keywords",
        "certification_keywords",
    )

    def __init__(self, roles: tuple[RoleDefinition, ...]) -> None:
        if not roles:
            raise InvalidCatalogError("role catalog must contain at least one role")
        identifiers = [role.id for role in roles]
        duplicates = sorted({value for value in identifiers if identifiers.count(value) > 1})
        if duplicates:
            raise InvalidCatalogError(f"duplicate role IDs: {', '.join(duplicates)}")
        self._roles = roles
        self._by_id = {role.id: role for role in roles}

    @property
    def roles(self) -> tuple[RoleDefinition, ...]:
        return self._roles

    @property
    def role_ids(self) -> tuple[str, ...]:
        return tuple(role.id for role in self._roles)

    def get(self, role_id: str) -> RoleDefinition:
        try:
            return self._by_id[role_id]
        except KeyError as exc:
            raise KeyError(f"unknown role ID: {role_id}") from exc

    @classmethod
    def load(cls, path: str | Path | None = None) -> RoleCatalog:
        source = Path(path) if path else Path(__file__).parent / "data" / "role_catalog.json"
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidCatalogError(f"cannot load role catalog from {source}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("roles"), list):
            raise InvalidCatalogError("role catalog must contain a 'roles' array")
        return cls(
            tuple(cls._parse_entry(item, index) for index, item in enumerate(payload["roles"]))
        )

    @classmethod
    def _parse_entry(cls, item: object, index: int) -> RoleDefinition:
        location = f"roles[{index}]"
        if not isinstance(item, dict):
            raise InvalidCatalogError(f"{location} must be an object")
        missing = [field for field in cls._REQUIRED_FIELDS if field not in item]
        if missing:
            raise InvalidCatalogError(f"{location} is missing: {', '.join(missing)}")
        for field_name in ("id", "name_en", "name_ar"):
            if not isinstance(item[field_name], str) or not item[field_name].strip():
                raise InvalidCatalogError(f"{location}.{field_name} must be a non-empty string")
        for field_name in cls._LIST_FIELDS:
            value = item.get(field_name, [])
            if not isinstance(value, list) or any(
                not isinstance(entry, str) or not entry.strip() for entry in value
            ):
                raise InvalidCatalogError(
                    f"{location}.{field_name} must be an array of non-empty strings"
                )
        signal_count = sum(len(item.get(field, [])) for field in cls._LIST_FIELDS)
        if signal_count == 0:
            raise InvalidCatalogError(f"{location} must define at least one alias or signal")
        if not item["id"].replace("_", "").isalnum() or item["id"] != item["id"].lower():
            raise InvalidCatalogError(f"{location}.id must be a lowercase snake-case identifier")
        return RoleDefinition(
            id=item["id"].strip(),
            name_en=item["name_en"].strip(),
            name_ar=item["name_ar"].strip(),
            aliases=tuple(value.strip() for value in item["aliases"]),
            required_signals=tuple(value.strip() for value in item["required_signals"]),
            preferred_signals=tuple(value.strip() for value in item["preferred_signals"]),
            experience_keywords=tuple(value.strip() for value in item["experience_keywords"]),
            project_keywords=tuple(value.strip() for value in item["project_keywords"]),
            education_keywords=tuple(value.strip() for value in item.get("education_keywords", [])),
            certification_keywords=tuple(
                value.strip() for value in item.get("certification_keywords", [])
            ),
        )
