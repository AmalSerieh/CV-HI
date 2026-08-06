"""Deterministic page/block graph and logical reading-order planning."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from statistics import median
from typing import Any

_BULLET_RE = re.compile(r"^\s*([•●▪◦‣⁃*–—-]|\d+[.)])\s*")
_TERMINAL_RE = re.compile(r"[.!?؟:؛]\s*$")
_TEMPLATE_RESIDUE_RE = re.compile(
    r"(?i)\b(?:do not remove|sample content|free online template|"
    r"replace (?:this|with your) text|your text here|template provider)\b"
)


def _bbox(block: dict[str, Any]) -> tuple[float, float, float, float]:
    value = block.get("bbox") or {}
    return (
        float(value.get("x0", 0.0)),
        float(value.get("top", 0.0)),
        float(value.get("x1", 0.0)),
        float(value.get("bottom", 0.0)),
    )


def _center(block: dict[str, Any]) -> tuple[float, float]:
    x0, top, x1, bottom = _bbox(block)
    return ((x0 + x1) / 2.0, (top + bottom) / 2.0)


def _height(block: dict[str, Any]) -> float:
    _, top, _, bottom = _bbox(block)
    return max(1.0, bottom - top)


def _overlaps(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    return min(left[2], right[2]) > max(left[0], right[0]) and min(
        left[3], right[3]
    ) > max(left[1], right[1])


def _heading_probability(block: dict[str, Any], median_font_size: float) -> float:
    text = str(block.get("text") or "").strip()
    if not text:
        return 0.0
    words = re.findall(r"[\w\u0600-\u06ff]+", text, flags=re.UNICODE)
    if not 1 <= len(words) <= 8 or len(text) > 80:
        return 0.05
    if _BULLET_RE.match(text) or re.search(r"\b(?:19|20)\d{2}\b", text):
        return 0.08

    score = 0.18
    cased = [char for char in text if char.isalpha()]
    if cased and sum(char.isupper() for char in cased) / len(cased) >= 0.82:
        score += 0.34
    if str(block.get("font_weight") or "").casefold() == "bold":
        score += 0.22
    font_size = float(block.get("font_size") or 0.0)
    if median_font_size and font_size >= median_font_size * 1.18:
        score += 0.2
    if text.endswith((".", ";", "؛", "؟")):
        score -= 0.22
    return round(max(0.0, min(1.0, score)), 3)


def _alignment(block: dict[str, Any], page_width: float) -> str:
    x0, _, x1, _ = _bbox(block)
    center = (x0 + x1) / 2.0
    width = max(1.0, x1 - x0)
    if abs(center - page_width / 2.0) <= page_width * 0.055 and width < page_width * 0.8:
        return "center"
    if x0 <= page_width * 0.12:
        return "left"
    if x1 >= page_width * 0.88:
        return "right"
    return "unknown"


def _assign_rows(blocks: list[dict[str, Any]], page_number: int) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for block in sorted(blocks, key=lambda item: (_center(item)[1], _bbox(item)[0])):
        center_y = _center(block)[1]
        target: list[dict[str, Any]] | None = None
        for row in reversed(rows[-3:]):
            row_center = median(_center(item)[1] for item in row)
            tolerance = max(3.0, median(_height(item) for item in row + [block]) * 0.72)
            if abs(center_y - row_center) <= tolerance:
                target = row
                break
        if target is None:
            target = []
            rows.append(target)
        target.append(block)

    for index, row in enumerate(rows):
        row.sort(key=lambda item: _bbox(item)[0])
        row_id = f"p{page_number}_r{index}"
        for block in row:
            block["row_id"] = row_id
    return rows


def _table_cells(rows: list[list[dict[str, Any]]]) -> None:
    for row in rows:
        by_column: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for block in row:
            by_column[str(block.get("column") or "unknown")].append(block)
        for column_blocks in by_column.values():
            if len(column_blocks) < 2:
                continue
            ordered = sorted(column_blocks, key=lambda item: _bbox(item)[0])
            has_gap = any(
                _bbox(right)[0] - _bbox(left)[2] >= 6.0
                for left, right in zip(ordered, ordered[1:], strict=False)
            )
            compact = all(len(str(item.get("text") or "").split()) <= 8 for item in ordered)
            if has_gap and compact:
                for block in ordered:
                    block["probable_table_cell"] = True


def _add_neighbor(
    block: dict[str, Any],
    relationship: str,
    other: dict[str, Any],
) -> None:
    neighbors = block.setdefault("neighbors", {})
    values = neighbors.setdefault(relationship, [])
    identifier = str(other.get("id") or "")
    if identifier and identifier not in values:
        values.append(identifier)


def _relationships(blocks: list[dict[str, Any]], rows: list[list[dict[str, Any]]]) -> None:
    for row in rows:
        for block in row:
            for other in row:
                if other is block:
                    continue
                _add_neighbor(block, "same_row", other)
                if abs(_center(block)[0] - _center(other)[0]) <= 6.0:
                    _add_neighbor(block, "aligned_center", other)

    by_column: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        by_column[str(block.get("column") or "unknown")].append(block)

    for column_blocks in by_column.values():
        ordered = sorted(column_blocks, key=lambda item: (_bbox(item)[1], _bbox(item)[0]))
        for index, block in enumerate(ordered):
            if index:
                above = ordered[index - 1]
                _add_neighbor(block, "above", above)
                _add_neighbor(block, "same_column", above)
                _add_neighbor(above, "below", block)
                _add_neighbor(above, "same_column", block)
                if abs(_bbox(block)[0] - _bbox(above)[0]) <= 5.0:
                    _add_neighbor(block, "aligned_left", above)
                    _add_neighbor(above, "aligned_left", block)
                vertical_gap = _bbox(block)[1] - _bbox(above)[3]
                if vertical_gap <= max(_height(block), _height(above)) * 1.35:
                    _add_neighbor(block, "spatially_close", above)
                    _add_neighbor(above, "spatially_close", block)
                    above_text = str(above.get("text") or "").strip()
                    block_text = str(block.get("text") or "").strip()
                    if (
                        above_text
                        and block_text
                        and not _TERMINAL_RE.search(above_text)
                        and float(block.get("heading_probability") or 0.0) < 0.55
                        and not _BULLET_RE.match(block_text)
                    ):
                        _add_neighbor(above, "likely_continuation", block)
                    if float(above.get("heading_probability") or 0.0) >= 0.55:
                        _add_neighbor(above, "likely_heading_child", block)
                    if not block.get("probable_table_cell"):
                        _add_neighbor(above, "likely_entry_group", block)


def _zone_bbox(blocks: list[dict[str, Any]]) -> dict[str, float] | None:
    if not blocks:
        return None
    boxes = [_bbox(block) for block in blocks]
    return {
        "x0": round(min(item[0] for item in boxes), 3),
        "top": round(min(item[1] for item in boxes), 3),
        "x1": round(max(item[2] for item in boxes), 3),
        "bottom": round(max(item[3] for item in boxes), 3),
    }


def _zone(
    identifier: str,
    kind: str,
    blocks: list[dict[str, Any]],
    order: int,
    confidence: float,
) -> dict[str, Any]:
    for block in blocks:
        block["zone_id"] = identifier
        block["zone_kind"] = kind
    columns = {str(block.get("column") or "unknown") for block in blocks}
    column = next(iter(columns)) if len(columns) == 1 else "mixed"
    return {
        "id": identifier,
        "kind": kind,
        "bbox": _zone_bbox(blocks),
        "column": column,
        "order": order,
        "confidence": round(confidence, 3),
        "block_ids": [str(block.get("id")) for block in blocks],
    }


def _by_yx(block: dict[str, Any]) -> tuple[float, float]:
    x0, top, _, _ = _bbox(block)
    return (top, x0)


def _column_interval_order(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    left = sorted(
        (block for block in blocks if block.get("column") == "left"),
        key=_by_yx,
    )
    right = sorted(
        (block for block in blocks if block.get("column") == "right"),
        key=_by_yx,
    )
    other = sorted(
        (
            block
            for block in blocks
            if block.get("column") not in {"left", "right", "full_width"}
        ),
        key=_by_yx,
    )
    return left + right + other


def _annotate_common(
    blocks: list[dict[str, Any]],
    page_width: float,
    page_height: float,
    image_rects: list[tuple[float, float, float, float]],
    link_rects: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    sizes = [
        float(block.get("font_size") or 0.0)
        for block in blocks
        if float(block.get("font_size") or 0.0) > 0
    ]
    median_font_size = median(sizes) if sizes else 0.0
    for block in blocks:
        text = str(block.get("text") or "")
        marker = _BULLET_RE.match(text)
        block.setdefault("font_size", None)
        block.setdefault("font_family", None)
        block.setdefault("font_weight", "unknown")
        block.setdefault("font_style", "unknown")
        block.setdefault("alignment", _alignment(block, page_width))
        block.setdefault("rotation", 0.0)
        block["bullet_marker"] = marker.group(1) if marker else None
        block.setdefault("probable_table_cell", False)
        block["heading_probability"] = _heading_probability(block, median_font_size)
        block["section_probability"] = block["heading_probability"]
        block["image_overlap"] = any(_overlaps(_bbox(block), rect) for rect in image_rects)
        block["link_annotations"] = [
            str(item["uri"])
            for item in link_rects
            if item.get("uri") and _overlaps(_bbox(block), tuple(item["bbox"]))
        ]
        block.setdefault("neighbors", {})
        block["is_template_residue"] = bool(_TEMPLATE_RESIDUE_RE.search(text))
        block["excluded_from_entities"] = block["is_template_residue"]
        block["quality_flags"] = (
            ["TEMPLATE_REMNANT_DETECTED"] if block["is_template_residue"] else []
        )
        if abs(float(block.get("rotation") or 0.0)) >= 5.0:
            block["block_type"] = "rotated_text"
            if "ROTATED_MARGINAL_TEXT" not in block["quality_flags"]:
                block["quality_flags"].append("ROTATED_MARGINAL_TEXT")
    rows = _assign_rows(blocks, int(blocks[0].get("page") or 1) if blocks else 1)
    _table_cells(rows)
    _relationships(blocks, rows)
    return rows


def build_page_graph(
    blocks: list[dict[str, Any]],
    *,
    page_width: float,
    page_height: float,
    split_x: float | None,
    confidence: float,
    image_rects: list[tuple[float, float, float, float]] | None = None,
    link_rects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Annotate blocks and produce a zone-aware reading plan.

    A detected multi-column page is never flattened by alternating visual rows.
    Grid-like rows remain graph relationships and probable cells, not prose.
    """

    image_rects = image_rects or []
    link_rects = link_rects or []
    page_number = int(blocks[0].get("page") or 1) if blocks else 1

    if split_x is None:
        for block in blocks:
            block["column"] = "single"
        _annotate_common(blocks, page_width, page_height, image_rects, link_rects)
        single_ordered = sorted(blocks, key=_by_yx)
        zone_id = f"p{page_number}_z0"
        single_zones = (
            [_zone(zone_id, "single", single_ordered, 0, confidence)]
            if single_ordered
            else []
        )
        return {
            "layout": "single_column",
            "reading_order": "top_to_bottom",
            "reading_order_risk": "low",
            "ordered_blocks": single_ordered,
            "zones": single_zones,
            "warnings": (
                ["TEMPLATE_REMNANT_DETECTED"]
                if any(block.get("is_template_residue") for block in blocks)
                else []
            ),
        }

    margin = max(10.0, page_width * 0.018)
    full_width: list[dict[str, Any]] = []
    column_blocks: list[dict[str, Any]] = []
    for block in blocks:
        x0, _, x1, _ = _bbox(block)
        center_x = (x0 + x1) / 2.0
        crosses = x0 < split_x - margin and x1 > split_x + margin
        is_wide = (x1 - x0) >= page_width * 0.72
        if crosses or is_wide:
            block["column"] = "full_width"
            full_width.append(block)
        elif center_x < split_x:
            block["column"] = "left"
            column_blocks.append(block)
        else:
            block["column"] = "right"
            column_blocks.append(block)

    left_top = min(
        (_bbox(block)[1] for block in column_blocks if block.get("column") == "left"),
        default=page_height,
    )
    right_top = min(
        (_bbox(block)[1] for block in column_blocks if block.get("column") == "right"),
        default=page_height,
    )
    shared_column_start = max(left_top, right_top)
    promoted_header = [
        block
        for block in column_blocks
        if _bbox(block)[3] < shared_column_start - 5.0
        and _bbox(block)[1] <= page_height * 0.18
    ]
    for block in promoted_header:
        block["column"] = "full_width"
        column_blocks.remove(block)
        full_width.append(block)

    rows = _annotate_common(blocks, page_width, page_height, image_rects, link_rects)
    paired_rows = sum(
        1
        for row in rows
        if {str(block.get("column")) for block in row}.issuperset({"left", "right"})
    )
    pair_ratio = paired_rows / max(1, len(rows))

    first_column_top = min((_bbox(block)[1] for block in column_blocks), default=page_height)
    last_column_bottom = max((_bbox(block)[3] for block in column_blocks), default=0.0)
    top_full = [
        block
        for block in full_width
        if _bbox(block)[1] <= page_height * 0.18
        and _bbox(block)[1] <= first_column_top + _height(block)
    ]
    bottom_full = [
        block
        for block in full_width
        if block not in top_full
        and _bbox(block)[1] >= page_height * 0.82
        and _bbox(block)[3] >= last_column_bottom - _height(block)
    ]
    middle_full = [
        block for block in full_width if block not in top_full and block not in bottom_full
    ]
    top_full.sort(key=_by_yx)
    bottom_full.sort(key=_by_yx)
    middle_full.sort(key=_by_yx)

    ordered: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []

    def add_zone(kind: str, zone_blocks: list[dict[str, Any]]) -> None:
        if not zone_blocks:
            return
        identifier = f"p{page_number}_z{len(zones)}"
        zones.append(_zone(identifier, kind, zone_blocks, len(zones), confidence))
        ordered.extend(zone_blocks)

    add_zone("header", top_full)
    previous_bottom = max((_bbox(block)[3] for block in top_full), default=-math.inf)
    for anchor in middle_full:
        anchor_top = _bbox(anchor)[1]
        anchor_row_id = anchor.get("row_id")
        row_companions = [
            block
            for block in column_blocks
            if anchor_row_id
            and block.get("row_id") == anchor_row_id
        ]
        interval = [
            block
            for block in column_blocks
            if previous_bottom < _center(block)[1] < anchor_top
            and block not in row_companions
        ]
        add_zone("column_pair", _column_interval_order(interval))
        # Standalone bullets and narrow labels are commonly emitted as a
        # separate block beside a line that crosses the inferred split.
        # Keep those same-row companions in the reading plan; otherwise the
        # list marker disappears and downstream bullet grouping collapses.
        add_zone("full_width", sorted([*row_companions, anchor], key=_by_yx))
        previous_bottom = _bbox(anchor)[3]
    remaining = [block for block in column_blocks if _center(block)[1] > previous_bottom]
    add_zone("column_pair", _column_interval_order(remaining))
    add_zone("footer", bottom_full)

    warnings = ["multi_column_reading_risk"]
    if pair_ratio >= 0.35:
        warnings.append("grid_rows_preserved_without_row_flattening")
    if confidence < 0.65:
        warnings.append("low_column_detection_confidence")
    if any(block.get("is_template_residue") for block in blocks):
        warnings.append("TEMPLATE_REMNANT_DETECTED")
    risk = "high" if confidence < 0.65 or pair_ratio >= 0.35 else "medium"
    return {
        "layout": "two_column",
        "reading_order": "column_wise",
        "reading_order_risk": risk,
        "ordered_blocks": ordered,
        "zones": zones,
        "warnings": warnings,
    }
