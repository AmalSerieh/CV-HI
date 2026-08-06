from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any


def _norm(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").casefold(),
    ).strip()


def _position_distance(a: dict, b: dict) -> float | None:
    ax, ay = a.get("x_pt"), a.get("y_pt")
    bx, by = b.get("x_pt"), b.get("y_pt")
    if not all(isinstance(value, (int, float)) for value in (ax, ay, bx, by)):
        return None
    return math.hypot(float(ax) - float(bx), float(ay) - float(by))


def _broad_mirror_factor(blocks: list[dict]) -> int:
    counts = Counter(
        _norm(item.get("text"))
        for item in blocks
        if _norm(item.get("text"))
    )
    duplicated_groups = [
        count for count in counts.values()
        if count >= 2
    ]
    if len(duplicated_groups) < 6:
        return 1

    raw_count = len(blocks)
    unique_count = len(counts)
    ratio = (
        (raw_count - unique_count) / raw_count
        if raw_count
        else 0.0
    )
    if ratio < 0.30:
        return 1

    pair_divisible = sum(count % 2 == 0 for count in duplicated_groups)
    if pair_divisible / len(duplicated_groups) >= 0.75:
        return 2
    return 1


def _is_structural_heading(text: str) -> bool:
    clean = re.sub(r"[^A-Za-z ]+", " ", str(text or "")).strip()
    words = clean.split()
    return bool(
        clean
        and len(words) <= 5
        and (
            clean.isupper()
            or _norm(clean) in {
                "summary", "objective", "profile", "skills",
                "education", "experience", "work experience",
                "languages", "hobbies", "interests", "projects",
                "certifications", "awards", "contact",
            }
        )
    )


def _is_template_slot(text: str) -> bool:
    key = _norm(text)
    signal_count = sum(
        phrase in key
        for phrase in {
            "job title", "company name", "key responsibility",
            "key achievement", "location", "current",
        }
    )
    return signal_count >= 3



def _compact(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").casefold(),
    )


def _is_aggregate_alternate_representation(
    block: dict,
    peer_blocks: list[dict],
) -> bool:
    """
    Detect one giant concatenated accessibility/alternate representation.

    Some visual DOCX templates contain both positioned text boxes and a
    flattened hidden representation of the whole page.  The flattened block
    has no useful coordinates and repeats many already-extracted blocks.  It
    must remain in raw_text for auditability, but must not enter ordered_text
    or semantic extractors.
    """
    text = str(block.get("text") or "").strip()
    if not text or block.get("bbox") is not None:
        return False

    peer_lengths = sorted(
        len(str(item.get("text") or "").strip())
        for item in peer_blocks
        if item is not block
        and str(item.get("text") or "").strip()
        and len(str(item.get("text") or "").strip()) <= 400
    )
    median_length = (
        peer_lengths[len(peer_lengths) // 2]
        if peer_lengths
        else 0
    )
    if len(text) < 700 or (
        median_length
        and len(text) < median_length * 10
    ):
        return False

    compact_text = _compact(text)
    if len(compact_text) < 500:
        return False

    covered_values: set[str] = set()
    for item in peer_blocks:
        if item is block:
            continue
        candidate = _compact(item.get("text"))
        if (
            5 <= len(candidate) <= 180
            and candidate in compact_text
        ):
            covered_values.add(candidate)

    heading_hits = sum(
        compact_text.count(token)
        for token in (
            "skills",
            "education",
            "experience",
            "languages",
            "objective",
            "hobbies",
        )
    )
    template_hits = sum(
        compact_text.count(token)
        for token in (
            "jobtitle",
            "companyname",
            "keyresponsibility",
        )
    )

    return bool(
        len(covered_values) >= 8
        and heading_hits >= 6
        and template_hits >= 3
    )


def _collapse_exact_repeated_text(
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Collapse an exact repeated half inside one OOXML text block.

    Word templates sometimes store one paragraph twice inside the same text
    box.  Raw text remains available in the source extraction, while the
    cleaned block carries one logical copy.
    """
    text = re.sub(
        r"\s+",
        " ",
        str(item.get("text") or ""),
    ).strip()

    if len(text) < 100:
        return item

    words = text.split()
    if len(words) < 16 or len(words) % 2:
        return item

    midpoint = len(words) // 2
    first = " ".join(words[:midpoint]).strip()
    second = " ".join(words[midpoint:]).strip()

    if _norm(first) != _norm(second):
        return item

    updated = dict(item)
    updated["raw_text_before_inner_dedup"] = text
    updated["text"] = first
    updated["inner_duplicate_factor"] = 2
    return updated


def _section_name_from_heading(
    value: Any,
) -> str | None:
    key = _norm(value)
    mapping = {
        "summary": "summary",
        "objective": "summary",
        "profile": "summary",
        "skills": "skills",
        "technical skills": "skills",
        "education": "education",
        "experience": "experience",
        "work experience": "experience",
        "languages": "languages",
        "hobbies": "interests",
        "interests": "interests",
        "projects": "projects",
        "certifications": "certifications",
        "awards": "awards",
    }
    return mapping.get(key)


def _collapse_repeated_section_sequences(
    blocks: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Collapse exact consecutive sequence mirrors inside non-experience sections.

    Experience placeholders are intentionally excluded because several equal
    placeholder cards can represent several real logical slots.
    """
    output: list[dict[str, Any]] = []
    index = 0

    while index < len(blocks):
        current = blocks[index]
        section = _section_name_from_heading(
            current.get("text")
        )

        if not section:
            output.append(current)
            index += 1
            continue

        output.append(current)
        segment_start = index + 1
        segment_end = segment_start
        while segment_end < len(blocks):
            if _section_name_from_heading(
                blocks[segment_end].get("text")
            ):
                break
            segment_end += 1

        segment = blocks[
            segment_start:segment_end
        ]

        if (
            section != "experience"
            and len(segment) >= 2
            and len(segment) % 2 == 0
        ):
            midpoint = len(segment) // 2
            first_keys = [
                _norm(item.get("text"))
                for item in segment[:midpoint]
            ]
            second_keys = [
                _norm(item.get("text"))
                for item in segment[midpoint:]
            ]
            if first_keys == second_keys:
                output.extend(segment[:midpoint])
                for item, original in zip(
                    segment[midpoint:],
                    segment[:midpoint],
                    strict=False,
                ):
                    removed = dict(item)
                    removed[
                        "excluded_from_ordered_text"
                    ] = True
                    removed["exclusion_reason"] = (
                        "repeated_section_sequence"
                    )
                    removed["duplicate_of"] = (
                        original.get("id")
                    )
                    excluded.append(removed)
                index = segment_end
                continue

        output.extend(segment)
        index = segment_end

    return output

def deduplicate_blocks(
    blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Remove technical extraction duplicates while preserving logical repeats.

    Rules:
    - Same content at the same/near visual position is one technical block.
    - Same XML identity is one technical block.
    - A broad two-representation mirror is collapsed by factor two.
      Six identical template-role blocks therefore become three logical slots.
    - Genuine repeats at different positions remain unless a document-wide
      mirror factor is strongly supported.
    """
    raw_blocks = [
        dict(item)
        for item in blocks
        if str(item.get("text") or "").strip()
    ]

    aggregate_blocks: list[dict] = []
    working_blocks: list[dict] = []
    for item in raw_blocks:
        if _is_aggregate_alternate_representation(
            item,
            raw_blocks,
        ):
            item["excluded_from_ordered_text"] = True
            item["exclusion_reason"] = (
                "aggregate_alternate_representation"
            )
            aggregate_blocks.append(item)
        else:
            working_blocks.append(
                _collapse_exact_repeated_text(
                    item
                )
            )

    mirror_factor = _broad_mirror_factor(
        working_blocks
    )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in working_blocks:
        grouped[_norm(item.get("text"))].append(item)

    kept: list[dict] = []
    excluded: list[dict] = list(aggregate_blocks)
    logical_placeholders: list[dict] = []

    for key, group in grouped.items():
        ordered = sorted(
            group,
            key=lambda item: (
                int(item.get("visual_order") if item.get("visual_order") is not None else item.get("order", 0)),
                int(item.get("source_order", 0)),
            ),
        )

        local_kept: list[dict] = []
        for item in ordered:
            duplicate_of: dict | None = None
            for existing in local_kept:
                same_identity = bool(
                    item.get("part") == existing.get("part")
                    and item.get("shape_id")
                    and item.get("shape_id") == existing.get("shape_id")
                    and item.get("source_order") == existing.get("source_order")
                )
                distance = _position_distance(item, existing)
                near_same_position = distance is not None and distance <= 3.0
                if same_identity or near_same_position:
                    duplicate_of = existing
                    break
            if duplicate_of is not None:
                item["excluded_from_ordered_text"] = True
                item["exclusion_reason"] = "technical_duplicate_same_source_or_position"
                item["duplicate_of"] = duplicate_of.get("id")
                excluded.append(item)
            else:
                local_kept.append(item)

        # When the package contains two broad alternate representations,
        # divide same-text runs by the detected mirror factor. This applies
        # only to documents with many mirrored groups.
        already_collapsed_by_position = bool(
            mirror_factor > 1
            and len(group) >= mirror_factor
            and len(local_kept) * mirror_factor
            <= len(group)
        )

        if (
            mirror_factor > 1
            and len(local_kept) >= mirror_factor
            and not already_collapsed_by_position
        ):
            target_count = (
                1
                if _is_structural_heading(
                    str(group[0].get("text") or "")
                )
                else max(
                    1,
                    math.ceil(
                        len(local_kept)
                        / mirror_factor
                    ),
                )
            )
            selected: list[dict] = []
            for index, item in enumerate(local_kept):
                if (
                    len(selected) < target_count
                    and index % mirror_factor == 0
                ):
                    selected.append(item)
                else:
                    item[
                        "excluded_from_ordered_text"
                    ] = True
                    item["exclusion_reason"] = (
                        "alternate_representation_duplicate"
                    )
                    item["duplicate_of"] = (
                        selected[-1].get("id")
                        if selected
                        else None
                    )
                    excluded.append(item)
            local_kept = selected

        if _is_template_slot(group[0].get("text", "")):
            logical_placeholders.append({
                "normalized_text": key,
                "raw_occurrence_count": len(group),
                "logical_slot_count": len(local_kept),
                "text": str(group[0].get("text") or ""),
            })

        kept.extend(local_kept)

    kept = sorted(
        kept,
        key=lambda item: (
            int(item.get("visual_order") if item.get("visual_order") is not None else item.get("order", 0)),
            int(item.get("source_order", 0)),
        ),
    )

    # Final adjacent-heading safety: duplicated headings from alternate
    # representations should never create empty/shifted sections.
    final_kept: list[dict] = []
    for item in kept:
        if final_kept:
            previous = final_kept[-1]
            if (
                _norm(item.get("text")) == _norm(previous.get("text"))
                and _is_structural_heading(str(item.get("text") or ""))
            ):
                item["excluded_from_ordered_text"] = True
                item["exclusion_reason"] = "adjacent_duplicate_heading"
                item["duplicate_of"] = previous.get("id")
                excluded.append(item)
                continue
        final_kept.append(item)

    final_kept = _collapse_repeated_section_sequences(
        final_kept,
        excluded,
    )

    raw_count = len(raw_blocks)
    unique_normalized = len(grouped)
    duplicate_occurrences = raw_count - len(final_kept)
    duplicate_ratio = duplicate_occurrences / raw_count if raw_count else 0.0

    for order, item in enumerate(final_kept):
        item["order"] = order
        item["visual_order"] = order
        item["excluded_from_ordered_text"] = False
        item["exclusion_reason"] = None

    return {
        "blocks": final_kept,
        "excluded_blocks": excluded,
        "duplicate_analysis": {
            "raw_block_count": raw_count,
            "unique_normalized_text_count": unique_normalized,
            "clean_block_count": len(final_kept),
            "duplicate_occurrence_count": duplicate_occurrences,
            "duplicate_ratio": round(duplicate_ratio, 4),
            "mirror_factor": mirror_factor,
            "logical_placeholder_slots": logical_placeholders,
            "aggregate_alternate_representation_count": len(aggregate_blocks),
            "mode": "provenance_position_aggregate_and_document_mirror_deduplication",
        },
    }
