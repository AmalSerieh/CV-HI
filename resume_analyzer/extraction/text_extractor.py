from __future__ import annotations

import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import docx as python_docx
import pdfplumber

try:
    from .docx_structure_analyzer import analyze_docx_package
    from .duplicate_content_cleaner import deduplicate_blocks
    from .layout_graph import build_page_graph as _build_page_graph
except ImportError:
    from docx_structure_analyzer import analyze_docx_package
    from duplicate_content_cleaner import deduplicate_blocks
    from layout_graph import build_page_graph as _build_page_graph  # type: ignore[no-redef]

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    from pytesseract import Output

    OCR_AVAILABLE = PYMUPDF_AVAILABLE
except ImportError:
    Image = None
    pytesseract = None
    Output = None
    OCR_AVAILABLE = False


SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
MIN_TEXT_WORDS_PER_PAGE = 10
HEADER_ZONE_RATIO = 0.12
FOOTER_ZONE_RATIO = 0.12
MIN_COLUMN_LINES = 4
MIN_MEANINGFUL_OVERLAP_AXIS_RATIO = 0.35
MIN_MEANINGFUL_OVERLAP_AREA_RATIO = 0.10


def _meaningful_text_box_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    """Reject font-box bleed while retaining materially overlaid text.

    PDF span boxes include ascender/descender padding, so normally spaced
    adjacent lines often intersect by one or two points even though their
    rendered glyphs do not. A real collision must occupy a meaningful share
    of both the smaller box's width and height.
    """

    left_width = max(0.0, left[2] - left[0])
    left_height = max(0.0, left[3] - left[1])
    right_width = max(0.0, right[2] - right[0])
    right_height = max(0.0, right[3] - right[1])
    smaller_width = min(left_width, right_width)
    smaller_height = min(left_height, right_height)
    if smaller_width <= 0.0 or smaller_height <= 0.0:
        return False

    overlap_x = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    overlap_y = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    if overlap_x <= 0.0 or overlap_y <= 0.0:
        return False

    width_ratio = overlap_x / smaller_width
    height_ratio = overlap_y / smaller_height
    area_ratio = (overlap_x * overlap_y) / (smaller_width * smaller_height)
    return (
        width_ratio >= MIN_MEANINGFUL_OVERLAP_AXIS_RATIO
        and height_ratio >= MIN_MEANINGFUL_OVERLAP_AXIS_RATIO
        and area_ratio >= MIN_MEANINGFUL_OVERLAP_AREA_RATIO
    )


class TextExtractor:
    """
    Layout-aware text extraction.

    PDF chain:
        PyMuPDF words/blocks -> pdfplumber words -> OCR

    The returned dict keeps old keys used by the current pipeline and adds:
        ordered_text
        raw_layout_blocks
        page_layouts
        layout
        reading_order
        engine
        quality_score
        warnings
    """

    def __init__(
        self,
        enable_ocr: bool = True,
        ocr_language: str = "eng",
        tesseract_cmd: str | None = None,
    ) -> None:
        self.enable_ocr = enable_ocr
        self.ocr_language = ocr_language

        if tesseract_cmd and pytesseract is not None:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract(self, file_path: str) -> dict[str, Any]:
        result = self._empty_result(file_path)

        validation_error = self._validate_file(file_path)
        if validation_error:
            result["error"] = validation_error
            return result

        extension = Path(file_path).suffix.lower()

        try:
            if extension == ".pdf":
                result.update(self._extract_pdf(file_path))
            else:
                result.update(self._extract_docx(file_path))

            result["links"] = self.extract_links(file_path)
            result["text"] = self._normalize_extracted_text(result["text"])
            result["ordered_text"] = result["text"]
            result["words"] = len(re.findall(r"\S+", result["text"]))
            result["chars"] = len(result["text"])
            result["success"] = bool(result["text"].strip())

            if not result["success"] and not result["error"]:
                result["error"] = "No readable text was extracted."

            result["quality_score"] = self._quality_score(result)

        except Exception as exc:
            result["success"] = False
            result["error"] = f"{type(exc).__name__}: {exc}"

        return result

    def _empty_result(self, file_path: str) -> dict[str, Any]:
        return {
            "success": False,
            "file_name": os.path.basename(file_path) if file_path else "",
            "file_type": "",
            "pages": 0,
            "words": 0,
            "chars": 0,
            "links": [],
            "text": "",
            "raw_text": "",
            "ordered_text": "",
            "raw_layout_blocks": [],
            "page_layouts": [],
            "visual_metadata": {
                "status": "not_available",
                "source": "none",
            },
            "layout": "unknown",
            "reading_order": "unknown",
            "engine": "unknown",
            "ocr_used": False,
            "ocr_available": OCR_AVAILABLE,
            "quality_score": 0,
            "warnings": [],
            "error": None,
            "ocr_error": None,
        }

    def _validate_file(self, file_path: str) -> str | None:
        if not file_path:
            return "No file path provided."
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"

        extension = Path(file_path).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            return (
                f"Unsupported file type: {extension}. "
                f"Supported extensions: {sorted(SUPPORTED_EXTENSIONS)}"
            )
        return None

    # -----------------------------------------------------------------
    # PDF
    # -----------------------------------------------------------------

    def _extract_pdf(self, file_path: str) -> dict[str, Any]:
        page_records: list[dict[str, Any]] = []
        all_blocks: list[dict[str, Any]] = []
        engines: set[str] = set()
        warnings: list[str] = []
        ocr_used = False
        contact_region: dict[str, Any] = {
            "possible_image_only_contact": False,
            "image_only_contact_fields": [],
            "contact_readability": "unknown",
            "contact_ocr_used": False,
            "contact_ocr_status": "not_needed",
            "contact_ocr_error": None,
            "contact_ocr_text": "",
            "contact_ocr_blocks": [],
            "warnings": [],
        }

        plumber_doc = pdfplumber.open(file_path)
        pymupdf_doc = fitz.open(file_path) if PYMUPDF_AVAILABLE else None

        try:
            page_count = len(pymupdf_doc) if pymupdf_doc is not None else len(plumber_doc.pages)

            for page_index in range(page_count):
                page_number = page_index + 1
                plumber_page = plumber_doc.pages[page_index]
                fitz_page = pymupdf_doc[page_index] if pymupdf_doc is not None else None

                width = float(fitz_page.rect.width if fitz_page is not None else plumber_page.width)
                height = float(
                    fitz_page.rect.height if fitz_page is not None else plumber_page.height
                )

                words: list[dict[str, Any]] = []
                engine = "unknown"

                if fitz_page is not None:
                    words = self._pymupdf_words(fitz_page)
                    engine = "pymupdf"

                if len(words) < MIN_TEXT_WORDS_PER_PAGE:
                    plumber_words = self._pdfplumber_words(plumber_page)
                    if len(plumber_words) > len(words):
                        words = plumber_words
                        engine = "pdfplumber"

                if (
                    len(words) < MIN_TEXT_WORDS_PER_PAGE
                    and self.enable_ocr
                    and OCR_AVAILABLE
                    and fitz_page is not None
                ):
                    ocr_words = self._ocr_words(fitz_page)
                    if len(ocr_words) > len(words):
                        words = ocr_words
                        engine = "ocr"
                        ocr_used = True

                if not words:
                    warnings.append(f"page_{page_number}:no_text")
                    page_records.append(
                        {
                            "page": page_number,
                            "width": width,
                            "height": height,
                            "layout": "unknown",
                            "reading_order": "unknown",
                            "split_x": None,
                            "confidence": 0.0,
                            "engine": engine,
                            "blocks": [],
                            "ordered_ids": [],
                            "warnings": ["no_text"],
                        }
                    )
                    continue

                lines = self._words_to_lines(
                    words=words,
                    page_number=page_number,
                    page_width=width,
                    engine=engine,
                )
                image_rects = self._page_image_rects(fitz_page)
                link_rects = self._page_link_rects(fitz_page)
                ordered = self._order_page(
                    lines,
                    width,
                    height,
                    image_rects=image_rects,
                    link_rects=link_rects,
                )
                if page_index == 0:
                    contact_region = self._analyze_contact_region(
                        fitz_page,
                        lines,
                        image_rects,
                    )
                    warnings.extend(contact_region["warnings"])
                    if contact_region["contact_ocr_used"]:
                        ocr_used = True
                engines.add(engine)

                for order_index, block in enumerate(ordered["ordered_blocks"]):
                    block["order"] = order_index

                page_record = {
                    "page": page_number,
                    "width": width,
                    "height": height,
                    "layout": ordered["layout"],
                    "reading_order": ordered["reading_order"],
                    "split_x": ordered["split_x"],
                    "confidence": ordered["confidence"],
                    "engine": engine,
                    "blocks": lines,
                    "ordered_ids": [block["id"] for block in ordered["ordered_blocks"]],
                    "warnings": ordered["warnings"],
                    "zones": ordered.get("zones", []),
                    "reading_order_risk": ordered.get("reading_order_risk", "unknown"),
                }
                page_records.append(page_record)
                all_blocks.extend(lines)
                warnings.extend(f"page_{page_number}:{warning}" for warning in ordered["warnings"])

            repeated_ids = self._mark_repeated_headers_footers(page_records)
            self._augment_page_metrics(page_records, pymupdf_doc)
            if page_records:
                page_records[0]["image_only_contact_risk"] = bool(
                    contact_region["possible_image_only_contact"]
                )
            for page in page_records:
                for warning in page["warnings"]:
                    qualified = f"page_{page['page']}:{warning}"
                    if qualified not in warnings:
                        warnings.append(qualified)
            block_map = {block["id"]: block for block in all_blocks}

            raw_pages: list[str] = []
            cleaned_pages: list[str] = []

            for page in page_records:
                raw_lines: list[str] = []
                clean_lines: list[str] = []

                for block_id in page["ordered_ids"]:
                    block = block_map[block_id]
                    text = block["text"].strip()
                    if not text:
                        continue
                    raw_lines.append(text)
                    if block_id not in repeated_ids:
                        clean_lines.append(text)

                if raw_lines:
                    raw_pages.append("\n".join(raw_lines))
                if clean_lines:
                    cleaned_pages.append("\n".join(clean_lines))

            layouts = {page["layout"] for page in page_records if page["layout"] != "unknown"}
            reading_orders = {
                page["reading_order"] for page in page_records if page["reading_order"] != "unknown"
            }

            document_layout = (
                next(iter(layouts)) if len(layouts) == 1 else "mixed" if layouts else "unknown"
            )
            reading_order = (
                next(iter(reading_orders))
                if len(reading_orders) == 1
                else "mixed" if reading_orders else "unknown"
            )
            document_engine = (
                next(iter(engines)) if len(engines) == 1 else "mixed" if engines else "unknown"
            )

            public_page_layouts = [
                {
                    "page": page["page"],
                    "width": page["width"],
                    "height": page["height"],
                    "layout": page["layout"],
                    "reading_order": page["reading_order"],
                    "split_x": page["split_x"],
                    "confidence": page["confidence"],
                    "engine": page["engine"],
                    "block_ids": page["ordered_ids"],
                    "warnings": page["warnings"],
                    "zones": page.get("zones", []),
                    "reading_order_risk": page.get("reading_order_risk", "unknown"),
                    "useful_text_density": page.get("useful_text_density"),
                    "whitespace_ratio": page.get("whitespace_ratio"),
                    "minimum_font_size": page.get("minimum_font_size"),
                    "small_font_proportion": page.get("small_font_proportion"),
                    "decorative_shape_count": page.get("decorative_shape_count", 0),
                    "image_only_contact_risk": page.get("image_only_contact_risk", False),
                    "sparse_trailing_page": page.get("sparse_trailing_page", False),
                    "column_complexity": page.get("column_complexity", 1),
                }
                for page in page_records
            ]

            if repeated_ids:
                warnings.append(f"removed_repeated_header_footer_blocks:{len(repeated_ids)}")

            visual_metadata = self._pdf_visual_metadata(pymupdf_doc, all_blocks)
            visual_metadata.update(
                {
                    "possible_image_only_contact": contact_region[
                        "possible_image_only_contact"
                    ],
                    "image_only_contact_fields": contact_region[
                        "image_only_contact_fields"
                    ],
                    "contact_readability": contact_region["contact_readability"],
                    "contact_ocr_used": contact_region["contact_ocr_used"],
                    "contact_ocr_status": contact_region["contact_ocr_status"],
                    "contact_ocr_error": contact_region["contact_ocr_error"],
                }
            )

            return {
                "file_type": "pdf",
                "pages": page_count,
                "raw_text": "\n\n".join(raw_pages).strip(),
                "text": "\n\n".join(cleaned_pages).strip(),
                "ordered_text": "\n\n".join(cleaned_pages).strip(),
                "raw_layout_blocks": all_blocks,
                "page_layouts": public_page_layouts,
                "layout": document_layout,
                "reading_order": reading_order,
                "engine": document_engine,
                "ocr_used": ocr_used,
                "ocr_available": OCR_AVAILABLE,
                "warnings": sorted(set(warnings)),
                "visual_metadata": visual_metadata,
                "contact_ocr_text": contact_region["contact_ocr_text"],
                "contact_ocr_blocks": contact_region["contact_ocr_blocks"],
            }
        finally:
            plumber_doc.close()
            if pymupdf_doc is not None:
                pymupdf_doc.close()

    @staticmethod
    def _page_image_rects(page: Any) -> list[tuple[float, float, float, float]]:
        if page is None:
            return []
        output: list[tuple[float, float, float, float]] = []
        try:
            for image in page.get_images(full=True) or []:
                for rect in page.get_image_rects(int(image[0])) or []:
                    output.append(
                        (
                            float(rect.x0),
                            float(rect.y0),
                            float(rect.x1),
                            float(rect.y1),
                        )
                    )
        except Exception:
            return []
        return output

    @staticmethod
    def _page_link_rects(page: Any) -> list[dict[str, Any]]:
        if page is None:
            return []
        output: list[dict[str, Any]] = []
        try:
            for link in page.get_links() or []:
                uri = str(link.get("uri") or "").strip()
                rect = link.get("from")
                if not uri or rect is None:
                    continue
                output.append(
                    {
                        "uri": uri,
                        "bbox": (
                            float(rect.x0),
                            float(rect.y0),
                            float(rect.x1),
                            float(rect.y1),
                        ),
                    }
                )
        except Exception:
            return []
        return output

    @staticmethod
    def _contact_fields(text: str) -> set[str]:
        fields: set[str] = set()
        if re.search(
            r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,24}\b",
            text,
        ):
            fields.add("email")
        for candidate in re.findall(r"(?<!\d)\+?\d[\d .()/-]{6,}\d(?!\d)", text):
            digits = re.sub(r"\D", "", candidate)
            if 7 <= len(digits) <= 15 and not re.search(
                r"\b(?:19|20)\d{2}\D+(?:19|20)\d{2}\b",
                candidate,
            ):
                fields.add("phone")
                break
        if re.search(r"(?i)\blinkedin(?:\.com|:|/)", text):
            fields.add("linkedin")
        return fields

    def _analyze_contact_region(
        self,
        page: Any,
        blocks: list[dict[str, Any]],
        image_rects: list[tuple[float, float, float, float]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "possible_image_only_contact": False,
            "image_only_contact_fields": [],
            "contact_readability": "unknown",
            "contact_ocr_used": False,
            "contact_ocr_status": "not_needed",
            "contact_ocr_error": None,
            "contact_ocr_text": "",
            "contact_ocr_blocks": [],
            "warnings": [],
        }
        if page is None:
            return result

        page_height = float(page.rect.height)
        header_limit = max(150.0, page_height * 0.22)
        header_blocks = [
            block for block in blocks if float((block.get("bbox") or {}).get("top", 9999)) < header_limit
        ]
        header_text = "\n".join(str(block.get("text") or "") for block in header_blocks)
        present = self._contact_fields(header_text)
        missing = sorted({"email", "phone", "linkedin"} - present)
        header_images = [
            rect for rect in image_rects if rect[1] < header_limit and rect[3] > 0.0
        ]

        if not missing:
            result["contact_readability"] = "readable"
            return result
        if not header_images:
            core_present = present & {"email", "phone"}
            if core_present:
                result["contact_readability"] = "readable"
            elif present:
                result["contact_readability"] = "partially_readable"
                result["warnings"].append("CONTACT_MISSING")
            else:
                result["contact_readability"] = "unknown"
                result["warnings"].append("CONTACT_MISSING")
            return result

        result["possible_image_only_contact"] = True
        result["image_only_contact_fields"] = missing
        result["contact_readability"] = "image_only"
        result["warnings"].append("POSSIBLE_IMAGE_ONLY_CONTACT")

        if not self.enable_ocr:
            result["contact_ocr_status"] = "disabled"
            result["warnings"].extend(["CONTACT_UNREADABLE", "CONTACT_MISSING"])
            return result
        if not OCR_AVAILABLE or pytesseract is None or Image is None:
            result["contact_ocr_status"] = "unavailable"
            result["contact_ocr_error"] = "Targeted contact OCR dependency is unavailable."
            result["warnings"].extend(["CONTACT_UNREADABLE", "CONTACT_MISSING"])
            return result

        crop = (
            max(0.0, min(rect[0] for rect in header_images) - 4.0),
            max(0.0, min(rect[1] for rect in header_images) - 4.0),
            min(float(page.rect.width), max(rect[2] for rect in header_images) + 4.0),
            min(page_height, max(rect[3] for rect in header_images) + 4.0),
        )
        result["contact_ocr_used"] = True
        result["warnings"].append("CONTACT_IMAGE_OCR_USED")
        try:
            zoom = 3.0
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(zoom, zoom),
                clip=fitz.Rect(*crop),
                alpha=False,
            )
            image = Image.frombytes(
                "RGB",
                (pixmap.width, pixmap.height),
                pixmap.samples,
            )
            ocr_text = str(
                pytesseract.image_to_string(
                    image,
                    lang=self.ocr_language,
                    config="--psm 6",
                )
                or ""
            ).strip()
        except Exception as exc:
            result["contact_ocr_status"] = "failed"
            result["contact_ocr_error"] = (
                f"{type(exc).__name__}: targeted contact OCR could not be completed."
            )
            result["warnings"].extend(["CONTACT_UNREADABLE", "CONTACT_MISSING"])
            return result

        recovered = sorted(self._contact_fields(ocr_text))
        result["contact_ocr_text"] = ocr_text
        if ocr_text:
            result["contact_ocr_blocks"] = [
                {
                    "id": "p1_contact_ocr_b0",
                    "page": 1,
                    "text": ocr_text,
                    "bbox": {
                        "x0": round(crop[0], 3),
                        "top": round(crop[1], 3),
                        "x1": round(crop[2], 3),
                        "bottom": round(crop[3], 3),
                    },
                    "column": "full_width",
                    "zone_id": "p1_contact_ocr",
                    "zone_kind": "header",
                    "order": 0,
                    "engine": "ocr",
                    "block_type": "ocr_line",
                    "is_repeated_header_footer": False,
                }
            ]
        if recovered:
            result["image_only_contact_fields"] = recovered
            result["contact_readability"] = (
                "readable"
                if set(missing).issubset(recovered)
                else "partially_readable"
            )
            result["contact_ocr_status"] = (
                "complete"
                if set(missing).issubset(recovered)
                else "partial"
            )
            if result["contact_ocr_status"] == "partial":
                result["warnings"].extend(["CONTACT_UNREADABLE", "CONTACT_MISSING"])
        else:
            result["contact_ocr_status"] = "failed"
            result["contact_readability"] = "unreadable"
            result["warnings"].extend(["CONTACT_UNREADABLE", "CONTACT_MISSING"])
        return result

    def _pdf_visual_metadata(self, document: Any, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        """Collect bounded visual facts while the already-open PDF is available."""

        repeated = sum(bool(item.get("is_repeated_header_footer")) for item in blocks)
        if document is None:
            return {
                "status": "cannot_verify",
                "source": "pymupdf_unavailable",
                "repeated_header_footer_count": repeated,
            }

        image_count = 0
        icon_count = 0
        decorative_count = 0
        candidate_photo = False
        drawing_count = 0
        font_sizes: set[float] = set()
        font_names: set[str] = set()
        colors: set[int] = set()
        small_font_count = 0
        white_text_count = 0
        overlap_count = 0

        for page in document:
            page_area = max(1.0, float(page.rect.width) * float(page.rect.height))
            images = list(page.get_images(full=True) or [])
            image_count += len(images)
            for image in images:
                xref = int(image[0])
                rects = list(page.get_image_rects(xref) or [])
                rect = rects[0] if rects else None
                if rect is None:
                    decorative_count += 1
                    continue
                ratio = max(0.0, float(rect.width) * float(rect.height) / page_area)
                aspect = float(rect.width) / max(1.0, float(rect.height))
                if ratio <= 0.012:
                    icon_count += 1
                elif (
                    ratio >= 0.025 and 0.55 <= aspect <= 1.35 and rect.y0 <= page.rect.height * 0.35
                ):
                    candidate_photo = True
                else:
                    decorative_count += 1

            try:
                drawing_count += len(page.get_drawings() or [])
            except Exception:
                pass

            span_boxes: list[tuple[float, float, float, float]] = []
            page_dict = page.get_text("dict") or {}
            for block in page_dict.get("blocks", []) or []:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []) or []:
                    for span in line.get("spans", []) or []:
                        text = str(span.get("text") or "").strip()
                        if not text:
                            continue
                        size = float(span.get("size") or 0.0)
                        if size > 0:
                            font_sizes.add(round(size, 2))
                        if 0 < size < 8.0:
                            small_font_count += 1
                        font = str(span.get("font") or "").strip()
                        if font:
                            font_names.add(font)
                        color = int(span.get("color") or 0)
                        colors.add(color)
                        if (color & 0xFFFFFF) >= 0xF5F5F5:
                            white_text_count += 1
                        bbox = span.get("bbox")
                        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                            x0, top, x1, bottom = (float(value) for value in bbox)
                            span_boxes.append((x0, top, x1, bottom))

            # Bound overlap work for unusually complex documents.
            candidates = sorted(span_boxes[:400], key=lambda item: (item[1], item[0]))
            for index, left in enumerate(candidates):
                for right in candidates[index + 1 :]:
                    if right[1] >= left[3]:
                        break
                    if _meaningful_text_box_overlap(left, right):
                        overlap_count += 1

        chromatic = {color for color in colors if color not in {0, 0xFFFFFF}}
        return {
            "status": "complete",
            "source": "pymupdf_in_pass_visual_metadata",
            "has_images": bool(image_count),
            "image_count": image_count,
            "icon_count": icon_count,
            "candidate_photo_detected": candidate_photo,
            "decorative_image_count": decorative_count,
            "image_only_contact_fields": [],
            "text_box_count": None,
            "drawing_count": drawing_count,
            "shape_count": drawing_count,
            "table_count": None,
            "has_color": bool(chromatic),
            "detected_color_count": len(colors),
            "contrast_status": "cannot_verify",
            "ats_color_risk": "unknown",
            "font_sizes": sorted(font_sizes),
            "font_names": sorted(font_names),
            "small_font_count": small_font_count,
            "overlap_count": overlap_count,
            "hidden_text_count": None,
            "white_text_count": white_text_count,
            "duplicate_ratio": None,
            "repeated_header_footer_count": repeated,
        }

    @staticmethod
    def _augment_page_metrics(
        page_records: list[dict[str, Any]],
        document: Any,
    ) -> None:
        useful_character_counts: list[int] = []
        vertical_coverages: list[float] = []
        for page_index, page in enumerate(page_records):
            blocks = list(page.get("blocks") or [])
            useful = [
                block
                for block in blocks
                if str(block.get("text") or "").strip()
                and not block.get("is_repeated_header_footer")
                and not block.get("is_template_residue")
                and not re.search(
                    r"(?i)^\s*page\s+\d+\s+(?:of|/)\s+\d+",
                    str(block.get("text") or ""),
                )
            ]
            page_area = max(1.0, float(page["width"]) * float(page["height"]))
            text_area = sum(
                max(
                    0.0,
                    float((block.get("bbox") or {}).get("x1", 0.0))
                    - float((block.get("bbox") or {}).get("x0", 0.0)),
                )
                * max(
                    0.0,
                    float((block.get("bbox") or {}).get("bottom", 0.0))
                    - float((block.get("bbox") or {}).get("top", 0.0)),
                )
                for block in useful
            )
            density = max(0.0, min(1.0, text_area / page_area))
            sizes = [
                float(block.get("font_size") or 0.0)
                for block in useful
                if float(block.get("font_size") or 0.0) > 0.0
            ]
            small_count = sum(size < 8.0 for size in sizes)
            top = min(
                (float((block.get("bbox") or {}).get("top", 0.0)) for block in useful),
                default=0.0,
            )
            bottom = max(
                (float((block.get("bbox") or {}).get("bottom", 0.0)) for block in useful),
                default=0.0,
            )
            vertical_coverage = max(
                0.0,
                min(1.0, (bottom - top) / max(1.0, float(page["height"]))),
            )
            useful_character_counts.append(
                sum(len(str(block.get("text") or "")) for block in useful)
            )
            vertical_coverages.append(vertical_coverage)
            page["useful_text_density"] = round(density, 4)
            page["whitespace_ratio"] = round(1.0 - density, 4)
            page["minimum_font_size"] = round(min(sizes), 2) if sizes else None
            page["small_font_proportion"] = (
                round(small_count / len(sizes), 4) if sizes else None
            )
            try:
                page["decorative_shape_count"] = (
                    len(document[page_index].get_drawings() or [])
                    if document is not None
                    else 0
                )
            except Exception:
                page["decorative_shape_count"] = 0
            page["column_complexity"] = (
                2 if page.get("layout") == "two_column" else 1
            )
            page["sparse_trailing_page"] = False

            page_warnings = page.setdefault("warnings", [])
            if page.get("reading_order_risk") in {"medium", "high"}:
                page_warnings.append("MULTI_COLUMN_READING_RISK")
            if sizes and min(sizes) < 7.5 and small_count / len(sizes) >= 0.25:
                page_warnings.append("EXCESSIVE_SMALL_TEXT")
            if page["decorative_shape_count"] >= 15:
                page_warnings.append("TEMPLATE_DECORATION_OVERUSE")

        if len(page_records) >= 2:
            last_index = len(page_records) - 1
            prior_average = sum(useful_character_counts[:-1]) / max(
                1,
                len(useful_character_counts) - 1,
            )
            last = page_records[last_index]
            sparse = (
                vertical_coverages[last_index] < 0.5
                and (
                    float(last.get("useful_text_density") or 0.0) < 0.065
                    or useful_character_counts[last_index] < prior_average * 0.6
                )
            )
            if sparse:
                last["sparse_trailing_page"] = True
                last["warnings"].extend(
                    ["SPARSE_TRAILING_PAGE", "EXCESSIVE_WHITESPACE"]
                )

        for page in page_records:
            page["warnings"] = list(dict.fromkeys(page.get("warnings") or []))

    def _pymupdf_words(self, page: Any) -> list[dict[str, Any]]:
        words: list[dict[str, Any]] = []
        try:
            spans: list[dict[str, Any]] = []
            page_dict = page.get_text("dict") or {}
            for block in page_dict.get("blocks", []) or []:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []) or []:
                    direction = line.get("dir") or (1.0, 0.0)
                    rotation = round(
                        math.degrees(math.atan2(float(direction[1]), float(direction[0]))),
                        3,
                    )
                    for span in line.get("spans", []) or []:
                        bbox = span.get("bbox")
                        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                            continue
                        font = str(span.get("font") or "")
                        flags = int(span.get("flags") or 0)
                        spans.append(
                            {
                                "bbox": tuple(float(value) for value in bbox),
                                "font_size": float(span.get("size") or 0.0) or None,
                                "font_family": font or None,
                                "font_weight": (
                                    "bold"
                                    if "bold" in font.casefold() or bool(flags & 16)
                                    else "normal"
                                ),
                                "font_style": (
                                    "italic"
                                    if "italic" in font.casefold()
                                    or "oblique" in font.casefold()
                                    or bool(flags & 2)
                                    else "normal"
                                ),
                                "rotation": rotation,
                            }
                        )
            for item in page.get_text("words", sort=True):
                x0, top, x1, bottom, text, block_no, line_no, word_no = item[:8]
                if str(text).strip():
                    center_x = (float(x0) + float(x1)) / 2.0
                    center_y = (float(top) + float(bottom)) / 2.0
                    style = next(
                        (
                            span
                            for span in spans
                            if span["bbox"][0] - 0.5 <= center_x <= span["bbox"][2] + 0.5
                            and span["bbox"][1] - 0.5 <= center_y <= span["bbox"][3] + 0.5
                        ),
                        {},
                    )
                    words.append(
                        {
                            "text": str(text),
                            "x0": float(x0),
                            "top": float(top),
                            "x1": float(x1),
                            "bottom": float(bottom),
                            "line_id": f"{block_no}:{line_no}",
                            "word_no": int(word_no),
                            "font_size": style.get("font_size"),
                            "font_family": style.get("font_family"),
                            "font_weight": style.get("font_weight", "unknown"),
                            "font_style": style.get("font_style", "unknown"),
                            "rotation": style.get("rotation", 0.0),
                        }
                    )
        except Exception:
            return []
        return words

    def _pdfplumber_words(self, page: Any) -> list[dict[str, Any]]:
        try:
            extracted = (
                page.extract_words(
                    keep_blank_chars=False,
                    x_tolerance=3,
                    y_tolerance=3,
                )
                or []
            )
        except Exception:
            return []

        return [
            {
                "text": str(word.get("text", "")),
                "x0": float(word.get("x0", 0)),
                "top": float(word.get("top", 0)),
                "x1": float(word.get("x1", 0)),
                "bottom": float(word.get("bottom", 0)),
                "line_id": None,
                "word_no": index,
                "font_size": None,
                "font_family": None,
                "font_weight": "unknown",
                "font_style": "unknown",
                "rotation": 0.0,
            }
            for index, word in enumerate(extracted)
            if str(word.get("text", "")).strip()
        ]

    def _ocr_words(self, page: Any) -> list[dict[str, Any]]:
        if not OCR_AVAILABLE:
            return []

        try:
            zoom = 2.0
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image = Image.frombytes(
                "RGB",
                [pixmap.width, pixmap.height],
                pixmap.samples,
            )
            data = pytesseract.image_to_data(
                image,
                lang=self.ocr_language,
                config="--psm 3",
                output_type=Output.DICT,
            )
        except Exception:
            return []

        words: list[dict[str, Any]] = []
        count = len(data.get("text", []))

        for index in range(count):
            text = str(data["text"][index]).strip()
            if not text:
                continue

            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                confidence = -1

            if confidence < 25:
                continue

            x0 = float(data["left"][index]) / zoom
            top = float(data["top"][index]) / zoom
            width = float(data["width"][index]) / zoom
            height = float(data["height"][index]) / zoom

            words.append(
                {
                    "text": text,
                    "x0": x0,
                    "top": top,
                    "x1": x0 + width,
                    "bottom": top + height,
                    "line_id": (
                        f"ocr:{data['block_num'][index]}:"
                        f"{data['par_num'][index]}:{data['line_num'][index]}"
                    ),
                    "word_no": int(data["word_num"][index]),
                    "font_size": None,
                    "font_family": None,
                    "font_weight": "unknown",
                    "font_style": "unknown",
                    "rotation": 0.0,
                }
            )

        return words

    def _words_to_lines(
        self,
        words: list[dict[str, Any]],
        page_number: int,
        page_width: float,
        engine: str,
    ) -> list[dict[str, Any]]:
        """
        Build line-like blocks and split a visual row when it contains a large
        horizontal gap. This is important for two-column resumes.
        """
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        loose_words: list[dict[str, Any]] = []

        for word in words:
            line_id = word.get("line_id")
            if line_id:
                grouped[str(line_id)].append(word)
            else:
                loose_words.append(word)

        # pdfplumber does not provide block/line ids, so group by vertical position.
        for word in loose_words:
            center_y = (float(word["top"]) + float(word["bottom"])) / 2
            key = f"y:{round(center_y / 3.0) * 3.0:.1f}"
            grouped[key].append(word)

        lines: list[dict[str, Any]] = []
        block_index = 0
        large_gap = max(28.0, page_width * 0.055)

        for _, row_words in grouped.items():
            if engine == "ocr":
                # Tesseract's word numbers preserve logical reading order for
                # both left-to-right and right-to-left lines. Re-sorting Arabic
                # words by x-coordinate reverses their meaning.
                row_words.sort(key=lambda item: int(item.get("word_no", 0)))
            else:
                row_words.sort(key=lambda item: (float(item["x0"]), int(item.get("word_no", 0))))
            segments: list[list[dict[str, Any]]] = [[]]

            previous_x1: float | None = None
            for word in row_words:
                x0 = float(word["x0"])
                if previous_x1 is not None and x0 - previous_x1 > large_gap:
                    segments.append([])
                segments[-1].append(word)
                previous_x1 = float(word["x1"])

            for segment in segments:
                if not segment:
                    continue

                text = " ".join(str(item["text"]).strip() for item in segment).strip()
                if not text:
                    continue

                x0 = min(float(item["x0"]) for item in segment)
                top = min(float(item["top"]) for item in segment)
                x1 = max(float(item["x1"]) for item in segment)
                bottom = max(float(item["bottom"]) for item in segment)

                lines.append(
                    {
                        "id": f"p{page_number}_b{block_index}",
                        "page": page_number,
                        "text": text,
                        "bbox": {
                            "x0": round(x0, 3),
                            "top": round(top, 3),
                            "x1": round(x1, 3),
                            "bottom": round(bottom, 3),
                        },
                        "column": "unknown",
                        "order": 0,
                        "engine": engine,
                        "block_type": "ocr_line" if engine == "ocr" else "line",
                        "is_repeated_header_footer": False,
                        "font_size": self._representative_number(
                            [item.get("font_size") for item in segment]
                        ),
                        "font_family": self._representative_text(
                            [item.get("font_family") for item in segment]
                        ),
                        "font_weight": self._representative_text(
                            [item.get("font_weight") for item in segment],
                            default="unknown",
                        ),
                        "font_style": self._representative_text(
                            [item.get("font_style") for item in segment],
                            default="unknown",
                        ),
                        "rotation": self._representative_number(
                            [item.get("rotation") for item in segment],
                            default=0.0,
                        ),
                    }
                )
                block_index += 1

        lines.sort(
            key=lambda block: (
                float(block["bbox"]["top"]),
                float(block["bbox"]["x0"]),
            )
        )
        return lines

    @staticmethod
    def _representative_number(
        values: list[Any],
        *,
        default: float | None = None,
    ) -> float | None:
        numeric = [float(value) for value in values if isinstance(value, (int, float))]
        if not numeric:
            return default
        numeric.sort()
        middle = len(numeric) // 2
        if len(numeric) % 2:
            return round(numeric[middle], 3)
        return round((numeric[middle - 1] + numeric[middle]) / 2.0, 3)

    @staticmethod
    def _representative_text(
        values: list[Any],
        *,
        default: str | None = None,
    ) -> str | None:
        text_values = [str(value).strip() for value in values if str(value or "").strip()]
        if not text_values:
            return default
        return Counter(text_values).most_common(1)[0][0]

    def _order_page(
        self,
        lines: list[dict[str, Any]],
        page_width: float,
        page_height: float,
        *,
        image_rects: list[tuple[float, float, float, float]] | None = None,
        link_rects: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        split = self._detect_column_split(lines, page_width)

        if split is None:
            graph = _build_page_graph(
                lines,
                page_width=page_width,
                page_height=page_height,
                split_x=None,
                confidence=0.9,
                image_rects=image_rects,
                link_rects=link_rects,
            )
            graph.update({"split_x": None, "confidence": 0.9})
            return graph

        split_x, confidence = split
        graph = _build_page_graph(
            lines,
            page_width=page_width,
            page_height=page_height,
            split_x=split_x,
            confidence=confidence,
            image_rects=image_rects,
            link_rects=link_rects,
        )
        graph.update(
            {
                "split_x": round(split_x, 3),
                "confidence": round(confidence, 3),
            }
        )
        return graph

    def _detect_column_split(
        self,
        lines: list[dict[str, Any]],
        page_width: float,
    ) -> tuple[float, float] | None:
        if len(lines) < MIN_COLUMN_LINES * 2:
            return None

        candidates = [
            page_width * ratio
            for ratio in (0.32, 0.36, 0.40, 0.44, 0.48, 0.52, 0.56, 0.60, 0.64, 0.68)
        ]
        best: tuple[float, float] | None = None
        best_score = float("-inf")
        margin = max(10.0, page_width * 0.018)

        for split_x in candidates:
            left_count = 0
            right_count = 0
            crossing_count = 0
            left_edges: list[float] = []
            right_edges: list[float] = []

            for block in lines:
                bbox = block["bbox"]
                x0 = float(bbox["x0"])
                x1 = float(bbox["x1"])
                center = (x0 + x1) / 2

                if x0 < split_x - margin and x1 > split_x + margin:
                    crossing_count += 1
                elif center < split_x:
                    left_count += 1
                    left_edges.append(x1)
                else:
                    right_count += 1
                    right_edges.append(x0)

            if left_count < MIN_COLUMN_LINES or right_count < MIN_COLUMN_LINES:
                continue

            balance = min(left_count, right_count) / max(left_count, right_count)
            crossing_ratio = crossing_count / max(1, len(lines))
            left_clearance = split_x - max(
                (edge for edge in left_edges if edge <= split_x),
                default=split_x,
            )
            right_clearance = min(
                (edge for edge in right_edges if edge >= split_x),
                default=split_x,
            ) - split_x
            gutter_clearance = max(0.0, min(left_clearance, right_clearance))
            score = (
                (min(left_count, right_count) * balance)
                - (crossing_count * 1.4)
                + (gutter_clearance * 0.55)
            )

            if crossing_ratio > 0.42:
                continue

            if score > best_score:
                confidence = max(
                    0.0,
                    min(1.0, (balance * 0.65) + ((1.0 - crossing_ratio) * 0.35)),
                )
                best_score = score
                best = (split_x, confidence)

        if best is None or best_score < MIN_COLUMN_LINES * 0.65:
            return None

        return best

    def _paired_line_ratio(
        self,
        left: list[dict[str, Any]],
        right: list[dict[str, Any]],
    ) -> float:
        if not left or not right:
            return 0.0

        matched = 0
        right_centers = [
            (
                (float(block["bbox"]["top"]) + float(block["bbox"]["bottom"])) / 2,
                max(3.0, float(block["bbox"]["bottom"]) - float(block["bbox"]["top"])),
            )
            for block in right
        ]

        for block in left:
            center = (float(block["bbox"]["top"]) + float(block["bbox"]["bottom"])) / 2
            height = max(
                3.0,
                float(block["bbox"]["bottom"]) - float(block["bbox"]["top"]),
            )

            if any(
                abs(center - other_center) <= max(height, other_height) * 0.8
                for other_center, other_height in right_centers
            ):
                matched += 1

        return matched / max(1, min(len(left), len(right)))

    def _row_wise_order(
        self,
        lines: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return sorted(
            lines,
            key=lambda block: (
                round(float(block["bbox"]["top"]) / 3.0) * 3.0,
                float(block["bbox"]["x0"]),
            ),
        )

    def _column_wise_order(
        self,
        full_width: list[dict[str, Any]],
        left: list[dict[str, Any]],
        right: list[dict[str, Any]],
        page_height: float,
    ) -> list[dict[str, Any]]:
        top_full = [
            block for block in full_width if float(block["bbox"]["top"]) <= page_height * 0.18
        ]
        bottom_full = [
            block for block in full_width if float(block["bbox"]["top"]) >= page_height * 0.82
        ]
        middle_full = [
            block for block in full_width if block not in top_full and block not in bottom_full
        ]

        def by_yx(block: dict[str, Any]) -> tuple[float, float]:
            return (
                float(block["bbox"]["top"]),
                float(block["bbox"]["x0"]),
            )

        # Middle full-width blocks are retained after the columns. Their original
        # coordinates remain available in raw_layout_blocks for later refinements.
        return (
            sorted(top_full, key=by_yx)
            + sorted(left, key=by_yx)
            + sorted(right, key=by_yx)
            + sorted(middle_full, key=by_yx)
            + sorted(bottom_full, key=by_yx)
        )

    def _mark_repeated_headers_footers(
        self,
        pages: list[dict[str, Any]],
    ) -> set[str]:
        candidates_by_key: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)

        for page in pages:
            page_number = int(page["page"])
            page_height = float(page["height"])

            for block in page["blocks"]:
                top = float(block["bbox"]["top"])
                bottom = float(block["bbox"]["bottom"])
                in_header = top <= page_height * HEADER_ZONE_RATIO
                in_footer = bottom >= page_height * (1.0 - FOOTER_ZONE_RATIO)

                if not (in_header or in_footer):
                    continue

                key = self._repeat_key(block["text"])
                if key:
                    candidates_by_key[key].append((page_number, block))

        repeated_ids: set[str] = set()

        for occurrences in candidates_by_key.values():
            distinct_pages = {page_number for page_number, _ in occurrences}
            if len(distinct_pages) < 2:
                continue

            for _, block in occurrences:
                block["is_repeated_header_footer"] = True
                block["block_type"] = "header" if float(block["bbox"]["top"]) < 100 else "footer"
                repeated_ids.add(block["id"])

        return repeated_ids

    def _repeat_key(self, text: str) -> str:
        normalized = text.lower().strip()
        normalized = re.sub(r"\bpage\s+\d+\s+of\s+\d+\b", "page # of #", normalized)
        normalized = re.sub(r"\d", "#", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^a-z0-9@.|#:/ -]", "", normalized)
        return normalized if len(normalized) >= 4 else ""

    # -----------------------------------------------------------------
    # DOCX
    # -----------------------------------------------------------------

    def _extract_docx(self, file_path: str) -> dict[str, Any]:
        """
        Extract DOCX through OOXML instead of concatenating python-docx
        paragraphs, tables, and text boxes independently.

        This prevents the same visible content from being emitted twice and
        reconstructs anchored/text-box content in visual order when position
        metadata is available.
        """
        analysis = analyze_docx_package(file_path)
        if analysis.get("status") != "ok":
            error = analysis.get("error") or "DOCX OOXML analysis failed"
            raise RuntimeError(str(error))

        raw_blocks = list(analysis.get("visual_blocks") or analysis.get("blocks") or [])
        deduplicated = deduplicate_blocks(raw_blocks)
        clean_blocks = list(deduplicated.get("blocks") or [])
        duplicate_analysis = dict(deduplicated.get("duplicate_analysis") or {})

        raw_text = "\n".join(
            str(block.get("text") or "").strip()
            for block in raw_blocks
            if str(block.get("text") or "").strip()
        )
        clean_text = "\n".join(
            str(block.get("text") or "").strip()
            for block in clean_blocks
            if str(block.get("text") or "").strip()
        )

        def public_block_type(
            block: dict[str, Any],
        ) -> str:
            """
            Map rich OOXML source kinds to the stable public schema.

            Rich values such as ``textbox`` remain available internally in
            ``docx_structure_analyzer``.  The pipeline's
            TextExtractionResult contract intentionally exposes only the
            established cross-format block types.
            """
            source_kind = (
                str(block.get("block_type") or block.get("source_kind") or "paragraph")
                .strip()
                .casefold()
            )

            if source_kind in {
                "table",
                "table_cell",
                "cell",
            }:
                return "table"
            if source_kind in {
                "header",
                "header_paragraph",
                "header_textbox",
            }:
                return "header"
            if source_kind in {
                "footer",
                "footer_paragraph",
                "footer_textbox",
            }:
                return "footer"

            # Text boxes, shapes, drawings with text, and ordinary OOXML
            # paragraphs are all represented as paragraphs in the stable
            # public extraction contract.
            return "paragraph"

        public_blocks: list[dict[str, Any]] = []
        for index, block in enumerate(clean_blocks):
            public_blocks.append(
                {
                    "id": f"p1_b{index}",
                    "page": 1,
                    "text": str(block.get("text") or "").strip(),
                    "bbox": block.get("bbox"),
                    "column": block.get("column") or "single",
                    "order": index,
                    "engine": "docx",
                    "block_type": public_block_type(block),
                    "is_repeated_header_footer": bool(
                        block.get(
                            "is_repeated_header_footer",
                            False,
                        )
                    ),
                }
            )

        warnings = list(analysis.get("warnings") or [])
        removed = int(duplicate_analysis.get("duplicate_occurrence_count", 0) or 0)
        if removed:
            warnings.append(f"removed_docx_duplicate_blocks:{removed}")
        mirror_factor = int(duplicate_analysis.get("mirror_factor", 1) or 1)
        if mirror_factor > 1:
            warnings.append(f"docx_alternate_representation_factor:{mirror_factor}")
        if analysis.get("reading_order") == "visual_top_to_bottom":
            warnings.append("docx_visual_order_reconstructed")
        if not any(block.get("bbox") for block in public_blocks):
            warnings.append("docx_has_no_pdf_coordinates")

        # Estimate pages conservatively. DOCX does not store stable rendered
        # page boundaries, so one logical page is used unless explicit page
        # breaks are found in the raw package analysis.
        pages = 1

        return {
            "file_type": "docx",
            "pages": pages,
            "raw_text": raw_text,
            "text": clean_text,
            "ordered_text": clean_text,
            "raw_layout_blocks": public_blocks,
            "page_layouts": [
                {
                    "page": 1,
                    "width": 0.0,
                    "height": 0.0,
                    "layout": analysis.get("layout") or "single_column",
                    "reading_order": "top_to_bottom",
                    "split_x": None,
                    "confidence": float(analysis.get("layout_confidence", 0.8) or 0.8),
                    # PageLayoutResult currently has no DOCX engine literal.
                    # The document-level engine below records ``docx_ooxml``.
                    "engine": "unknown",
                    "block_ids": [block["id"] for block in public_blocks],
                    "warnings": warnings,
                }
            ],
            "layout": analysis.get("layout") or "single_column",
            "reading_order": "top_to_bottom",
            "engine": "docx_ooxml",
            "ocr_used": False,
            "ocr_available": OCR_AVAILABLE,
            "warnings": list(dict.fromkeys(warnings)),
            "visual_metadata": {
                "status": "complete",
                "source": "docx_ooxml_in_pass_visual_metadata",
                **dict(analysis.get("document_assets") or {}),
                **{
                    key: value
                    for key, value in dict(analysis.get("document_style") or {}).items()
                    if key
                    in {
                        "has_color",
                        "detected_color_count",
                        "contrast_status",
                        "ats_color_risk",
                    }
                },
                "table_count": sum(
                    str(block.get("block_type") or "").casefold() in {"table", "table_cell", "cell"}
                    for block in raw_blocks
                ),
                "font_sizes": sorted(
                    {
                        float(block.get("font_size"))
                        for block in raw_blocks
                        if isinstance(block.get("font_size"), (int, float))
                    }
                ),
                "font_names": sorted(
                    {
                        str(block.get("font_name")).strip()
                        for block in raw_blocks
                        if str(block.get("font_name") or "").strip()
                    }
                ),
                "duplicate_ratio": duplicate_analysis.get("duplicate_ratio"),
                "repeated_header_footer_count": sum(
                    bool(block.get("is_repeated_header_footer")) for block in public_blocks
                ),
            },
        }

    def _normalize_cell_text(self, text: str) -> str:
        return " ".join(line.strip() for line in text.splitlines() if line.strip())

    # -----------------------------------------------------------------
    # Text normalization and quality
    # -----------------------------------------------------------------

    def _normalize_extracted_text(self, text: str) -> str:
        """
        Conservative normalization only. It never inserts words or expands
        abbreviations, so it will not create errors such as "A MBA ssador".
        """
        if not text:
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u00a0", " ")
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = self._fix_broken_contacts(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _fix_broken_contacts(self, text: str) -> str:
        text = re.sub(
            r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{1,3})\s+([A-Za-z]{1,3})(?=\b)",
            r"\1\2",
            text,
        )
        return text

    def _quality_score(self, result: dict[str, Any]) -> int:
        if not result.get("success"):
            return 0

        score = 100
        warnings = result.get("warnings", [])

        if result.get("ocr_used"):
            score -= 8
        if result.get("engine") == "mixed":
            score -= 4
        if result.get("layout") == "mixed":
            score -= 3
        if result.get("words", 0) < 50:
            score -= 20
        if any("no_text" in warning for warning in warnings):
            score -= 20
        if any("low_column_detection_confidence" in warning for warning in warnings):
            score -= 8

        return max(0, min(100, score))

    # -----------------------------------------------------------------
    # Links
    # -----------------------------------------------------------------

    def extract_links(self, file_path: str) -> list[str]:
        extension = Path(file_path).suffix.lower()
        if extension == ".pdf":
            return self._links_from_pdf(file_path)
        if extension == ".docx":
            return self._links_from_docx(file_path)
        return []

    def _links_from_pdf(self, file_path: str) -> list[str]:
        links: list[str] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    for item in getattr(page, "hyperlinks", []) or []:
                        uri = item.get("uri")
                        if self._valid_link(uri):
                            links.append(uri.strip())
        except Exception:
            pass
        if PYMUPDF_AVAILABLE:
            try:
                with fitz.open(file_path) as document:
                    for page in document:
                        for item in page.get_links() or []:
                            uri = item.get("uri")
                            if self._valid_link(uri):
                                links.append(str(uri).strip())
            except Exception:
                pass
        return self._unique(links)

    def _links_from_docx(self, file_path: str) -> list[str]:
        links: list[str] = []
        try:
            from docx.opc.constants import RELATIONSHIP_TYPE

            document = python_docx.Document(file_path)
            for relationship in document.part.rels.values():
                if relationship.reltype == RELATIONSHIP_TYPE.HYPERLINK:
                    target = relationship.target_ref
                    if self._valid_link(target):
                        links.append(target.strip())
        except Exception:
            return []
        return self._unique(links)

    def _valid_link(self, value: str | None) -> bool:
        if not value:
            return False
        lowered = value.strip().lower()
        return lowered.startswith(("http://", "https://", "mailto:", "tel:")) and not lowered.startswith(
            ("http://schemas.", "https://schemas.")
        )

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            key = value.lower()
            if key not in seen:
                seen.add(key)
                output.append(value)
        return output


if __name__ == "__main__":
    from pprint import pprint

    extractor = TextExtractor()
    path = input("Enter PDF/DOCX file path: ").strip()
    extraction = extractor.extract(path)

    pprint(
        {
            "success": extraction["success"],
            "file_name": extraction["file_name"],
            "pages": extraction["pages"],
            "layout": extraction["layout"],
            "reading_order": extraction["reading_order"],
            "engine": extraction["engine"],
            "quality_score": extraction["quality_score"],
            "warnings": extraction["warnings"],
        }
    )
    print("\n" + "=" * 80)
    print(extraction["text"])
