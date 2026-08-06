from __future__ import annotations

import colorsys
import copy
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from .docx_structure_analyzer import analyze_docx_package
    from .duplicate_content_cleaner import deduplicate_blocks
except ImportError:
    from docx_structure_analyzer import analyze_docx_package
    from duplicate_content_cleaner import deduplicate_blocks

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional dependency guard
    fitz = None

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency guard
    Image = None


# ---------------------------------------------------------------------------
# Normalization and generic placeholder detection
# ---------------------------------------------------------------------------

_DATE_PLACEHOLDER_RE = re.compile(
    r"(?ix)"
    r"(?:\b(?:month|mon|mm)\s+)?"
    r"(?:"
    r"(?:19|20)?[xy]{2,4}"
    r"|yyyy"
    r"|yy"
    r"|mm\s*/\s*yyyy"
    r"|month\s+year"
    r")"
    r"(?:\s*(?:-|–|—|to)\s*"
    r"(?:19|20)?[xy]{2,4})?\b"
)

_SAMPLE_HEADING_RE = re.compile(
    r"(?i)\b(?:resume|résumé|cv|curriculum vitae)\b"
    r".{0,30}\b(?:sample|template|example|demo)\b"
    r"|\b(?:sample|template|example|demo)\b"
    r".{0,30}\b(?:resume|résumé|cv)\b"
)

_PLACEHOLDER_NAME_RE = re.compile(
    r"(?i)^\s*(?:student|candidate|applicant|your|full|first|last)\s+name\s*$"
    r"|^\s*name\s+surname\s*$"
)

_PLACEHOLDER_LOCATION_RE = re.compile(
    r"(?i)^\s*(?:city|town)\s*,\s*(?:country|state|province|region)\s*$"
    r"|^\s*(?:address|street address|city state zip)\s*$"
)

_PLACEHOLDER_EMAIL_RE = re.compile(
    r"(?i)^(?:email|name|student|candidate|yourname|user)@"
    r"(?:email|example|test|sample)\.(?:com|org|net|ca)$"
    r"|^[^@]+@example\.(?:com|org|net)$"
)

_ROLE_WORDS = {
    "accountant", "accounting", "bookkeeper", "assistant", "associate",
    "manager", "director", "analyst", "specialist", "coordinator",
    "consultant", "representative", "executive", "administrator",
    "administration", "officer", "developer", "engineer", "designer",
    "auditor", "tax", "preparer", "intern", "trainee", "co-op",
    "teacher", "nurse", "sales", "marketing", "operations", "advisor",
    "technician", "supervisor", "lead", "researcher", "volunteer",
}

_STRONG_ROLE_WORDS = {
    "accountant", "bookkeeper", "assistant", "associate", "manager",
    "director", "analyst", "specialist", "coordinator", "consultant",
    "representative", "executive", "administrator", "officer",
    "developer", "engineer", "designer", "auditor", "preparer",
    "intern", "trainee", "teacher", "nurse", "technician",
    "supervisor", "lead", "researcher", "advisor", "agent",
}

_ACTION_WORDS = {
    "managed", "developed", "implemented", "created", "prepared",
    "reconciled", "increased", "reduced", "drafted", "answered",
    "coordinated", "conducted", "performed", "showed", "became",
    "worked", "offered", "received", "awarded", "improved", "led",
    "generated", "supported", "provided", "cultivated", "built",
    "achieved", "earned", "analyzed", "maintained", "handled",
}

_SECTION_ALIASES = {
    "summary": {
        "summary", "professional summary", "profile", "objective",
    },
    "education": {
        "education", "educational background", "academic background",
        "academic qualifications",
    },
    "experience": {
        "experience", "work experience", "professional experience",
        "employment history", "career history", "relevant experience",
    },
    "volunteer": {
        "volunteer", "volunteer experience", "community engagement",
        "community service", "volunteering",
    },
    "awards": {
        "awards", "achievements", "honors", "honours",
    },
    "certifications": {
        "certifications", "certificates", "credentials",
    },
    "skills": {
        "skills", "technical skills", "technology skills",
        "core competencies", "competencies",
    },
}


def _ascii_fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char))


def _norm(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9+#/.]+",
        " ",
        _ascii_fold(value).casefold(),
    ).strip()


def _norm_heading(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _ascii_fold(value).casefold()).strip()


def _unique_strings(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = re.sub(r"\s+", " ", str(value or "").strip())
        key = _norm(clean)
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def _section_name_for_heading(value: str) -> str | None:
    normalized = _norm_heading(value)
    for name, aliases in _SECTION_ALIASES.items():
        if normalized in aliases:
            return name
    return None


def _is_placeholder_date(value: Any) -> bool:
    return bool(_DATE_PLACEHOLDER_RE.search(str(value or "")))


def _placeholder_date_kind(value: str) -> str:
    clean = str(value or "")
    if re.search(r"[-–—]|\bto\b", clean, re.IGNORECASE):
        return "range"
    if re.search(r"(?i)\b(?:month|mon|mm)\b", clean):
        return "month_year"
    return "year"


def _is_placeholder_phone(value: Any) -> bool:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return False
    if len(set(digits)) <= 2 and len(digits) >= 7:
        return True
    return digits in {
        "1234567890", "0123456789", "5555555555", "1111111111",
        "0000000000", "9999999999",
    }


def _is_placeholder_email(value: Any) -> bool:
    return bool(_PLACEHOLDER_EMAIL_RE.match(str(value or "").strip()))


def _is_placeholder_name(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(_PLACEHOLDER_NAME_RE.match(text) or _SAMPLE_HEADING_RE.search(text))


def _is_placeholder_location(value: Any) -> bool:
    return bool(_PLACEHOLDER_LOCATION_RE.match(str(value or "").strip()))


def _extract_section_texts(result: dict) -> dict[str, str]:
    sections = (result.get("sections", {}) or {}).get("sections", {}) or {}
    output: dict[str, str] = {}
    for name, section in sections.items():
        if isinstance(section, dict):
            output[str(name)] = str(section.get("content") or "")
        else:
            output[str(name)] = str(section or "")
    return output


def detect_date_placeholders(result: dict) -> dict:
    sections = _extract_section_texts(result)
    records: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for section_name, text in sections.items():
        for line_index, raw_line in enumerate(str(text or "").splitlines(), start=1):
            for match in _DATE_PLACEHOLDER_RE.finditer(raw_line):
                raw = match.group(0).strip()
                key = (section_name, str(line_index), str(match.start()))
                if key in seen:
                    continue
                seen.add(key)
                records.append({
                    "raw": raw,
                    "normalized": re.sub(r"\s+", " ", raw),
                    "section": section_name,
                    "line_index": line_index,
                    "line_text": raw_line.strip(),
                    "kind": _placeholder_date_kind(raw),
                    "status": "placeholder_unresolved",
                    "validation": {
                        "valid": False,
                        "reason": "template_date_placeholder",
                    },
                })

    full_text = str(
        (result.get("extracted_resume_text", {}) or {}).get("analysis_text")
        or (result.get("extracted_resume_text", {}) or {}).get("cleaned_text")
        or ""
    )
    if not sections and full_text:
        for line_index, raw_line in enumerate(full_text.splitlines(), start=1):
            for match in _DATE_PLACEHOLDER_RE.finditer(raw_line):
                raw = match.group(0).strip()
                key = ("document", str(line_index), str(match.start()))
                if key in seen:
                    continue
                seen.add(key)
                records.append({
                    "raw": raw,
                    "normalized": re.sub(r"\s+", " ", raw),
                    "section": "document",
                    "line_index": line_index,
                    "line_text": raw_line.strip(),
                    "kind": _placeholder_date_kind(raw),
                    "status": "placeholder_unresolved",
                    "validation": {
                        "valid": False,
                        "reason": "template_date_placeholder",
                    },
                })

    by_section = Counter(record["section"] for record in records)
    return {
        "detected": bool(records),
        "count": len(records),
        "items": records,
        "counts_by_section": dict(sorted(by_section.items())),
        "mode": "generic_placeholder_date_detection",
    }


def detect_document_profile(result: dict, date_placeholders: dict) -> dict:
    extracted = result.get("extracted_resume_text", {}) or {}
    profile_text = str(
        extracted.get("ordered_text")
        or extracted.get("cleaned_text")
        or extracted.get("analysis_text")
        or ""
    )
    text = str(
        extracted.get("analysis_text")
        or extracted.get("cleaned_text")
        or profile_text
    )
    first_lines = [line.strip() for line in profile_text.splitlines()[:12] if line.strip()]
    contact = result.get("contact", {}) or {}
    signals: list[dict] = []

    if any(_SAMPLE_HEADING_RE.search(line) for line in first_lines):
        signals.append({
            "type": "resume_sample_heading",
            "weight": 0.35,
            "evidence": next(line for line in first_lines if _SAMPLE_HEADING_RE.search(line)),
        })

    for line in first_lines:
        if _PLACEHOLDER_NAME_RE.match(line):
            signals.append({
                "type": "placeholder_candidate_name",
                "weight": 0.25,
                "evidence": line,
            })
            break

    email = str(contact.get("email") or "")
    if _is_placeholder_email(email):
        signals.append({
            "type": "placeholder_email",
            "weight": 0.18,
            "evidence": email,
        })

    phone = str(contact.get("phone") or "")
    if _is_placeholder_phone(phone):
        signals.append({
            "type": "placeholder_phone",
            "weight": 0.18,
            "evidence": phone,
        })

    placeholder_location_matches = [
        line for line in text.splitlines() if _is_placeholder_location(line)
    ]
    if placeholder_location_matches:
        signals.append({
            "type": "placeholder_location",
            "weight": 0.12,
            "evidence": placeholder_location_matches[0].strip(),
        })

    placeholder_count = int(date_placeholders.get("count", 0) or 0)
    if placeholder_count:
        signals.append({
            "type": "placeholder_dates",
            "weight": min(0.35, 0.08 + placeholder_count * 0.035),
            "evidence_count": placeholder_count,
        })

    confidence = min(0.99, round(sum(float(item["weight"]) for item in signals), 3))
    categories = {item["type"] for item in signals}
    is_template = bool(
        confidence >= 0.62
        and (
            "resume_sample_heading" in categories
            or len(categories) >= 3
        )
    )

    return {
        "document_type": "resume_template" if is_template else "resume",
        "is_template": is_template,
        "template_confidence": confidence,
        "signals": signals,
        "signal_types": [item["type"] for item in signals],
        "detection_mode": "weighted_generic_template_signals",
    }


# ---------------------------------------------------------------------------
# Dynamic color extraction (no fixed palette)
# ---------------------------------------------------------------------------


def _rgb_from_pdf_color(value: Any) -> tuple[int, int, int] | None:
    if value is None:
        return None
    if isinstance(value, int):
        return (
            (value >> 16) & 255,
            (value >> 8) & 255,
            value & 255,
        )
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        values = list(value[:3])
        if all(isinstance(item, (int, float)) for item in values):
            if max(values) <= 1.0:
                values = [round(float(item) * 255) for item in values]
            return tuple(max(0, min(255, int(round(float(item))))) for item in values)  # type: ignore[return-value]
    return None


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in rgb)


def _luminance(rgb: tuple[int, int, int]) -> float:
    converted = []
    for channel in rgb:
        value = channel / 255.0
        converted.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * converted[0] + 0.7152 * converted[1] + 0.0722 * converted[2]


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    l1, l2 = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _saturation(rgb: tuple[int, int, int]) -> float:
    return colorsys.rgb_to_hsv(*(channel / 255.0 for channel in rgb))[1]


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def _usage_region(bbox: Any, page_height: float) -> str:
    try:
        top = float(bbox[1])
        bottom = float(bbox[3])
    except Exception:
        return "unknown"
    center = (top + bottom) / 2
    if center <= page_height * 0.18:
        return "header"
    if center >= page_height * 0.84:
        return "footer"
    return "body"


def _cluster_colors(samples: list[dict], max_colors: int = 64) -> list[dict]:
    if not samples:
        return []
    exact: dict[tuple[int, int, int], dict] = {}
    for sample in samples:
        rgb = sample.get("rgb")
        if not isinstance(rgb, tuple):
            continue
        item = exact.setdefault(rgb, {
            "rgb": rgb,
            "weight": 0.0,
            "sources": Counter(),
            "usage": Counter(),
        })
        weight = float(sample.get("weight", 1.0) or 1.0)
        item["weight"] += weight
        item["sources"][str(sample.get("source") or "unknown")] += weight
        item["usage"][str(sample.get("usage") or "unknown")] += weight

    ordered = sorted(exact.values(), key=lambda item: item["weight"], reverse=True)
    clusters: list[dict] = []
    for item in ordered:
        rgb = item["rgb"]
        target = None
        for cluster in clusters:
            if _color_distance(rgb, cluster["rgb"]) <= 18:
                target = cluster
                break
        if target is None:
            clusters.append({
                "rgb": rgb,
                "weight": item["weight"],
                "sum_rgb": [channel * item["weight"] for channel in rgb],
                "sources": Counter(item["sources"]),
                "usage": Counter(item["usage"]),
            })
        else:
            target["weight"] += item["weight"]
            for index in range(3):
                target["sum_rgb"][index] += rgb[index] * item["weight"]
            target["sources"].update(item["sources"])
            target["usage"].update(item["usage"])
            target["rgb"] = tuple(
                int(round(target["sum_rgb"][index] / target["weight"]))
                for index in range(3)
            )

    total_weight = sum(cluster["weight"] for cluster in clusters) or 1.0
    output = []
    for cluster in sorted(clusters, key=lambda item: item["weight"], reverse=True)[:max_colors]:
        rgb = cluster["rgb"]
        output.append({
            "hex": _hex(rgb),
            "rgb": list(rgb),
            "weight": round(cluster["weight"], 2),
            "coverage": round(cluster["weight"] / total_weight, 6),
            "saturation": round(_saturation(rgb), 4),
            "luminance": round(_luminance(rgb), 4),
            "sources": sorted(cluster["sources"], key=cluster["sources"].get, reverse=True),
            "usage": sorted(cluster["usage"], key=cluster["usage"].get, reverse=True),
        })
    return output


def extract_dynamic_document_style(pdf_path: str | Path | None) -> dict:
    base = {
        "status": "not_available",
        "has_color": False,
        "is_multicolor": False,
        "detected_color_count": 0,
        "chromatic_color_count": 0,
        "palette": [],
        "primary_color": None,
        "accent_colors": [],
        "text_colors": [],
        "graphic_colors": [],
        "background_color": None,
        "contrast_status": "unknown",
        "ats_color_risk": "unknown",
        "palette_method": "dynamic_pdf_sampling",
        "fixed_palette_used": False,
    }
    if fitz is None or not pdf_path:
        return base
    path = Path(str(pdf_path))
    if not path.is_file():
        return base

    samples: list[dict] = []
    text_color_weights: Counter[tuple[int, int, int]] = Counter()
    graphic_color_weights: Counter[tuple[int, int, int]] = Counter()
    raster_color_weights: Counter[tuple[int, int, int]] = Counter()

    try:
        document = fitz.open(path)
    except Exception as exc:
        return {**base, "status": "error", "error": str(exc)}

    try:
        for page in document:
            page_height = float(page.rect.height or 1)
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []) or []:
                for line in block.get("lines", []) or []:
                    for span in line.get("spans", []) or []:
                        rgb = _rgb_from_pdf_color(span.get("color"))
                        if rgb is None:
                            continue
                        text = str(span.get("text") or "")
                        weight = max(1.0, len(text.strip())) * max(1.0, float(span.get("size") or 1.0))
                        usage = _usage_region(span.get("bbox"), page_height)
                        samples.append({"rgb": rgb, "weight": weight, "source": "text", "usage": usage})
                        text_color_weights[rgb] += weight

            try:
                drawings = page.get_drawings()
            except Exception:
                drawings = []
            for drawing in drawings:
                rect = drawing.get("rect")
                area = 1.0
                if rect is not None:
                    try:
                        area = max(1.0, float(rect.width) * float(rect.height))
                    except Exception:
                        area = 1.0
                usage = _usage_region(rect, page_height) if rect is not None else "unknown"
                for field in ("fill", "color"):
                    rgb = _rgb_from_pdf_color(drawing.get(field))
                    if rgb is None:
                        continue
                    weight = math.sqrt(area) if field == "color" else area
                    samples.append({"rgb": rgb, "weight": weight, "source": "vector", "usage": usage})
                    graphic_color_weights[rgb] += weight

            if Image is not None:
                try:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), alpha=False)
                    mode = "RGB" if pixmap.n < 4 else "RGBA"
                    image = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
                    if image.mode != "RGB":
                        image = image.convert("RGB")
                    quantized = image.quantize(colors=64, method=Image.Quantize.MEDIANCUT).convert("RGB")
                    pixel_values = (
                        quantized.get_flattened_data()
                        if hasattr(quantized, "get_flattened_data")
                        else quantized.getdata()
                    )
                    counts = Counter(pixel_values)
                    for rgb, count in counts.items():
                        rgb_tuple = tuple(int(channel) for channel in rgb)
                        samples.append({"rgb": rgb_tuple, "weight": float(count) * 0.25, "source": "raster", "usage": "page"})
                        raster_color_weights[rgb_tuple] += count
                except Exception:
                    pass
    finally:
        document.close()

    palette = _cluster_colors(samples)
    if not palette:
        return {**base, "status": "empty"}

    chromatic = [
        item for item in palette
        if item["saturation"] >= 0.18
        and 0.03 < item["luminance"] < 0.97
    ]
    primary = chromatic[0]["hex"] if chromatic else None
    accents = [item["hex"] for item in chromatic[1:17]]

    def clustered_hexes(counter: Counter[tuple[int, int, int]]) -> list[str]:
        if not counter:
            return []
        samples_local = [
            {"rgb": rgb, "weight": float(weight), "source": "local", "usage": "unknown"}
            for rgb, weight in counter.items()
        ]
        return [item["hex"] for item in _cluster_colors(samples_local, max_colors=32)]

    background = max(raster_color_weights, key=raster_color_weights.get) if raster_color_weights else (255, 255, 255)
    body_text_colors: list[tuple[tuple[int, int, int], float]] = []
    for rgb, weight in text_color_weights.items():
        body_text_colors.append((rgb, float(weight)))
    contrast_values = [(_contrast(rgb, background), weight) for rgb, weight in body_text_colors]
    low_weight = sum(weight for value, weight in contrast_values if value < 4.5)
    total_text_weight = sum(weight for _, weight in contrast_values) or 1.0
    if not contrast_values:
        contrast_status = "unknown"
    elif low_weight / total_text_weight <= 0.05:
        contrast_status = "good"
    elif low_weight / total_text_weight <= 0.25:
        contrast_status = "mixed"
    else:
        contrast_status = "poor"

    body_chromatic_weight = 0.0
    total_body_weight = 0.0
    for sample in samples:
        if sample.get("source") != "text" or sample.get("usage") != "body":
            continue
        weight = float(sample.get("weight", 0.0) or 0.0)
        total_body_weight += weight
        if _saturation(sample["rgb"]) >= 0.18:
            body_chromatic_weight += weight
    body_color_ratio = body_chromatic_weight / total_body_weight if total_body_weight else 0.0
    ats_risk = "low" if contrast_status == "good" and body_color_ratio <= 0.20 else "moderate" if contrast_status != "poor" else "high"

    return {
        "status": "ok",
        "has_color": bool(chromatic),
        "is_multicolor": len(chromatic) >= 2,
        "detected_color_count": len(palette),
        "chromatic_color_count": len(chromatic),
        "palette": palette,
        "primary_color": primary,
        "accent_colors": accents,
        "text_colors": clustered_hexes(text_color_weights),
        "graphic_colors": clustered_hexes(graphic_color_weights),
        "background_color": _hex(background),
        "contrast_status": contrast_status,
        "body_chromatic_text_ratio": round(body_color_ratio, 4),
        "ats_color_risk": ats_risk,
        "palette_method": "pdf_text_vector_and_quantized_raster_clustering",
        "fixed_palette_used": False,
    }


# ---------------------------------------------------------------------------
# Layout-aware row pairing
# ---------------------------------------------------------------------------


def _page_widths(result: dict) -> dict[int, float]:
    widths: dict[int, float] = {}
    page_layouts = (result.get("text_extraction", {}) or {}).get("page_layouts", []) or []
    for page in page_layouts:
        if isinstance(page, dict):
            try:
                widths[int(page.get("page"))] = float(page.get("width") or 612.0)
            except Exception:
                continue
    return widths


def _layout_rows(result: dict) -> list[dict]:
    blocks = (result.get("layout_data", {}) or {}).get("blocks", []) or []
    widths = _page_widths(result)
    by_page: dict[int, list[dict]] = defaultdict(list)
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("is_repeated_header_footer") or block.get("excluded_from_ordered_text"):
            continue
        text = str(block.get("text") or "").strip()
        bbox = block.get("bbox") or {}
        if not text or not isinstance(bbox, dict):
            continue
        try:
            page = int(block.get("page") or 1)
            top = float(bbox.get("top") or 0.0)
            bottom = float(bbox.get("bottom") or top)
            x0 = float(bbox.get("x0") or 0.0)
            x1 = float(bbox.get("x1") or x0)
        except Exception:
            continue
        by_page[page].append({
            "id": block.get("id"),
            "text": text,
            "page": page,
            "top": top,
            "bottom": bottom,
            "x0": x0,
            "x1": x1,
        })

    rows: list[dict] = []
    for page in sorted(by_page):
        page_blocks = sorted(by_page[page], key=lambda item: (item["top"], item["x0"]))
        page_rows: list[dict] = []
        for block in page_blocks:
            height = max(1.0, block["bottom"] - block["top"])
            center = (block["top"] + block["bottom"]) / 2
            target = None
            for row in reversed(page_rows[-3:]):
                row_center = row["center"]
                tolerance = max(3.5, min(height, row["height"]) * 0.45)
                overlap = min(block["bottom"], row["bottom"]) - max(block["top"], row["top"])
                if abs(center - row_center) <= tolerance or overlap >= min(height, row["height"]) * 0.45:
                    target = row
                    break
            if target is None:
                target = {
                    "page": page,
                    "top": block["top"],
                    "bottom": block["bottom"],
                    "center": center,
                    "height": height,
                    "blocks": [],
                }
                page_rows.append(target)
            target["blocks"].append(block)
            target["top"] = min(target["top"], block["top"])
            target["bottom"] = max(target["bottom"], block["bottom"])
            target["center"] = (target["top"] + target["bottom"]) / 2
            target["height"] = max(1.0, target["bottom"] - target["top"])

        width = widths.get(page, 612.0)
        for row in page_rows:
            row["blocks"] = sorted(row["blocks"], key=lambda item: item["x0"])
            left = [item for item in row["blocks"] if item["x0"] < width * 0.56]
            right = [item for item in row["blocks"] if item["x0"] >= width * 0.56]
            row["left_text"] = " ".join(item["text"] for item in left).strip()
            row["right_text"] = " ".join(item["text"] for item in right).strip()
            row["text"] = " ".join(item["text"] for item in row["blocks"]).strip()
            row["block_ids"] = [item["id"] for item in row["blocks"] if item.get("id")]
            rows.append(row)
    return sorted(rows, key=lambda row: (row["page"], row["top"]))


def _rows_for_section(rows: list[dict], section_name: str) -> list[dict]:
    started = False
    output: list[dict] = []
    for row in rows:
        heading = _section_name_for_heading(row.get("text", ""))
        if heading:
            if not started and heading == section_name:
                started = True
                continue
            if started and heading != section_name:
                break
        if started:
            output.append(row)
    return output


def _strip_bullet(value: str) -> str:
    return re.sub(r"^[\s•▪●◦*\-]+", "", str(value or "")).strip()


def _is_bullet_row(row: dict) -> bool:
    return any(str(block.get("text") or "").strip() in {"•", "▪", "●", "◦", "-"} for block in row.get("blocks", []))


def _is_location_line(value: Any) -> bool:
    text = _strip_bullet(str(value or ""))
    if not text or len(text) > 70 or _is_placeholder_date(text):
        return False
    if _is_placeholder_location(text):
        return True
    if re.match(r"^[A-Za-zÀ-ÿ .'-]{2,40},\s*[A-Za-zÀ-ÿ .'-]{2,30}$", text):
        return not any(word in _norm(text).split() for word in _ROLE_WORDS)
    return False


def _is_role_line(value: Any) -> bool:
    text = _strip_bullet(str(value or ""))
    normalized = _norm_heading(text)
    if not text or len(text) > 100 or _is_placeholder_date(text) or _is_location_line(text):
        return False
    words = set(normalized.split())
    if words & _STRONG_ROLE_WORDS:
        return True
    if normalized in {"volunteer", "student", "trainee"}:
        return True
    return bool(re.search(r"(?i)\((?:co-?op|intern(?:ship)?|contract|part[- ]time)\)", text))


def _is_company_line(value: Any) -> bool:
    text = _strip_bullet(str(value or ""))
    normalized = _norm_heading(text)
    words = normalized.split()
    if (
        not text
        or len(text) > 110
        or len(words) > 12
        or _is_placeholder_date(text)
        or _is_location_line(text)
        or _is_role_line(text)
        or _section_name_for_heading(text)
    ):
        return False
    if words and words[0] in _ACTION_WORDS:
        return False
    if re.search(r"[.!?;:]$", text):
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ]", text))


def _row_left_content(row: dict) -> str:
    value = row.get("left_text") or row.get("text") or ""
    return _strip_bullet(value)


def _row_right_content(row: dict) -> str:
    return _strip_bullet(row.get("right_text") or "")


def _header_at(rows: list[dict], index: int) -> dict | None:
    if index < 0 or index >= len(rows):
        return None
    company_row = rows[index]
    company = _row_left_content(company_row)
    location = _row_right_content(company_row)
    if not _is_company_line(company):
        return None
    if not location or not _is_location_line(location):
        return None

    for role_index in range(index + 1, min(len(rows), index + 4)):
        role_row = rows[role_index]
        title = _row_left_content(role_row)
        date_text = _row_right_content(role_row)
        if _is_role_line(title) and _is_placeholder_date(date_text):
            return {
                "company": company,
                "location": location or None,
                "job_title": title,
                "raw_date_text": date_text,
                "company_row_index": index,
                "role_row_index": role_index,
                "source_block_ids": _unique_strings(
                    list(company_row.get("block_ids", []))
                    + list(role_row.get("block_ids", []))
                ),
            }
    return None


def _collect_responsibilities(rows: list[dict], start: int, end: int) -> list[str]:
    responsibilities: list[str] = []
    current = ""
    for row in rows[start:end]:
        text = _strip_bullet(row.get("text") or "")
        if not text or _is_placeholder_date(text) or _is_location_line(text):
            continue
        if _is_bullet_row(row):
            if current:
                responsibilities.append(re.sub(r"\s+", " ", current).strip())
            current = text
        elif current:
            current = f"{current} {text}".strip()
        elif _norm_heading(text).split()[:1] and _norm_heading(text).split()[0] in _ACTION_WORDS:
            current = text
    if current:
        responsibilities.append(re.sub(r"\s+", " ", current).strip())
    return _unique_strings(responsibilities)


def _employment_type(title: str, volunteer: bool = False) -> str | None:
    if volunteer:
        return "Volunteer"
    normalized = _norm_heading(title)
    if "co op" in normalized:
        return "Co-op"
    if "intern" in normalized:
        return "Internship"
    return None


def _metrics_for_text(result: dict, text: str) -> list[str]:
    corpus = _norm(text)
    metrics = []
    reconciliation = result.get("evidence_reconciliation", {}) or {}
    for item in reconciliation.get("document_metrics", []) or []:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence", [])
        evidence_values: list[str] = []
        if isinstance(evidence, str):
            evidence_values.append(evidence)
        elif isinstance(evidence, dict):
            evidence_values.append(str(evidence.get("text") or evidence.get("evidence") or ""))
        elif isinstance(evidence, list):
            for evidence_item in evidence:
                if isinstance(evidence_item, str):
                    evidence_values.append(evidence_item)
                elif isinstance(evidence_item, dict):
                    evidence_values.append(str(evidence_item.get("text") or evidence_item.get("evidence") or ""))
        if any(_norm(value) and _norm(value) in corpus for value in evidence_values):
            metrics.append(str(item.get("value") or "").strip())
    return _unique_strings(metrics)


def _entry_from_header(
    result: dict,
    header: dict,
    responsibilities: list[str],
    *,
    volunteer: bool,
) -> dict:
    raw_date = header["raw_date_text"]
    raw_text_parts = [
        header["company"],
        header.get("location") or "",
        header["job_title"],
        raw_date,
        *responsibilities,
    ]
    raw_text = "\n".join(value for value in raw_text_parts if value)
    metrics = _metrics_for_text(result, "\n".join(responsibilities))
    duration_months = None
    duration_source = None
    duration_confidence = None
    if volunteer:
        match = re.search(
            r"(?i)\b(\d+(?:\.\d+)?)\s*[- ]\s*month\s+(?:program|engagement|placement|term)\b",
            " ".join(responsibilities),
        )
        if match:
            duration_months = int(float(match.group(1)))
            duration_source = "explicit_narrative"
            duration_confidence = 0.80

    return {
        "job_title": header["job_title"],
        "company": header["company"],
        "location": header.get("location"),
        "employment_type": _employment_type(header["job_title"], volunteer=volunteer),
        "volunteer": volunteer,
        "start_date": None,
        "end_date": None,
        "start_year": None,
        "end_year": None,
        "current": False,
        "periods": [],
        "period_count": 0,
        "raw_date_text": raw_date,
        "date_mode": "placeholder",
        "date_status": "placeholder_unresolved",
        "date_validation": {
            "valid": False,
            "reason": "template_date_placeholder",
        },
        "duration_months": duration_months,
        "duration_source": duration_source,
        "duration_confidence": duration_confidence,
        "description": " ".join(responsibilities[:2]),
        "responsibilities": responsibilities,
        "technologies": [],
        "metrics": metrics,
        "raw_text": raw_text,
        "confidence": 94,
        "responsibilities_scope": "role_specific",
        "responsibility_scope": "role_specific",
        "shared_role_responsibilities": False,
        "responsibility_attribution": "role_specific",
        "metrics_attribution": "role_specific" if metrics else "none_provided",
        "source_company_line": header["company"],
        "source_role_line": header["job_title"],
        "source_block_ids": header.get("source_block_ids", []),
        "layout_pattern": "single_column_with_aligned_metadata",
        "source_completeness_status": "template_placeholder_dates",
        "field_quality": {
            "status": "ok",
            "quality_status": "source_placeholder",
            "score": 88,
            "warnings": [],
            "informational_warnings": ["dates_are_template_placeholders"],
        },
    }


def _extract_aligned_entries(result: dict, section_name: str, *, volunteer: bool) -> list[dict]:
    rows = _rows_for_section(_layout_rows(result), section_name)
    entries: list[dict] = []
    index = 0
    while index < len(rows):
        header = _header_at(rows, index)
        if not header:
            index += 1
            continue
        next_header_index = len(rows)
        probe = header["role_row_index"] + 1
        while probe < len(rows):
            if _header_at(rows, probe):
                next_header_index = probe
                break
            probe += 1
        responsibilities = _collect_responsibilities(
            rows,
            header["role_row_index"] + 1,
            next_header_index,
        )
        entries.append(_entry_from_header(result, header, responsibilities, volunteer=volunteer))
        index = max(next_header_index, header["role_row_index"] + 1)
    return entries


def _text_fallback_placeholder_entries(result: dict, section_name: str, *, volunteer: bool) -> list[dict]:
    sections = _extract_section_texts(result)
    lines = [line.strip() for line in sections.get(section_name, "").splitlines() if line.strip()]
    entries: list[dict] = []
    for index, line in enumerate(lines):
        if not _is_placeholder_date(line):
            continue
        nearby = lines[max(0, index - 4): min(len(lines), index + 2)]
        title = next((value for value in reversed(nearby) if _is_role_line(value)), None)
        if not title:
            continue
        title_index = max(i for i in range(max(0, index - 4), min(len(lines), index + 2)) if lines[i] == title)
        company = next((lines[i] for i in range(title_index - 1, max(-1, title_index - 5), -1) if _is_company_line(lines[i])), None)
        location = next((value for value in nearby if _is_location_line(value)), None)
        if not company:
            continue
        next_date = next((i for i in range(index + 1, len(lines)) if _is_placeholder_date(lines[i])), len(lines))
        responsibilities = [
            _strip_bullet(value)
            for value in lines[index + 1:next_date]
            if _strip_bullet(value) and _norm_heading(_strip_bullet(value)).split()[:1]
            and _norm_heading(_strip_bullet(value)).split()[0] in _ACTION_WORDS
        ]
        header = {
            "company": company,
            "location": location,
            "job_title": title,
            "raw_date_text": line,
            "source_block_ids": [],
        }
        entries.append(_entry_from_header(result, header, responsibilities, volunteer=volunteer))
    unique: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        key = (_norm(entry["company"]), _norm(entry["job_title"]), _norm(entry["raw_date_text"]))
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


def reconstruct_placeholder_experience(result: dict, profile: dict) -> None:
    if not profile.get("is_template"):
        return
    professional = _extract_aligned_entries(result, "experience", volunteer=False)
    if len(professional) < 2:
        professional = _text_fallback_placeholder_entries(result, "experience", volunteer=False)
    volunteer = _extract_aligned_entries(result, "volunteer", volunteer=True)
    if not volunteer:
        volunteer = _text_fallback_placeholder_entries(result, "volunteer", volunteer=True)
    if not professional:
        return

    experience = result.setdefault("experience", {})
    if "legacy_extraction" not in experience:
        experience["legacy_extraction"] = {
            "experiences": copy.deepcopy(experience.get("experiences", [])),
            "count": experience.get("count"),
            "mode": experience.get("mode"),
            "reason": "replaced_by_placeholder_aware_aligned_row_parser",
        }

    entries = professional + volunteer
    volunteer_months = sum(int(item.get("duration_months") or 0) for item in volunteer)
    informational = [
        f"experience_{index}_date_placeholder_unresolved"
        for index in range(1, len(entries) + 1)
    ]
    experience.update({
        "experiences": entries,
        "experience_groups": [],
        "shared_responsibility_group_count": 0,
        "count": len(entries),
        "professional_role_count": len(professional),
        "volunteer_role_count": len(volunteer),
        "has_experience": True,
        "total_experience_months": volunteer_months,
        "total_experience_years": round(volunteer_months / 12, 1) if volunteer_months else 0,
        "professional_experience_months": 0,
        "professional_experience_years": 0,
        "professional_duration_status": "not_computable_placeholder_dates",
        "paid_experience_months": 0,
        "volunteer_experience_months": volunteer_months,
        "volunteer_experience_years": round(volunteer_months / 12, 1) if volunteer_months else 0,
        "volunteer_duration_status": "explicit_narrative" if volunteer_months else "not_computable_placeholder_dates",
        "total_validated_experience_months": volunteer_months,
        "total_validated_experience_years": round(volunteer_months / 12, 1) if volunteer_months else 0,
        "current_position": None,
        "top_companies": _unique_strings([item.get("company") for item in professional]),
        "top_titles": _unique_strings([item.get("job_title") for item in professional]),
        "overlapping_experiences": [],
        "overlap_count": 0,
        "experience_score": 90,
        "experience_quality": {
            "status": "ok",
            "score": 90,
            "valid_count": len(entries),
            "rejected_count": 0,
            "warnings": [],
            "informational_warnings": informational,
            "entry_quality": [copy.deepcopy(item["field_quality"]) for item in entries],
            "source_readiness_status": "template_placeholder_dates",
        },
        "rejected_entries": [],
        "layout_mode": "aligned_metadata_rows",
        "layout_pattern": "single_column_with_aligned_metadata",
        "row_pairing": {
            "left_fields": ["company", "job_title"],
            "right_fields": ["location", "date"],
        },
        "mode": "placeholder_aware_layout_reconstruction",
    })

    activities = []
    for item in volunteer:
        activities.append({
            "organization": item.get("company"),
            "job_title": item.get("job_title"),
            "location": item.get("location"),
            "raw_date_text": item.get("raw_date_text"),
            "date_status": item.get("date_status"),
            "duration_months": item.get("duration_months"),
            "duration_source": item.get("duration_source"),
            "responsibilities": copy.deepcopy(item.get("responsibilities", [])),
            "source_section": "volunteer",
        })
    experience["undated_volunteer_activities"] = activities
    experience["undated_volunteer_activity_count"] = len(activities)
    experience["volunteer_date_status"] = "placeholder_unresolved" if activities else "not_applicable"

    experience["recommendations"] = [
        {
            "severity": "high",
            "type": "placeholder_employment_dates",
            "message": "Replace the employment date placeholders with actual start and end dates.",
            "affected_role_count": len(professional),
        }
    ]
    if volunteer:
        experience["recommendations"].append({
            "severity": "high",
            "type": "placeholder_volunteer_dates",
            "message": "Replace the volunteer date placeholder with the actual program dates.",
            "affected_role_count": len(volunteer),
        })


# ---------------------------------------------------------------------------
# Education, contact, skills, metrics, and source-readiness policies
# ---------------------------------------------------------------------------


def reconstruct_placeholder_education(result: dict, profile: dict) -> None:
    if not profile.get("is_template"):
        return

    education = result.setdefault(
        "education",
        {},
    )
    existing_entries = [
        item
        for item
        in list(
            education.get(
                "education",
                [],
            )
            or []
        )
        if isinstance(item, dict)
    ]
    legacy = (
        education.get(
            "legacy_extraction",
            {},
        )
        or {}
    )
    legacy_entries = [
        item
        for item
        in list(
            legacy.get(
                "education",
                [],
            )
            or []
        )
        if isinstance(item, dict)
    ]

    def is_completed_entry(
        entry: dict,
    ) -> bool:
        return bool(
            entry.get("degree")
            and entry.get("institution")
            and (
                entry.get("graduation_year")
                or entry.get("end_date")
                or entry.get(
                    "graduation_date_status"
                )
                == "provided"
            )
            and entry.get(
                "graduation_date_status"
            )
            != "placeholder_unresolved"
        )

    completed_entries = [
        item
        for item
        in existing_entries
        if is_completed_entry(item)
    ]
    if not completed_entries:
        completed_entries = [
            item
            for item
            in legacy_entries
            if is_completed_entry(item)
        ]

    if completed_entries:
        unique_entries: list[dict] = []
        seen_entries: set[
            tuple[str, str, str]
        ] = set()
        for item in completed_entries:
            key = (
                _norm(item.get("degree")),
                _norm(item.get("institution")),
                str(
                    item.get("graduation_year")
                    or item.get("end_date")
                    or ""
                ),
            )
            if key in seen_entries:
                continue
            seen_entries.add(key)
            unique_entries.append(
                copy.deepcopy(item)
            )

        score = int(
            legacy.get(
                "score",
                education.get(
                    "education_score",
                    90,
                ),
            )
            or 90
        )
        education.update({
            "education": unique_entries,
            "count": len(unique_entries),
            "has_education": bool(unique_entries),
            "highest_degree": (
                education.get(
                    "highest_degree"
                )
                or (
                    unique_entries[0].get(
                        "degree"
                    )
                    if unique_entries
                    else None
                )
            ),
            "education_score": max(
                90,
                score,
            ),
            "education_quality": {
                "status": "ok",
                "score": max(
                    90,
                    score,
                ),
                "warnings": [],
                "informational_warnings": [],
                "entry_count": len(
                    unique_entries
                ),
                "source_readiness_status":
                    "complete_source",
            },
            "recommendations": [{
                "severity": "good",
                "type": "complete",
                "message":
                    "Education section looks complete.",
            }],
            "mode":
                "completed_education_preserved",
        })
        return

    rows = _rows_for_section(_layout_rows(result), "education")
    institution = school = location = degree_line = raw_date = None
    for row in rows:
        left = _row_left_content(row)
        right = _row_right_content(row)
        if not institution and _is_company_line(left) and re.search(r"(?i)\b(?:university|college|school|institute|academy)\b", left):
            institution = left
            location = right if _is_location_line(right) else None
            continue
        if institution and not degree_line and re.search(r"(?i)\b(?:bachelor|master|doctor|diploma|certificate|degree)\b", left):
            degree_line = left
            raw_date = right if _is_placeholder_date(right) else None
            break

    if not institution or not degree_line:
        raw_text = str((result.get("education", {}) or {}).get("raw_education_text") or "")
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        institution = institution or next((line for line in lines if re.search(r"(?i)\b(?:university|college|school|institute|academy)\b", line)), None)
        degree_line = degree_line or next((line for line in lines if re.search(r"(?i)\b(?:bachelor|master|doctor|diploma|certificate|degree)\b", line)), None)
        location = location or next((line for line in lines if _is_location_line(line)), None)
        raw_date = raw_date or next((line for line in lines if _is_placeholder_date(line)), None)
    if not institution or not degree_line:
        return

    parenthetical = re.match(r"^(.*?)\s*\((.+)\)\s*$", institution)
    if parenthetical:
        institution_name = parenthetical.group(1).strip()
        school = parenthetical.group(2).strip()
    else:
        institution_name = institution.strip()

    degree_parts = [part.strip() for part in degree_line.split(",", 1)]
    degree = degree_parts[0]
    field = None
    if len(degree_parts) > 1:
        field = re.sub(
            r"(?i)\b(?:specialization|specialisation|major|concentration|focus)\b.*$",
            "",
            degree_parts[1],
        ).strip(" ,-:") or degree_parts[1].strip()

    if "legacy_extraction" not in education:
        education["legacy_extraction"] = {
            "education": copy.deepcopy(education.get("education", [])),
            "score": education.get("education_score"),
            "reason": "replaced_by_placeholder_aware_education_pairing",
        }
    entry = {
        "degree": degree,
        "field": field,
        "institution": institution_name,
        "school": school,
        "location": location,
        "start_date": None,
        "end_date": None,
        "graduation_year": None,
        "raw_date_text": raw_date,
        "graduation_date_status": "placeholder_unresolved" if raw_date else "not_provided_in_source",
        "date_validation": {
            "valid": False,
            "reason": "template_date_placeholder",
        } if raw_date else None,
        "gpa": None,
        "honors": None,
        "accreditation": None,
        "description": "",
        "current": False,
        "raw_text": "\n".join(value for value in (institution, location, degree_line, raw_date) if value),
        "confidence": 94,
        "field_quality": {
            "status": "ok",
            "score": 88,
            "warnings": [],
            "informational_warnings": ["graduation_date_placeholder_unresolved"] if raw_date else ["graduation_date_not_provided_in_source"],
        },
        "education_completeness_score": 88,
    }
    education.update({
        "education": [entry],
        "highest_degree": degree.split(" of ", 1)[0],
        "education_score": 88,
        "education_quality": {
            "status": "ok",
            "score": 88,
            "warnings": [],
            "informational_warnings": ["education_entry_1:graduation_date_placeholder_unresolved"] if raw_date else [],
            "entry_count": 1,
            "source_readiness_status": "template_placeholder_date" if raw_date else "partial_source",
        },
        "recommendations": [{
            "severity": "high",
            "type": "placeholder_graduation_date",
            "message": f'Replace the graduation date placeholder "{raw_date}" with the actual graduation date.' if raw_date else "Add the graduation date when available.",
        }],
        "count": 1,
        "has_education": True,
        "rejected_entries": [],
        "mode": "placeholder_aware_aligned_education",
    })


def apply_contact_placeholder_policy(result: dict, profile: dict) -> None:
    if not profile.get("is_template"):
        return
    contact = result.setdefault("contact", {})
    candidates = (contact.get("candidates", {}) or {}).get("names", []) or []
    placeholder_candidate = next(
        (
            str(item.get("value") or "").strip()
            for item in candidates
            if isinstance(item, dict) and _PLACEHOLDER_NAME_RE.match(str(item.get("value") or "").strip())
        ),
        None,
    )
    raw_name = contact.get("name")
    if _is_placeholder_name(raw_name) or placeholder_candidate:
        if "raw_name" not in contact and raw_name is not None:
            contact["raw_name"] = raw_name
        contact["name_placeholder"] = contact.get("name_placeholder") or placeholder_candidate or raw_name
        contact["name"] = None
        contact["name_status"] = "placeholder"
        contact.setdefault("confidence", {})["name"] = 0.0

    email = contact.get("email")
    if _is_placeholder_email(email):
        if "raw_email" not in contact:
            contact["raw_email"] = email
        contact["email_status"] = "placeholder"
        contact.setdefault("confidence", {})["email"] = 0.0

    phone = contact.get("phone")
    if _is_placeholder_phone(phone):
        if "raw_phone" not in contact:
            contact["raw_phone"] = phone
        contact["phone_status"] = "placeholder"
        contact.setdefault("confidence", {})["phone"] = 0.0

    location = contact.get("location")
    location_confidence = float(
        (
            contact.get(
                "confidence",
                {},
            )
            or {}
        ).get(
            "location",
            0.0,
        )
        or 0.0
    )
    evidence = (
        (
            contact.get(
                "evidence",
                {},
            )
            or {}
        ).get(
            "location"
        )
        or {}
    )
    evidence_text = (
        str(evidence.get("text") or "")
        if isinstance(evidence, dict)
        else ""
    )
    location_is_placeholder = bool(
        _is_placeholder_location(location)
        or _is_placeholder_location(
            evidence_text
        )
    )
    low_confidence_location = bool(
        location
        and location_confidence < 0.30
    )

    if (
        location_is_placeholder
        or low_confidence_location
    ):
        if "raw_location" not in contact:
            contact["raw_location"] = location
        contact["location"] = None
        contact["location_status"] = (
            "unverified_or_placeholder"
        )
        contact.setdefault(
            "confidence",
            {},
        )["location"] = 0.0
    elif location:
        contact["location_status"] = "resolved"

    placeholder_fields = [
        field
        for field
        in (
            "name",
            "email",
            "phone",
            "location",
        )
        if contact.get(
            f"{field}_status"
        )
        in {
            "placeholder",
            "unverified_or_placeholder",
        }
    ]

    existing_quality = (
        contact.get("quality", {})
        or {}
    )
    if placeholder_fields:
        contact["quality"] = {
            **existing_quality,
            "status": "source_placeholder",
            "score": min(
                25,
                int(
                    existing_quality.get(
                        "score",
                        25,
                    )
                    or 25
                ),
            ),
            "warnings": [
                f"{field}_placeholder_or_unverified"
                for field in placeholder_fields
            ],
        }
        contact["recommendations"] = [{
            "severity": "high",
            "type": "replace_placeholder_contact",
            "message": (
                "Replace only the unresolved "
                "placeholder contact fields with "
                "real candidate information."
            ),
            "fields": placeholder_fields,
        }]
    else:
        contact["quality"] = {
            **existing_quality,
            "status": (
                "needs_review"
                if existing_quality.get(
                    "status"
                )
                in {
                    "source_placeholder",
                    "degraded",
                }
                else existing_quality.get(
                    "status",
                    "needs_review",
                )
            ),
            "warnings": [
                warning
                for warning
                in list(
                    existing_quality.get(
                        "warnings",
                        [],
                    )
                    or []
                )
                if "placeholder" not in str(
                    warning
                )
            ],
        }
        contact["recommendations"] = [
            item
            for item
            in list(
                contact.get(
                    "recommendations",
                    [],
                )
                or []
            )
            if item.get("type")
            != "replace_placeholder_contact"
        ]

    summary = result.setdefault("summary", {})
    summary["name"] = contact.get("name")
    summary["email"] = contact.get("email")
    summary["phone"] = contact.get("phone")
    summary["location"] = contact.get("location")


def _explicit_r_programming(text: str) -> bool:
    return bool(re.search(
        r"(?i)\b(?:r\s+programming|programming\s+in\s+r|using\s+r|r\s+language|rstudio|tidyverse|ggplot2)\b",
        text,
    ))


def refine_template_skills(result: dict, profile: dict) -> None:
    if not profile.get("is_template"):
        return
    skills = result.setdefault("skills", {})
    text = str((result.get("extracted_resume_text", {}) or {}).get("analysis_text") or "")

    if not _explicit_r_programming(text):
        for key in ("all_skills", "hard_skills", "soft_skills", "general_skills"):
            skills[key] = [value for value in skills.get(key, []) or [] if _norm(value) != "r"]
        categorized = skills.get("categorized_skills", {}) or {}
        for category in list(categorized):
            categorized[category] = [value for value in categorized.get(category, []) or [] if _norm(value) != "r"]
        removed = skills.setdefault("skill_filtering", {}).setdefault("removed_false_positives", [])
        record = {
            "skill": "R",
            "reason": "accounting_A/R_abbreviation_without_R_programming_context",
        }
        if record not in removed:
            removed.append(record)

    tool_patterns = [
        (r"(?i)\bcaseware\b", "Caseware", "finance_accounting_software"),
        (r"(?i)\btaxprep\b", "Taxprep", "finance_accounting_software"),
        (r"(?i)\b(?:microsoft|ms)\s+access\b", "Microsoft Access", "productivity_tools"),
        (
            r"(?i)\b(?:experience\s+using|proficient\s+in|skilled\s+in|"
            r"(?:tools?|software|databases?)\s*[:\-])"
            r"[^.\n;]{0,80}\baccess\b",
            "Microsoft Access",
            "productivity_tools",
        ),
        (r"(?i)\bquickbooks\b", "QuickBooks", "finance_accounting_software"),
        (r"(?i)\b(?:microsoft\s+|ms\s+)?excel\b", "Microsoft Excel", "productivity_tools"),
        (r"(?i)\b(?:microsoft\s+|ms\s+)?powerpoint\b", "Microsoft PowerPoint", "productivity_tools"),
        (r"(?i)\bkeynote(?:\s+for\s+mac)?\b", "Apple Keynote", "productivity_tools"),
    ]
    detected_tools: list[tuple[str, str]] = []
    for pattern, canonical, category in tool_patterns:
        if re.search(pattern, text):
            detected_tools.append((canonical, category))

    hard = _unique_strings(list(skills.get("hard_skills", []) or []) + [item[0] for item in detected_tools])
    all_skills = _unique_strings(list(skills.get("all_skills", []) or []) + [item[0] for item in detected_tools])
    categorized = copy.deepcopy(skills.get("categorized_skills", {}) or {})
    for canonical, category in detected_tools:
        categorized.setdefault(category, [])
        categorized[category] = _unique_strings(list(categorized[category]) + [canonical])
    skills["hard_skills"] = hard
    skills["all_skills"] = all_skills
    skills["categorized_skills"] = categorized
    skills["top_technologies"] = _unique_strings([item[0] for item in detected_tools] + list(skills.get("top_technologies", []) or []))

    accounting_patterns = [
        r"(?i)\baccounting\b", r"(?i)\bbookkeeper\b", r"(?i)\bgeneral ledger\b",
        r"(?i)\bA/P\b", r"(?i)\bA/R\b", r"(?i)\btax(?:ation|prep| return)\b",
        r"(?i)\baccounts receivable\b", r"(?i)\bquickbooks\b", r"(?i)\bcaseware\b",
    ]
    evidence = _unique_strings([
        match.group(0)
        for pattern in accounting_patterns
        for match in re.finditer(pattern, text)
    ])
    if len(evidence) >= 4:
        skills["detected_sector"] = "finance_accounting"
        skills["sector"] = "finance_accounting"
        skills["sector_label"] = "Finance / Accounting"
        skills["sector_evidence"] = evidence
        skills["role_family"] = "accounting"
        skills["current_role"] = "accounting_assistant"
        skills["primary_title"] = "Bookkeeper/Accounting Assistant"
        skills["seniority"] = "junior"
        match = skills.setdefault("sector_match", {})
        match.update({
            "sector": "Finance / Accounting",
            "sector_key": "finance_accounting",
            "status": "sector_detected_job_description_required",
            "evidence_skills": evidence,
            "evidence_count": len(evidence),
        })
        result.setdefault("summary", {})["job_title"] = "Bookkeeper/Accounting Assistant"
        result.setdefault("contact", {})["job_title"] = "Bookkeeper/Accounting Assistant"

    skills["total_count"] = len(_unique_strings(list(skills.get("hard_skills", [])) + list(skills.get("soft_skills", []))))
    skills["hard_count"] = len(skills.get("hard_skills", []) or [])
    skills["soft_count"] = len(skills.get("soft_skills", []) or [])
    skills["categorized_count"] = sum(len(values or []) for values in categorized.values())
    skills["skills_score"] = max(88, int(skills.get("skills_score", 0) or 0))
    skills["skills_quality"] = {"status": "ok", "score": skills["skills_score"], "warnings": []}


def augment_document_metrics(result: dict) -> None:
    sections = _extract_section_texts(result)
    patterns = [
        (
            re.compile(r"(?i)\b(?:over|more than|up to|approximately|about|around)\s+\d[\d,]*(?:\.\d+)?\s+[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,3}"),
            "quantity",
        ),
        (
            re.compile(r"(?i)\b\d+(?:\.\d+)?\s*[- ]\s*(?:month|year|week|day)s?\s+(?:program|project|engagement|contract|placement|term)\b"),
            "duration",
        ),
        (
            re.compile(r"(?i)\btop\s+\d+(?:\.\d+)?%\s+of\s+(?:their|the|his|her)\s+[^,\n.;]{1,45}"),
            "ranking",
        ),
    ]
    reconciliation = result.setdefault("evidence_reconciliation", {})
    existing = list(reconciliation.get("document_metrics", []) or [])
    existing_keys = {_norm(item.get("value")) for item in existing if isinstance(item, dict)}
    for section_name, text in sections.items():
        for line in str(text or "").splitlines():
            if _is_placeholder_date(line):
                continue
            for pattern, metric_type in patterns:
                for match in pattern.finditer(line):
                    value = re.sub(r"\s+", " ", match.group(0)).strip(" ,.;")
                    if metric_type == "quantity":
                        concise = re.match(
                            r"(?i)^((?:over|more than|up to|approximately|about|around)\s+"
                            r"\d[\d,]*(?:\.\d+)?\s+[A-Za-z][A-Za-z-]*)",
                            value,
                        )
                        if concise:
                            value = concise.group(1)
                    key = _norm(value)
                    if not key or key in existing_keys:
                        continue
                    number_match = re.search(r"\d[\d,]*(?:\.\d+)?", value)
                    normalized_value: int | float | None = None
                    if number_match:
                        number = float(number_match.group(0).replace(",", ""))
                        normalized_value = int(number) if number.is_integer() else number
                    existing.append({
                        "value": value,
                        "normalized_value": normalized_value,
                        "metric_type": metric_type,
                        "approximate": bool(re.search(r"(?i)\b(?:over|more than|up to|approximately|about|around)\b", value)),
                        "evidence": [{
                            "section": section_name,
                            "text": line.strip(),
                            "source_type": metric_type,
                        }],
                    })
                    existing_keys.add(key)
    reconciliation["document_metrics"] = existing
    reconciliation["canonical_metric_count"] = len(existing)
    experience = result.get("experience")
    if isinstance(experience, dict):
        experience["document_metrics"] = copy.deepcopy(existing)


def build_source_readiness(result: dict, profile: dict, date_placeholders: dict) -> None:
    if not profile.get("is_template"):
        result.setdefault("source_readiness", {
            "status": "ready",
            "score": 100,
            "score_cap": 100,
            "warnings": [],
            "required_actions": [],
        })
        return
    contact = result.get("contact", {}) or {}
    warnings = ["document_is_template"]
    if contact.get("name_status") == "placeholder":
        warnings.append("candidate_identity_placeholder")
    if any(contact.get(f"{field}_status") == "placeholder" for field in ("email", "phone")):
        warnings.append("contact_details_placeholder")
    if contact.get("location_status") == "unverified_or_placeholder":
        warnings.append("location_placeholder_or_unverified")
    if date_placeholders.get("detected"):
        warnings.append("date_placeholders_detected")
        if (date_placeholders.get("counts_by_section", {}) or {}).get("experience"):
            warnings.append("professional_dates_not_resolved")

    required_actions: list[str] = []
    if contact.get("name_status") in {
        "placeholder",
        "unresolved",
    }:
        required_actions.append(
            "Replace the candidate-name placeholder "
            "with the real candidate name."
        )
    if contact.get("email_status") in {
        "placeholder",
        "unresolved",
    }:
        required_actions.append(
            "Add a valid candidate email address."
        )
    if contact.get("phone_status") in {
        "placeholder",
        "unresolved",
    }:
        required_actions.append(
            "Add a valid candidate phone number."
        )
    if contact.get("location_status") in {
        "placeholder",
        "unverified_or_placeholder",
    }:
        required_actions.append(
            "Replace the generic location with "
            "the real candidate location."
        )
    if date_placeholders.get("count"):
        required_actions.append(
            "Replace all date placeholders with "
            "actual dates."
        )

    result["source_readiness"] = {
        "status": "template_incomplete",
        "score": 35,
        "score_cap": 60,
        "trusted": False,
        "warnings": _unique_strings(warnings),
        "required_actions": _unique_strings(
            required_actions
        ),
        "meaning": (
            "The extractor can read the document, "
            "but unresolved template content prevents "
            "a hiring-ready ATS score."
        ),
    }

    issues = [
        item
        for item
        in result.get(
            "document_issues",
            [],
        )
        or []
        if isinstance(item, dict)
        and item.get("type")
        not in {
            "template_document",
            "placeholder_identity",
            "placeholder_dates",
            "placeholder_location",
        }
    ]
    issues.append({
        "type": "template_document",
        "severity": "high",
        "message": (
            "The uploaded document is an unfinished "
            "resume template."
        ),
    })

    if contact.get("name_status") in {
        "placeholder",
        "unresolved",
    } or any(
        contact.get(f"{field}_status")
        in {
            "placeholder",
            "unresolved",
        }
        for field in ("email", "phone")
    ):
        issues.append({
            "type": "placeholder_identity",
            "severity": "high",
            "message": (
                "Candidate identity or contact fields "
                "contain unresolved placeholders."
            ),
        })

    placeholder_count = int(
        date_placeholders.get(
            "count",
            0,
        )
        or 0
    )
    if placeholder_count:
        issues.append({
            "type": "placeholder_dates",
            "severity": "high",
            "message": (
                f"Detected {placeholder_count} "
                "unresolved date placeholder "
                "expressions."
            ),
        })

    if contact.get("location_status") in {
        "placeholder",
        "unverified_or_placeholder",
    }:
        issues.append({
            "type": "placeholder_location",
            "severity": "medium",
            "message": (
                "A generic or unverified candidate "
                "location was detected."
            ),
        })

    result["document_issues"] = issues


def clean_stale_extraction_warnings(result: dict, profile: dict) -> None:
    if not profile.get("is_template"):
        return
    quality = result.setdefault("extraction_quality", {})
    stale_patterns = {
        "education_entry_1:missing_institution",
        "education_extraction_degraded",
        "experience_critical_field_unresolved",
        "experience_extraction_degraded",
    }
    existing = list(quality.get("warnings", []) or [])
    resolved = [warning for warning in existing if warning in stale_patterns]
    quality["warnings"] = [warning for warning in existing if warning not in stale_patterns]
    quality["resolved_warnings"] = _unique_strings(list(quality.get("resolved_warnings", []) or []) + resolved)
    components = quality.setdefault("component_scores", {})
    components["contact"] = int(((result.get("contact", {}) or {}).get("quality", {}) or {}).get("score", 25) or 25)
    components["experience"] = int((result.get("experience", {}) or {}).get("experience_score", 90) or 90)
    components["education"] = int((result.get("education", {}) or {}).get("education_score", 88) or 88)
    components["skills"] = int((result.get("skills", {}) or {}).get("skills_score", 88) or 88)
    extraction_components = [value for key, value in components.items() if key != "contact"]
    quality["score"] = round(sum(int(value or 0) for value in extraction_components) / len(extraction_components)) if extraction_components else int(quality.get("score", 0) or 0)
    quality["status"] = "ok" if quality["score"] >= 85 and not quality.get("warnings") else "degraded"
    quality["source_readiness_status"] = "template_incomplete"


def _merge_recommendations(result: dict, profile: dict, date_placeholders: dict) -> None:
    if not profile.get("is_template"):
        return
    contact = result.get("contact", {}) or {}
    sections_found = set((result.get("sections", {}) or {}).get("found_sections", []) or [])
    recommendations = [
        item for item in result.get("recommendations", []) or []
        if isinstance(item, dict)
        and item.get("type") not in {
            "missing_email", "missing_phone", "replace_placeholder_contact",
            "replace_date_placeholders", "template_incomplete", "dedicated_skills_section",
        }
    ]
    recommendations.append({
        "severity": "high",
        "type": "template_incomplete",
        "area": "source_readiness",
        "message": "Complete all unresolved template content before using the score for hiring or ATS decisions.",
    })
    unresolved_contact = [
        field for field in ("name", "email", "phone")
        if contact.get(f"{field}_status") in {"placeholder", "unresolved"}
    ]
    if unresolved_contact:
        recommendations.append({
            "severity": "high",
            "type": "replace_placeholder_contact",
            "area": "contact",
            "message": "Replace unresolved or placeholder contact fields: " + ", ".join(unresolved_contact) + ".",
        })
    if int(date_placeholders.get("count", 0) or 0) > 0:
        recommendations.append({
            "severity": "high",
            "type": "replace_date_placeholders",
            "area": "dates",
            "message": f"Replace all {date_placeholders.get('count', 0)} detected date placeholders with actual dates.",
            "counts_by_section": date_placeholders.get("counts_by_section", {}),
        })
    if "skills" not in sections_found and int((result.get("skills", {}) or {}).get("total_count", 0) or 0) > 0:
        recommendations.append({
            "severity": "medium",
            "type": "dedicated_skills_section",
            "area": "skills",
            "message": "Consider adding a dedicated Technical Skills section; skills were found elsewhere but no standalone skills section exists.",
        })
    result["recommendations"] = recommendations


def _pdf_document_assets(file_path: str | Path | None) -> dict:
    base = {
        "has_images": False,
        "image_count": 0,
        "raster_image_count": 0,
        "vector_asset_count": 0,
        "icon_count": 0,
        "candidate_photo_detected": False,
        "candidate_photo_candidates": [],
        "decorative_image_count": 0,
        "image_only_contact_fields": [],
        "text_box_count": 0,
        "drawing_count": 0,
        "shape_count": 0,
        "media": [],
        "analysis_mode": "pdf_pymupdf_asset_inventory",
    }
    if fitz is None or not file_path:
        return base
    path = Path(str(file_path))
    if not path.is_file() or path.suffix.casefold() != ".pdf":
        return base
    try:
        document = fitz.open(path)
    except Exception:
        return base

    media: list[dict] = []
    drawing_count = 0
    try:
        for page_index, page in enumerate(document):
            page_height = float(page.rect.height or 1)
            page_width = float(page.rect.width or 1)
            drawing_count += len(page.get_drawings() or [])
            for image_index, image in enumerate(page.get_images(full=True) or []):
                xref = image[0]
                width_px = int(image[2] or 0)
                height_px = int(image[3] or 0)
                rects = page.get_image_rects(xref) or []
                rect = rects[0] if rects else None
                x_pt = float(rect.x0) if rect is not None else None
                y_pt = float(rect.y0) if rect is not None else None
                width_pt = float(rect.width) if rect is not None else None
                height_pt = float(rect.height) if rect is not None else None
                area_ratio = (
                    (width_pt * height_pt) / (page_width * page_height)
                    if width_pt and height_pt
                    else 0.0
                )
                aspect = width_px / height_px if height_px else None
                icon = bool(
                    (width_px and height_px and width_px * height_px <= 40000)
                    or area_ratio <= 0.012
                )
                photo_score = 0.0
                reasons = []
                if width_px * height_px >= 40000:
                    photo_score += 0.35
                    reasons.append("substantial_raster_resolution")
                if aspect is not None and 0.55 <= aspect <= 1.35:
                    photo_score += 0.25
                    reasons.append("portrait_or_square_aspect")
                if y_pt is not None and y_pt <= page_height * 0.28:
                    photo_score += 0.25
                    reasons.append("header_region")
                if area_ratio >= 0.025:
                    photo_score += 0.15
                    reasons.append("large_page_area")
                candidate = bool(photo_score >= 0.6 and not icon)
                media.append({
                    "page": page_index + 1,
                    "index": image_index,
                    "xref": xref,
                    "width_px": width_px,
                    "height_px": height_px,
                    "x_pt": x_pt,
                    "y_pt": y_pt,
                    "width_pt": width_pt,
                    "height_pt": height_pt,
                    "page_area_ratio": round(area_ratio, 6),
                    "classification": (
                        "candidate_photo_candidate"
                        if candidate
                        else "icon"
                        if icon
                        else "decorative_or_content_image"
                    ),
                    "is_icon": icon,
                    "candidate_photo_candidate": candidate,
                    "candidate_photo_confidence": round(min(1.0, photo_score), 3),
                    "classification_reasons": reasons,
                })
    finally:
        document.close()

    photos = [item for item in media if item.get("candidate_photo_candidate")]
    icons = [item for item in media if item.get("is_icon")]
    decorative = [item for item in media if not item.get("candidate_photo_candidate") and not item.get("is_icon")]
    return {
        **base,
        "has_images": bool(media),
        "image_count": len(media),
        "raster_image_count": len(media),
        "icon_count": len(icons),
        "candidate_photo_detected": bool(photos),
        "candidate_photo_candidates": photos,
        "decorative_image_count": len(decorative),
        "drawing_count": drawing_count,
        "shape_count": drawing_count,
        "media": media,
    }


def _document_structure(result: dict) -> dict:
    file_info = result.get("file", {}) or {}
    file_path = file_info.get("path")
    extension = str(file_info.get("extension") or Path(str(file_path or "")).suffix).casefold()
    if extension == ".docx" and file_path:
        analysis = analyze_docx_package(file_path)
        if analysis.get("status") == "ok":
            dedup = deduplicate_blocks(list(analysis.get("visual_blocks") or analysis.get("blocks") or []))
            analysis["duplicate_analysis"] = dedup.get("duplicate_analysis", {})
            analysis["deduplicated_blocks"] = dedup.get("blocks", [])
            return analysis
        # The serialized analysis may be reviewed on a different machine where
        # the original DOCX path is unavailable. Preserve semantic recovery
        # from the stored blocks instead of losing duplicate/template evidence.
        stored_blocks = list(
            (
                result.get(
                    "layout_data",
                    {},
                )
                or {}
            ).get(
                "blocks",
                [],
            )
            or []
        )
        if not stored_blocks:
            stored_blocks = list(
                (
                    result.get(
                        "text_extraction",
                        {},
                    )
                    or {}
                ).get(
                    "raw_layout_blocks",
                    [],
                )
                or []
            )
        deduplicated = (
            deduplicate_blocks(stored_blocks)
            if stored_blocks
            else {
                "blocks": [],
                "duplicate_analysis":
                    _duplicate_analysis_from_result(
                        result
                    ),
            }
        )
        recomputed_duplicate = (
            deduplicated.get(
                "duplicate_analysis",
                {},
            )
            or {}
        )
        stored_duplicate = (
            result.get(
                "duplicate_analysis",
                {},
            )
            or {}
        )
        analysis["duplicate_analysis"] = (
            stored_duplicate
            if int(
                stored_duplicate.get(
                    "raw_block_count",
                    0,
                )
                or 0
            )
            > int(
                recomputed_duplicate.get(
                    "raw_block_count",
                    0,
                )
                or 0
            )
            else recomputed_duplicate
        )
        analysis["deduplicated_blocks"] = (
            deduplicated.get(
                "blocks",
                [],
            )
            or []
        )
        analysis["document_style"] = (
            result.get("document_style")
            or {}
        )
        analysis["document_assets"] = (
            result.get("document_assets")
            or {}
        )
        return analysis
    return {
        "status": "ok" if extension == ".pdf" else "not_available",
        "file_type": extension.lstrip("."),
        "document_style": extract_dynamic_document_style(file_path),
        "document_assets": _pdf_document_assets(file_path),
        "duplicate_analysis": _duplicate_analysis_from_result(result),
        "warnings": [],
    }


def _duplicate_analysis_from_result(result: dict) -> dict:
    blocks = list((result.get("layout_data", {}) or {}).get("blocks", []) or [])
    if not blocks:
        blocks = list((result.get("text_extraction", {}) or {}).get("raw_layout_blocks", []) or [])
    if not blocks:
        text = str((result.get("extracted_resume_text", {}) or {}).get("raw_text") or "")
        blocks = [
            {"id": f"line_{index}", "text": line, "order": index, "visual_order": index}
            for index, line in enumerate(text.splitlines())
            if line.strip()
        ]
    if not blocks:
        return {
            "raw_block_count": 0,
            "unique_normalized_text_count": 0,
            "clean_block_count": 0,
            "duplicate_occurrence_count": 0,
            "duplicate_ratio": 0.0,
            "mirror_factor": 1,
            "logical_placeholder_slots": [],
            "mode": "no_blocks",
        }
    return deduplicate_blocks(blocks).get("duplicate_analysis", {})


def _full_document_text(result: dict) -> str:
    extracted = result.get("extracted_resume_text", {}) or {}
    return str(
        extracted.get("analysis_text")
        or extracted.get("cleaned_text")
        or extracted.get("ordered_text")
        or extracted.get("raw_text")
        or ""
    )


_GENERIC_TEMPLATE_PATTERNS = {
    "placeholder_job_title": re.compile(r"(?i)\bjob\s+title\b"),
    "placeholder_company_name": re.compile(r"(?i)\bcompany\s+name\b"),
    "placeholder_responsibility": re.compile(r"(?i)\bkey\s+(?:responsibility|achievement)\b"),
    "objective_instruction": re.compile(
        r"(?i)\bdescribe\s+in\s+a\s+few\s+lines\b|"
        r"\bintroduction\s+to\s+your\s+cover\s+letter\b|"
        r"\byour\s+career\s+goals\b"
    ),
}


def _enhance_template_profile(result: dict, profile: dict, structure: dict) -> dict:
    text = _full_document_text(result)
    signals = list(profile.get("signals", []) or [])
    signal_types = {item.get("type") for item in signals if isinstance(item, dict)}
    generic_matches = []
    for signal_type, pattern in _GENERIC_TEMPLATE_PATTERNS.items():
        match = pattern.search(text)
        if match:
            generic_matches.append(signal_type)
            if signal_type not in signal_types:
                signals.append({
                    "type": signal_type,
                    "weight": 0.2,
                    "evidence": match.group(0),
                })
                signal_types.add(signal_type)

    duplicate_analysis = structure.get("duplicate_analysis", {}) or {}
    placeholder_slots = _placeholder_role_slot_count(text, duplicate_analysis)
    if placeholder_slots and "placeholder_role_slots" not in signal_types:
        signals.append({
            "type": "placeholder_role_slots",
            "weight": min(0.35, 0.12 + placeholder_slots * 0.06),
            "evidence_count": placeholder_slots,
        })
        signal_types.add("placeholder_role_slots")

    confidence = min(0.99, round(sum(float(item.get("weight", 0) or 0) for item in signals), 3))
    generic_template = len(generic_matches) >= 2 or placeholder_slots > 0
    is_template = bool(profile.get("is_template") or generic_template)

    contact = result.get("contact", {}) or {}
    education_count = int((result.get("education", {}) or {}).get("count", 0) or 0)
    partially_completed = bool(
        is_template
        and (
            contact.get("name")
            or education_count
            or (result.get("languages", {}) or {}).get("count")
        )
        and generic_template
    )
    unresolved_sections = []
    if _GENERIC_TEMPLATE_PATTERNS["objective_instruction"].search(text):
        unresolved_sections.append("objective")
    if placeholder_slots:
        unresolved_sections.append("experience")

    return {
        **profile,
        "document_type": (
            "partially_completed_resume_template"
            if partially_completed
            else "resume_template"
            if is_template
            else "resume"
        ),
        "is_template": is_template,
        "partially_completed": partially_completed,
        "template_confidence": confidence,
        "signals": signals,
        "signal_types": [item.get("type") for item in signals if isinstance(item, dict)],
        "unresolved_template_sections": unresolved_sections,
        "placeholder_role_slot_count": placeholder_slots,
        "detection_mode": "weighted_generic_template_and_ooxml_signals",
    }


def _placeholder_role_slot_count(
    text: str,
    duplicate_analysis: dict,
) -> int:
    logical = list(
        duplicate_analysis.get(
            "logical_placeholder_slots",
            [],
        )
        or []
    )
    mirror = max(
        1,
        int(
            duplicate_analysis.get(
                "mirror_factor",
                1,
            )
            or 1
        ),
    )

    counts: list[int] = []
    for item in logical:
        item_text = str(
            item.get("text")
            or ""
        )
        if not (
            re.search(
                r"(?i)\bjob\s+title\b",
                item_text,
            )
            or re.search(
                r"(?i)\bcompany\s+name\b",
                item_text,
            )
        ):
            continue

        logical_count = int(
            item.get(
                "logical_slot_count",
                0,
            )
            or 0
        )
        raw_count = int(
            item.get(
                "raw_occurrence_count",
                0,
            )
            or 0
        )
        if logical_count:
            counts.append(logical_count)
        if raw_count:
            counts.append(
                math.ceil(
                    raw_count
                    / mirror
                )
            )

    if counts:
        return max(counts)

    matches = re.findall(
        r"(?is)\bjob\s+title\b"
        r".{0,180}?"
        r"\bcompany\s+name\b"
        r".{0,260}?"
        r"\bkey\s+"
        r"(?:responsibility|achievement)\b",
        text,
    )
    return max(
        0,
        math.ceil(
            len(matches)
            / mirror
        ),
    )



def _generic_template_phrase(value: Any) -> bool:
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").casefold(),
    ).strip()
    return any(
        phrase in normalized
        for phrase in (
            "key responsibility or achievement",
            "key responsibility",
            "key achievement",
            "job title",
            "company name",
            "describe in a few lines",
            "introduction to your cover letter",
            "your career goals",
        )
    )


def _plausible_candidate_name(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or len(text) > 60:
        return False
    if _generic_template_phrase(text):
        return False
    if any(
        character.isdigit()
        for character in text
    ):
        return False
    if any(
        marker in text
        for marker in (
            "@",
            "|",
            ":",
            ",",
        )
    ):
        return False
    normalized = re.sub(
        r"[^a-z]+",
        " ",
        text.casefold(),
    ).strip()
    if normalized in {
        "professional summary",
        "career summary",
        "work experience",
        "professional experience",
        "educational background",
        "technical skills",
        "core competencies",
        "contact information",
        "graphic designer",
        "project manager",
        "software engineer",
        "data analyst",
    }:
        return False

    words = re.findall(
        r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+",
        text,
    )
    return bool(
        2 <= len(words) <= 4
        and len(" ".join(words)) >= 5
    )


def _repair_contact_identity_and_location(
    result: dict,
    structure: dict,
    profile: dict,
) -> None:
    contact = result.setdefault(
        "contact",
        {},
    )
    blocks = list(
        structure.get(
            "deduplicated_blocks",
            [],
        )
        or []
    )
    if not blocks:
        blocks = list(
            (
                result.get(
                    "layout_data",
                    {},
                )
                or {}
            ).get(
                "blocks",
                [],
            )
            or []
        )

    name_candidates: list[dict] = []
    for index, block in enumerate(
        blocks[:20]
    ):
        text = str(
            block.get("text")
            or ""
        ).strip()
        if not _plausible_candidate_name(
            text
        ):
            continue
        normalized = text.casefold()
        if normalized in {
            "graphic designer",
            "project manager",
            "software engineer",
            "data analyst",
        }:
            continue
        score = 0
        if index <= 3:
            score += 60
        elif index <= 8:
            score += 30
        if text.isupper():
            score += 15
        if block.get("bbox") is not None:
            score += 10
        if _is_placeholder_name(text):
            score -= 100
        name_candidates.append({
            "value": " ".join(
                word.capitalize()
                if not word.isupper()
                else word.title()
                for word in text.split()
            ),
            "score": score,
            "source": {
                "page": block.get(
                    "page",
                    1,
                ),
                "text": text,
                "bbox": block.get(
                    "bbox"
                ),
                "block_id": block.get(
                    "id"
                ),
                "is_repeated_header_footer":
                    bool(
                        block.get(
                            "is_repeated_header_footer",
                            False,
                        )
                    ),
            },
        })

    existing_name = contact.get("name")
    allow_template_name_repair = bool(
        profile.get("document_type")
        == "partially_completed_resume_template"
        or (
            existing_name
            and _generic_template_phrase(
                existing_name
            )
        )
    )
    name_needs_repair = bool(
        contact.get("name_status")
        in {
            "placeholder",
            "unresolved",
        }
        or not _plausible_candidate_name(
            existing_name
        )
        or _generic_template_phrase(
            existing_name
        )
        or float(
            (
                contact.get(
                    "confidence",
                    {},
                )
                or {}
            ).get(
                "name",
                0.0,
            )
            or 0.0
        )
        < 0.50
        or not (
            (
                contact.get(
                    "evidence",
                    {},
                )
                or {}
            ).get(
                "name"
            )
        )
    )

    if (
        allow_template_name_repair
        and name_needs_repair
        and name_candidates
    ):
        selected = max(
            name_candidates,
            key=lambda item: item[
                "score"
            ],
        )
        contact["raw_name"] = (
            existing_name
        )
        contact["name"] = selected[
            "value"
        ]
        contact["name_status"] = (
            "resolved"
        )
        contact.setdefault(
            "confidence",
            {},
        )["name"] = min(
            0.99,
            max(
                0.90,
                selected["score"]
                / 100.0,
            ),
        )
        contact.setdefault(
            "evidence",
            {},
        )["name"] = selected[
            "source"
        ]
        contact["name_placeholder"] = None

    rejected_names = []
    accepted_names = []
    for item in list(
        (
            contact.get(
                "candidates",
                {},
            )
            or {}
        ).get(
            "names",
            [],
        )
        or []
    ):
        if _generic_template_phrase(
            item.get("value")
        ):
            rejected_names.append({
                **item,
                "type": "name",
                "reason":
                    "template_instruction_not_candidate_name",
            })
        else:
            accepted_names.append(item)
    contact.setdefault(
        "candidates",
        {},
    )["names"] = accepted_names
    selected_name_key = re.sub(
        r"[^a-z]+",
        " ",
        str(
            contact.get("name")
            or ""
        ).casefold(),
    ).strip()

    combined_rejected = (
        list(
            contact.get(
                "rejected_candidates",
                [],
            )
            or []
        )
        + rejected_names
    )
    deduplicated_rejected: list[dict] = []
    rejected_keys: set[
        tuple[str, str, str]
    ] = set()

    for item in combined_rejected:
        value_key = re.sub(
            r"[^a-z]+",
            " ",
            str(
                item.get("value")
                or ""
            ).casefold(),
        ).strip()
        if (
            selected_name_key
            and value_key
            == selected_name_key
            and item.get("type") == "name"
        ):
            continue

        key = (
            str(
                item.get(
                    "type",
                    "",
                )
            ).casefold(),
            value_key,
            str(
                item.get(
                    "reason",
                    "",
                )
            ).casefold(),
        )
        if key in rejected_keys:
            continue
        rejected_keys.add(key)
        deduplicated_rejected.append(item)

    contact["rejected_candidates"] = (
        deduplicated_rejected
    )

    location = contact.get("location")
    allow_location_recovery = bool(
        not profile.get("is_template")
        or profile.get("document_type")
        == "partially_completed_resume_template"
    )
    if (
        not location
        and allow_location_recovery
    ):
        location_candidates = list(
            (
                contact.get(
                    "candidates",
                    {},
                )
                or {}
            ).get(
                "locations",
                [],
            )
            or []
        )
        valid_locations = [
            item
            for item in location_candidates
            if not _is_placeholder_location(
                item.get("value")
            )
            and not re.search(
                r"(?i)\\b(?:university|college|school|institute)\\b",
                str(
                    item.get("value")
                    or ""
                ),
            )
        ]
        if valid_locations:
            selected_location = max(
                valid_locations,
                key=lambda item: int(
                    item.get(
                        "score",
                        0,
                    )
                    or 0
                ),
            )
            contact["location"] = (
                selected_location.get(
                    "value"
                )
            )
            contact[
                "location_status"
            ] = "resolved"
            contact.setdefault(
                "confidence",
                {},
            )["location"] = max(
                0.60,
                min(
                    0.99,
                    int(
                        selected_location.get(
                            "score",
                            0,
                        )
                        or 0
                    )
                    / 100.0,
                ),
            )
            contact.setdefault(
                "evidence",
                {},
            )["location"] = (
                selected_location.get(
                    "source"
                )
            )

    existing_quality = (
        contact.get("quality", {})
        or {}
    )
    placeholder_fields = [
        field
        for field
        in (
            "name",
            "email",
            "phone",
            "location",
        )
        if contact.get(
            f"{field}_status"
        )
        in {
            "placeholder",
            "unverified_or_placeholder",
        }
    ]
    if not placeholder_fields:
        resolved_count = sum(
            bool(contact.get(field))
            for field in (
                "name",
                "email",
                "phone",
                "location",
            )
        )
        resolved_score = (
            90
            if resolved_count == 4
            else 82
            if resolved_count == 3
            else 70
        )
        contact["quality"] = {
            **existing_quality,
            "status": (
                "ok"
                if resolved_count == 4
                else "needs_review"
            ),
            "score": max(
                resolved_score,
                int(
                    existing_quality.get(
                        "score",
                        resolved_score,
                    )
                    or resolved_score
                ),
            ),
            "warnings": [
                warning
                for warning
                in list(
                    existing_quality.get(
                        "warnings",
                        [],
                    )
                    or []
                )
                if "placeholder"
                not in str(
                    warning
                )
            ],
        }

    summary = result.setdefault(
        "summary",
        {},
    )
    for field in (
        "name",
        "email",
        "phone",
        "location",
        "job_title",
    ):
        summary[field] = contact.get(
            field
        )


def _apply_deduplicated_docx_text(
    result: dict,
    structure: dict,
) -> None:
    extension = str(
        (
            result.get(
                "file",
                {},
            )
            or {}
        ).get(
            "extension",
            ""
        )
    ).casefold()
    if extension != ".docx":
        return

    blocks = list(
        structure.get(
            "deduplicated_blocks",
            [],
        )
        or []
    )
    if not blocks:
        return

    clean_text = "\n".join(
        str(
            item.get("text")
            or ""
        ).strip()
        for item in blocks
        if str(
            item.get("text")
            or ""
        ).strip()
    )
    if not clean_text:
        return

    extracted = result.setdefault(
        "extracted_resume_text",
        {},
    )
    for field in (
        "preliminary_ordered_text",
        "ordered_text",
        "cleaned_text",
    ):
        extracted[field] = clean_text

    current_analysis = str(
        extracted.get(
            "analysis_text"
        )
        or ""
    )
    if (
        len(current_analysis)
        > len(clean_text) * 1.35
        or re.search(
            r"(?i)SKILLSSKILLS|"
            r"EDUCATIONEDUCATION|"
            r"EXPERIENCEEXPERIENCE",
            current_analysis,
        )
    ):
        extracted[
            "analysis_text"
        ] = clean_text


def _repair_section_metadata_from_visual_blocks(
    result: dict,
    structure: dict,
) -> None:
    sections_root = result.setdefault(
        "sections",
        {},
    )
    sections = sections_root.setdefault(
        "sections",
        {},
    )
    skills = result.get(
        "skills",
        {},
    ) or {}
    detected_skills = list(
        skills.get(
            "all_skills",
            [],
        )
        or []
    )

    blocks = list(
        structure.get(
            "deduplicated_blocks",
            [],
        )
        or []
    )
    heading_index = next(
        (
            index
            for index, block
            in enumerate(blocks)
            if re.sub(
                r"[^a-z]+",
                " ",
                str(
                    block.get(
                        "text"
                    )
                    or ""
                ).casefold(),
            ).strip()
            in {
                "skills",
                "technical skills",
                "core skills",
            }
        ),
        None,
    )

    recovered_lines: list[str] = []
    if heading_index is not None:
        heading_block = blocks[
            heading_index
        ]
        heading_column = (
            heading_block.get(
                "column"
            )
        )
        for block in blocks[
            heading_index + 1:
        ]:
            if (
                heading_column
                and block.get(
                    "column"
                )
                != heading_column
            ):
                continue
            text = str(
                block.get("text")
                or ""
            ).strip()
            normalized = re.sub(
                r"[^a-z]+",
                " ",
                text.casefold(),
            ).strip()
            if normalized in {
                "summary",
                "objective",
                "education",
                "experience",
                "work experience",
                "languages",
                "hobbies",
                "interests",
                "projects",
                "certifications",
                "awards",
            }:
                break
            if text:
                recovered_lines.append(
                    text
                )

    if (
        detected_skills
        and heading_index is not None
    ):
        skill_section = sections.setdefault(
            "skills",
            {},
        )
        if not str(
            skill_section.get(
                "content",
                "",
            )
        ).strip():
            skill_section["content"] = (
                "\n".join(
                    recovered_lines
                ).strip()
                or "\n".join(
                    detected_skills
                )
            )
        skill_section["heading"] = (
            skill_section.get(
                "heading"
            )
            or "SKILLS"
        )
        skill_section[
            "source_headings"
        ] = list(dict.fromkeys(
            list(
                skill_section.get(
                    "source_headings",
                    [],
                )
                or []
            )
            + ["SKILLS"]
        ))
        skill_section["words"] = len(
            str(
                skill_section.get(
                    "content",
                    "",
                )
            ).split()
        )
        skill_section["confidence"] = max(
            90,
            int(
                skill_section.get(
                    "confidence",
                    0,
                )
                or 0
            ),
        )

        found = list(
            sections_root.get(
                "found_sections",
                [],
            )
            or []
        )
        if "skills" not in found:
            found.append("skills")
        sections_root[
            "found_sections"
        ] = found

        missing = [
            item
            for item
            in list(
                sections_root.get(
                    "missing_required",
                    [],
                )
                or []
            )
            if item != "skills"
        ]
        sections_root[
            "missing_required"
        ] = missing

        summary = result.setdefault(
            "summary",
            {},
        )
        summary["sections_found"] = found
        summary[
            "missing_required_sections"
        ] = missing


def _repair_contact_from_visual_text(result: dict) -> None:
    text = _full_document_text(result)
    contact = result.setdefault("contact", {})
    existing_email = str(
        contact.get("email")
        or ""
    ).strip()
    existing_email_valid = bool(
        re.fullmatch(
            r"(?i)[\w.+-]+@[\w.-]+\.[A-Z]{2,24}",
            existing_email,
        )
    )

    email_match = None
    if not existing_email_valid:
        for line in text.splitlines():
            candidate = re.search(
                r"(?i)(?<![A-Z0-9._%+-])"
                r"([A-Z0-9._%+-]{1,64})"
                r"\s*@\s*"
                r"([A-Z0-9-]+"
                r"(?:\s*\.\s*[A-Z0-9-]+)+)",
                line,
            )
            if candidate:
                email_match = candidate
                break

    if email_match:
        raw_email = email_match.group(0)
        normalized_domain = re.sub(r"\s+", "", email_match.group(2))
        email = f"{email_match.group(1)}@{normalized_domain}"
        if re.fullmatch(
            r"(?i)[\w.+-]+@[\w.-]+\.[A-Z]{2,24}",
            email,
        ):
            contact["email"] = email
            contact["email_raw"] = raw_email
            contact["email_normalization"] = (
                "removed_internal_style_whitespace"
            )
            contact["email_status"] = (
                "placeholder"
                if _is_placeholder_email(email)
                else "resolved"
            )
            contact.setdefault(
                "confidence",
                {},
            )["email"] = max(
                float(
                    (
                        contact.get(
                            "confidence",
                            {},
                        )
                        or {}
                    ).get(
                        "email",
                        0,
                    )
                    or 0
                ),
                0.9,
            )

    phone_match = re.search(r"(?<!\d)(\+\s*\d[\d .()/-]{7,}\d)(?!\d)", text)
    if phone_match:
        raw_phone = phone_match.group(1).strip()
        compact = re.sub(r"[^+\d()]", "", raw_phone)
        trunk = re.match(r"\+(\d{1,3})\(0\)(\d+)$", compact)
        if trunk:
            phone = "+" + trunk.group(1) + trunk.group(2)
        else:
            phone = "+" + re.sub(r"\D", "", raw_phone)
        contact["phone"] = phone
        contact["phone_raw"] = raw_phone
        contact["phone_status"] = (
            "placeholder" if _is_placeholder_phone(phone) else "resolved"
        )
        contact.setdefault("confidence", {})["phone"] = max(
            float((contact.get("confidence", {}) or {}).get("phone", 0) or 0),
            0.85,
        )

    if not contact.get("job_title"):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        role_re = re.compile(
            r"(?i)^(?:senior|junior|lead|principal|chief|assistant|associate|graphic|"
            r"product|project|accounting|administrative|software|data|marketing|sales|"
            r"operations|financial)?\s*(?:designer|manager|director|analyst|developer|"
            r"engineer|assistant|accountant|bookkeeper|specialist|coordinator|consultant|"
            r"representative|administrator|officer|advisor|executive|intern|trainee)$"
        )
        for line in lines:
            if role_re.fullmatch(line) and _norm_heading(line) not in _SECTION_ALIASES.get("experience", set()):
                contact["job_title"] = " ".join(word.capitalize() for word in line.split())
                break

    resolved_fields = sum(
        contact.get(field) is not None
        for field in ("name", "email", "phone", "location")
    )
    if resolved_fields >= 3 and not any(
        contact.get(f"{field}_status") == "placeholder"
        for field in ("name", "email", "phone")
    ):
        contact["quality"] = {
            "status": "ok" if resolved_fields == 4 else "needs_review",
            "score": 90 if resolved_fields == 4 else 82,
            "warnings": [],
        }
        contact["recommendations"] = [
            item for item in list(contact.get("recommendations", []) or [])
            if item.get("type") not in {"missing_email", "missing_phone"}
        ]


def _repair_languages_from_text(result: dict) -> None:
    text = _full_document_text(result)
    pair_re = re.compile(
        r"(?ix)\b(?P<language>[A-Za-z][A-Za-z .'-]{1,28}?)\s*[-–—:]\s*"
        r"(?P<level>A1|A2|B1|B2|C1|C2)\b"
    )
    known = {
        "english", "spanish", "chinese", "mandarin", "cantonese", "german", "french",
        "italian", "portuguese", "arabic", "hindi", "urdu", "russian", "japanese",
        "korean", "dutch", "swedish", "norwegian", "danish", "finnish", "polish",
        "turkish", "greek", "hebrew", "persian", "farsi", "bengali", "punjabi",
        "vietnamese", "thai", "indonesian", "malay", "swahili",
    }
    mapping = {
        "A1": ("Beginner", 1), "A2": ("Elementary", 2),
        "B1": ("Intermediate", 3), "B2": ("Upper Intermediate", 4),
        "C1": ("Advanced", 5), "C2": ("Proficient", 6),
    }
    records = []
    seen = set()
    for line in text.splitlines():
        for match in pair_re.finditer(line):
            words = match.group("language").strip().casefold().split()
            language = None
            for width in (2, 1):
                candidate = " ".join(words[-width:])
                if candidate in known:
                    language = " ".join(word.capitalize() for word in candidate.split())
                    break
            if not language or language.casefold() in seen:
                continue
            seen.add(language.casefold())
            cefr = match.group("level").upper()
            label, rank = mapping[cefr]
            records.append({
                "language": language,
                "proficiency": label,
                "proficiency_rank": rank,
                "cefr": cefr,
                "test_score": None,
                "evidence": line.strip(),
                "confidence": 96,
            })
    if not records:
        return
    languages = result.setdefault("languages", {})
    languages.update({
        "languages": records,
        "count": len(records),
        "has_languages": True,
        "native_languages": [item["language"] for item in records if item["proficiency_rank"] >= 7],
        "fluent_languages": [item["language"] for item in records if item["proficiency_rank"] >= 5],
        "language_score": min(100, 55 + len(records) * 13),
        "recommendations": [{
            "severity": "good",
            "type": "complete",
            "message": "Languages section looks complete.",
        }],
        "raw_languages_text": next((item["evidence"] for item in records), ""),
        "mode": "pairwise_language_level_reconciliation",
        "status": "present",
        "applicable": True,
    })


def _repair_visual_skills(result: dict) -> None:
    text = _full_document_text(result)
    patterns = (
        (r"(?i)\bproject\s+management\b", "Project Management", "hard"),
        (r"(?i)\bstrong\s+decision\s+maker\b|\bdecision\s+making\b", "Decision Making", "soft"),
        (r"(?i)\bcomplex\s+problem\s+solver\b|\bcomplex\s+problem\s+solving\b", "Complex Problem Solving", "soft"),
        (r"(?i)\bcreative\s+design\b", "Creative Design", "hard"),
    )
    detected = [(canonical, kind) for pattern, canonical, kind in patterns if re.search(pattern, text)]
    if not detected:
        return
    skills = result.setdefault("skills", {})
    invalid_location_keys = {
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
        "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
        "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
        "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
        "wi", "wy", "dc",
    }
    education = result.get("education", {}) or {}
    education_text = "\n".join(
        str(item.get("raw_text") or "")
        for item in list(education.get("education", []) or [])
        if isinstance(item, dict)
    )
    visual_aliases = {
        "project management":
            "Project Management",
        "strong decision maker":
            "Decision Making",
        "decision maker":
            "Decision Making",
        "decision making":
            "Decision Making",
        "complex problem solver":
            "Complex Problem Solving",
        "complex problem solving":
            "Complex Problem Solving",
        "creative design":
            "Creative Design",
    }

    existing = []
    for value in list(skills.get("all_skills", []) or []):
        key = _norm(value)
        if key in invalid_location_keys or re.fullmatch(r"(?i)[A-Z]{2}", str(value or "").strip()):
            continue
        value = visual_aliases.get(
            key,
            value,
        )
        key = _norm(value)
        appears_as_education_field = bool(
            key
            and re.search(rf"(?i)(?<![A-Za-z0-9]){re.escape(str(value))}(?![A-Za-z0-9])", education_text)
        )
        if appears_as_education_field and not any(_norm(value) == _norm(item[0]) for item in detected):
            continue
        existing.append(value)
    all_values = _unique_strings(existing + [item[0] for item in detected])
    soft_names = {_norm(item[0]) for item in detected if item[1] == "soft"}
    soft = _unique_strings(list(skills.get("soft_skills", []) or []) + [value for value in all_values if _norm(value) in soft_names])
    soft_keys = {_norm(value) for value in soft}
    hard = _unique_strings([value for value in all_values if _norm(value) not in soft_keys])
    final_skills = _unique_strings(hard + soft)
    recovered_score = min(90, 25 + len(final_skills) * 7 + len(hard) * 4 + len(soft) * 3)
    skills.update({
        "all_skills": final_skills,
        "hard_skills": hard,
        "soft_skills": soft,
        "total_count": len(final_skills),
        "hard_count": len(hard),
        "soft_count": len(soft),
        "skills_score": max(int(skills.get("skills_score", 0) or 0), recovered_score),
        "skills_quality": {
            "status": "ok" if recovered_score >= 65 else "needs_review",
            "score": max(int(skills.get("skills_score", 0) or 0), recovered_score),
            "warnings": [],
        },
        "score_adjustments": {
            "original_score": max(int(skills.get("skills_score", 0) or 0), recovered_score),
            "visual_template_recovery": True,
        },
    })
    recommendations = [
        item
        for item
        in list(
            skills.get(
                "recommendations",
                [],
            )
            or []
        )
        if item.get("type")
        not in {
            "empty",
            "quantity",
            "hard_skills",
            "soft_skills",
        }
    ]
    total = skills["total_count"]
    if total:
        recommendations.append({
            "severity": (
                "medium"
                if total < 8
                else "low"
                if total < 12
                else "good"
            ),
            "type": "quantity",
            "message": (
                f"{total} skills were detected. "
                "Add more role-specific technical "
                "skills only when they are factual "
                "and supported by the resume."
                if total < 8
                else
                f"{total} skills were detected. "
                "The skills section has reasonable "
                "coverage."
                if total < 12
                else
                f"{total} skills were detected with "
                "strong breadth."
            ),
        })
    skills["recommendations"] = recommendations


def _repair_placeholder_experience_slots(result: dict, profile: dict) -> None:
    slots = int(profile.get("placeholder_role_slot_count", 0) or 0)
    if not slots:
        return
    experience = result.setdefault("experience", {})
    def is_template_experience(
        item: dict,
    ) -> bool:
        title = re.sub(
            r"[^a-z0-9]+",
            " ",
            str(
                item.get(
                    "job_title"
                )
                or ""
            ).casefold(),
        ).strip()
        company = re.sub(
            r"[^a-z0-9]+",
            " ",
            str(
                item.get(
                    "company"
                )
                or ""
            ).casefold(),
        ).strip()
        raw = re.sub(
            r"[^a-z0-9]+",
            " ",
            str(
                item.get(
                    "raw_text"
                )
                or ""
            ).casefold(),
        ).strip()
        return bool(
            item.get("date_status")
            == "template_placeholder"
            or title
            in {
                "job title",
                "position title",
                "role title",
            }
            or company
            in {
                "company name",
                "employer name",
                "organization name",
            }
            or (
                "job title" in raw
                and "company name" in raw
            )
            or "key responsibility or achievement"
            in raw
        )

    all_experiences = [
        item
        for item
        in list(
            experience.get(
                "experiences",
                [],
            )
            or []
        )
        if isinstance(item, dict)
    ]
    template_experiences = [
        item
        for item
        in all_experiences
        if is_template_experience(item)
    ]
    real_experiences = [
        item
        for item
        in all_experiences
        if not is_template_experience(item)
    ]
    placeholder_items = [
        {
            "slot_index": index,
            "job_title_placeholder": "Job Title",
            "company_placeholder": "Company Name",
            "location_placeholder": "Location",
            "date_example": "Jan 2020 - current",
            "responsibility_placeholder_count": 4,
            "status": "unresolved_template_slot",
        }
        for index in range(1, slots + 1)
    ]
    experience["placeholder_role_slots"] = placeholder_items
    experience["placeholder_role_slot_count"] = slots
    experience["experiences"] = real_experiences
    experience["count"] = len(real_experiences)
    experience["has_experience"] = bool(real_experiences)
    experience["professional_role_count"] = sum(
        not bool(item.get("volunteer")) for item in real_experiences
    )
    if template_experiences:
        rejected = list(
            experience.get(
                "rejected_entries",
                [],
            )
            or []
        )
        for item in template_experiences:
            rejected.append({
                "raw_text": item.get(
                    "raw_text"
                ),
                "reasons": [
                    "template_experience_placeholder"
                ],
                "parsed": {
                    "job_title": item.get(
                        "job_title"
                    ),
                    "company": item.get(
                        "company"
                    ),
                    "start_date": item.get(
                        "start_date"
                    ),
                    "end_date": item.get(
                        "end_date"
                    ),
                    "confidence": item.get(
                        "confidence"
                    ),
                },
            })
        experience["rejected_entries"] = (
            rejected
        )

    if not real_experiences:
        experience[
            "professional_duration_status"
        ] = (
            "not_computable_template_placeholders"
        )
        for field in (
            "total_experience_months",
            "professional_experience_months",
            "paid_experience_months",
            "total_validated_experience_months",
        ):
            experience[field] = 0
        for field in (
            "total_experience_years",
            "professional_experience_years",
            "total_validated_experience_years",
        ):
            experience[field] = 0
        experience["current_position"] = None
        experience["top_companies"] = []
        experience["top_titles"] = []
        experience["overlapping_experiences"] = []
        experience["overlap_count"] = 0
        experience["experience_groups"] = []
        experience[
            "shared_responsibility_group_count"
        ] = 0
        experience["experience_score"] = 0
        experience["experience_quality"] = {
            "status": "source_incomplete",
            "score": 0,
            "valid_count": 0,
            "rejected_count": len(
                experience.get(
                    "rejected_entries",
                    [],
                )
                or []
            ),
            "warnings": [
                "template_experience_slots_unresolved"
            ],
            "informational_warnings": [],
            "entry_quality": [],
        }
        experience["recommendations"] = [{
            "severity": "high",
            "type":
                "replace_experience_placeholders",
            "message": (
                f"Replace all {slots} experience "
                "placeholder entries with actual "
                "roles, companies, dates, and "
                "achievements."
            ),
        }]


def _ats_structure_policy(result: dict, profile: dict, structure: dict) -> dict:
    assets = structure.get("document_assets", {}) or {}
    style = structure.get("document_style", {}) or {}
    duplicate = structure.get("duplicate_analysis", {}) or {}
    risks: list[dict] = []

    if assets.get("candidate_photo_detected"):
        risks.append({
            "type": "candidate_photo",
            "severity": "medium",
            "message": "A candidate-photo image was detected. Keep a text-first ATS version without the photo for stricter screening systems.",
        })
    if int(assets.get("text_box_count", 0) or 0) >= 3:
        risks.append({
            "type": "text_box_heavy_layout",
            "severity": "high",
            "message": "The document uses several text boxes or positioned shapes that can change ATS reading order.",
        })
    duplicate_ratio = float(duplicate.get("duplicate_ratio", 0) or 0)
    if duplicate_ratio >= 0.2:
        risks.append({
            "type": "duplicate_extraction_risk",
            "severity": "high" if duplicate_ratio >= 0.4 else "medium",
            "message": f"Technical duplicate content represented {duplicate_ratio * 100:.1f}% of extracted blocks and was reconciled before analysis.",
        })
    if style.get("has_color"):
        risks.append({
            "type": "color_present",
            "severity": "info",
            "message": "Colors were detected. Color alone is not penalized; readability and text contrast remain the deciding factors.",
        })
    if int(assets.get("icon_count", 0) or 0):
        risks.append({
            "type": "contact_or_decorative_icons",
            "severity": "low",
            "message": "Icons were detected. Keep visible text labels next to contact icons so ATS parsing does not depend on graphics.",
        })
    if profile.get("is_template"):
        risks.append({
            "type": "unresolved_template_content",
            "severity": "critical",
            "message": "Unresolved template instructions or role placeholders were detected.",
        })

    ranks = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    risk = "none"
    for item in risks:
        severity = str(item.get("severity") or "none")
        if ranks.get(severity, 0) > ranks.get(risk, 0):
            risk = severity
    return {
        "status": "needs_review" if risks else "ok",
        "risk_level": risk,
        "strict_ats_mode": {
            "candidate_photo_policy": "remove_or_supply_text_first_variant",
            "color_policy": "allowed_when_contrast_is_readable",
            "icon_policy": "text_label_required",
            "text_box_policy": "avoid_when_reading_order_changes",
        },
        "issues": risks,
    }


def _merge_visual_recommendations(result: dict, profile: dict, structure: dict, ats: dict) -> None:
    recommendations = [item for item in list(result.get("recommendations", []) or []) if isinstance(item, dict)]
    remove_types = {
        "candidate_photo_ats", "contact_icon_text", "visual_text_boxes", "duplicate_content",
        "replace_experience_placeholders", "replace_objective_instruction",
    }
    if (result.get("contact", {}) or {}).get("email"):
        remove_types.add("missing_email")
    if int(profile.get("placeholder_role_slot_count", 0) or 0):
        remove_types.add("missing")
    recommendations = [item for item in recommendations if item.get("type") not in remove_types]
    for issue in ats.get("issues", []) or []:
        mapping = {
            "candidate_photo": "candidate_photo_ats",
            "contact_or_decorative_icons": "contact_icon_text",
            "text_box_heavy_layout": "visual_text_boxes",
            "duplicate_extraction_risk": "duplicate_content",
        }
        if issue.get("type") in mapping:
            recommendations.append({
                "severity": "high" if issue.get("severity") in {"high", "critical"} else "medium" if issue.get("severity") == "medium" else "low",
                "type": mapping[issue.get("type")],
                "area": "ats_structure",
                "message": issue.get("message"),
            })
    slots = int(profile.get("placeholder_role_slot_count", 0) or 0)
    if slots:
        recommendations.append({
            "severity": "high",
            "type": "replace_experience_placeholders",
            "area": "experience",
            "message": f"Replace the {slots} experience template slots with actual employment information.",
        })
    if "objective" in list(profile.get("unresolved_template_sections", []) or []):
        recommendations.append({
            "severity": "high",
            "type": "replace_objective_instruction",
            "area": "summary",
            "message": "Replace the objective instruction text with a concise professional summary tailored to the target role.",
        })
    deduped = []
    seen = set()
    for item in recommendations:
        key = (str(item.get("area") or ""), str(item.get("type") or ""), str(item.get("message") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    result["recommendations"] = deduped


def _build_visual_source_readiness(result: dict, profile: dict, structure: dict) -> None:
    if not profile.get("is_template"):
        return
    contact = result.get("contact", {}) or {}
    date_placeholders = result.get("date_placeholders", {}) or {}
    required_actions = []
    warnings = ["document_is_template"]

    if contact.get("name_status") in {"placeholder", "unresolved"}:
        required_actions.append("Replace the candidate-name placeholder with a real name.")
        warnings.append("candidate_identity_placeholder")
    if contact.get("email_status") in {"placeholder", "unresolved"}:
        required_actions.append("Add a valid candidate email address.")
        warnings.append("candidate_email_unresolved_or_placeholder")
    if contact.get("phone_status") in {"placeholder", "unresolved"}:
        required_actions.append("Add a valid candidate phone number.")
        warnings.append("candidate_phone_unresolved_or_placeholder")
    if date_placeholders.get("count"):
        required_actions.append("Replace all date placeholders with actual dates.")
        warnings.append("date_placeholders_detected")
    if profile.get("placeholder_role_slot_count"):
        required_actions.append("Replace all experience template slots with real employment history.")
        warnings.append("experience_template_slots_unresolved")
    if "objective" in list(profile.get("unresolved_template_sections", []) or []):
        required_actions.append("Replace objective instructions with candidate-specific summary text.")
        warnings.append("objective_instruction_unresolved")
    assets = structure.get("document_assets", {}) or {}
    if assets.get("candidate_photo_detected"):
        required_actions.append("Provide a text-first ATS variant without the candidate photo.")

    result["source_readiness"] = {
        "status": "template_incomplete",
        "score": 35,
        "score_cap": 60,
        "trusted": False,
        "warnings": _unique_strings(warnings),
        "required_actions": _unique_strings(required_actions),
        "meaning": "The file is readable, but unresolved template content prevents a hiring-ready ATS score.",
    }


def apply_document_intelligence(result: dict) -> dict:
    if not isinstance(result, dict):
        return result

    structure = _document_structure(result)
    _apply_deduplicated_docx_text(
        result,
        structure,
    )
    date_placeholders = detect_date_placeholders(result)
    profile = detect_document_profile(result, date_placeholders)
    profile = _enhance_template_profile(result, profile, structure)

    result["date_placeholders"] = date_placeholders
    result["document_profile"] = profile
    result["document_style"] = structure.get("document_style") or extract_dynamic_document_style((result.get("file", {}) or {}).get("path"))
    result["document_assets"] = structure.get("document_assets") or _pdf_document_assets((result.get("file", {}) or {}).get("path"))
    result["duplicate_analysis"] = structure.get("duplicate_analysis") or _duplicate_analysis_from_result(result)

    apply_contact_placeholder_policy(
        result,
        profile,
    )
    _repair_contact_from_visual_text(result)
    _repair_contact_identity_and_location(
        result,
        structure,
        profile,
    )
    _repair_languages_from_text(result)
    _repair_visual_skills(result)
    _repair_section_metadata_from_visual_blocks(
        result,
        structure,
    )
    augment_document_metrics(result)
    reconstruct_placeholder_experience(result, profile)
    _repair_placeholder_experience_slots(result, profile)
    reconstruct_placeholder_education(result, profile)
    refine_template_skills(result, profile)
    build_source_readiness(result, profile, date_placeholders)
    _build_visual_source_readiness(result, profile, structure)
    clean_stale_extraction_warnings(result, profile)
    _merge_recommendations(result, profile, date_placeholders)

    ats_structure = _ats_structure_policy(result, profile, structure)
    result["ats_structure"] = ats_structure
    _merge_visual_recommendations(result, profile, structure, ats_structure)

    result["document_intelligence"] = {
        "version": "1.5.3",
        "applied": True,
        "file_type": str((result.get("file", {}) or {}).get("extension") or "").lstrip(".").casefold(),
        "areas": [
            "pdf_docx_parity", "docx_ooxml_structure", "provenance_deduplication",
            "visual_order_reconstruction", "dynamic_color_palette", "image_icon_inventory",
            "candidate_photo_policy", "template_detection", "placeholder_role_slots",
            "contact_normalization", "pairwise_language_proficiency", "skill_disambiguation",
            "ats_visual_structure_policy", "source_readiness",
        ],
        "fixed_palette_used": False,
    }
    return result
