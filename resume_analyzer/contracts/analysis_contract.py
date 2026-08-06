from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.1.0"


_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _norm(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    ).casefold()


def _analysis_date(result: dict) -> str:
    value = str(result.get("analyzed_at", "") or "").strip()

    if value:
        return value[:10]

    return date.today().isoformat()


def _words_to_int(value: str) -> int | None:
    normalized = re.sub(
        r"[^a-z0-9\s-]",
        " ",
        str(value or "").casefold(),
    )

    digit_match = re.search(r"\b\d+\b", normalized)
    if digit_match:
        return int(digit_match.group(0))

    words = [word for word in re.split(r"[\s-]+", normalized) if word]

    total = 0
    found = False

    for word in words:
        if word not in _NUMBER_WORDS:
            continue

        total += _NUMBER_WORDS[word]
        found = True

    return total if found else None


def _metric_numeric_value(value: str) -> int | float | None:
    raw = str(value or "").strip()
    number_match = re.search(
        r"(?:[$€£]\s*)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)" r"\s*([KMB]|thousand|million|billion)?",
        raw,
        re.IGNORECASE,
    )
    if not number_match:
        return _words_to_int(raw)

    number = float(number_match.group(1).replace(",", ""))
    suffix = str(number_match.group(2) or "").casefold()
    multiplier = {
        "k": 1_000,
        "thousand": 1_000,
        "m": 1_000_000,
        "million": 1_000_000,
        "b": 1_000_000_000,
        "billion": 1_000_000_000,
    }.get(suffix, 1)
    normalized = number * multiplier
    return int(normalized) if normalized.is_integer() else normalized


def _recover_metric_value(
    value: str,
    evidence: str,
) -> str:
    if "$" in value and not re.search(
        r"(?:[KMB]|thousand|million|billion)\b",
        value,
        re.IGNORECASE,
    ):
        match = re.search(
            r"[$€£]\s*\d+(?:\.\d+)?\s*" r"(?:[KMB]|thousand|million|billion)\b",
            str(evidence or ""),
            re.IGNORECASE,
        )
        if match:
            recovered = re.sub(r"\s+", "", match.group(0))
            if recovered[-1:].casefold() in {"k", "m", "b"}:
                recovered = recovered[:-1] + recovered[-1].upper()
            return recovered
    return value


def _metric_type(value: str) -> str:
    normalized = _norm(value)

    if re.search(
        r"\b\d+(?:\.\d+)?[- ](?:month|year|week|day)s?\b",
        normalized,
    ) and any(
        token in normalized
        for token in (
            "program",
            "project",
            "engagement",
            "contract",
            "placement",
            "term",
        )
    ):
        return "duration"

    if re.search(r"\btop\s+\d+(?:\.\d+)?%", normalized):
        return "ranking"

    if "location" in normalized:
        return "location_count"

    if "vendor" in normalized:
        return "vendor_count"

    if "employee" in normalized or "team member" in normalized:
        return "people_count"

    if "%" in str(value):
        return "percentage"

    if "$" in str(value):
        return "currency"

    return "quantity"


def _metric_key(value: str) -> tuple[str, int | float | None]:
    return (
        _metric_type(value),
        _metric_numeric_value(value),
    )


def _canonicalize_metrics(result: dict) -> None:
    reconciliation = result.setdefault(
        "evidence_reconciliation",
        {},
    )
    raw_metrics = list(reconciliation.get("document_metrics", []) or [])

    grouped: dict[tuple[str, int | float | None], dict] = {}

    for item in raw_metrics:
        if not isinstance(item, dict):
            continue

        value = str(item.get("value", "") or "").strip()
        if not value:
            continue

        evidence_text = str(item.get("evidence", "") or "")
        value = _recover_metric_value(value, evidence_text)

        if item.get("type") == "quantity" and re.match(r"^(?:19|20)\d{2}\b", value):
            continue

        key = _metric_key(value)
        normalized_value = key[1]
        metric_type = key[0]

        entry = grouped.setdefault(
            key,
            {
                "value": value,
                "normalized_value": normalized_value,
                "metric_type": metric_type,
                "approximate": bool(
                    re.search(
                        r"\b(?:approximately|about|around|nearly)\b",
                        value,
                        flags=re.IGNORECASE,
                    )
                ),
                "evidence": [],
            },
        )

        evidence_item = {
            "section": item.get("section"),
            "text": item.get("evidence"),
            "source_type": item.get("type"),
        }

        if evidence_item not in entry["evidence"]:
            entry["evidence"].append(evidence_item)

    canonical = list(grouped.values())

    reconciliation["raw_document_metrics"] = raw_metrics
    reconciliation["document_metrics"] = canonical
    reconciliation["canonical_metric_count"] = len(canonical)
    reconciliation["raw_metric_evidence_count"] = len(raw_metrics)

    experience = result.get("experience")
    if isinstance(experience, dict):
        experience["document_metrics"] = canonical


def _annotate_shared_experience(
    result: dict,
    duration_as_of: str,
) -> None:
    experience = result.setdefault("experience", {})
    entries = experience.get("experiences", []) or []

    groups: dict[str, list[dict]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        group_id = str(entry.get("employer_group_id", "") or "").strip()

        if group_id:
            groups.setdefault(group_id, []).append(entry)

        if entry.get("current") is True:
            entry["duration_as_of"] = duration_as_of

            for period in entry.get("periods", []) or []:
                if isinstance(period, dict) and _norm(period.get("end_date")) == "present":
                    period["duration_as_of"] = duration_as_of

    for group_id, group_entries in groups.items():
        shared_entries = [
            entry
            for entry in group_entries
            if entry.get("responsibilities_scope") == "employer_group_shared"
        ]

        if len(shared_entries) < 2:
            continue

        responsibility_sets = {
            tuple(
                _norm(item)
                for item in entry.get(
                    "responsibilities",
                    [],
                )
                or []
            )
            for entry in shared_entries
        }
        identical = len(responsibility_sets) == 1

        for entry in shared_entries:
            entry["shared_description_group_id"] = group_id
            entry["responsibility_assignment"] = "shared_across_roles"
            entry["assignment_confidence"] = 0.75 if identical else 0.65

    experience["duration_as_of"] = duration_as_of


def _normalize_volunteer_summary(result: dict) -> None:
    experience = result.setdefault("experience", {})
    activities = list(
        experience.get(
            "undated_volunteer_activities",
            [],
        )
        or []
    )

    experience["undated_volunteer_activity_count"] = len(activities)
    experience["volunteer_date_status"] = (
        "not_provided"
        if activities
        and not experience.get(
            "volunteer_experience_months",
            0,
        )
        else "dated_or_not_present"
    )

    summary = result.setdefault("summary", {})
    summary["undated_volunteer_activity_count"] = len(activities)
    summary["volunteer_date_status"] = experience["volunteer_date_status"]
    summary["volunteer_activities"] = activities


def _normalize_languages(result: dict) -> None:
    sections = result.get("sections", {}).get("sections", {})
    language_section = sections.get("languages", {})
    language_content = ""

    if isinstance(language_section, dict):
        language_content = str(language_section.get("content", "") or "")
    elif language_section:
        language_content = str(language_section)

    languages = result.setdefault("languages", {})
    count = int(languages.get("count", 0) or 0)

    if not language_content.strip() and count == 0:
        languages["status"] = "optional_not_present"
        languages["applicable"] = False
        languages["recommendations"] = []
    else:
        languages["status"] = "present" if count > 0 else "present_but_unparsed"
        languages["applicable"] = True


def _boost_location_confidence(result: dict) -> None:
    """
    Raise confidence only when a real first-page contact cluster exists.

    Placeholder/template documents can intentionally have:
        contact["location"] is None
        contact["evidence"]["location"] is None

    Those are valid states and must never crash contract finalization.
    """
    contact = result.setdefault("contact", {})
    if not isinstance(contact, dict):
        contact = {}
        result["contact"] = contact

    confidence = contact.get("confidence")
    if not isinstance(confidence, dict):
        confidence = {}
        contact["confidence"] = confidence

    current = float(confidence.get("location", 0) or 0)
    location = str(contact.get("location", "") or "").strip()

    if not location:
        return

    evidence_root = contact.get("evidence")
    if not isinstance(evidence_root, dict):
        return

    evidence = evidence_root.get("location")
    if not isinstance(evidence, dict):
        return

    text = str(evidence.get("text", "") or "")
    page = evidence.get("page")
    block_id = str(evidence.get("block_id", "") or "")

    has_contact_cluster = (
        bool(location)
        and _norm(location) in _norm(text)
        and bool(
            re.search(
                r"\b\d{5}(?:-\d{4})?\b",
                text,
            )
        )
        and (
            "@" in text
            or bool(
                re.search(
                    r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
                    text,
                )
            )
        )
        and (page == 1 or block_id.startswith("p1_"))
    )

    if not has_contact_cluster or current >= 0.70:
        return

    new_confidence = 0.90
    confidence["location"] = new_confidence

    contact.setdefault(
        "confidence_adjustments",
        [],
    ).append(
        {
            "field": "location",
            "original_confidence": current,
            "adjusted_confidence": new_confidence,
            "method": "top_contact_cluster_with_postal_and_contact_evidence",
            "evidence": {
                "page": page,
                "block_id": block_id,
                "text": text,
            },
        }
    )

    candidates = contact.get("candidates", {}).get("locations", [])

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        if _norm(candidate.get("value")) != _norm(location):
            continue

        candidate["score"] = max(
            int(candidate.get("score", 0) or 0),
            90,
        )
        reasons = list(candidate.get("reasons", []) or [])

        for reason in (
            "top_contact_cluster",
            "postal_code_context",
            "adjacent_to_email_or_phone",
        ):
            if reason not in reasons:
                reasons.append(reason)

        candidate["reasons"] = reasons


def _attach_skill_score_metadata(result: dict) -> None:
    skills = result.setdefault("skills", {})
    categorized = (
        skills.get(
            "categorized_skills",
            {},
        )
        or {}
    )

    hard_count = int(skills.get("hard_count", 0) or 0)
    soft_count = int(skills.get("soft_count", 0) or 0)
    total_count = int(skills.get("total_count", 0) or 0)

    uncategorized_count = len(categorized.get("other", []) or [])
    categorized_count = sum(
        len(values)
        for key, values in categorized.items()
        if key != "other" and isinstance(values, list)
    )

    quantity_score = min(
        30,
        round(total_count / 15 * 30),
    )
    hard_score = min(
        25,
        round(hard_count / 10 * 25),
    )
    soft_score = min(
        15,
        round(soft_count / 4 * 15),
    )
    categorization_score = min(
        20,
        round(categorized_count / 8 * 20),
    )

    sector_evidence = list(skills.get("sector_evidence", []) or [])
    sector_score = min(
        10,
        round(len(sector_evidence) / 4 * 10),
    )

    raw_total = quantity_score + hard_score + soft_score + categorization_score + sector_score

    skills["categorized_count"] = categorized_count
    skills["uncategorized_count"] = uncategorized_count
    skills["categorized_ratio"] = (
        round(
            categorized_count / hard_count,
            4,
        )
        if hard_count
        else 0.0
    )
    skills["score_breakdown"] = {
        "quantity": quantity_score,
        "hard_skill_presence": hard_score,
        "soft_skill_evidence": soft_score,
        "categorization": categorization_score,
        "sector_evidence": sector_score,
        "raw_total": raw_total,
        "score_cap": 95,
    }


def _build_analysis_layers(result: dict) -> None:
    skills = result.get("skills", {})
    experience = result.get("experience", {})
    metrics = result.get("evidence_reconciliation", {}).get("document_metrics", [])

    years = float(
        experience.get(
            "professional_experience_years",
            0,
        )
        or 0
    )

    if years >= 10:
        seniority = "senior"
        seniority_confidence = 0.85
    elif years >= 5:
        seniority = "mid"
        seniority_confidence = 0.78
    elif years >= 2:
        seniority = "early_career"
        seniority_confidence = 0.72
    else:
        seniority = "entry"
        seniority_confidence = 0.68

    sector = skills.get("detected_sector")
    sector_evidence = list(skills.get("sector_evidence", []) or [])

    recommendations = [
        item for item in result.get("recommendations", []) or [] if isinstance(item, dict)
    ]

    gaps = [
        {
            "type": item.get("type"),
            "area": item.get("area"),
            "severity": item.get("severity"),
            "message": item.get("message"),
            "evidence": item.get("evidence", []),
        }
        for item in recommendations
        if item.get("severity") in {"high", "medium"}
    ]

    strengths = [
        {
            "type": item.get("type"),
            "area": item.get("area"),
            "message": item.get("message"),
            "evidence": item.get("evidence", []),
        }
        for item in recommendations
        if item.get("severity") == "good"
    ]

    for metric in metrics:
        strengths.append(
            {
                "type": "document_metric",
                "area": "experience",
                "message": metric.get("value"),
                "evidence": metric.get("evidence", []),
            }
        )

    result["analysis"] = {
        "facts": {
            "source_document": deepcopy(result.get("file", {})),
            "text": deepcopy(
                result.get(
                    "extracted_resume_text",
                    {},
                )
            ),
            "layout": deepcopy(result.get("layout_data", {})),
            "contact": deepcopy(result.get("contact", {})),
            "sections": deepcopy(result.get("sections", {})),
            "experience": deepcopy(experience),
            "education": deepcopy(result.get("education", {})),
            "skills": {
                "all_skills": deepcopy(skills.get("all_skills", [])),
                "hard_skills": deepcopy(skills.get("hard_skills", [])),
                "soft_skills": deepcopy(skills.get("soft_skills", [])),
                "categorized_skills": deepcopy(
                    skills.get(
                        "categorized_skills",
                        {},
                    )
                ),
                "top_technologies": deepcopy(
                    skills.get(
                        "top_technologies",
                        [],
                    )
                ),
            },
            "projects": deepcopy(result.get("projects", {})),
            "languages": deepcopy(result.get("languages", {})),
            "metrics": deepcopy(metrics),
        },
        "inferences": {
            "candidate_profile": {
                "sector": {
                    "value": sector,
                    "confidence": (
                        0.95
                        if sector
                        and skills.get(
                            "model_usage",
                            {},
                        )
                        .get(
                            "rules",
                            {},
                        )
                        .get("regex_sector_detected")
                        else 0.70 if sector else 0.0
                    ),
                    "method": ("rules_regex" if sector else "not_detected"),
                    "evidence": sector_evidence,
                },
                "seniority": {
                    "value": seniority,
                    "confidence": seniority_confidence,
                    "method": "professional_experience_duration_v1",
                    "evidence": {
                        "professional_experience_years": years,
                    },
                },
                "role_family": {
                    "value": sector,
                    "confidence": 0.75 if sector else 0.0,
                    "method": "sector_role_family_v1",
                    "evidence": sector_evidence,
                },
            },
            "semantic_skills": deepcopy(
                skills.get(
                    "model_usage",
                    {},
                )
                .get(
                    "sbert",
                    {},
                )
                .get(
                    "classified_items",
                    [],
                )
            ),
            "strengths": strengths,
            "gaps": gaps,
            "model_usage": {
                "skills": deepcopy(skills.get("model_usage", {})),
                "experience": {
                    "mode": experience.get("mode"),
                    "extractor_mode": experience.get("extractor_mode"),
                    "spacy_available": experience.get("spacy_available"),
                    "sbert_available": experience.get("sbert_available"),
                },
            },
        },
        "generated_insights": {
            "status": "not_generated",
            "provider": None,
            "model": None,
            "personalized_summary": None,
            "recommendations": [],
        },
    }


def finalize_analysis_result(
    value: dict,
    *,
    keep_legacy_top_level: bool = True,
) -> dict:
    """
    Build the stable v1.1 contract while preserving the full source text.

    The current top-level module outputs remain available for compatibility.
    `analysis` becomes the canonical layered API for future UI/LLM work.
    """
    if not isinstance(value, dict):
        raise TypeError("analysis result must be a dict")

    result = deepcopy(value)
    result["schema_version"] = SCHEMA_VERSION
    result["contract_version"] = SCHEMA_VERSION

    duration_as_of = _analysis_date(result)

    _canonicalize_metrics(result)
    _annotate_shared_experience(
        result,
        duration_as_of,
    )
    _normalize_volunteer_summary(result)
    _normalize_languages(result)
    _boost_location_confidence(result)
    _attach_skill_score_metadata(result)
    _build_analysis_layers(result)

    extraction_quality = deepcopy(result.get("extraction_quality", {}))
    result["quality"] = {
        "status": extraction_quality.get(
            "status",
            "unknown",
        ),
        "score": extraction_quality.get("score", 0),
        "component_scores": extraction_quality.get(
            "component_scores",
            {},
        ),
        "warnings": extraction_quality.get(
            "warnings",
            [],
        ),
        "resolved_warnings": extraction_quality.get(
            "resolved_warnings",
            [],
        ),
        "critical_warnings": extraction_quality.get(
            "critical_warnings",
            [],
        ),
    }

    result["compatibility"] = {
        "legacy_top_level_modules_preserved": bool(keep_legacy_top_level),
        "canonical_analysis_path": "analysis",
        "full_text_preserved": bool(result.get("extracted_resume_text")),
    }

    return result


def validate_analysis_result(
    result: dict,
    schema_path: str | Path,
) -> dict:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return {
            "valid": False,
            "status": "validator_dependency_missing",
            "errors": [
                {
                    "path": "",
                    "message": ("Install jsonschema to enable contract validation."),
                }
            ],
        }

    schema = json.loads(
        Path(schema_path).read_text(
            encoding="utf-8",
        )
    )
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(result),
        key=lambda item: list(item.absolute_path),
    )

    return {
        "valid": not errors,
        "status": "valid" if not errors else "invalid",
        "schema_version": result.get("schema_version"),
        "errors": [
            {
                "path": ".".join(str(part) for part in error.absolute_path),
                "message": error.message,
            }
            for error in errors
        ],
    }


def finalize_and_validate(
    value: dict,
    schema_path: str | Path,
) -> dict:
    result = finalize_analysis_result(value)
    result["contract_validation"] = validate_analysis_result(
        result,
        schema_path,
    )
    return result
