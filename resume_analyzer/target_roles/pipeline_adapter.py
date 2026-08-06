"""Adapters for legacy, layered, and schema-oriented Pipeline JSON variants."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import replace
from typing import Any

from .contracts import EvidenceRecord, NormalizedResumeProfile
from .exceptions import InvalidPipelineInputError
from .normalizer import SkillAliasResolver, normalize_skill_values
from .text_utils import detect_language, normalize_text, unique_normalized

_MISSING = object()


class _EvidenceBuilder:
    def __init__(self) -> None:
        self.items: list[EvidenceRecord] = []
        self._seen: set[tuple[str, str, str]] = set()

    def add(self, source: str, path: str, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise InvalidPipelineInputError(f"{path} must be a string or null")
        clean = value.strip()
        normalized = normalize_text(clean)
        key = (source, path, normalized)
        if not normalized or key in self._seen:
            return ""
        self._seen.add(key)
        self.items.append(EvidenceRecord(source, path, clean, normalized))
        return clean


class PipelineAdapter:
    """Normalize reasonable Pipeline JSON variations without mutating input."""

    def __init__(self, aliases: SkillAliasResolver | None = None) -> None:
        self.aliases = aliases or SkillAliasResolver.from_json()

    def adapt(
        self,
        value: dict[str, Any] | NormalizedResumeProfile,
        *,
        language: str | None = None,
    ) -> NormalizedResumeProfile:
        if isinstance(value, NormalizedResumeProfile):
            return replace(value, language=language) if language else value
        if not isinstance(value, dict):
            raise InvalidPipelineInputError("pipeline input must be a dictionary")

        root = deepcopy(value)
        self._validate_recognized_types(root)
        evidence = _EvidenceBuilder()

        summary = self._extract_summary(root, evidence)
        original_skills = self._extract_skills(root, evidence)
        normalized_skills = normalize_skill_values(original_skills, self.aliases)
        titles, companies, bullets = self._extract_experience(root, evidence)
        (
            project_names,
            project_descriptions,
            project_technologies,
        ) = self._extract_projects(root, evidence)
        education = self._extract_generic_collection(
            root,
            (
                ("education",),
                ("entities", "education"),
                ("analysis", "facts", "education"),
            ),
            collection_keys=("education", "items", "entries", "degrees"),
            value_keys=(
                "degree",
                "field",
                "institution",
                "description",
                "qualification",
                "major",
            ),
            source="education_certifications",
            evidence=evidence,
        )
        certifications = self._extract_certifications(root, evidence)
        languages = self._extract_generic_collection(
            root,
            (
                ("languages",),
                ("entities", "languages"),
                ("analysis", "facts", "languages"),
            ),
            collection_keys=("languages", "items", "found"),
            value_keys=("language", "name", "value", "proficiency"),
            source="languages",
            evidence=evidence,
        )
        extracted_text = self._extract_text(root)
        contact = self._extract_contact(root)
        metadata = self._extract_metadata(root)

        language_values = [
            summary,
            *original_skills,
            *titles,
            *bullets,
            *project_descriptions,
            *education,
            *certifications,
        ]
        detected = language or detect_language(language_values)
        if detected not in {"ar", "en", "mixed", "unknown"}:
            raise InvalidPipelineInputError("language must be ar, en, mixed, or unknown")

        return NormalizedResumeProfile(
            summary=summary,
            skills=normalized_skills,
            original_skills=unique_normalized(original_skills),
            experience_titles=unique_normalized(titles),
            experience_companies=unique_normalized(companies),
            experience_bullets=unique_normalized(bullets),
            project_names=unique_normalized(project_names),
            project_descriptions=unique_normalized(project_descriptions),
            project_technologies=unique_normalized(project_technologies),
            education=unique_normalized(education),
            certifications=unique_normalized(certifications),
            languages=unique_normalized(languages),
            extracted_text=extracted_text,
            contact=tuple(contact),
            metadata=tuple(metadata),
            evidence=tuple(evidence.items),
            language=detected,
        )

    def _validate_recognized_types(self, root: dict[str, Any]) -> None:
        rules: dict[str, tuple[type, ...]] = {
            "summary": (str, dict),
            "skills": (str, list, dict),
            "experience": (str, list, dict),
            "education": (str, list, dict),
            "projects": (str, list, dict),
            "languages": (str, list, dict),
            "certifications": (str, list, dict),
            "contact": (dict,),
            "sections": (dict,),
            "metadata": (dict,),
            "entities": (dict,),
            "extracted_text": (str, dict),
            "extracted_resume_text": (str, dict),
        }
        for field_name, allowed in rules.items():
            if (
                field_name in root
                and root[field_name] is not None
                and not isinstance(root[field_name], allowed)
            ):
                names = ", ".join(item.__name__ for item in allowed)
                raise InvalidPipelineInputError(f"{field_name} must be one of: {names}, or null")

    def _extract_summary(self, root: dict[str, Any], evidence: _EvidenceBuilder) -> str:
        candidates = (
            (
                ("summary",),
                ("content", "text", "value", "professional_summary", "profile"),
            ),
            (("entities", "summary"), ("content", "text", "value")),
            (("sections", "sections", "summary"), ("content", "text", "value")),
            (("sections", "summary"), ("content", "text", "value")),
            (
                ("analysis", "facts", "sections", "sections", "summary"),
                ("content", "text", "value"),
            ),
        )
        for path, keys in candidates:
            raw = self._get(root, path)
            value = self._scalar(raw, keys)
            if value:
                return evidence.add(
                    "summary", self._path(path, self._selected_key(raw, keys)), value
                )
        return ""

    def _extract_skills(self, root: dict[str, Any], evidence: _EvidenceBuilder) -> list[str]:
        for path in (
            ("skills",),
            ("entities", "skills"),
            ("analysis", "facts", "skills"),
        ):
            raw = self._get(root, path)
            if raw is _MISSING or raw is None:
                continue
            values = list(
                self._collection_values(
                    raw,
                    path,
                    collection_keys=(
                        "found",
                        "all_skills",
                        "skills",
                        "hard_skills",
                        "soft_skills",
                        "top_technologies",
                    ),
                    value_keys=("value", "skill", "name", "text"),
                    include_nested_dict="categorized_skills",
                )
            )
            if values:
                output: list[str] = []
                for item_path, item in values:
                    added = evidence.add("skills", item_path, item)
                    if added:
                        output.append(added)
                return output
        return []

    def _extract_experience(
        self, root: dict[str, Any], evidence: _EvidenceBuilder
    ) -> tuple[list[str], list[str], list[str]]:
        titles: list[str] = []
        companies: list[str] = []
        bullets: list[str] = []
        raw, base = self._first_collection(
            root,
            (
                ("experience",),
                ("entities", "experience"),
                ("analysis", "facts", "experience"),
            ),
            ("experiences", "items", "entries", "jobs", "work_experience"),
        )
        if raw is _MISSING:
            return titles, companies, bullets
        entries = self._as_entries(
            raw, base, ("experiences", "items", "entries", "jobs", "work_experience")
        )
        for item_path, item in entries:
            if isinstance(item, str):
                added = evidence.add("experience.bullets", item_path, item)
                if added:
                    bullets.append(added)
                continue
            if not isinstance(item, dict):
                raise InvalidPipelineInputError(f"{item_path} must be a string or object")
            for key in ("job_title", "title", "role", "position"):
                if key in item:
                    added = evidence.add(
                        "experience.titles",
                        f"{item_path}.{key}",
                        self._scalar(item[key], ("value", "text")),
                    )
                    if added:
                        titles.append(added)
                    break
            for key in ("company", "company_name", "employer", "organization"):
                if key in item:
                    value = self._scalar(item[key], ("value", "text", "name"))
                    if value:
                        companies.append(value)
                    break
            for key in (
                "bullets",
                "responsibilities",
                "achievements",
                "highlights",
                "description",
                "technologies",
            ):
                if key not in item or item[key] is None:
                    continue
                for child_path, value in self._simple_values(item[key], f"{item_path}.{key}"):
                    added = evidence.add("experience.bullets", child_path, value)
                    if added:
                        bullets.append(added)
        return titles, companies, bullets

    def _extract_projects(
        self, root: dict[str, Any], evidence: _EvidenceBuilder
    ) -> tuple[list[str], list[str], list[str]]:
        names: list[str] = []
        descriptions: list[str] = []
        technologies: list[str] = []
        raw, base = self._first_collection(
            root,
            (
                ("projects",),
                ("entities", "projects"),
                ("analysis", "facts", "projects"),
            ),
            ("projects", "items", "entries"),
        )
        if raw is _MISSING:
            return names, descriptions, technologies
        for item_path, item in self._as_entries(raw, base, ("projects", "items", "entries")):
            if isinstance(item, str):
                added = evidence.add("projects", item_path, item)
                if added:
                    descriptions.append(added)
                continue
            if not isinstance(item, dict):
                raise InvalidPipelineInputError(f"{item_path} must be a string or object")
            for key in ("name", "title", "project_name"):
                if key in item:
                    value = self._scalar(item[key], ("value", "text"))
                    added = evidence.add("projects", f"{item_path}.{key}", value)
                    if added:
                        names.append(added)
                    break
            for key in ("description", "summary", "highlights", "bullets"):
                if key in item and item[key] is not None:
                    for child_path, value in self._simple_values(item[key], f"{item_path}.{key}"):
                        added = evidence.add("projects", child_path, value)
                        if added:
                            descriptions.append(added)
            for key in ("technologies", "tech_stack", "tools"):
                if key in item and item[key] is not None:
                    for child_path, value in self._simple_values(item[key], f"{item_path}.{key}"):
                        added = evidence.add("projects", child_path, value)
                        if added:
                            technologies.append(added)
        return names, descriptions, technologies

    def _extract_certifications(
        self, root: dict[str, Any], evidence: _EvidenceBuilder
    ) -> list[str]:
        output = self._extract_generic_collection(
            root,
            (
                ("certifications",),
                ("entities", "certifications"),
                ("analysis", "facts", "certifications"),
            ),
            collection_keys=("certifications", "items", "entries", "found"),
            value_keys=("name", "title", "value", "certification", "issuer"),
            source="education_certifications",
            evidence=evidence,
        )
        if output:
            return output
        for path in (
            ("sections", "sections", "certifications", "content"),
            ("sections", "certifications", "content"),
            ("analysis", "facts", "sections", "sections", "certifications", "content"),
        ):
            raw = self._get(root, path)
            if isinstance(raw, str) and raw.strip():
                return [evidence.add("education_certifications", self._path(path), raw)]
        return []

    def _extract_generic_collection(
        self,
        root: dict[str, Any],
        paths: tuple[tuple[str, ...], ...],
        *,
        collection_keys: tuple[str, ...],
        value_keys: tuple[str, ...],
        source: str,
        evidence: _EvidenceBuilder,
    ) -> list[str]:
        for path in paths:
            raw = self._get(root, path)
            if raw is _MISSING or raw is None:
                continue
            values = list(self._collection_values(raw, path, collection_keys, value_keys))
            if values:
                output = []
                for item_path, item in values:
                    added = evidence.add(source, item_path, item)
                    if added:
                        output.append(added)
                return output
        return []

    def _collection_values(
        self,
        raw: Any,
        base: tuple[str, ...],
        collection_keys: tuple[str, ...],
        value_keys: tuple[str, ...],
        include_nested_dict: str | None = None,
    ) -> Iterable[tuple[str, str]]:
        if isinstance(raw, str):
            yield self._path(base), raw
            return
        entries = self._as_entries(raw, base, collection_keys)
        for item_path, item in entries:
            if isinstance(item, str):
                yield item_path, item
            elif isinstance(item, dict):
                found = False
                for key in value_keys:
                    if key in item:
                        value = self._scalar(item[key], ("value", "text", "name"))
                        if value:
                            yield f"{item_path}.{key}", value
                            found = True
                if include_nested_dict and isinstance(item.get(include_nested_dict), dict):
                    for category, values in item[include_nested_dict].items():
                        for nested_path, value in self._simple_values(
                            values, f"{item_path}.{include_nested_dict}.{category}"
                        ):
                            yield nested_path, value
                            found = True
                if not found and len(item) == 1:
                    key, value = next(iter(item.items()))
                    scalar = self._scalar(value, ("value", "text", "name"))
                    if scalar:
                        yield f"{item_path}.{key}", scalar
            else:
                raise InvalidPipelineInputError(f"{item_path} must be a string or object")

    def _first_collection(
        self,
        root: dict[str, Any],
        paths: tuple[tuple[str, ...], ...],
        collection_keys: tuple[str, ...],
    ) -> tuple[Any, tuple[str, ...]]:
        for path in paths:
            raw = self._get(root, path)
            if raw is _MISSING or raw is None:
                continue
            entries = self._as_entries(raw, path, collection_keys)
            if entries:
                return raw, path
        return _MISSING, ()

    def _as_entries(
        self, raw: Any, base: tuple[str, ...], collection_keys: tuple[str, ...]
    ) -> list[tuple[str, Any]]:
        if isinstance(raw, str):
            return [(self._path(base), raw)] if raw.strip() else []
        if isinstance(raw, list):
            return [
                (f"{self._path(base)}[{index}]", item)
                for index, item in enumerate(raw)
                if item is not None
            ]
        if not isinstance(raw, dict):
            raise InvalidPipelineInputError(
                f"{self._path(base)} must be a string, list, object, or null"
            )
        for key in collection_keys:
            if key in raw and raw[key] is not None:
                return self._as_entries(raw[key], (*base, key), ())
        if any(key in raw for key in ("title", "job_title", "name", "degree", "language", "value")):
            return [(self._path(base), raw)]
        object_values = [(key, value) for key, value in raw.items() if isinstance(value, dict)]
        if object_values and len(object_values) == len(raw):
            return [(f"{self._path(base)}.{key}", value) for key, value in object_values]
        return []

    def _simple_values(self, raw: Any, path: str) -> Iterable[tuple[str, str]]:
        if isinstance(raw, str):
            yield path, raw
        elif isinstance(raw, list):
            for index, item in enumerate(raw):
                if item is None:
                    continue
                if isinstance(item, str):
                    yield f"{path}[{index}]", item
                elif isinstance(item, dict):
                    value = self._scalar(item, ("value", "text", "description", "name"))
                    if value:
                        yield f"{path}[{index}]", value
                    else:
                        raise InvalidPipelineInputError(
                            f"{path}[{index}] has no supported text field"
                        )
                else:
                    raise InvalidPipelineInputError(f"{path}[{index}] must be a string or object")
        elif isinstance(raw, dict):
            value = self._scalar(raw, ("value", "text", "description", "name"))
            if value:
                yield path, value
            else:
                for key, item in raw.items():
                    if isinstance(item, str):
                        yield f"{path}.{key}", item
        else:
            raise InvalidPipelineInputError(f"{path} must be a string, list, object, or null")

    def _extract_text(self, root: dict[str, Any]) -> str:
        for path in (
            ("extracted_text",),
            ("extracted_resume_text", "analysis_text"),
            ("extracted_resume_text", "ordered_text"),
            ("extracted_resume_text", "cleaned_text"),
            ("extracted_resume_text", "raw_text"),
            ("text_extraction", "text"),
        ):
            raw = self._get(root, path)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    def _extract_contact(self, root: dict[str, Any]) -> list[tuple[str, str]]:
        output: list[tuple[str, str]] = []
        containers = [root]
        for path in (("contact",), ("candidate",), ("analysis", "facts", "contact")):
            raw = self._get(root, path)
            if isinstance(raw, dict):
                containers.append(raw)
        for field_name in ("name", "email", "phone", "location"):
            for container in containers:
                if field_name in container:
                    value = self._scalar(container[field_name], ("value", "text"))
                    if value:
                        output.append((field_name, value))
                        break
        return output

    def _extract_metadata(self, root: dict[str, Any]) -> list[tuple[str, str]]:
        output: list[tuple[str, str]] = []
        metadata = root.get("metadata")
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    output.append((str(key), str(value)))
        file_info = root.get("file")
        if isinstance(file_info, dict):
            for key in ("name", "extension"):
                if isinstance(file_info.get(key), str):
                    output.append((f"file.{key}", file_info[key]))
        return output

    @staticmethod
    def _get(root: dict[str, Any], path: tuple[str, ...]) -> Any:
        current: Any = root
        for part in path:
            if not isinstance(current, dict) or part not in current:
                return _MISSING
            current = current[part]
        return current

    @staticmethod
    def _scalar(raw: Any, keys: tuple[str, ...]) -> str:
        if raw is _MISSING or raw is None:
            return ""
        if isinstance(raw, str):
            return raw.strip()
        if isinstance(raw, dict):
            for key in keys:
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _selected_key(raw: Any, keys: tuple[str, ...]) -> str | None:
        if isinstance(raw, dict):
            return next(
                (key for key in keys if isinstance(raw.get(key), str) and raw[key].strip()),
                None,
            )
        return None

    @staticmethod
    def _path(parts: tuple[str, ...], leaf: str | None = None) -> str:
        values = (*parts, leaf) if leaf else parts
        return ".".join(part for part in values if part)
