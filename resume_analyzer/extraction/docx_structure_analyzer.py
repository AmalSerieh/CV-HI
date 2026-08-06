from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from lxml import etree

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}

REL_NS = {
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

EMU_PER_POINT = 12700.0
EMU_PER_INCH = 914400.0


@dataclass(frozen=True)
class Relationship:
    rel_id: str
    rel_type: str
    target: str
    external: bool


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _norm_text(value).casefold()).strip()


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


def _hex_from_value(value: Any) -> str | None:
    clean = str(value or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", clean):
        return f"#{clean.upper()}"
    if re.fullmatch(r"[0-9A-Fa-f]{3}", clean):
        return "#" + "".join(char * 2 for char in clean.upper())
    named = {
        "black": "#000000",
        "white": "#FFFFFF",
        "red": "#FF0000",
        "green": "#008000",
        "blue": "#0000FF",
        "yellow": "#FFFF00",
        "gray": "#808080",
        "grey": "#808080",
        "silver": "#C0C0C0",
        "navy": "#000080",
        "teal": "#008080",
        "maroon": "#800000",
        "purple": "#800080",
        "orange": "#FFA500",
    }
    return named.get(clean.casefold())


def _parse_style_number(style: str, key: str) -> float | None:
    match = re.search(
        rf"(?:^|;)\s*{re.escape(key)}\s*:\s*(-?\d+(?:\.\d+)?)\s*(pt|px|in|cm|mm)?",
        style or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "pt").casefold()
    if unit == "pt":
        return value
    if unit == "px":
        return value * 0.75
    if unit == "in":
        return value * 72.0
    if unit == "cm":
        return value * 28.3464567
    if unit == "mm":
        return value * 2.83464567
    return value


def _resolve_target(part_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base = PurePosixPath(part_name).parent
    combined = base.joinpath(target)
    parts: list[str] = []
    for item in combined.parts:
        if item in {"", "."}:
            continue
        if item == "..":
            if parts:
                parts.pop()
            continue
        parts.append(item)
    return "/".join(parts)


def _relationships_path(part_name: str) -> str:
    path = PurePosixPath(part_name)
    return str(path.parent / "_rels" / f"{path.name}.rels")


def _extract_text(element: etree._Element) -> str:
    tokens: list[str] = []
    for node in element.iter():
        local = etree.QName(node).localname
        if local == "t":
            if node.text:
                tokens.append(node.text)
        elif local == "tab":
            tokens.append("\t")
        elif local in {"br", "cr"}:
            tokens.append("\n")
    text = "".join(tokens)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _ancestor(element: etree._Element, local_names: set[str]) -> etree._Element | None:
    current = element.getparent()
    while current is not None:
        if etree.QName(current).localname in local_names:
            return current
        current = current.getparent()
    return None


def _shape_metadata(element: etree._Element) -> dict[str, Any]:
    anchor = _ancestor(element, {"anchor", "inline"})
    pict = _ancestor(element, {"pict"})
    shape = _ancestor(element, {"shape", "rect", "roundrect", "oval"})

    meta: dict[str, Any] = {
        "anchored": False,
        "inline": False,
        "x_pt": None,
        "y_pt": None,
        "width_pt": None,
        "height_pt": None,
        "shape_id": None,
        "shape_name": None,
        "behind_text": False,
    }

    if anchor is not None:
        local = etree.QName(anchor).localname
        meta["anchored"] = local == "anchor"
        meta["inline"] = local == "inline"
        meta["behind_text"] = str(anchor.get("behindDoc") or "0") in {"1", "true"}

        position_h = anchor.find("wp:positionH", namespaces=NS)
        position_v = anchor.find("wp:positionV", namespaces=NS)
        if position_h is not None:
            offset = position_h.findtext("wp:posOffset", namespaces=NS)
            if offset is not None:
                meta["x_pt"] = round(int(offset) / EMU_PER_POINT, 3)
        if position_v is not None:
            offset = position_v.findtext("wp:posOffset", namespaces=NS)
            if offset is not None:
                meta["y_pt"] = round(int(offset) / EMU_PER_POINT, 3)

        extent = anchor.find("wp:extent", namespaces=NS)
        if extent is not None:
            cx = _safe_int(extent.get("cx"))
            cy = _safe_int(extent.get("cy"))
            if cx is not None:
                meta["width_pt"] = round(cx / EMU_PER_POINT, 3)
            if cy is not None:
                meta["height_pt"] = round(cy / EMU_PER_POINT, 3)

        doc_pr = anchor.find("wp:docPr", namespaces=NS)
        if doc_pr is not None:
            meta["shape_id"] = doc_pr.get("id")
            meta["shape_name"] = doc_pr.get("name")

    if shape is not None:
        style = str(shape.get("style") or "")
        meta["shape_id"] = meta["shape_id"] or shape.get("id")
        meta["shape_name"] = meta["shape_name"] or shape.get("title") or shape.get("alt")
        meta["x_pt"] = meta["x_pt"] if meta["x_pt"] is not None else _parse_style_number(style, "margin-left")
        meta["y_pt"] = meta["y_pt"] if meta["y_pt"] is not None else _parse_style_number(style, "margin-top")
        meta["width_pt"] = meta["width_pt"] if meta["width_pt"] is not None else _parse_style_number(style, "width")
        meta["height_pt"] = meta["height_pt"] if meta["height_pt"] is not None else _parse_style_number(style, "height")
        meta["anchored"] = True

    if pict is not None and shape is None:
        meta["anchored"] = True

    return meta


def _parse_relationships(zf: zipfile.ZipFile, part_name: str) -> dict[str, Relationship]:
    rels_path = _relationships_path(part_name)
    if rels_path not in zf.namelist():
        return {}
    root = etree.fromstring(zf.read(rels_path))
    output: dict[str, Relationship] = {}
    for node in root.findall("pr:Relationship", namespaces=REL_NS):
        rel_id = str(node.get("Id") or "")
        if not rel_id:
            continue
        target = str(node.get("Target") or "")
        output[rel_id] = Relationship(
            rel_id=rel_id,
            rel_type=str(node.get("Type") or ""),
            target=target,
            external=str(node.get("TargetMode") or "").casefold() == "external",
        )
    return output


def _theme_colors(zf: zipfile.ZipFile) -> dict[str, str]:
    candidates = [
        name for name in zf.namelist()
        if name.startswith("word/theme/") and name.endswith(".xml")
    ]
    if not candidates:
        return {}
    try:
        root = etree.fromstring(zf.read(sorted(candidates)[0]))
    except Exception:
        return {}

    scheme = root.find(".//a:clrScheme", namespaces=NS)
    if scheme is None:
        return {}

    output: dict[str, str] = {}
    for child in scheme:
        key = etree.QName(child).localname
        value_node = next(iter(child), None)
        if value_node is None:
            continue
        value = value_node.get("val") or value_node.get("lastClr")
        color = _hex_from_value(value)
        if color:
            output[key] = color
    return output


def _style_colors(zf: zipfile.ZipFile, theme: dict[str, str]) -> list[dict[str, Any]]:
    if "word/styles.xml" not in zf.namelist():
        return []
    try:
        root = etree.fromstring(zf.read("word/styles.xml"))
    except Exception:
        return []
    samples: list[dict[str, Any]] = []
    for node in root.xpath(".//w:color | .//w:shd", namespaces=NS):
        local = etree.QName(node).localname
        direct = node.get(f"{{{NS['w']}}}val") or node.get(f"{{{NS['w']}}}fill")
        theme_key = node.get(f"{{{NS['w']}}}themeColor") or node.get(f"{{{NS['w']}}}themeFill")
        color = _hex_from_value(direct)
        if color is None and theme_key:
            color = theme.get(theme_key)
        if color and color not in {"#000000", "#FFFFFF"}:
            samples.append({
                "hex": color,
                "source": f"styles_{local}",
                "usage": "style",
                "weight": 1.0,
            })
    return samples


def _part_color_samples(root: etree._Element, theme: dict[str, str]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    for node in root.xpath(
        ".//w:color | .//w:highlight | .//w:shd | .//a:srgbClr | .//a:schemeClr | .//v:shape | .//v:fill | .//v:stroke",
        namespaces=NS,
    ):
        local = etree.QName(node).localname
        color: str | None = None
        source = local

        if local == "color":
            direct = node.get(f"{{{NS['w']}}}val")
            theme_key = node.get(f"{{{NS['w']}}}themeColor")
            color = _hex_from_value(direct) or theme.get(str(theme_key or ""))
        elif local == "highlight":
            color = _hex_from_value(node.get(f"{{{NS['w']}}}val"))
        elif local == "shd":
            direct = node.get(f"{{{NS['w']}}}fill")
            theme_key = node.get(f"{{{NS['w']}}}themeFill")
            color = _hex_from_value(direct) or theme.get(str(theme_key or ""))
        elif local == "srgbClr":
            color = _hex_from_value(node.get("val"))
        elif local == "schemeClr":
            color = theme.get(str(node.get("val") or ""))
        elif local == "shape":
            color = _hex_from_value(node.get("fillcolor"))
            if color:
                samples.append({"hex": color, "source": "shape_fill", "usage": "graphic", "weight": 2.0})
            stroke = _hex_from_value(node.get("strokecolor"))
            if stroke:
                samples.append({"hex": stroke, "source": "shape_stroke", "usage": "graphic", "weight": 1.0})
            continue
        elif local == "fill":
            color = _hex_from_value(node.get("color") or node.get("color2"))
        elif local == "stroke":
            color = _hex_from_value(node.get("color") or node.get("color2"))

        if color:
            usage = "text" if local in {"color", "highlight"} else "graphic"
            samples.append({
                "hex": color,
                "source": source,
                "usage": usage,
                "weight": 1.0,
            })

    return samples


def _paragraph_style(paragraph: etree._Element) -> dict[str, Any]:
    style_id = paragraph.find("./w:pPr/w:pStyle", namespaces=NS)
    style_value = style_id.get(f"{{{NS['w']}}}val") if style_id is not None else None
    outline = paragraph.find("./w:pPr/w:outlineLvl", namespaces=NS)
    outline_value = outline.get(f"{{{NS['w']}}}val") if outline is not None else None
    return {
        "style_id": style_value,
        "outline_level": _safe_int(outline_value),
    }


def _image_dimensions(data: bytes) -> tuple[int | None, int | None, str | None]:
    if Image is None:
        return None, None, None
    try:
        with Image.open(io.BytesIO(data)) as image:
            return int(image.width), int(image.height), str(image.format or "").lower() or None
    except Exception:
        return None, None, None


def _media_inventory(zf: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for name in zf.namelist():
        if not name.startswith("word/media/") or name.endswith("/"):
            continue
        data = zf.read(name)
        width, height, image_format = _image_dimensions(data)
        suffix = Path(name).suffix.lower().lstrip(".")
        vector = suffix in {"svg", "emf", "wmf"}
        output[name] = {
            "path": name,
            "file_name": PurePosixPath(name).name,
            "extension": suffix,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "width_px": width,
            "height_px": height,
            "format": image_format or suffix,
            "is_vector": vector,
        }
    return output


def _image_references(
    root: etree._Element,
    part_name: str,
    relationships: dict[str, Relationship],
    media: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()

    nodes: list[etree._Element] = []
    nodes.extend(root.xpath(".//a:blip", namespaces=NS))
    nodes.extend(root.xpath(".//v:imagedata", namespaces=NS))

    for node in nodes:
        rel_id = (
            node.get(f"{{{NS['r']}}}embed")
            or node.get(f"{{{NS['r']}}}link")
            or node.get(f"{{{NS['r']}}}id")
        )
        if not rel_id or rel_id not in relationships:
            continue
        relationship = relationships[rel_id]
        if relationship.external:
            target = relationship.target
        else:
            target = _resolve_target(part_name, relationship.target)
        meta = _shape_metadata(node)
        key = (target, str(meta.get("shape_id")), str(meta.get("y_pt")))
        if key in seen:
            continue
        seen.add(key)
        media_meta = dict(media.get(target, {}))
        refs.append({
            **media_meta,
            "relationship_id": rel_id,
            "part": part_name,
            "external": relationship.external,
            "x_pt": meta.get("x_pt"),
            "y_pt": meta.get("y_pt"),
            "width_pt": meta.get("width_pt"),
            "height_pt": meta.get("height_pt"),
            "shape_id": meta.get("shape_id"),
            "shape_name": meta.get("shape_name"),
            "behind_text": meta.get("behind_text", False),
        })
    return refs


def _classify_images(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for item in references:
        width_px = item.get("width_px")
        height_px = item.get("height_px")
        width_pt = item.get("width_pt")
        height_pt = item.get("height_pt")
        y_pt = item.get("y_pt")
        is_vector = bool(item.get("is_vector"))

        pixel_area = (
            int(width_px) * int(height_px)
            if isinstance(width_px, int) and isinstance(height_px, int)
            else 0
        )
        display_area = (
            float(width_pt) * float(height_pt)
            if isinstance(width_pt, (int, float)) and isinstance(height_pt, (int, float))
            else 0.0
        )
        aspect = (
            float(width_px) / float(height_px)
            if isinstance(width_px, int) and isinstance(height_px, int) and height_px
            else (
                float(width_pt) / float(height_pt)
                if isinstance(width_pt, (int, float)) and isinstance(height_pt, (int, float)) and height_pt
                else None
            )
        )

        is_icon = bool(
            is_vector
            or (pixel_area and pixel_area <= 40000)
            or (display_area and display_area <= 1600)
        )
        photo_score = 0.0
        reasons: list[str] = []
        if not is_vector and pixel_area >= 40000:
            photo_score += 0.35
            reasons.append("raster_image_with_substantial_resolution")
        if aspect is not None and 0.55 <= aspect <= 1.35:
            photo_score += 0.25
            reasons.append("portrait_or_square_aspect")
        if isinstance(y_pt, (int, float)) and y_pt <= 180:
            photo_score += 0.25
            reasons.append("positioned_in_header_region")
        if display_area >= 2500:
            photo_score += 0.15
            reasons.append("large_display_area")

        candidate_photo = bool(photo_score >= 0.6 and not is_icon)
        classification = (
            "candidate_photo_candidate"
            if candidate_photo
            else "icon"
            if is_icon
            else "decorative_or_content_image"
        )
        classified.append({
            **item,
            "classification": classification,
            "is_icon": is_icon,
            "candidate_photo_candidate": candidate_photo,
            "candidate_photo_confidence": round(min(1.0, photo_score), 3),
            "classification_reasons": reasons,
        })
    return classified


def _paragraph_nodes(root: etree._Element) -> Iterable[etree._Element]:
    # Select every paragraph once. Paragraphs nested in text boxes are included;
    # the caller records their source kind and parent shape.
    return root.xpath(".//w:p", namespaces=NS)


def _source_kind(paragraph: etree._Element, part_name: str) -> str:
    if _ancestor(paragraph, {"txbxContent"}) is not None:
        return "textbox"
    if _ancestor(paragraph, {"tc"}) is not None:
        return "table_cell"
    if "/header" in part_name:
        return "header"
    if "/footer" in part_name:
        return "footer"
    return "paragraph"


def _paragraph_hyperlinks(
    paragraph: etree._Element,
    relationships: dict[str, Relationship],
) -> list[str]:
    output: list[str] = []
    for link in paragraph.xpath(".//w:hyperlink", namespaces=NS):
        rel_id = link.get(f"{{{NS['r']}}}id")
        if not rel_id or rel_id not in relationships:
            continue
        relationship = relationships[rel_id]
        if relationship.external and relationship.target:
            output.append(relationship.target)
    return list(dict.fromkeys(output))


def _document_parts(zf: zipfile.ZipFile) -> list[str]:
    output = ["word/document.xml"] if "word/document.xml" in zf.namelist() else []
    output.extend(sorted(
        name for name in zf.namelist()
        if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
    ))
    return output


def _extract_blocks(
    zf: zipfile.ZipFile,
    part_name: str,
    root: etree._Element,
    relationships: dict[str, Relationship],
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for source_order, paragraph in enumerate(_paragraph_nodes(root)):
        text = _extract_text(paragraph)
        if not text:
            continue
        kind = _source_kind(paragraph, part_name)
        shape = _shape_metadata(paragraph)
        style = _paragraph_style(paragraph)
        block_id = hashlib.sha1(
            f"{part_name}|{source_order}|{text}".encode()
        ).hexdigest()[:16]

        x_pt = shape.get("x_pt")
        y_pt = shape.get("y_pt")
        width_pt = shape.get("width_pt")
        height_pt = shape.get("height_pt")
        bbox = None
        if isinstance(x_pt, (int, float)) and isinstance(y_pt, (int, float)):
            bbox = {
                "x0": round(float(x_pt), 3),
                "top": round(float(y_pt), 3),
                "x1": round(float(x_pt) + float(width_pt or 0), 3),
                "bottom": round(float(y_pt) + float(height_pt or 0), 3),
            }

        blocks.append({
            "id": block_id,
            "page": 1,
            "text": text,
            "bbox": bbox,
            "column": "single",
            "order": source_order,
            "engine": "docx_ooxml",
            "block_type": kind,
            "is_repeated_header_footer": False,
            "is_continuation_header": False,
            "excluded_from_ordered_text": False,
            "exclusion_reason": None,
            "part": part_name,
            "source_kind": kind,
            "source_order": source_order,
            "visual_order": None,
            "x_pt": x_pt,
            "y_pt": y_pt,
            "width_pt": width_pt,
            "height_pt": height_pt,
            "anchored": bool(shape.get("anchored")),
            "inline": bool(shape.get("inline")),
            "shape_id": shape.get("shape_id"),
            "shape_name": shape.get("shape_name"),
            "behind_text": bool(shape.get("behind_text")),
            "style_id": style.get("style_id"),
            "outline_level": style.get("outline_level"),
            "links": _paragraph_hyperlinks(paragraph, relationships),
            "normalized_text": _norm_key(text),
        })
    return blocks


def _visual_sort_key(block: dict[str, Any]) -> tuple:
    part = str(block.get("part") or "")
    part_priority = 0 if part == "word/document.xml" else 1 if "/header" in part else 2
    y = block.get("y_pt")
    x = block.get("x_pt")
    anchored = isinstance(y, (int, float))
    return (
        part_priority,
        0 if anchored else 1,
        round(float(y), 2) if anchored else 10_000_000 + int(block.get("source_order", 0)),
        round(float(x), 2) if isinstance(x, (int, float)) else 0.0,
        int(block.get("source_order", 0)),
    )


def _layout_classification(blocks: list[dict[str, Any]]) -> tuple[str, str, float]:
    positioned = [
        item for item in blocks
        if isinstance(item.get("x_pt"), (int, float)) and isinstance(item.get("y_pt"), (int, float))
    ]
    textboxes = [item for item in blocks if item.get("source_kind") == "textbox"]
    if len(positioned) >= max(4, len(blocks) // 3):
        xs = sorted(float(item["x_pt"]) for item in positioned)
        if xs and max(xs) - min(xs) >= 180:
            return "two_column", "visual_top_to_bottom", 0.9
        return "single_column", "visual_top_to_bottom", 0.86
    if textboxes:
        return "single_column", "xml_flow_with_textboxes", 0.72
    return "single_column", "top_to_bottom", 0.82


def _heading_key(value: Any) -> str:
    return re.sub(
        r"[^a-z]+",
        " ",
        str(value or "").casefold(),
    ).strip()


_SECTION_HEADING_KEYS = {
    "summary",
    "objective",
    "profile",
    "skills",
    "technical skills",
    "education",
    "experience",
    "work experience",
    "languages",
    "hobbies",
    "interests",
    "projects",
    "certifications",
    "awards",
}


def _column_aware_visual_order(
    blocks: list[dict[str, Any]],
    layout: str,
) -> list[dict[str, Any]]:
    """
    Reconstruct semantic order for positioned two-column DOCX resumes.

    Strategy:
    1. Detect the two x-position clusters from the largest horizontal gap.
    2. Use the column containing the topmost visible identity block as primary.
    3. Emit identity header from the primary column.
    4. Emit contact header from the secondary column.
    5. Emit the primary body, then the secondary body.

    This prevents headings from adjacent columns, such as SKILLS/HOBBIES,
    from being interleaved solely because their y coordinates are close.
    """
    if layout != "two_column":
        return list(blocks)

    positioned = [
        item
        for item in blocks
        if isinstance(item.get("x_pt"), (int, float))
        and isinstance(item.get("y_pt"), (int, float))
    ]
    if len(positioned) < 6:
        return list(blocks)

    xs = sorted({round(float(item["x_pt"]), 2) for item in positioned})
    if len(xs) < 2:
        return list(blocks)

    gaps = [
        (xs[index + 1] - xs[index], index)
        for index in range(len(xs) - 1)
    ]
    largest_gap, gap_index = max(gaps)
    if largest_gap < 90:
        return list(blocks)

    split_x = (xs[gap_index] + xs[gap_index + 1]) / 2.0

    for item in blocks:
        x_value = item.get("x_pt")
        if isinstance(x_value, (int, float)):
            item["column"] = (
                "left"
                if float(x_value) < split_x
                else "right"
            )
        else:
            item["column"] = "unpositioned"

    visible_positioned = sorted(
        positioned,
        key=lambda item: (
            float(item.get("y_pt") or 0),
            float(item.get("x_pt") or 0),
            int(item.get("source_order", 0)),
        ),
    )
    primary_column = visible_positioned[0].get("column")
    secondary_column = (
        "right"
        if primary_column == "left"
        else "left"
    )

    def column_items(column: str) -> list[dict[str, Any]]:
        return sorted(
            [
                item
                for item in blocks
                if item.get("column") == column
            ],
            key=lambda item: (
                float(item.get("y_pt") or 0),
                float(item.get("x_pt") or 0),
                int(item.get("source_order", 0)),
            ),
        )

    primary = column_items(str(primary_column))
    secondary = column_items(secondary_column)

    def first_heading_index(items: list[dict[str, Any]]) -> int:
        for index, item in enumerate(items):
            if _heading_key(item.get("text")) in _SECTION_HEADING_KEYS:
                return index
        return len(items)

    primary_break = first_heading_index(primary)
    secondary_break = first_heading_index(secondary)

    primary_header = primary[:primary_break]
    primary_body = primary[primary_break:]
    secondary_header = secondary[:secondary_break]
    secondary_body = secondary[secondary_break:]

    unpositioned = [
        item
        for item in blocks
        if item.get("column") == "unpositioned"
    ]
    unpositioned = sorted(
        unpositioned,
        key=lambda item: int(
            item.get("source_order", 0)
        ),
    )

    ordered = (
        primary_header
        + secondary_header
        + primary_body
        + secondary_body
        + unpositioned
    )
    return ordered


def _textbox_inventory(
    blocks: list[dict[str, Any]],
) -> dict[str, int]:
    textbox_blocks = [
        item
        for item in blocks
        if item.get("source_kind") == "textbox"
    ]

    container_keys: set[tuple[Any, ...]] = set()
    for item in textbox_blocks:
        shape_id = item.get("shape_id")
        if shape_id:
            key = (
                item.get("part"),
                "shape",
                str(shape_id),
            )
        else:
            key = (
                item.get("part"),
                "position",
                round(float(item.get("x_pt") or 0), 2),
                round(float(item.get("y_pt") or 0), 2),
                round(float(item.get("width_pt") or 0), 2),
                round(float(item.get("height_pt") or 0), 2),
            )
        container_keys.add(key)

    return {
        "text_box_count": len(container_keys),
        "text_box_text_block_count": len(textbox_blocks),
    }


def _detect_textbox_count(roots: list[etree._Element]) -> int:
    identifiers: set[str] = set()
    fallback = 0
    for root in roots:
        for content in root.xpath(".//w:txbxContent", namespaces=NS):
            shape = _ancestor(content, {"shape", "anchor", "inline"})
            if shape is not None:
                identity = shape.get("id") or shape.get("name") or shape.get("title")
                if not identity:
                    doc_pr = shape.find(".//wp:docPr", namespaces=NS)
                    if doc_pr is not None:
                        identity = doc_pr.get("id") or doc_pr.get("name")
                if identity:
                    identifiers.add(str(identity))
                    continue
            fallback += 1
    return len(identifiers) + fallback


def analyze_docx_package(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    base: dict[str, Any] = {
        "status": "not_available",
        "file_type": "docx",
        "blocks": [],
        "visual_blocks": [],
        "links": [],
        "layout": "unknown",
        "reading_order": "unknown",
        "layout_confidence": 0.0,
        "document_style": {
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
            "palette_method": "docx_ooxml_theme_direct_and_shape_analysis",
            "fixed_palette_used": False,
        },
        "document_assets": {
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
        },
        "warnings": [],
        "error": None,
    }
    if not path.is_file():
        return base

    try:
        zf = zipfile.ZipFile(path)
    except Exception as exc:
        return {**base, "status": "error", "error": f"{type(exc).__name__}: {exc}"}

    with zf:
        theme = _theme_colors(zf)
        media = _media_inventory(zf)
        roots: list[etree._Element] = []
        blocks: list[dict[str, Any]] = []
        links: list[str] = []
        image_refs: list[dict[str, Any]] = []
        color_samples: list[dict[str, Any]] = _style_colors(zf, theme)
        drawing_count = 0
        shape_count = 0

        for part_name in _document_parts(zf):
            try:
                root = etree.fromstring(zf.read(part_name))
            except Exception:
                continue
            roots.append(root)
            relationships = _parse_relationships(zf, part_name)
            part_blocks = _extract_blocks(zf, part_name, root, relationships)
            blocks.extend(part_blocks)
            for item in part_blocks:
                links.extend(item.get("links", []))
            image_refs.extend(_image_references(root, part_name, relationships, media))
            color_samples.extend(_part_color_samples(root, theme))
            drawing_count += len(root.xpath(".//w:drawing", namespaces=NS))
            shape_count += len(root.xpath(".//v:shape | .//wps:wsp", namespaces=NS))

        visual_blocks = sorted(
            blocks,
            key=_visual_sort_key,
        )
        layout, reading_order, layout_confidence = (
            _layout_classification(visual_blocks)
        )
        visual_blocks = _column_aware_visual_order(
            visual_blocks,
            layout,
        )
        if layout == "two_column":
            reading_order = (
                "column_aware_visual_order"
            )

        for index, item in enumerate(visual_blocks):
            item["visual_order"] = index
        image_refs = _classify_images(image_refs)
        candidate_photos = [item for item in image_refs if item.get("candidate_photo_candidate")]
        icons = [item for item in image_refs if item.get("is_icon")]
        decorative = [
            item for item in image_refs
            if not item.get("candidate_photo_candidate") and not item.get("is_icon")
        ]

        color_counter: Counter[str] = Counter()
        color_usage: dict[str, Counter[str]] = defaultdict(Counter)
        color_source: dict[str, Counter[str]] = defaultdict(Counter)
        for sample in color_samples:
            color = _hex_from_value(sample.get("hex"))
            if not color:
                continue
            weight = max(0.1, float(sample.get("weight", 1.0) or 1.0))
            color_counter[color] += weight
            color_usage[color][str(sample.get("usage") or "unknown")] += weight
            color_source[color][str(sample.get("source") or "unknown")] += weight

        total_color_weight = float(sum(color_counter.values()) or 1.0)
        palette: list[dict[str, Any]] = []
        for color, weight in color_counter.most_common(64):
            rgb = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
            maximum = max(rgb)
            minimum = min(rgb)
            saturation = 0.0 if maximum == 0 else (maximum - minimum) / maximum
            palette.append({
                "hex": color,
                "rgb": list(rgb),
                "weight": round(float(weight), 3),
                "coverage": round(float(weight) / total_color_weight, 6),
                "saturation": round(saturation, 4),
                "sources": [key for key, _ in color_source[color].most_common()],
                "usage": [key for key, _ in color_usage[color].most_common()],
            })

        chromatic = [item for item in palette if item["saturation"] >= 0.12]
        text_colors = [
            item["hex"] for item in palette
            if "text" in item.get("usage", []) or any("color" in source for source in item.get("sources", []))
        ]
        graphic_colors = [
            item["hex"] for item in palette
            if "graphic" in item.get("usage", []) or any("shape" in source or "shd" in source for source in item.get("sources", []))
        ]

        style = {
            "status": "ok",
            "has_color": bool(chromatic),
            "is_multicolor": len(chromatic) >= 2,
            "detected_color_count": len(palette),
            "chromatic_color_count": len(chromatic),
            "palette": palette,
            "primary_color": chromatic[0]["hex"] if chromatic else (palette[0]["hex"] if palette else None),
            "accent_colors": [item["hex"] for item in chromatic[:12]],
            "text_colors": list(dict.fromkeys(text_colors)),
            "graphic_colors": list(dict.fromkeys(graphic_colors)),
            "background_color": None,
            "contrast_status": "not_measurable_from_ooxml_only",
            "ats_color_risk": "low" if len(chromatic) <= 8 else "medium",
            "palette_method": "docx_ooxml_theme_direct_and_shape_analysis",
            "fixed_palette_used": False,
            "theme_colors": theme,
        }

        textbox_inventory = _textbox_inventory(
            blocks
        )
        text_box_count = int(
            textbox_inventory.get(
                "text_box_count",
                0,
            )
            or 0
        )
        text_box_text_block_count = int(
            textbox_inventory.get(
                "text_box_text_block_count",
                0,
            )
            or 0
        )
        assets = {
            "has_images": bool(image_refs),
            "image_count": len(image_refs),
            "raster_image_count": sum(not bool(item.get("is_vector")) for item in image_refs),
            "vector_asset_count": sum(bool(item.get("is_vector")) for item in image_refs),
            "icon_count": len(icons),
            "candidate_photo_detected": bool(candidate_photos),
            "candidate_photo_candidates": candidate_photos,
            "decorative_image_count": len(decorative),
            "image_only_contact_fields": [],
            "text_box_count": text_box_count,
            "text_box_text_block_count":
                text_box_text_block_count,
            "drawing_count": drawing_count,
            "shape_count": shape_count,
            "media": image_refs,
            "analysis_mode": "docx_ooxml_package_inventory",
        }

        warnings: list[str] = []
        if text_box_count:
            warnings.append(
                "docx_text_boxes_detected:"
                f"{text_box_count}"
            )
        if (
            text_box_text_block_count
            and text_box_text_block_count
            != text_box_count
        ):
            warnings.append(
                "docx_textbox_text_blocks_detected:"
                f"{text_box_text_block_count}"
            )
        if image_refs:
            warnings.append(f"docx_embedded_images_detected:{len(image_refs)}")
        if candidate_photos:
            warnings.append(f"candidate_photo_candidates_detected:{len(candidate_photos)}")
        if chromatic:
            warnings.append(f"docx_chromatic_colors_detected:{len(chromatic)}")

        return {
            "status": "ok",
            "file_type": "docx",
            "blocks": blocks,
            "visual_blocks": visual_blocks,
            "links": list(dict.fromkeys(links)),
            "layout": layout,
            "reading_order": reading_order,
            "layout_confidence": layout_confidence,
            "document_style": style,
            "document_assets": assets,
            "warnings": warnings,
            "error": None,
        }
