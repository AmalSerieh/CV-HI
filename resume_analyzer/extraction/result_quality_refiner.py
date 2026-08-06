from __future__ import annotations

import copy
import math
import re
from typing import Any

try:
    from .document_intelligence import apply_document_intelligence
except ImportError:
    from document_intelligence import apply_document_intelligence


SOFT_SKILL_ALIASES = {
    "proven leadership": "Leadership",
    "leadership": "Leadership",
    "team leadership": "Leadership",
    "communication": "Communication",
    "communications": "Communication",
    "effective communication": "Communication",
    "teamwork": "Teamwork",
    "effective teamwork": "Teamwork",
    "collaboration": "Collaboration",
    "team collaboration": "Collaboration",
    "professional presentation": "Presentation",
    "presentation skills": "Presentation",
    "presentations": "Presentation",
    "presentation": "Presentation",
    "effective networking": "Networking",
    "networking": "Networking",
    "customer service": "Customer Service",
    "conflict resolution": "Conflict Resolution",
    "problem solving": "Problem Solving",
    "creative problem solving": "Problem Solving",
    "negotiation": "Negotiation",
    "mentoring": "Mentoring",
    "coaching": "Coaching",
    "organizational skills": "Organizational Skills",
    "attention to detail": "Attention to Detail",
    "decision making": "Decision Making",
    "strategic thinking": "Strategic Thinking",
}

INVALID_SKILLS = {
    "provider", "kpi", "kpis", "other internal systems",
    "/problem", "problem",
}

# Conservative ontology separation. Only exact standalone values move.
DOMAIN_CONTEXT_ALIASES = {
    "healthcare": "Healthcare",
    "insurance": "Insurance",
    "retail": "Retail",
    "banking": "Banking",
    "manufacturing": "Manufacturing",
    "telecommunications": "Telecommunications",
    "hospitality": "Hospitality",
    "real estate": "Real Estate",
    "pharmaceutical": "Pharmaceuticals",
    "pharmaceuticals": "Pharmaceuticals",
    "nonprofit": "Nonprofit",
    "non profit": "Nonprofit",
    "government": "Government",
    "public sector": "Public Sector",
    "ecommerce": "E-commerce",
    "e commerce": "E-commerce",
}

GENERAL_SKILL_ALIASES = {
    "planning": "Planning",
    "management": "Management",
}

HARD_SKILL_ALIASES = {
    "successful business/sales management": "Business/Sales Management",
}

SECTOR_LABELS = {
    "marketing": ("marketing_sales", "Marketing / Sales"),
    "marketing_sales": ("marketing_sales", "Marketing / Sales"),
    "sales_marketing": ("marketing_sales", "Marketing / Sales"),
    "finance": ("finance_accounting", "Finance / Accounting"),
    "accounting": ("finance_accounting", "Finance / Accounting"),
    "finance_accounting": ("finance_accounting", "Finance / Accounting"),
    "software": ("software_engineering", "Software Engineering"),
    "software_engineering": ("software_engineering", "Software Engineering"),
    "data": ("data_ai", "Data / AI"),
    "data_ai": ("data_ai", "Data / AI"),
    "hr": ("human_resources", "Human Resources"),
    "human_resources": ("human_resources", "Human Resources"),
}


def _norm(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    ).casefold()


def _unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []

    for value in values:
        key = _norm(value)

        if not key or key in seen:
            continue

        seen.add(key)
        output.append(value)

    return output


def _slug(value: Any) -> str | None:
    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        _norm(value),
    ).strip("_")

    return text or None


def _canonical_hard_skill(value: Any) -> str:
    raw = str(value or "").strip()
    return HARD_SKILL_ALIASES.get(
        _norm(raw),
        raw,
    )


def _display_skill(value: Any) -> str:
    """Normalize capitalization for UI display only."""
    raw = str(value or "").strip()

    if not raw:
        return raw

    if raw == raw.casefold():
        return raw.title()

    return raw


def _role_family(job_title: str | None) -> str | None:
    title = _norm(job_title)

    if not title:
        return None

    if "marketing" in title and "purchas" in title:
        return "marketing_operations"

    if "marketing" in title:
        return "marketing"

    if any(
        token in title
        for token in (
            "sales",
            "account executive",
            "business development",
        )
    ):
        return "sales"

    if any(
        token in title
        for token in (
            "accountant",
            "accounting",
            "finance",
            "auditor",
        )
    ):
        return "finance_accounting"

    if any(
        token in title
        for token in (
            "software",
            "developer",
            "engineer",
        )
    ):
        return "software_engineering"

    return None


def _seniority(job_title: str | None) -> str | None:
    title = _norm(job_title)

    if not title:
        return None

    if any(
        token in title
        for token in (
            "chief",
            "vice president",
            "director",
            "head",
        )
    ):
        return "leadership"

    if any(
        token in title
        for token in (
            "senior",
            "lead",
            "manager",
            "executive",
        )
    ):
        return "senior"

    if "intern" in title or "trainee" in title:
        return "entry"

    if "assistant" in title:
        return "assistant"

    return "individual_contributor"


def _clean_uncategorized_recommendations(
    skills: dict,
    removed_keys: set[str],
) -> None:
    for item in skills.get("recommendations", []) or []:
        if not isinstance(item, dict):
            continue

        if item.get("type") != "uncategorized_skills":
            continue

        values = item.get("skills", []) or []

        item["skills"] = [
            value
            for value in values
            if _norm(value) not in removed_keys
        ]


def _skill_tokens(value: Any) -> set[str]:
    normalized = re.sub(
        r"[&/\-]+",
        " ",
        _norm(value),
    )
    return {
        token
        for token in normalized.split()
        if token not in {"and", "of", "the"}
    }


def _semantic_dedupe_skills(
    values: list[str],
) -> list[str]:
    unique = _unique(values)
    token_sets = [_skill_tokens(value) for value in unique]
    remove: set[int] = set()

    for index, _value in enumerate(unique):
        current = token_sets[index]
        if not current:
            continue

        for other_index, other in enumerate(unique):
            if index == other_index:
                continue

            broader = token_sets[other_index]
            if current and current < broader and (
                len(current) <= 2
                or any(char in str(other) for char in "&/")
            ):
                remove.add(index)
                break

    return [
        value
        for index, value in enumerate(unique)
        if index not in remove
    ]


def _clean_skill_value(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(" ,;/\\"),
    )


def _canonicalize_skills(skills: dict) -> dict:
    if not isinstance(skills, dict):
        return skills

    original_all = list(skills.get("all_skills", []) or [])
    original_hard = list(skills.get("hard_skills", []) or [])
    original_soft = list(skills.get("soft_skills", []) or [])
    original_domains = list(skills.get("domain_context", []) or [])
    previous_canonicalization = copy.deepcopy(
        skills.get("canonicalization", {}) or {}
    )
    previous_score_adjustments = copy.deepcopy(
        skills.get("score_adjustments", {}) or {}
    )

    def merge_records(*record_groups: list[dict]) -> list[dict]:
        merged: list[dict] = []
        seen: set[tuple] = set()
        for records in record_groups:
            for record in records or []:
                if not isinstance(record, dict):
                    continue
                key = tuple(
                    sorted(
                        (
                            str(name),
                            _norm(value),
                        )
                        for name, value in record.items()
                    )
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(copy.deepcopy(record))
        return merged

    soft_values: list[str] = []
    domain_values: list[str] = []
    general_values: list[str] = []
    hard_values: list[str] = []
    alias_records: list[dict[str, str]] = []
    domain_records: list[dict[str, str]] = []

    for raw_value in original_all + original_soft + original_hard:
        value = _clean_skill_value(raw_value)
        key = _norm(value)

        if not key or key in INVALID_SKILLS:
            continue

        if key in DOMAIN_CONTEXT_ALIASES:
            canonical_domain = DOMAIN_CONTEXT_ALIASES[key]
            domain_values.append(canonical_domain)
            domain_records.append({
                "raw": str(raw_value),
                "canonical": canonical_domain,
                "reason": "standalone_industry_context",
            })
            continue

        if key in SOFT_SKILL_ALIASES:
            canonical = SOFT_SKILL_ALIASES[key]
            soft_values.append(canonical)
            if _norm(canonical) != key:
                alias_records.append({
                    "raw": str(raw_value),
                    "canonical": canonical,
                })
            continue

        if key in GENERAL_SKILL_ALIASES:
            general_values.append(
                GENERAL_SKILL_ALIASES[key]
            )
            continue

        hard_values.append(_canonical_hard_skill(value))

    soft_values = _unique(soft_values)
    domain_values = _unique(
        [
            DOMAIN_CONTEXT_ALIASES.get(
                _norm(value),
                str(value),
            )
            for value in original_domains + domain_values
            if _norm(value)
        ]
    )
    hard_values = _semantic_dedupe_skills(hard_values)

    # Generic Planning/Management are omitted when a more specific
    # compound hard skill already contains them.
    hard_token_union = [_skill_tokens(value) for value in hard_values]
    general_values = [
        value
        for value in _unique(general_values)
        if not any(
            _skill_tokens(value) < tokens
            for tokens in hard_token_union
        )
    ]

    soft_keys = {_norm(value) for value in soft_values}
    hard_values = [
        value
        for value in hard_values
        if _norm(value) not in soft_keys
    ]

    hard_keys = {_norm(value) for value in hard_values}
    removed_keys = (
        set(SOFT_SKILL_ALIASES)
        | set(GENERAL_SKILL_ALIASES)
        | set(INVALID_SKILLS)
        | set(DOMAIN_CONTEXT_ALIASES)
        | soft_keys
    )

    categorized = copy.deepcopy(
        skills.get("categorized_skills", {}) or {}
    )
    clean_categorized: dict[str, list[str]] = {}

    for category, values in categorized.items():
        if not isinstance(values, list):
            continue
        filtered = []
        for raw_value in values:
            value = _clean_skill_value(raw_value)
            key = _norm(value)
            if key in removed_keys:
                continue
            canonical = _canonical_hard_skill(value)
            if _norm(canonical) in hard_keys:
                filtered.append(canonical)
        filtered = _unique(filtered)
        if filtered:
            clean_categorized[category] = filtered

    categorized = clean_categorized
    all_values = _unique(hard_values + soft_values + general_values)

    uncategorized = list(categorized.get("other", []) or [])
    categorized_count = sum(
        len(values)
        for category, values in categorized.items()
        if category != "other"
    )
    hard_count = len(hard_values)
    categorized_ratio = (
        round(categorized_count / hard_count, 4)
        if hard_count
        else 0.0
    )

    baseline_score = int(
        previous_score_adjustments.get(
            "original_score",
            skills.get("skills_score", 0),
        )
        or 0
    )
    generic_penalty = min(2, len(general_values))
    ratio_penalty = 0
    if hard_count and categorized_ratio < 0.70:
        ratio_penalty = min(
            3,
            math.ceil((0.70 - categorized_ratio) * 8),
        )

    adjusted_score = max(
        0,
        min(95, baseline_score - generic_penalty - ratio_penalty),
    )

    skills["all_skills"] = all_values
    skills["hard_skills"] = hard_values
    skills["soft_skills"] = soft_values
    skills["domain_context"] = domain_values
    skills["general_skills"] = general_values
    skills["categorized_skills"] = categorized
    skills["total_count"] = len(all_values)
    skills["hard_count"] = hard_count
    skills["soft_count"] = len(soft_values)
    skills["domain_count"] = len(domain_values)
    skills["general_count"] = len(general_values)
    skills["categorized_count"] = categorized_count
    skills["uncategorized_count"] = len(uncategorized)
    skills["categorized_ratio"] = categorized_ratio
    skills["skills_score"] = adjusted_score
    skills["skills_quality"] = {
        "status": "ok" if adjusted_score >= 65 else "degraded",
        "score": adjusted_score,
        "warnings": [],
    }
    current_invalid_removed = [
        value
        for value in original_all + original_hard
        if _norm(_clean_skill_value(value)) in INVALID_SKILLS
    ]
    skills["canonicalization"] = {
        "soft_skill_aliases_resolved": merge_records(
            list(
                previous_canonicalization.get(
                    "soft_skill_aliases_resolved",
                    [],
                )
                or []
            ),
            alias_records,
        ),
        "domain_context_reclassified": merge_records(
            list(
                previous_canonicalization.get(
                    "domain_context_reclassified",
                    [],
                )
                or []
            ),
            domain_records,
        ),
        "general_skills_excluded_from_hard_score": general_values,
        "duplicate_soft_skills_removed": max(
            int(
                previous_canonicalization.get(
                    "duplicate_soft_skills_removed",
                    0,
                )
                or 0
            ),
            max(0, len(original_soft) - len(soft_values)),
        ),
        "semantic_duplicates_removed": max(
            int(
                previous_canonicalization.get(
                    "semantic_duplicates_removed",
                    0,
                )
                or 0
            ),
            max(0, len(original_all) - len(all_values)),
        ),
        "invalid_skills_removed": _unique(
            list(
                previous_canonicalization.get(
                    "invalid_skills_removed",
                    [],
                )
                or []
            )
            + current_invalid_removed
        ),
    }
    skills["score_adjustments"] = {
        "original_score": baseline_score,
        "generic_skill_penalty": generic_penalty,
        "uncategorized_ratio_penalty": ratio_penalty,
        "final_score": adjusted_score,
    }

    for item in skills.get("recommendations", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "quantity":
            total = int(skills.get("total_count", 0) or 0)
            if total < 8:
                item["severity"] = "medium"
                item["message"] = (
                    f"{total} skills were detected. "
                    "Add more role-specific technical "
                    "skills only when they are factual "
                    "and supported by the resume."
                )
            elif total < 12:
                item["severity"] = "low"
                item["message"] = (
                    f"{total} skills were detected. "
                    "The skills section has reasonable "
                    "coverage."
                )
            else:
                item["severity"] = "good"
                item["message"] = (
                    f"{total} skills were detected with "
                    "strong breadth."
                )

    _clean_uncategorized_recommendations(skills, removed_keys)

    sector_key = str(skills.get("detected_sector") or "")
    canonical_sector, sector_label = SECTOR_LABELS.get(
        sector_key,
        (sector_key or None, sector_key or None),
    )
    if canonical_sector:
        skills["sector"] = canonical_sector
        skills["sector_label"] = sector_label
        match = skills.get("sector_match")
        if isinstance(match, dict):
            match["sector_key"] = canonical_sector
            match["sector"] = sector_label

    return skills


def _is_source_explicit_undated_role(item: dict) -> bool:
    return bool(
        item.get("undated_prior_role")
        or item.get("date_status") == "not_provided_in_source"
        or item.get("responsibilities_scope") == "prior_roles_shared"
        or str(item.get("employer_group_id") or "").startswith(
            "undated_prior_group_"
        )
    )


def _shared_experience_groups(
    experience: dict,
) -> list[dict]:
    entries = list(experience.get("experiences", []) or [])
    grouped: dict[tuple[str, str], dict] = {}
    previous_fingerprint_ids: dict[str, str] = {}

    def unique_strings(values: list[Any]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = re.sub(r"\s+", " ", str(value or "").strip())
            key = _norm(clean)
            if clean and key not in seen:
                seen.add(key)
                output.append(clean)
        return output

    for role_index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            continue
        legacy_scope = str(item.get("responsibilities_scope") or "")
        public_scope = str(item.get("responsibility_scope") or "")
        employer_shared = (
            legacy_scope == "employer_group_shared"
            or public_scope == "employer_group"
        )
        previous_shared = (
            legacy_scope == "prior_roles_shared"
            or public_scope == "previous_roles_group"
        )
        if not (employer_shared or previous_shared):
            continue

        responsibilities = unique_strings(
            list(item.get("responsibilities", []) or [])
        )
        metrics = unique_strings(
            list(item.get("metrics", []) or [])
        )

        if employer_shared:
            scope = "employer_group"
            group_type = "employer"
            group_id = str(
                item.get("shared_responsibility_group_id")
                or item.get("employer_group_id")
                or (
                    "employer_group_"
                    + re.sub(
                        r"[^a-z0-9]+",
                        "_",
                        _norm(item.get("company") or "unknown"),
                    ).strip("_")
                )
            )
        else:
            scope = "previous_roles_group"
            group_type = "previous_roles"
            fingerprint = "|".join(
                _norm(value) for value in responsibilities
            ) or "no_shared_narrative"
            group_id = str(
                item.get("shared_responsibility_group_id")
                or previous_fingerprint_ids.setdefault(
                    fingerprint,
                    "previous_roles_group_"
                    f"{len(previous_fingerprint_ids) + 1}",
                )
            )

        item["shared_role_responsibilities"] = True
        item["responsibility_scope"] = scope
        item["shared_responsibility_group_id"] = group_id
        item["responsibility_attribution"] = "shared_not_role_specific"
        item["metrics_attribution"] = (
            "shared_group" if metrics else "none_provided"
        )
        item.setdefault("role_specific_responsibilities", [])
        item.setdefault("role_specific_metrics", [])

        key = (group_type, group_id)
        group = grouped.setdefault(
            key,
            {
                "group_id": group_id,
                "group_type": group_type,
                "company": (
                    item.get("company")
                    if group_type == "employer"
                    else None
                ),
                "companies": [],
                "role_indexes": [],
                "role_titles": [],
                "shared_role_responsibilities": True,
                "responsibility_scope": scope,
                "responsibilities": [],
                "metrics": [],
                "source_evidence": [],
            },
        )
        group["role_indexes"].append(role_index)
        group["role_titles"].append(item.get("job_title"))
        group["companies"].append(item.get("company"))
        group["responsibilities"].extend(responsibilities)
        group["metrics"].extend(metrics)
        for source_key in ("source_company_line", "source_role_line"):
            group["source_evidence"].append(item.get(source_key))

    groups: list[dict] = []
    for group in grouped.values():
        for key in (
            "companies", "role_titles", "responsibilities",
            "metrics", "source_evidence",
        ):
            group[key] = unique_strings(group[key])
        group["role_count"] = len(group["role_indexes"])
        groups.append(group)
    groups.sort(
        key=lambda value: min(
            value.get("role_indexes")
            or [10**9]
        )
    )
    groups = _trim_cross_group_boundary_leakage(
        groups
    )
    groups = _reconcile_group_metrics(
        groups,
        entries,
        list(
            experience.get(
                "document_metrics",
                [],
            )
            or []
        ),
    )
    return groups


def _trim_cross_group_boundary_leakage(
    groups: list[dict],
) -> list[dict]:
    """
    Reconcile only an immediately adjacent employer -> previous-roles
    boundary. Role-level source payloads remain unchanged.
    """
    ordered = list(groups or [])

    for index in range(len(ordered) - 1):
        current = ordered[index]
        following = ordered[index + 1]

        if (
            current.get("group_type") != "employer"
            or following.get("group_type")
            != "previous_roles"
        ):
            continue

        current_indexes = list(
            current.get("role_indexes", [])
            or []
        )
        following_indexes = list(
            following.get("role_indexes", [])
            or []
        )

        if (
            not current_indexes
            or not following_indexes
            or min(following_indexes)
            != max(current_indexes) + 1
        ):
            continue

        next_values = {
            _norm(value)
            for value in (
                following.get("responsibilities", [])
                or []
            )
            if value
        }
        responsibilities = list(
            current.get("responsibilities", [])
            or []
        )
        removed: list[str] = []

        while (
            responsibilities
            and _norm(
                responsibilities[-1]
            ) in next_values
        ):
            removed.insert(
                0,
                responsibilities.pop(),
            )

        if not removed:
            continue

        current["responsibilities"] = responsibilities
        current[
            "excluded_cross_group_responsibilities"
        ] = [
            {
                "value": value,
                "reason":
                    "trailing_duplicate_after_group_boundary",
                "target_group_id":
                    following.get("group_id"),
            }
            for value in removed
        ]
        current["boundary_status"] = "reconciled"

    return ordered


def _metric_evidence_texts(
    metric: dict,
) -> list[str]:
    evidence = metric.get("evidence", [])
    values: list[str] = []

    if isinstance(evidence, str):
        values.append(evidence)
    elif isinstance(evidence, dict):
        values.append(
            str(
                evidence.get("text")
                or evidence.get("evidence")
                or ""
            )
        )
    elif isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, str):
                values.append(item)
            elif isinstance(item, dict):
                values.append(
                    str(
                        item.get("text")
                        or item.get("evidence")
                        or ""
                    )
                )

    return [
        value
        for value in values
        if str(value or "").strip()
    ]


def _metric_belongs_to_group(
    metric: dict,
    corpus: str,
) -> bool:
    normalized_corpus = _norm(corpus)

    if not normalized_corpus:
        return False

    for evidence_text in _metric_evidence_texts(
        metric
    ):
        normalized_evidence = _norm(
            evidence_text
        )

        if (
            normalized_evidence
            and normalized_evidence
            in normalized_corpus
        ):
            return True

    return False


def _metric_match_key(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9%$€£]+",
        " ",
        str(value or "").casefold(),
    ).strip()


def _metric_number_prefix(
    value: str,
) -> str | None:
    match = re.search(
        r"(?<!\w)\d[\d,]*(?:\.\d+)?",
        str(value or ""),
    )
    return (
        match.group(0).replace(",", "")
        if match
        else None
    )


def _reconcile_group_metrics(
    groups: list[dict],
    entries: list[dict],
    document_metrics: list[dict],
) -> list[dict]:
    """
    Build complete group-level metrics from two evidence sources:

    1. legacy entry metrics, retained for backward compatibility;
    2. document-level reconciled metrics whose evidence line occurs inside
       the group's source text.

    This allows a shortened legacy value such as "10 product" to be
    replaced by the evidence-backed "10 product representatives".
    """
    normalized_document_metrics = [
        metric
        for metric in (
            document_metrics or []
        )
        if isinstance(metric, dict)
        and str(metric.get("value") or "").strip()
    ]

    for group in groups or []:
        role_indexes = list(
            group.get("role_indexes", [])
            or []
        )
        group_entries = [
            entries[index - 1]
            for index in role_indexes
            if (
                isinstance(index, int)
                and 1 <= index <= len(entries)
                and isinstance(
                    entries[index - 1],
                    dict,
                )
            )
        ]

        corpus_parts: list[str] = []

        for item in group_entries:
            corpus_parts.append(
                str(item.get("raw_text") or "")
            )
            corpus_parts.extend(
                str(value or "")
                for value in (
                    item.get("responsibilities", [])
                    or []
                )
            )

        corpus = "\n".join(corpus_parts)
        matching_document_metrics = [
            metric
            for metric in normalized_document_metrics
            if _metric_belongs_to_group(
                metric,
                corpus,
            )
        ]

        matching_values = [
            str(metric.get("value") or "").strip()
            for metric in matching_document_metrics
        ]
        legacy_values = [
            str(value or "").strip()
            for value in (
                group.get("metrics", [])
                or []
            )
            if str(value or "").strip()
        ]

        reconciled_values: list[str] = []

        for legacy in legacy_values:
            legacy_norm = _norm(legacy)
            legacy_key = _metric_match_key(
                legacy
            )
            exact = next(
                (
                    value
                    for value in matching_values
                    if (
                        _norm(value) == legacy_norm
                        or _metric_match_key(
                            value
                        ) == legacy_key
                    )
                ),
                None,
            )

            if exact:
                candidate = exact
            else:
                legacy_number = (
                    _metric_number_prefix(legacy)
                )
                expansions = [
                    value
                    for value in matching_values
                    if (
                        legacy_number
                        and _metric_number_prefix(
                            value
                        ) == legacy_number
                        and (
                            _metric_match_key(
                                value
                            ).startswith(
                                legacy_key + " "
                            )
                            or legacy_key.startswith(
                                _metric_match_key(
                                    value
                                ) + " "
                            )
                        )
                    )
                ]
                candidate = (
                    max(expansions, key=len)
                    if expansions
                    else legacy
                )

            if _norm(candidate) not in {
                _norm(value)
                for value in reconciled_values
            }:
                reconciled_values.append(
                    candidate
                )

        for value in matching_values:
            if _norm(value) not in {
                _norm(item)
                for item in reconciled_values
            }:
                reconciled_values.append(value)

        group["legacy_entry_metrics"] = (
            legacy_values
        )
        group["metrics"] = reconciled_values
        group["metric_evidence"] = (
            copy.deepcopy(
                matching_document_metrics
            )
        )
        group["metrics_source"] = (
            "entry_metrics_plus_document_evidence"
            if matching_document_metrics
            else "entry_metrics"
        )

    return groups


def _filter_shared_metrics_recommendations(
    recommendations: list[dict],
    experience_groups: list[dict],
) -> list[dict]:
    shared_indexes = {
        index
        for group in experience_groups
        for index in group.get("role_indexes", []) or []
    }
    output: list[dict] = []

    for recommendation in recommendations or []:
        if not isinstance(recommendation, dict):
            continue
        if recommendation.get("type") != "metrics_partial":
            output.append(recommendation)
            continue

        message = str(recommendation.get("message") or "")
        match = re.search(r"\[([^\]]*)\]", message)
        if not match:
            output.append(recommendation)
            continue
        indexes = [
            int(value)
            for value in re.findall(r"\d+", match.group(1))
        ]
        remaining = [
            index for index in indexes
            if index not in shared_indexes
        ]
        if not remaining:
            continue
        item = copy.deepcopy(recommendation)
        item["message"] = (
            "Add quantified results only to role-specific entries "
            "that do not already contain them, and only when you have "
            f"factual numbers: {remaining}."
        )
        output.append(item)

    if experience_groups and not any(
        item.get("type") == "shared_source_responsibilities"
        for item in output
    ):
        output.append({
            "severity": "info",
            "type": "shared_source_responsibilities",
            "message": (
                "The source resume uses shared responsibilities for "
                "multiple roles; they are represented at group level and "
                "are not attributed to one role without evidence."
            ),
            "group_ids": [
                group.get("group_id")
                for group in experience_groups
            ],
        })
    return output


def _refine_experience(
    experience: dict,
    contact: dict,
) -> dict:
    if not isinstance(experience, dict):
        return experience

    contact_location = str(contact.get("location") or "").strip()
    contact_match = re.match(
        r"^(.+?),\s*([A-Za-z]{2})$",
        contact_location,
    )
    contact_city = _norm(contact_match.group(1)) if contact_match else ""
    contact_region = contact_match.group(2).upper() if contact_match else ""

    qualities: list[dict] = []

    for index, item in enumerate(
        experience.get("experiences", []) or [],
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        quality = copy.deepcopy(item.get("field_quality", {}) or {})
        warnings = list(quality.get("warnings", []) or [])
        informational = list(
            quality.get("informational_warnings", []) or []
        )
        score = int(quality.get("score", 0) or 0)

        if item.get("date_status") == "placeholder_unresolved":
            warnings = [
                warning
                for warning in warnings
                if not re.search(
                    r"(?:start_date|end_date|duration)_unresolved$",
                    str(warning),
                )
            ]
            item["source_completeness_status"] = "template_placeholder_dates"
            item["quality_status"] = "source_placeholder"
            score = max(score, 88)
            informational = _unique(
                informational
                + [f"experience_{index}_date_placeholder_unresolved"]
            )

        elif _is_source_explicit_undated_role(item):
            removable_suffixes = (
                "_start_date_unresolved",
                "_end_date_unresolved",
                "_duration_unresolved",
                "_location_unresolved",
            )
            warnings = [
                warning
                for warning in warnings
                if not warning.endswith(removable_suffixes)
            ]
            item["undated_prior_role"] = True
            item["date_status"] = "not_provided_in_source"
            item["location_status"] = (
                "provided"
                if item.get("location")
                else "not_provided_in_source"
            )
            item["source_completeness_status"] = "partial_source"
            item["quality_status"] = "partial_source"
            score = max(score, 84)
            info_prefix = f"experience_{index}"
            informational = _unique(
                informational
                + [f"{info_prefix}_dates_not_provided_in_source"]
                + (
                    [f"{info_prefix}_location_not_provided_in_source"]
                    if not item.get("location")
                    else []
                )
            )

        raw_location = str(item.get("location") or "").strip()
        if not raw_location:
            source = str(item.get("source_company_line") or "")
            source_match = re.search(
                r",\s*([^,]+?,\s*[A-Za-z])\s*$",
                source,
            )
            if source_match:
                raw_location = source_match.group(1).strip()

        incomplete = re.match(r"^(.+?),\s*([A-Za-z])$", raw_location)
        if incomplete:
            city = incomplete.group(1).strip()
            region_character = incomplete.group(2).upper()
            item["raw_location"] = raw_location
            item["location_quality"] = "incomplete_region_code"
            warning = (
                f"experience_{index}_location_incomplete_region_code"
            )
            if warning not in warnings:
                warnings.append(warning)
            score = min(score or 100, 86)
            if (
                contact_city
                and _norm(city) == contact_city
                and region_character in contact_region
            ):
                item["normalized_location_candidate"] = contact_location
                item["location_normalization_confidence"] = 0.70
                item["location_normalization_method"] = (
                    "same_city_contact_region_completion"
                )

        quality["warnings"] = _unique(warnings)
        quality["informational_warnings"] = _unique(informational)
        quality["score"] = score
        quality["status"] = "degraded" if warnings else "ok"
        quality["quality_status"] = (
            "source_placeholder"
            if item.get("date_status") == "placeholder_unresolved" and not warnings
            else "partial_source"
            if _is_source_explicit_undated_role(item) and not warnings
            else "complete_source"
            if not warnings
            else "unresolved"
        )
        item["field_quality"] = quality
        qualities.append(quality)

    if qualities:
        old_score = int(experience.get("experience_score", 0) or 0)
        average_entry_score = round(
            sum(int(q.get("score", 0) or 0) for q in qualities)
            / len(qualities)
        )
        adjusted_score = max(
            0,
            min(
                92,
                round(old_score * 0.40 + average_entry_score * 0.60),
            ),
        )
        warnings = _unique([
            warning
            for quality in qualities
            for warning in quality.get("warnings", []) or []
        ])
        informational = _unique([
            warning
            for quality in qualities
            for warning in quality.get("informational_warnings", []) or []
        ])
        experience["experience_score"] = adjusted_score
        experience["experience_quality"] = {
            **(experience.get("experience_quality", {}) or {}),
            "status": "degraded" if warnings else "ok",
            "score": adjusted_score,
            "warnings": warnings,
            "informational_warnings": informational,
            "entry_quality": qualities,
        }

    # Remove stale missing-date recommendations when the source either:
    # - explicitly lists an undated historical role, or
    # - contains a template date placeholder.
    undated_indexes = {
        index
        for index, item in enumerate(
            experience.get("experiences", []) or [],
            start=1,
        )
        if isinstance(item, dict)
        and _is_source_explicit_undated_role(item)
    }
    placeholder_date_indexes = {
        index
        for index, item in enumerate(
            experience.get("experiences", []) or [],
            start=1,
        )
        if (
            isinstance(item, dict)
            and item.get("date_status")
            == "placeholder_unresolved"
        )
    }
    recommendations = []
    for rec in experience.get("recommendations", []) or []:
        message = str(rec.get("message", ""))
        match = re.search(r"Experience #([0-9]+)", message)
        if (
            rec.get("type") == "incomplete_experience"
            and match
            and int(match.group(1))
            in (
                undated_indexes
                | placeholder_date_indexes
            )
        ):
            continue
        recommendations.append(rec)
    experience_groups = _shared_experience_groups(
        experience
    )
    experience["experience_groups"] = experience_groups
    experience["shared_responsibility_group_count"] = len(
        experience_groups
    )
    experience["recommendations"] = (
        _filter_shared_metrics_recommendations(
            recommendations,
            experience_groups,
        )
    )

    activities = list(
        experience.get("undated_volunteer_activities", []) or []
    )
    experience["undated_volunteer_activity_count"] = len(activities)
    experience["volunteer_date_status"] = (
        "not_provided"
        if activities and not experience.get("volunteer_experience_months")
        else "provided_or_not_applicable"
    )
    return experience


def _refine_education(
    education: dict,
) -> dict:
    if not isinstance(education, dict):
        return education

    entries = list(education.get("education", []) or [])
    if not entries:
        return education

    entry_scores: list[int] = []
    informational_warnings: list[str] = []

    for index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            continue

        core_complete = bool(
            item.get("degree")
            and item.get("institution")
            and item.get("field")
        )
        has_date = bool(
            item.get("graduation_year")
            or item.get("end_date")
        )

        breakdown = {
            "degree": 30 if item.get("degree") else 0,
            "institution": 30 if item.get("institution") else 0,
            "field": 20 if item.get("field") else 0,
            "core_completeness_bonus": 8 if core_complete else 0,
            "graduation_date_bonus": 7 if has_date else 0,
            "location_bonus": 3 if item.get("location") else 0,
            "accreditation_bonus": 4 if item.get("accreditation") else 0,
            "gpa_bonus": 2 if item.get("gpa") else 0,
            "honors_bonus": 2 if item.get("honors") else 0,
        }
        score = min(100, sum(breakdown.values()))
        item["education_completeness_score"] = score
        item["education_score_breakdown"] = breakdown

        field_quality = copy.deepcopy(item.get("field_quality", {}) or {})
        warnings = [
            warning
            for warning in field_quality.get("warnings", []) or []
            if warning != "missing_graduation_date"
        ]
        info = list(
            field_quality.get("informational_warnings", []) or []
        )
        placeholder_date = (
            item.get("graduation_date_status") == "placeholder_unresolved"
            or bool(item.get("raw_date_text") and re.search(
                r"(?i)(?:19|20)?[xy]{2,4}|yyyy|month\s+year",
                str(item.get("raw_date_text")),
            ))
        )
        if placeholder_date:
            item["graduation_date_status"] = "placeholder_unresolved"
            info = [
                warning for warning in info
                if warning != "graduation_date_not_provided_in_source"
            ]
            info.append("graduation_date_placeholder_unresolved")
            informational_warnings.append(
                f"education_entry_{index}:graduation_date_placeholder_unresolved"
            )
        elif not has_date:
            item["graduation_date_status"] = "not_provided_in_source"
            info.append("graduation_date_not_provided_in_source")
            informational_warnings.append(
                f"education_entry_{index}:graduation_date_not_provided_in_source"
            )
        else:
            item["graduation_date_status"] = "provided"

        field_quality["warnings"] = _unique(warnings)
        field_quality["informational_warnings"] = _unique(info)
        field_quality["score"] = score
        field_quality["status"] = "degraded" if warnings else "ok"
        item["field_quality"] = field_quality
        entry_scores.append(score)

    if entry_scores:
        score = round(sum(entry_scores) / len(entry_scores))
        education["education_score"] = score
        education["education_quality"] = {
            **(education.get("education_quality", {}) or {}),
            "status": "ok" if score >= 80 else "degraded",
            "score": score,
            "warnings": [],
            "informational_warnings": _unique(informational_warnings),
            "entry_count": len(entries),
        }
        education["score_policy"] = {
            "core_fields": ["degree", "institution", "field"],
            "optional_bonus_fields": [
                "graduation_date", "location", "accreditation",
                "gpa", "honors",
            ],
            "graduation_date_absence_penalized": False,
            "gpa_or_honors_absence_penalized": False,
        }

    placeholder_entries = [
        item
        for item in entries
        if (
            isinstance(item, dict)
            and item.get("graduation_date_status")
            == "placeholder_unresolved"
        )
    ]
    placeholder_raw_date = (
        str(
            placeholder_entries[0].get(
                "raw_date_text"
            )
            or ""
        ).strip()
        if placeholder_entries
        else ""
    )

    recommendations = []
    for rec in education.get("recommendations", []) or []:
        message = str(rec.get("message", ""))
        is_stale_date_message = (
            (
                rec.get("type")
                in {
                    "incomplete_entry",
                    "source_optional_missing",
                }
            )
            and (
                "graduation year/date" in message
                or "graduation date was not provided"
                in message.casefold()
            )
            and "institution" not in message
            and "degree" not in message
        )

        if (
            placeholder_entries
            and is_stale_date_message
        ):
            recommendations.append({
                "severity": "high",
                "type":
                    "placeholder_graduation_date",
                "message": (
                    "Replace the graduation date "
                    f'placeholder "{placeholder_raw_date}" '
                    "with the actual graduation date."
                ),
            })
            continue

        if is_stale_date_message:
            recommendations.append({
                "severity": "low",
                "type": "source_optional_missing",
                "message": (
                    "Graduation date was not provided "
                    "in the source resume."
                ),
            })
            continue

        recommendations.append(rec)

    # Stable recommendation deduplication.
    deduplicated_recommendations = []
    seen_recommendations = set()

    for rec in recommendations:
        key = (
            str(rec.get("type") or ""),
            str(rec.get("message") or ""),
        )
        if key in seen_recommendations:
            continue
        seen_recommendations.add(key)
        deduplicated_recommendations.append(rec)

    education["recommendations"] = (
        deduplicated_recommendations
    )
    return education


def _update_summary(
    result: dict,
) -> None:
    summary = result.setdefault(
        "summary",
        {},
    )

    contact = (
        result.get("contact", {})
        or {}
    )
    for field in ("name", "email", "phone", "location", "job_title"):
        if contact.get(field) is not None:
            summary[field] = contact.get(field)

    skills = (
        result.get("skills", {})
        or {}
    )

    experience = (
        result.get("experience", {})
        or {}
    )

    technologies = list(
        skills.get(
            "top_technologies",
            [],
        )
        or []
    )

    technology_keys = {
        _norm(value)
        for value in technologies
    }

    hard_skills = [
        value
        for value in (
            skills.get("hard_skills", [])
            or []
        )
        if _norm(value)
        not in technology_keys
    ]

    soft_skills = list(
        skills.get("soft_skills", [])
        or []
    )

    summary["top_skills"] = _unique([
        _display_skill(value)
        for value in (
            hard_skills
            + soft_skills
        )
    ])[:20]

    summary["top_technologies"] = _unique(
        technologies
    )[:20]

    activities = list(
        experience.get(
            "undated_volunteer_activities",
            [],
        )
        or []
    )

    summary[
        "undated_volunteer_activity_count"
    ] = len(activities)

    summary[
        "volunteer_activity_count"
    ] = len(activities)

    summary["volunteer_date_status"] = (
        experience.get(
            "volunteer_date_status"
        )
    )

    summary["volunteer_activities"] = (
        activities
    )

    job_title = summary.get("job_title")

    skills["role_family"] = (
        skills.get("role_family")
        or _role_family(job_title)
    )

    skills["current_role"] = (
        skills.get("current_role")
        or _slug(job_title)
    )

    skills["seniority"] = (
        skills.get("seniority")
        or _seniority(job_title)
    )

    summary["experience_count"] = int(experience.get("count", 0) or 0)
    summary["professional_role_count"] = int(experience.get("professional_role_count", 0) or 0)
    summary["volunteer_role_count"] = int(experience.get("volunteer_role_count", 0) or 0)
    summary["professional_experience_months"] = int(experience.get("professional_experience_months", 0) or 0)
    summary["volunteer_experience_months"] = int(experience.get("volunteer_experience_months", 0) or 0)
    summary["total_validated_experience_months"] = int(experience.get("total_validated_experience_months", 0) or 0)
    summary["professional_duration_status"] = experience.get("professional_duration_status")
    education = result.get("education", {}) or {}
    summary["education_count"] = int(education.get("count", 0) or 0)
    summary["highest_degree"] = education.get("highest_degree")
    languages = result.get("languages", {}) or {}
    summary["languages_count"] = int(languages.get("count", 0) or 0)


def _sync_final_recommendations(
    result: dict,
) -> None:
    skills = result.get("skills", {}) or {}
    sector_label = (
        skills.get("sector_label")
        or skills.get("detected_sector")
    )
    total_count = int(skills.get("total_count", 0) or 0)

    experiences = list(
        (result.get("experience", {}) or {}).get(
            "experiences",
            [],
        )
        or []
    )
    undated_indexes = {
        index
        for index, item in enumerate(
            experiences,
            start=1,
        )
        if isinstance(item, dict)
        and _is_source_explicit_undated_role(item)
    }
    placeholder_date_indexes = {
        index
        for index, item in enumerate(
            experiences,
            start=1,
        )
        if (
            isinstance(item, dict)
            and item.get("date_status")
            == "placeholder_unresolved"
        )
    }

    education_entries = list(
        (result.get("education", {}) or {}).get(
            "education",
            [],
        )
        or []
    )
    placeholder_education_entries = [
        item
        for item in education_entries
        if (
            isinstance(item, dict)
            and item.get("graduation_date_status")
            == "placeholder_unresolved"
        )
    ]
    placeholder_graduation_text = (
        str(
            placeholder_education_entries[0].get(
                "raw_date_text"
            )
            or ""
        ).strip()
        if placeholder_education_entries
        else ""
    )

    for key in ("recommendations",):
        recommendations = result.get(key, [])
        if not isinstance(recommendations, list):
            continue
        filtered = []
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message", ""))
            match = re.search(r"Experience #([0-9]+)", message)
            if (
                item.get("type")
                == "incomplete_experience"
                and match
                and int(match.group(1))
                in (
                    undated_indexes
                    | placeholder_date_indexes
                )
            ):
                continue

            date_message = (
                "graduation year/date"
                in message
                or "graduation date was not provided"
                in message.casefold()
            )
            education_date_recommendation = (
                item.get("area") == "education"
                and item.get("type")
                in {
                    "incomplete_entry",
                    "source_optional_missing",
                }
                and date_message
                and "institution" not in message
                and "degree" not in message
            )

            if (
                education_date_recommendation
                and placeholder_education_entries
            ):
                filtered.append({
                    "severity": "high",
                    "type":
                        "placeholder_graduation_date",
                    "area": "education",
                    "message": (
                        "Replace the graduation date "
                        f'placeholder "'
                        f'{placeholder_graduation_text}" '
                        "with the actual graduation date."
                    ),
                })
                continue

            if education_date_recommendation:
                filtered.append({
                    "severity": "low",
                    "type": "source_optional_missing",
                    "area": "education",
                    "message": (
                        "Graduation date was not "
                        "provided in the source resume."
                    ),
                })
                continue

            filtered.append(item)
        filtered = (
            _filter_shared_metrics_recommendations(
                filtered,
                list(
                    (
                        result.get(
                            "experience",
                            {},
                        )
                        or {}
                    ).get(
                        "experience_groups",
                        [],
                    )
                    or []
                ),
            )
        )

        # Top-level recommendations can be assembled before semantic
        # refinement. Reconcile them with the authoritative module result.
        module_education_recommendations = list(
            (
                result.get(
                    "education",
                    {},
                )
                or {}
            ).get(
                "recommendations",
                [],
            )
            or []
        )
        if placeholder_education_entries:
            filtered = [
                item
                for item in filtered
                if not (
                    item.get("area")
                    == "education"
                    and (
                        "graduation date"
                        in str(
                            item.get("message")
                            or ""
                        ).casefold()
                    )
                )
            ]
            for item in module_education_recommendations:
                if (
                    item.get("type")
                    == "placeholder_graduation_date"
                ):
                    replacement = dict(item)
                    replacement["area"] = "education"
                    filtered.append(replacement)

        deduplicated = []
        seen = set()
        for item in filtered:
            rec_key = (
                str(item.get("area") or ""),
                str(item.get("type") or ""),
                str(item.get("message") or ""),
            )
            if rec_key in seen:
                continue
            seen.add(rec_key)
            deduplicated.append(item)

        result[key] = deduplicated

    recommendation_groups = [
        skills.get("recommendations", []),
        result.get("recommendations", []),
    ]
    for recommendations in recommendation_groups:
        if not isinstance(recommendations, list):
            continue
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "sector_detected" and sector_label:
                item["message"] = (
                    f"تم اكتشاف قطاع {sector_label} "
                    "مع أدلة مهارية واضحة."
                )
            if item_type == "quantity":
                if total_count < 8:
                    item["severity"] = "medium"
                    item["message"] = (
                        f"{total_count} skills were detected. "
                        "Add more role-specific technical "
                        "skills only when they are factual "
                        "and supported by the resume."
                    )
                elif total_count < 12:
                    item["severity"] = "low"
                    item["message"] = (
                        f"{total_count} skills were detected. "
                        "The skills section has reasonable "
                        "coverage."
                    )
                else:
                    item["severity"] = "good"
                    item["message"] = (
                        f"{total_count} skills were detected "
                        "with strong breadth."
                    )


def _update_scores(
    result: dict,
) -> None:
    scores = result.setdefault("scores", {})
    module_scores = scores.setdefault("module_scores", {})

    contact_quality = (
        (result.get("contact", {}) or {}).get("quality", {})
        or {}
    )
    if "score" in contact_quality:
        module_scores["contact"] = int(contact_quality.get("score", 0) or 0)

    for module_name, score_field in (
        ("skills", "skills_score"),
        ("education", "education_score"),
        ("experience", "experience_score"),
        ("languages", "language_score"),
    ):
        module = result.get(module_name, {}) or {}
        if score_field in module:
            module_scores[module_name] = int(
                module.get(score_field, 0) or 0
            )

    quality = result.get("extraction_quality")
    if isinstance(quality, dict):
        components = quality.setdefault("component_scores", {})
        applicability = scores.get("module_applicability", {}) or {}
        for module_name in ("skills", "education", "experience", "languages"):
            if (
                module_name in module_scores
                and (module_name != "languages" or applicability.get("languages", False))
            ):
                components[module_name] = module_scores[module_name]
            elif module_name == "languages":
                components.pop("languages", None)

        experience_quality = (
            (result.get("experience", {}) or {}).get(
                "experience_quality",
                {},
            )
            or {}
        )
        experience_warnings = list(
            experience_quality.get("warnings", []) or []
        )
        education_quality = (
            (result.get("education", {}) or {}).get(
                "education_quality",
                {},
            )
            or {}
        )

        experience_items = list(
            (
                result.get(
                    "experience",
                    {},
                )
                or {}
            ).get(
                "experiences",
                [],
            )
            or []
        )
        undated_indexes = {
            index
            for index, item in enumerate(
                experience_items,
                start=1,
            )
            if isinstance(item, dict)
            and _is_source_explicit_undated_role(item)
        }
        placeholder_date_indexes = {
            index
            for index, item in enumerate(
                experience_items,
                start=1,
            )
            if (
                isinstance(item, dict)
                and item.get("date_status")
                == "placeholder_unresolved"
            )
        }

        def resolved_stale_warning(warning: str) -> bool:
            if warning == "experience_critical_field_unresolved":
                return experience_quality.get("status") == "ok"
            if warning == "experience_extraction_degraded":
                return experience_quality.get("status") == "ok"
            if warning.startswith("low_confidence_experiences:"):
                return experience_quality.get("status") == "ok"
            if warning == "education_extraction_degraded":
                return education_quality.get("status") == "ok"
            if re.match(
                r"education_entry_\d+:missing_graduation_date$",
                warning,
            ):
                return education_quality.get("status") == "ok"

            match = re.match(
                r"experience_(\d+)_(?:start_date|end_date|duration|location)_unresolved$",
                warning,
            )
            return bool(
                match
                and int(match.group(1))
                in (
                    undated_indexes
                    | placeholder_date_indexes
                )
            )

        existing_quality_warnings = list(
            quality.get("warnings", []) or []
        )
        resolved_quality_warnings = [
            warning
            for warning in existing_quality_warnings
            if resolved_stale_warning(str(warning))
        ]
        quality_warnings = [
            warning
            for warning in existing_quality_warnings
            if not resolved_stale_warning(str(warning))
        ]
        quality["warnings"] = _unique(
            quality_warnings + experience_warnings
        )
        quality["resolved_warnings"] = _unique(
            list(quality.get("resolved_warnings", []) or [])
            + resolved_quality_warnings
        )

        critical = list(quality.get("critical_warnings", []) or [])
        if experience_quality.get("status") == "ok":
            resolved = [
                warning
                for warning in critical
                if warning == "experience_critical_field_unresolved"
            ]
            critical = [
                warning
                for warning in critical
                if warning != "experience_critical_field_unresolved"
            ]
            quality["resolved_warnings"] = _unique(
                list(quality.get("resolved_warnings", []) or [])
                + resolved
            )
        quality["critical_warnings"] = critical

        if components:
            quality_values = [
                int(value or 0)
                for name, value in components.items()
                if not (
                    name == "contact"
                    and str(contact_quality.get("status") or "")
                    == "source_placeholder"
                )
            ]
            quality["score"] = round(
                sum(quality_values) / len(quality_values)
            ) if quality_values else 0
        quality["status"] = (
            "needs_review"
            if critical or int(quality.get("score", 0) or 0) < 60
            else "degraded"
            if int(quality.get("score", 0) or 0) < 85
            else "ok"
        )

    active_weights = scores.get("active_weights", {}) or {}
    applicability = scores.get("module_applicability", {}) or {}
    total_weight = 0.0
    weighted_score = 0.0

    for module_name, weight in active_weights.items():
        if applicability and not applicability.get(module_name, True):
            continue
        if module_name not in module_scores:
            continue
        total_weight += float(weight)
        weighted_score += float(module_scores[module_name]) * float(weight)

    if not total_weight:
        return

    raw_score = round(weighted_score / total_weight)
    quality_score = int((quality or {}).get("score", 0) or 0)
    quality_status = str((quality or {}).get("status", "needs_review"))
    critical_warnings = list(
        (quality or {}).get("critical_warnings", []) or []
    )

    source_readiness = result.get("source_readiness", {}) or {}
    source_status = str(source_readiness.get("status") or "ready")

    if source_status != "ready":
        score_status = "source_incomplete"
        trusted = False
        score_cap = int(source_readiness.get("score_cap", 60) or 60)
    elif critical_warnings or quality_status == "needs_review":
        score_status = "needs_review"
        trusted = False
        score_cap = min(55, quality_score or 55)
    elif quality_status == "degraded":
        score_status = "degraded"
        trusted = False
        score_cap = min(75, quality_score)
    else:
        score_status = "ok"
        trusted = True
        score_cap = 100

    displayed_score = min(raw_score, score_cap)

    scores["status"] = score_status
    scores["trusted"] = trusted
    scores["score_cap"] = score_cap
    scores["raw_resume_completeness_score"] = raw_score
    scores["resume_completeness_score"] = displayed_score
    scores["raw_overall_score"] = raw_score
    scores["overall_score"] = displayed_score

    summary = result.setdefault("summary", {})
    summary["resume_completeness_score"] = displayed_score
    summary["overall_score"] = displayed_score


def refine_resume_result(
    result: dict,
    *,
    copy_result: bool = False,
) -> dict:
    """
    Apply semantic quality refinements to the final result.

    Call this after extractors/evidence reconciliation and before:
    - finalize_and_validate(...)
    - JSON export
    - print_report(...)
    """
    if not isinstance(result, dict):
        return result

    output = (
        copy.deepcopy(result)
        if copy_result
        else result
    )

    output = apply_document_intelligence(output)

    contact = (
        output.get("contact", {})
        or {}
    )

    output["skills"] = (
        _canonicalize_skills(
            output.get("skills", {})
            or {}
        )
    )

    output["experience"] = (
        _refine_experience(
            output.get("experience", {})
            or {},
            contact,
        )
    )

    output["education"] = (
        _refine_education(
            output.get("education", {})
            or {}
        )
    )

    _update_summary(output)
    _sync_final_recommendations(output)
    _update_scores(output)

    output[
        "semantic_quality_refinement"
    ] = {
        "version": "1.5.3",
        "applied": True,
        "areas": [
            "experience",
            "experience_groups",
            "volunteer",
            "skills",
            "domain_context",
            "summary",
            "sector",
            "education",
            "scores",
            "document_profile",
            "document_style",
            "placeholder_dates",
            "aligned_metadata_rows",
            "source_readiness",
            "docx_ooxml_structure",
            "duplicate_content",
            "document_assets",
            "candidate_photo_policy",
            "ats_structure",
            "pairwise_language_proficiency",
        ],
    }

    return output
