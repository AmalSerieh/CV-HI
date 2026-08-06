"""Geometry-grounded canonical entity assembly for verified layout sections."""

from __future__ import annotations

import re
from typing import Any

from resume_analyzer.terminology import (
    canonical_technology,
    is_known_technology,
)

_BULLET_RE = re.compile(r"^\s*[•●▪◦‣⁃*–—-]\s*")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_DATE_RANGE_RE = re.compile(
    r"(?i)\b((?:19|20)\d{2}(?:[/-]\d{1,2})?)\s*"
    r"(?:-|–|—|to|until|حتى)\s*"
    r"((?:19|20)\d{2}(?:[/-]\d{1,2})?|present|current|now|الآن|حتى الآن)\b"
)
_PLACEHOLDER_DATE_RE = re.compile(
    r"(?i)\b(?:19|20)X{2}\b\s*(?:-|–|—|to|until)\s*\b(?:19|20)X{2}\b"
)
_SEASON_YEAR_RE = re.compile(
    r"(?i)\b(?:spring|summer|fall|autumn|winter)\s+(?:19|20)\d{2}\b"
)
_TEMPLATE_RE = re.compile(
    r"(?i)\b(?:do not remove|sample content|free online template|"
    r"replace this text|your text here)\b"
)
_METRIC_RE = re.compile(
    r"(?i)(?:\b\d+(?:\.\d+)?%|\$\s*\d[\d,.]*|\b\d+\s*(?:users|clients|hours|days)\b)"
)


def _bbox(block: dict[str, Any]) -> dict[str, Any]:
    value = block.get("bbox")
    return value if isinstance(value, dict) else {}


def _top(block: dict[str, Any]) -> float:
    return float(_bbox(block).get("top", 0.0))


def _bottom(block: dict[str, Any]) -> float:
    return float(_bbox(block).get("bottom", 0.0))


def _left(block: dict[str, Any]) -> float:
    return float(_bbox(block).get("x0", 0.0))


def _strip_bullet(value: str) -> str:
    text = str(value or "").replace("’", "'").replace("‘", "'")
    return _BULLET_RE.sub("", text).strip()


def _join_wrapped_line(current: str, continuation: str) -> str:
    """Join visual line fragments without preserving discretionary hyphens."""

    current = str(current or "").rstrip()
    continuation = str(continuation or "").lstrip()
    if current.endswith("\u00ad"):
        return f"{current[:-1]}{continuation}".strip()
    if continuation in {".", ",", ";", ":", "!", "?", "،", "؛"}:
        return f"{current}{continuation}".strip()
    return f"{current} {continuation}".strip()


def _deduplicate(values: list[str]) -> tuple[list[str], int]:
    output: list[str] = []
    seen: set[str] = set()
    removed = 0
    for value in values:
        normalized = re.sub(r"[\W_]+", " ", value.casefold()).strip()
        if not normalized:
            continue
        if normalized in seen:
            removed += 1
            continue
        seen.add(normalized)
        output.append(value.strip())
    return output, removed


def _date_parts(value: str) -> tuple[str | None, str | None, bool]:
    match = _DATE_RANGE_RE.search(value)
    if match:
        start = match.group(1).replace("/", "-")
        end = match.group(2).replace("/", "-")
        current = end.casefold() in {
            "present",
            "current",
            "now",
            "الآن",
            "حتى الآن",
        }
        if current:
            end = "Present"
        return start, end, current
    season = _SEASON_YEAR_RE.search(value)
    if season:
        return None, season.group(0), False
    year = _YEAR_RE.search(value)
    if year:
        return None, year.group(0), False
    return None, None, False


class StructuredEntityAssembler:
    """Build entities only when section-local block geometry is available."""

    SKILL_ALIASES = {
        "py": "Python",
        "python": "Python",
        "ms office": "Microsoft Office",
        "microsoft office": "Microsoft Office",
        "office 365": "Microsoft Office",
        "react": "React",
        "react js": "React",
        "react.js": "React",
        "docker": "Docker",
        "sql": "SQL",
        "structured query language": "SQL",
    }
    SKILL_CATEGORIES = {
        "python": "programming_languages",
        "react": "frontend",
        "docker": "cloud_devops",
        "sql": "databases",
        "microsoft office": "tools",
        "leadership": "soft_skills",
        "communication": "soft_skills",
        "planning": "soft_skills",
        "presentation": "soft_skills",
        "hard worker": "soft_skills",
        "hard-working": "soft_skills",
        "operations": "business_domain",
        "ai-powered automation": "ai_ml",
    }
    GENERIC_SKILLS = {
        "internet",
        "computer",
        "technology",
        "technologies",
        "other",
        "things",
    }
    _ROLE_WORDS = re.compile(
        r"(?i)\b(?:engineer|developer|architect|analyst|scientist|consultant|"
        r"manager|director|specialist|administrator|designer|researcher|intern|"
        r"lead|officer|coordinator|accountant|auditor|teacher|nurse|technician|"
        r"assistant|associate|bookkeeper|advisor|representative|"
        r"مهندس(?:ة)?|مطور(?:ة)?|محلل(?:ة)?|مدير(?:ة)?|أخصائي(?:ة)?|باحث(?:ة)?)\b"
    )
    _ACTION_START = re.compile(
        r"(?i)^(?:built|build|developed|developing|designed|designing|created|"
        r"implemented|implementing|integrated|integrating|prepared|preparing|"
        r"evaluated|communicated|managed|worked|working|helped|using|led|delivered|"
        r"reconciled|increased|reduced|improved|contributed|drafted|answered|"
        r"coordinated|conducted|performed|showed|became|completed|participated|"
        r"successfully|supported|maintained|optimized|analyzed|"
        r"طوّر|طور|عمل|بنى|صمم|نفذ|أدار|قاد)\b"
    )
    _ORG_SUFFIX = re.compile(
        r"(?i)\b(?:inc|llc|ltd|limited|corp|corporation|company|co|group|"
        r"gmbh|plc|labs?|laborator(?:y|ies)|systems?|solutions?|technologies|"
        r"consulting|partners?|studio|agency|bank|university|institute|"
        r"شركة|مؤسسة|مجموعة|جامعة|بنك)\b"
    )
    _PRODUCT_SUFFIX = re.compile(
        r"(?i)\b(?:platform|application|app|project|product|model|toolkit|"
        r"dashboard|portal|engine)\s*$"
    )
    _TECH_LABEL = re.compile(
        r"(?i)^\s*(?:technologies|technology|tech\s*stack|stack|tools?)\s*[:：-]\s*"
    )
    _PROJECT_ROLE_LINE = re.compile(
        r"(?i)^(?:participant|contributor|project lead|team lead|developer|"
        r"designer|researcher|owner|maintainer|دور|مشارك|مساهمة|قائد الفريق)$"
    )
    COUNTRY_TERMS = {
        "argentina",
        "australia",
        "bahrain",
        "brazil",
        "canada",
        "china",
        "egypt",
        "france",
        "germany",
        "india",
        "iraq",
        "ireland",
        "italy",
        "japan",
        "jordan",
        "kuwait",
        "lebanon",
        "mexico",
        "netherlands",
        "oman",
        "pakistan",
        "qatar",
        "saudi arabia",
        "spain",
        "syria",
        "turkey",
        "uae",
        "united arab emirates",
        "united kingdom",
        "uk",
        "united states",
        "usa",
        "yemen",
    }

    def __init__(
        self,
        *,
        layout_blocks: list[dict[str, Any]],
        sections: dict[str, Any],
    ) -> None:
        self.blocks = {
            str(block.get("id")): block
            for block in layout_blocks
            if str(block.get("id") or "")
        }
        self.sections = sections.get("sections", sections)

    def _section_blocks(
        self,
        section_name: str,
        *,
        include_heading: bool = False,
    ) -> list[dict[str, Any]]:
        section = self.sections.get(section_name) or {}
        heading = str(section.get("heading") or "").strip()
        output = []
        for block_id in section.get("block_ids") or []:
            block = self.blocks.get(str(block_id))
            if not block:
                continue
            if not include_heading and heading and str(block.get("text") or "").strip() == heading:
                continue
            output.append(block)
        return output

    @staticmethod
    def _valid_semantic_block(block: dict[str, Any]) -> bool:
        text = str(block.get("text") or "").strip()
        return bool(
            text
            and abs(float(block.get("rotation") or 0.0)) < 5.0
            and not _TEMPLATE_RE.search(text)
        )

    @classmethod
    def _plausible_company(
        cls,
        value: str,
        *,
        structural_support: bool = False,
    ) -> bool:
        text = str(value or "").strip()
        words = text.split()
        if not text or len(words) > 8 or text.endswith((".", ",", ";", ":")):
            return False
        if re.match(
            r"(?i)^(?:for|where|because|while|and|or|to|with|i|we|they|"
            r"built|developed|implemented|using)\b",
            text,
        ):
            return False
        if re.search(
            r"(?i)\b(?:i am|i can|i want|seeking|passionate|responsible for|worked on)\b",
            text,
        ):
            return False
        has_org_context = bool(cls._ORG_SUFFIX.search(text))
        if re.fullmatch(r"[A-Z][A-Z0-9+./-]{1,9}s?", text) and not has_org_context:
            return False
        if cls._PRODUCT_SUFFIX.search(text) and not has_org_context:
            return False
        if is_known_technology(text) and not has_org_context:
            return False
        if cls._ROLE_WORDS.search(text) and not has_org_context:
            return False
        return structural_support or has_org_context

    @classmethod
    def _likely_job_title(cls, block: dict[str, Any]) -> bool:
        text = str(block.get("text") or "").strip()
        if (
            not text
            or len(text.split()) > 14
            or text.endswith((".", ",", ";", ":"))
            or block.get("bullet_marker")
            or _YEAR_RE.search(text)
        ):
            return False
        return bool(
            cls._ROLE_WORDS.search(text)
            or (
                str(block.get("font_weight") or "").casefold() == "bold"
                and not cls._ACTION_START.search(text)
            )
        )

    @staticmethod
    def _same_stream(first: dict[str, Any], second: dict[str, Any]) -> bool:
        if (
            first.get("page") is not None
            and second.get("page") is not None
            and first.get("page") != second.get("page")
        ):
            return False
        columns = {
            str(value)
            for value in (first.get("column"), second.get("column"))
            if value not in {None, "", "single", "full_width", "unknown"}
        }
        return columns != {"left", "right"}

    @staticmethod
    def _explicit_continuation(first: dict[str, Any], second: dict[str, Any]) -> bool:
        neighbors = first.get("neighbors")
        if not isinstance(neighbors, dict):
            return False
        values = neighbors.get("likely_continuation") or []
        return str(second.get("id") or "") in {str(value) for value in values}

    @classmethod
    def _should_join_body_lines(
        cls,
        first: dict[str, Any],
        second: dict[str, Any],
    ) -> bool:
        if second.get("bullet_marker") or _BULLET_RE.match(str(second.get("text") or "")):
            return False
        if not cls._same_stream(first, second):
            return False
        if cls._explicit_continuation(first, second):
            return True
        first_text = str(first.get("text") or "").rstrip()
        if re.search(r"[.!?؟]\s*$", first_text):
            return False
        vertical_gap = _top(second) - _bottom(first)
        return (
            -2.0 <= vertical_gap <= 4.0
            and abs(_left(first) - _left(second)) <= 8.0
            and not _DATE_RANGE_RE.search(str(second.get("text") or ""))
            and not _PLACEHOLDER_DATE_RE.search(str(second.get("text") or ""))
            and not _YEAR_RE.fullmatch(str(second.get("text") or "").strip())
        )

    @classmethod
    def _body_groups(
        cls,
        blocks: list[dict[str, Any]],
    ) -> list[tuple[str, list[str]]]:
        groups: list[tuple[str, list[str]]] = []
        previous: dict[str, Any] | None = None
        for block in blocks:
            raw_text = str(block.get("text") or "")
            text = _strip_bullet(raw_text)
            if not text:
                if block.get("bullet_marker") or _BULLET_RE.match(raw_text):
                    previous = None
                continue
            block_id = str(block.get("id") or "")
            if groups and previous is not None and cls._should_join_body_lines(previous, block):
                current, source_ids = groups[-1]
                groups[-1] = (
                    _join_wrapped_line(current, text),
                    [*source_ids, block_id],
                )
            else:
                groups.append((text, [block_id]))
            previous = block
        return groups

    def _experience_location(
        self,
        block: dict[str, Any],
        *,
        title_left: float,
    ) -> str | None:
        text = str(block.get("text") or "").strip()
        direct = self._geographic_location(text)
        if direct:
            return direct
        parts = [part.strip() for part in re.split(r"[,،]", text) if part.strip()]
        if (
            len(parts) == 2
            and _left(block) > title_left + 80.0
            and len(text.split()) <= 6
            and not any(is_known_technology(part) for part in parts)
        ):
            return f"{parts[0]}, {parts[1]}"
        return None

    @staticmethod
    def _clean_job_title(value: str) -> tuple[str, str | None]:
        text = str(value or "").strip()
        employment_type = None
        employment_match = re.search(
            r"(?i)\((co-?op|internship|contract|part[- ]time|full[- ]time|temporary)\)",
            text,
        )
        if employment_match:
            label = employment_match.group(1)
            employment_type = (
                "Co-op"
                if re.fullmatch(r"(?i)co-?op", label)
                else label.replace("-", " ").title()
            )
            text = (
                text[: employment_match.start()] + text[employment_match.end() :]
            ).strip()
        if "," in text:
            primary, qualifier = [part.strip() for part in text.split(",", 1)]
            if re.search(
                r"(?i)\b(?:department|store|division|team|unit|branch)\b",
                qualifier,
            ):
                text = primary
        return re.sub(r"\s+", " ", text).strip(" ,-"), employment_type

    def experience(self, fallback: dict[str, Any]) -> dict[str, Any]:
        blocks = [
            block
            for block in self._section_blocks("experience")
            if self._valid_semantic_block(block)
        ]
        if not blocks:
            return fallback

        header_left = min(
            (
                _left(block)
                for block in blocks
                if not block.get("bullet_marker")
                and not _BULLET_RE.match(str(block.get("text") or ""))
            ),
            default=0.0,
        )
        role_indices = [
            index
            for index, block in enumerate(blocks)
            if self._ROLE_WORDS.search(str(block.get("text") or ""))
            and self._likely_job_title(block)
            and (
                _left(block) <= header_left + 14.0
                or str(block.get("font_weight") or "").casefold() == "bold"
            )
        ]
        title_indices = role_indices or [
            index
            for index, block in enumerate(blocks)
            if self._likely_job_title(block)
        ]
        if not title_indices:
            return fallback

        entry_starts: list[int] = []
        previous_title_index = -1
        for title_index in title_indices:
            start_index = title_index
            title_block = blocks[title_index]
            cursor = title_index - 1
            while cursor > previous_title_index:
                candidate = blocks[cursor]
                text = str(candidate.get("text") or "").strip()
                if (
                    candidate.get("page") != title_block.get("page")
                    or title_index - cursor > 3
                    or candidate.get("bullet_marker")
                    or _BULLET_RE.match(text)
                    or self._ACTION_START.search(text)
                    or text.endswith((".", "!", "?", "؟"))
                    or _top(title_block) - _bottom(candidate) > 45.0
                ):
                    break
                start_index = cursor
                cursor -= 1
            entry_starts.append(start_index)
            previous_title_index = title_index

        entries: list[dict[str, Any]] = []
        warnings: list[str] = []
        for position, title_index in enumerate(title_indices):
            end_index = (
                entry_starts[position + 1]
                if position + 1 < len(entry_starts)
                else len(blocks)
            )
            start_index = entry_starts[position]
            entry_blocks = blocks[start_index:end_index]
            title_offset = title_index - start_index
            title_block = entry_blocks[title_offset]
            raw_title = str(title_block.get("text") or "").strip()
            title, employment_type = self._clean_job_title(raw_title)
            title_left = _left(title_block)

            body_index: int | None = None
            for index, block in enumerate(
                entry_blocks[title_offset + 1 :],
                start=title_offset + 1,
            ):
                text = str(block.get("text") or "").strip()
                if (
                    _DATE_RANGE_RE.search(text)
                    or _SEASON_YEAR_RE.search(text)
                    or _YEAR_RE.fullmatch(text)
                    or _PLACEHOLDER_DATE_RE.search(text)
                    or self._experience_location(block, title_left=title_left)
                ):
                    continue
                if (
                    block.get("bullet_marker")
                    or _BULLET_RE.match(text)
                    or self._ACTION_START.search(text)
                    or _left(block) > title_left + 8.0
                ):
                    body_index = index
                    break
            if body_index is None:
                body_index = len(entry_blocks)

            header_blocks = entry_blocks[title_offset + 1 : body_index]
            prior_header_blocks = entry_blocks[:title_offset]
            date_blocks = [
                block
                for block in entry_blocks
                if _DATE_RANGE_RE.search(str(block.get("text") or ""))
                or _SEASON_YEAR_RE.search(str(block.get("text") or ""))
                or _YEAR_RE.fullmatch(str(block.get("text") or "").strip())
                or _PLACEHOLDER_DATE_RE.search(str(block.get("text") or ""))
            ]
            company_candidates = [
                block
                for block in header_blocks
                if block not in date_blocks
                and abs(_left(block) - title_left) <= 12.0
                and self._experience_location(block, title_left=title_left) is None
            ]
            company_candidates.extend(
                block
                for block in reversed(prior_header_blocks)
                if block not in date_blocks
                and abs(_left(block) - title_left) <= 12.0
                and self._experience_location(block, title_left=title_left) is None
            )
            company_block = next(iter(company_candidates), None)
            company = str((company_block or {}).get("text") or "").strip() or None
            location = next(
                (
                    self._experience_location(block, title_left=title_left)
                    for block in [*prior_header_blocks, *header_blocks]
                    if self._experience_location(block, title_left=title_left)
                ),
                None,
            )
            company_supported = bool(
                company_block
                and self._same_stream(title_block, company_block)
                and min(
                    abs(_top(company_block) - _bottom(title_block)),
                    abs(_top(title_block) - _bottom(company_block)),
                )
                <= 24.0
            )
            if company and not self._plausible_company(
                company,
                structural_support=company_supported,
            ):
                warnings.append("EXPERIENCE_COMPANY_SUSPECT")
                company = None
                company_block = None

            body_blocks = [
                block
                for block in entry_blocks[body_index:]
                if block not in date_blocks
            ]
            grouped = self._body_groups(body_blocks)
            bullets, duplicate_count = _deduplicate([value for value, _ in grouped])
            if duplicate_count:
                warnings.append("EXPERIENCE_BULLET_DUPLICATE")
            retained_groups: list[tuple[str, list[str]]] = []
            retained_keys = {
                re.sub(r"[\W_]+", " ", value.casefold()).strip() for value in bullets
            }
            seen_group_keys: set[str] = set()
            for value, source_ids in grouped:
                key = re.sub(r"[\W_]+", " ", value.casefold()).strip()
                if key in retained_keys and key not in seen_group_keys:
                    retained_groups.append((value, source_ids))
                    seen_group_keys.add(key)

            date_text = " ".join(
                str(block.get("text") or "").strip() for block in date_blocks
            )
            start_date, end_date, current_role = _date_parts(date_text)
            metrics = list(
                dict.fromkeys(
                    match.group(0)
                    for value in bullets
                    for match in _METRIC_RE.finditer(value)
                )
            )
            field_sources: dict[str, list[str]] = {
                "job_title": [str(title_block.get("id"))],
            }
            if company_block:
                field_sources["company"] = [str(company_block.get("id"))]
            if location:
                location_block = next(
                    block
                    for block in [*prior_header_blocks, *header_blocks]
                    if self._experience_location(block, title_left=title_left) == location
                )
                field_sources["location"] = [str(location_block.get("id"))]
            if date_blocks:
                date_ids = [str(block.get("id")) for block in date_blocks]
                field_sources["start_date"] = date_ids
                field_sources["end_date"] = date_ids
            for bullet_index, (_, source_ids) in enumerate(retained_groups):
                field_sources[f"responsibilities[{bullet_index}]"] = source_ids
            source_ids = [
                str(block.get("id"))
                for block in entry_blocks
                if str(block.get("id") or "")
            ]
            confidence = (
                0.94
                if company and (start_date or end_date)
                else 0.90
                if company and bullets
                else 0.82
                if bullets
                else 0.62
            )
            entries.append(
                {
                    "job_title": title,
                    "company": company,
                    "location": location,
                    "employment_type": (
                        employment_type
                        or ("Internship" if "intern" in title.casefold() else None)
                    ),
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": current_role,
                    "responsibilities": bullets,
                    "achievements": [],
                    "technologies": [],
                    "metrics": metrics,
                    "confidence": confidence,
                    "needs_review": not bool(bullets),
                    "source_block_ids": source_ids,
                    "field_source_block_ids": field_sources,
                }
            )

        return {
            "experiences": entries,
            "count": len(entries),
            "has_experience": True,
            "experience_quality": {
                "status": "degraded" if warnings else "ok",
                "score": max(45, 100 - len(set(warnings)) * 12),
                "warnings": list(dict.fromkeys(warnings)),
            },
            "mode": "layout_local_groups",
        }

    @classmethod
    def _project_title_candidate(
        cls,
        blocks: list[dict[str, Any]],
        index: int,
        *,
        technology_continuation: bool,
    ) -> bool:
        block = blocks[index]
        text = str(block.get("text") or "").strip()
        if (
            not text
            or cls._TECH_LABEL.match(text)
            or _BULLET_RE.match(text)
            or cls._ACTION_START.search(text)
            or len(text.split()) > 14
            or text.endswith((".", ",", ";", ":"))
            or _YEAR_RE.fullmatch(text)
            or technology_continuation
        ):
            return False
        if index + 1 >= len(blocks):
            return False
        previous = blocks[index - 1] if index else None
        following = blocks[index + 1]
        gap_before = (
            _top(block) - _bottom(previous)
            if previous is not None and cls._same_stream(previous, block)
            else 999.0
        )
        font_signal = str(block.get("font_weight") or "").casefold() == "bold"
        indent_signal = (
            abs(_left(block) - _left(following)) >= 10.0
            and cls._same_stream(block, following)
        )
        boundary_signal = index == 0 or gap_before >= 7.0 or font_signal or indent_signal
        if not boundary_signal:
            return False
        if is_known_technology(text) and not (
            index == 0 or gap_before >= 7.0 or font_signal or indent_signal
        ):
            return False
        following_text = str(following.get("text") or "").strip()
        return bool(
            _YEAR_RE.search(following_text)
            or cls._ACTION_START.search(following_text)
            or cls._PROJECT_ROLE_LINE.fullmatch(following_text)
            or cls._TECH_LABEL.match(following_text)
            or _left(following) < _left(block) - 8.0
            or cls._explicit_continuation(block, following)
        )

    @classmethod
    def _split_explicit_technologies(
        cls,
        blocks: list[dict[str, Any]],
    ) -> list[tuple[str, str, str | None, list[str]]]:
        if not blocks:
            return []
        text = " ".join(str(block.get("text") or "").strip() for block in blocks)
        text = cls._TECH_LABEL.sub("", text, count=1)
        values: list[tuple[str, str, str | None, list[str]]] = []
        source_ids = [str(block.get("id")) for block in blocks]
        for raw in re.split(r"[,،;|]|\s+\+\s+", text):
            cleaned = raw.strip()
            if (
                not cleaned
                or len(cleaned.split()) > 6
                or cls._ACTION_START.search(cleaned)
            ):
                continue
            term = canonical_technology(cleaned)
            if not term.display:
                continue
            values.append((term.display, term.key, term.category, source_ids))
        merged: dict[str, tuple[str, str, str | None, list[str]]] = {}
        for display, key, category, block_ids in values:
            if key not in merged:
                merged[key] = (display, key, category, list(block_ids))
            else:
                existing = merged[key]
                merged[key] = (
                    existing[0],
                    key,
                    existing[2] or category,
                    list(dict.fromkeys([*existing[3], *block_ids])),
                )
        return list(merged.values())

    def projects(self, fallback: dict[str, Any]) -> dict[str, Any]:
        blocks = [
            block
            for block in self._section_blocks("projects")
            if self._valid_semantic_block(block)
        ]
        if not blocks:
            return fallback

        title_indices: list[int] = []
        technology_continuation = False
        for index, block in enumerate(blocks):
            text = str(block.get("text") or "").strip()
            if technology_continuation and index:
                boundary_previous = blocks[index - 1]
                if (
                    not self._same_stream(boundary_previous, block)
                    or _top(block) - _bottom(boundary_previous) > 4.0
                ):
                    technology_continuation = False
            role_continuation = bool(
                title_indices
                and self._PROJECT_ROLE_LINE.fullmatch(text)
                and not any(
                    self._ACTION_START.search(str(item.get("text") or ""))
                    or self._TECH_LABEL.match(str(item.get("text") or ""))
                    for item in blocks[title_indices[-1] + 1 : index]
                )
            )
            candidate = (
                False
                if role_continuation
                else self._project_title_candidate(
                    blocks,
                    index,
                    technology_continuation=technology_continuation,
                )
            )
            if candidate:
                title_indices.append(index)
                technology_continuation = False
                continue
            if self._TECH_LABEL.match(text):
                technology_continuation = True
            elif technology_continuation:
                technology_continuation = True
        if not title_indices:
            return fallback

        projects: list[dict[str, Any]] = []
        for position, title_index in enumerate(title_indices):
            end_index = (
                title_indices[position + 1]
                if position + 1 < len(title_indices)
                else len(blocks)
            )
            entry_blocks = blocks[title_index:end_index]
            title_block = entry_blocks[0]
            title = str(title_block.get("text") or "").strip()
            role_block = next(
                (
                    block
                    for block in entry_blocks[1:3]
                    if self._PROJECT_ROLE_LINE.fullmatch(
                        str(block.get("text") or "").strip()
                    )
                ),
                None,
            )
            role = str((role_block or {}).get("text") or "").strip() or None
            date_blocks = [
                block
                for block in entry_blocks[1:]
                if _DATE_RANGE_RE.search(str(block.get("text") or ""))
                or _SEASON_YEAR_RE.search(str(block.get("text") or ""))
                or _YEAR_RE.fullmatch(str(block.get("text") or "").strip())
            ]
            description_blocks: list[dict[str, Any]] = []
            technology_blocks: list[dict[str, Any]] = []
            in_technologies = False
            previous: dict[str, Any] | None = None
            for block in entry_blocks[1:]:
                if block in date_blocks or block is role_block:
                    previous = block
                    continue
                text = str(block.get("text") or "").strip()
                if self._TECH_LABEL.match(text):
                    in_technologies = True
                    technology_blocks.append(block)
                elif (
                    in_technologies
                    and previous is not None
                    and self._same_stream(previous, block)
                    and _top(block) - _bottom(previous) <= 4.0
                ):
                    technology_blocks.append(block)
                else:
                    in_technologies = False
                    description_blocks.append(block)
                previous = block

            description_groups = self._body_groups(description_blocks)
            description = " ".join(value for value, _ in description_groups).strip()
            technologies = self._split_explicit_technologies(technology_blocks)
            date_text = " ".join(
                str(block.get("text") or "").strip() for block in date_blocks
            )
            start_date, end_date, current = _date_parts(date_text)
            source_ids = [
                str(block.get("id"))
                for block in entry_blocks
                if str(block.get("id") or "")
            ]
            field_sources: dict[str, list[str]] = {
                "name": [str(title_block.get("id"))],
            }
            if date_blocks:
                date_ids = [str(block.get("id")) for block in date_blocks]
                field_sources["start_date"] = date_ids
                field_sources["end_date"] = date_ids
            if role_block:
                field_sources["role"] = [str(role_block.get("id"))]
            description_source_ids = list(
                dict.fromkeys(
                    block_id
                    for _, block_ids in description_groups
                    for block_id in block_ids
                )
            )
            if description_source_ids:
                field_sources["description"] = description_source_ids
            for tech_index, (_, _, _, block_ids) in enumerate(technologies):
                field_sources[f"technologies[{tech_index}]"] = block_ids
            confidence = (
                0.92
                if description and (
                    str(title_block.get("font_weight") or "").casefold() == "bold"
                    or (
                        title_index > 0
                        and _top(title_block) - _bottom(blocks[title_index - 1]) >= 7.0
                    )
                )
                else 0.86
                if description
                else 0.58
            )
            projects.append(
                {
                    "name": title,
                    "role": role,
                    "start_date": start_date,
                    "end_date": end_date,
                    "current": current,
                    "description": description,
                    "technologies": [value[0] for value in technologies],
                    "url": None,
                    "confidence": confidence,
                    "needs_review": not bool(description),
                    "source_block_ids": source_ids,
                    "field_source_block_ids": field_sources,
                }
            )
        return {
            "projects": projects,
            "count": len(projects),
            "has_projects": True,
            "mode": "layout_boundary_groups",
        }

    @classmethod
    def _geographic_location(cls, value: str) -> str | None:
        text = str(value or "").strip()
        labelled = re.match(r"(?i)^(?:location|address)\s*:\s*(.+)$", text)
        if labelled:
            return labelled.group(1).strip() or None
        parts = [part.strip() for part in re.split(r"[,،]", text) if part.strip()]
        if len(parts) != 2:
            return None
        region = parts[1].casefold()
        if region in cls.COUNTRY_TERMS or re.fullmatch(r"[A-Z]{2,3}", parts[1]):
            return f"{parts[0]}, {parts[1]}"
        return None

    def education(self, fallback: dict[str, Any]) -> dict[str, Any]:
        blocks = [
            block
            for block in self._section_blocks("education")
            if self._valid_semantic_block(block)
        ]
        if not blocks:
            return fallback
        lines = [str(block.get("text") or "").strip() for block in blocks]
        date_index = next(
            (index for index, line in enumerate(lines) if _DATE_RANGE_RE.search(line)),
            None,
        )
        if date_index is None:
            return fallback
        date_text = lines[date_index]
        start_date, end_date, _ = _date_parts(date_text)
        primary = lines[0] if lines else ""
        institution = None
        degree = None
        field = None
        if " - " in primary:
            left, right = [value.strip() for value in primary.split(" - ", 1)]
            if re.search(r"(?i)\b(?:university|college|institute|school|academy)\b", left):
                institution = left
                primary = right
        degree_match = re.search(
            r"(?i)\b(bachelor|master|doctorate|ph\.?d\.?|diploma|associate|mba|bsc|msc)\b"
            r"(?:\s+of|\s+in)?\s*(.*)",
            primary,
        )
        if degree_match:
            degree = degree_match.group(1)
            field = degree_match.group(2).strip(" ,-|") or None
        elif primary:
            institution = institution or primary

        gpa = None
        location = None
        coursework: list[str] = []
        description_lines: list[str] = []
        for index, line in enumerate(lines):
            if index in {0, date_index}:
                continue
            gpa_match = re.match(r"(?i)^GPA\s*:\s*(.+)$", line)
            if gpa_match:
                gpa = gpa_match.group(1).strip()
                continue
            candidate_location = self._geographic_location(line)
            if candidate_location:
                location = candidate_location
                continue
            if "," in line or "،" in line:
                coursework.extend(
                    value.strip()
                    for value in re.split(r"[,،]", line)
                    if value.strip()
                )
            else:
                description_lines.append(line)
        item = {
            "degree": degree,
            "field": field,
            "specialization": None,
            "institution": institution,
            "location": location,
            "start_date": start_date,
            "end_date": end_date,
            "graduation_year": None,
            "gpa": gpa,
            "honors": [],
            "coursework": coursework,
            "description": " ".join(description_lines),
            "confidence": 0.93 if institution and (degree or field) else 0.72,
            "needs_review": not bool(institution),
            "source_block_ids": [str(block.get("id")) for block in blocks],
        }
        return {
            "education": [item],
            "count": 1,
            "has_education": True,
            "mode": "layout_directional_dates",
        }

    @staticmethod
    def _normalize_skill(value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        text = re.sub(r"(?i)^AIpowered\b", "AI-powered", text)
        return text

    def skills(self, fallback: dict[str, Any]) -> dict[str, Any]:
        blocks = [
            block
            for block in self._section_blocks("skills")
            if self._valid_semantic_block(block)
        ]
        if not blocks:
            return fallback
        candidates: list[dict[str, Any]] = []
        for block in blocks:
            value = self._normalize_skill(str(block.get("text") or ""))
            label = ""
            payload = value
            if ":" in value or "：" in value:
                label, payload = re.split(r"[:：]", value, maxsplit=1)
                label = label.strip()
            pieces = [
                item.strip()
                for item in re.split(r"[,،|;]", payload)
                if item.strip()
            ]
            if (
                not label
                and len(pieces) == 1
                and 2 <= len(payload.split()) <= 8
                and all(is_known_technology(token) for token in payload.split())
            ):
                pieces = payload.split()
            explicit_list = bool(label or len(pieces) > 1)
            label_term = canonical_technology(label) if label else None
            category_hint = (
                label_term.category
                if label_term and label_term.known
                else {
                    "programming and tools": "frameworks_tools",
                    "programming & tools": "frameworks_tools",
                    "databases and streaming": "data",
                    "databases & streaming": "data",
                    "data engineering": "data",
                }.get(label.casefold())
            )
            if label_term and label_term.known:
                pieces.insert(0, label)
            for piece in pieces:
                normalized = piece.casefold().strip()
                if (
                    not piece
                    or normalized in self.GENERIC_SKILLS
                    or re.search(r"(?i)(?:&|\band|\bor)\s*$", piece)
                    or len(piece.split()) > 7
                ):
                    continue
                term = canonical_technology(piece)
                if not term.known and (
                    not explicit_list
                    or category_hint is None
                    or len(piece.split()) > 4
                    or self._ACTION_START.search(piece)
                ):
                    continue
                display = term.display
                key = term.key
                category = term.category or category_hint
                if not display or category is None:
                    continue
                candidates.append(
                    {
                        "value": display,
                        "normalized": key,
                        "category": category,
                        "confidence": 0.96 if term.known else 0.86,
                        "source_block_ids": [str(block.get("id"))],
                        "field_source_block_ids": {
                            "value": [str(block.get("id"))],
                        },
                    }
                )
        merged: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            key = candidate["normalized"]
            if key not in merged:
                merged[key] = candidate
            else:
                merged[key]["source_block_ids"].extend(candidate["source_block_ids"])
                merged[key]["source_block_ids"] = list(
                    dict.fromkeys(merged[key]["source_block_ids"])
                )
                merged[key]["field_source_block_ids"]["value"] = list(
                    merged[key]["source_block_ids"]
                )
        if not merged:
            return fallback
        values = list(merged.values())
        return {
            "all_skills": values,
            "categorized_skills": {
                category: [item["value"] for item in values if item["category"] == category]
                for category in sorted({item["category"] for item in values})
            },
            "count": len(values),
            "mode": "dedicated_section_context",
        }

    def certifications(self, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocks = [
            block
            for block in self._section_blocks("certifications")
            if self._valid_semantic_block(block)
        ]
        if not blocks:
            return fallback
        groups: dict[str, list[str]] = {
            "certifications": [],
            "courses": [],
            "licenses": [],
            "interests": [],
            "unclassified": [],
        }
        section = self.sections.get("certifications") or {}
        heading = str(section.get("heading") or "")
        mixed_heading = bool(re.search(r"[/&]|\bfacts?\b|\bother\b", heading, re.I))
        certifications: list[dict[str, Any]] = []
        for block in blocks:
            text = _strip_bullet(str(block.get("text") or ""))
            lowered = text.casefold()
            if re.search(r"(?i)\bhobb(?:y|ies)\b|\binterests?\b", text):
                groups["interests"].append(text)
            elif "driving license" in lowered or "driver" in lowered:
                groups["licenses"].append(text)
            elif re.search(r"(?i)\b(?:course|training|workshop|bootcamp)\b", text):
                groups["courses"].append(text)
            elif re.search(r"(?i)\b(?:certificat(?:e|ion)|credential|accreditation)\b", text):
                groups["certifications"].append(text)
                date_match = _YEAR_RE.search(text)
                name = re.sub(r"\s*[-–—]\s*(?:19|20)\d{2}\s*$", "", text).strip()
                certifications.append(
                    {
                        "name": name,
                        "issuer": None,
                        "date": date_match.group(0) if date_match else None,
                        "credential_id": None,
                        "url": None,
                        "confidence": 0.72 if mixed_heading else 0.88,
                        "source_block_ids": [str(block.get("id"))],
                    }
                )
            else:
                groups["unclassified"].append(text)
        section["mixed_content"] = len([values for values in groups.values() if values]) > 1
        section["item_groups"] = groups
        section_warnings = section.setdefault("warnings", [])
        if section["mixed_content"] and "MIXED_SECTION_CONTENT" not in section_warnings:
            section_warnings.append("MIXED_SECTION_CONTENT")
        return certifications
