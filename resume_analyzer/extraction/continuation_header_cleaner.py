from __future__ import annotations

import copy
import re
from collections import defaultdict
from typing import Any


class ContinuationHeaderCleaner:
    """
    Remove continuation-page contact headers from downstream ordered text,
    while preserving and annotating every original layout block as evidence.

    This runs after ContactResolver, because the resolved candidate identity
    makes repeated-name/phone/email detection much safer.
    """

    PAGE_MARKER_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        page\s+\d+\s+(?:of|/)\s+\d+
        |
        resume\s*,?\s*p\.?\s*\d+
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

    def __init__(
        self,
        top_region_ratio: float = 0.18,
        max_top_blocks: int = 12,
    ) -> None:
        self.top_region_ratio = max(0.08, min(0.30, top_region_ratio))
        self.max_top_blocks = max(4, max_top_blocks)

    def clean(
        self,
        *,
        ordered_text: str,
        layout_blocks: list[Any] | None,
        page_layouts: list[Any] | None,
        candidate_name: str | None,
        candidate_phone: str | None,
        candidate_email: str | None = None,
    ) -> dict:
        """
        Return final ordered text, annotated blocks, duplicate evidence,
        and structured document issues for the later AI stage.
        """
        original_text = str(ordered_text or "")
        blocks = [
            self._to_mutable_dict(block)
            for block in (layout_blocks or [])
        ]
        page_layouts = [
            self._to_mutable_dict(page)
            for page in (page_layouts or [])
        ]

        if not blocks:
            return self._empty_result(
                ordered_text=original_text,
                layout_blocks=[],
            )

        page_heights = self._page_heights(
            page_layouts=page_layouts,
            blocks=blocks,
        )

        identity = {
            "name": self._normalize_text(candidate_name),
            "phone": self._normalize_digits(candidate_phone),
            "email": self._normalize_email(candidate_email),
        }

        blocks_by_page: dict[int, list[dict]] = defaultdict(list)

        for block in blocks:
            page_number = self._safe_int(block.get("page"), default=1)
            blocks_by_page[page_number].append(block)

            # Stable default annotations.
            block.setdefault("is_continuation_header", False)
            block.setdefault("excluded_from_ordered_text", False)
            block.setdefault("exclusion_reason", None)

        removed_blocks = []
        detected_pages = []

        for page_number, page_blocks in sorted(blocks_by_page.items()):
            page_blocks.sort(key=self._block_sort_key)

            if page_number <= 1:
                continue

            top_blocks = self._top_region_blocks(
                page_blocks=page_blocks,
                page_height=page_heights.get(page_number),
            )

            # Repeated identity blocks remain available as evidence even
            # when TextExtractor has already excluded them from ordered text.
            # They are required to confirm a continuation-page cluster.
            classified = [
                (
                    block,
                    self._classify_contact_header_block(
                        block=block,
                        identity=identity,
                    ),
                )
                for block in top_blocks
            ]

            present_signals = {
                signal
                for _, signal in classified
                if signal is not None
            }

            has_identity_signal = bool(
                present_signals.intersection(
                    {"candidate_name", "candidate_phone", "candidate_email"}
                )
            )
            identity_signal_count = len(
                present_signals.intersection(
                    {"candidate_name", "candidate_phone", "candidate_email"}
                )
            )
            has_page_marker = "page_marker" in present_signals

            # Strong continuation-header evidence:
            # - at least two identity/contact signals; or
            # - one identity/contact signal plus a page marker.
            cluster_is_continuation_header = (
                identity_signal_count >= 2
                or (has_identity_signal and has_page_marker)
            )

            if not cluster_is_continuation_header:
                continue

            page_removed = []

            for block, signal in classified:
                if signal is None:
                    continue

                reason = {
                    "candidate_name":
                        "candidate_identity_repeated_in_page_header",
                    "candidate_phone":
                        "candidate_phone_repeated_in_page_header",
                    "candidate_email":
                        "candidate_email_repeated_in_page_header",
                    "page_marker":
                        "page_marker",
                }[signal]

                block["is_continuation_header"] = True
                block["excluded_from_ordered_text"] = True
                block["exclusion_reason"] = reason
                evidence = self._block_evidence(block)
                evidence["signal"] = signal
                evidence["reason"] = reason

                page_removed.append(evidence)
                removed_blocks.append(evidence)

            if page_removed:
                detected_pages.append({
                    "page": page_number,
                    "signals": sorted(present_signals),
                    "removed_blocks": page_removed,
                })

        final_ordered_text = self._rebuild_ordered_text(blocks)

        # Defensive fallback: never replace good text with an empty string.
        if not final_ordered_text.strip():
            final_ordered_text = original_text

        duplicate_contact_evidence = self._build_duplicate_contact_evidence(
            blocks=blocks,
            identity=identity,
        )

        document_issues = self._build_document_issues(
            duplicate_contact_evidence=duplicate_contact_evidence,
            removed_blocks=removed_blocks,
        )

        return {
            "status": (
                "cleaned"
                if removed_blocks
                else "no_continuation_header_detected"
            ),
            "ordered_text": final_ordered_text,
            "preliminary_ordered_text": original_text,
            "layout_blocks": blocks,
            "removed_block_count": len(removed_blocks),
            "removed_blocks": removed_blocks,
            "detected_pages": detected_pages,
            "duplicate_contact_evidence": duplicate_contact_evidence,
            "document_issues": document_issues,
            "mode": "post_contact_layout_aware_cleaning",
        }

    def _classify_contact_header_block(
        self,
        *,
        block: dict,
        identity: dict[str, str],
    ) -> str | None:
        text = str(block.get("text") or "").strip()

        if not text:
            return None

        if self.PAGE_MARKER_PATTERN.fullmatch(text):
            return "page_marker"

        normalized_text = self._normalize_text(text)
        normalized_digits = self._normalize_digits(text)
        normalized_email = self._normalize_email(text)

        if (
            identity["name"]
            and normalized_text == identity["name"]
        ):
            return "candidate_name"

        if (
            identity["phone"]
            and normalized_digits == identity["phone"]
        ):
            return "candidate_phone"

        if (
            identity["email"]
            and normalized_email == identity["email"]
        ):
            return "candidate_email"

        return None

    def _top_region_blocks(
        self,
        *,
        page_blocks: list[dict],
        page_height: float | None,
    ) -> list[dict]:
        if not page_blocks:
            return []

        if not page_height or page_height <= 0:
            page_height = max(
                self._bbox_bottom(block)
                for block in page_blocks
            ) or 792.0

        top_limit = page_height * self.top_region_ratio
        top_blocks = [
            block
            for block in page_blocks
            if self._bbox_top(block) <= top_limit
        ]

        # Some DOCX-derived or OCR blocks may not have useful bbox values.
        if not top_blocks:
            top_blocks = page_blocks[:self.max_top_blocks]

        return top_blocks[:self.max_top_blocks]

    def _rebuild_ordered_text(
        self,
        blocks: list[dict],
    ) -> str:
        included_blocks = []

        for block in sorted(
            blocks,
            key=self._global_block_sort_key,
        ):
            # TextExtractor already preserves a valid first-page identity by
            # leaving its repeated flag false. Every block still marked as a
            # repeated header/footer should therefore remain excluded.
            if block.get(
                "is_repeated_header_footer"
            ):
                continue

            if block.get(
                "excluded_from_ordered_text"
            ):
                continue

            text = str(
                block.get("text")
                or ""
            ).strip()

            if text:
                included_blocks.append(text)

        text = "\n".join(included_blocks)
        text = text.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )
        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    def _build_duplicate_contact_evidence(
        self,
        *,
        blocks: list[dict],
        identity: dict[str, str],
    ) -> list[dict]:
        evidence = []

        matchers = {
            "name": (
                identity["name"],
                lambda value: self._normalize_text(value),
            ),
            "phone": (
                identity["phone"],
                lambda value: self._normalize_digits(value),
            ),
            "email": (
                identity["email"],
                lambda value: self._normalize_email(value),
            ),
        }

        for field_name, (target, normalizer) in matchers.items():
            if not target:
                continue

            matches = []

            for block in sorted(blocks, key=self._global_block_sort_key):
                value = str(block.get("text") or "").strip()

                if normalizer(value) != target:
                    continue

                item = self._block_evidence(block)
                item["is_continuation_header"] = bool(
                    block.get("is_continuation_header")
                )
                item["excluded_from_ordered_text"] = bool(
                    block.get("excluded_from_ordered_text")
                )
                item["exclusion_reason"] = block.get("exclusion_reason")
                matches.append(item)

            if len(matches) <= 1:
                continue

            evidence.append({
                "field": field_name,
                "value": matches[0]["text"],
                "occurrence_count": len(matches),
                "continuation_header_occurrence_count": sum(
                    1
                    for match in matches
                    if match["is_continuation_header"]
                ),
                "pages": sorted({
                    match["page"]
                    for match in matches
                    if match.get("page") is not None
                }),
                "occurrences": matches,
            })

        return evidence

    def _build_document_issues(
        self,
        *,
        duplicate_contact_evidence: list[dict],
        removed_blocks: list[dict],
    ) -> list[dict]:
        if not removed_blocks:
            return []

        repeated_fields = [
            item["field"]
            for item in duplicate_contact_evidence
            if item.get("continuation_header_occurrence_count", 0) > 0
        ]

        return [{
            "type": "repeated_contact_in_continuation_header",
            "status": "detected_and_excluded_from_analysis_text",
            "severity": "low",
            "fields": repeated_fields,
            "evidence": duplicate_contact_evidence,
            "ai_action": {
                "allowed": True,
                "instruction": (
                    "Suggest removing repeated contact details from "
                    "continuation-page headers. Base the suggestion only "
                    "on the attached evidence."
                ),
                "conditional_message": (
                    "Your name or contact details appear again in a later "
                    "page header. Consider removing the duplicate header "
                    "if it is not required by your template."
                ),
            },
        }]

    def _page_heights(
        self,
        *,
        page_layouts: list[dict],
        blocks: list[dict],
    ) -> dict[int, float]:
        heights = {}

        for page in page_layouts:
            page_number = self._safe_int(page.get("page"), default=0)
            height = self._safe_float(page.get("height"), default=0.0)

            if page_number > 0 and height > 0:
                heights[page_number] = height

        if heights:
            return heights

        for block in blocks:
            page_number = self._safe_int(block.get("page"), default=1)
            heights[page_number] = max(
                heights.get(page_number, 0.0),
                self._bbox_bottom(block),
            )

        return heights

    def _block_evidence(self, block: dict) -> dict:
        return {
            "id": block.get("id"),
            "page": block.get("page"),
            "order": block.get("order"),
            "text": block.get("text"),
            "bbox": copy.deepcopy(block.get("bbox")),
        }

    def _to_mutable_dict(self, value: Any) -> dict:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="python")

        if not isinstance(value, dict):
            return {}

        return copy.deepcopy(value)

    def _block_sort_key(self, block: dict) -> tuple:
        return (
            self._safe_int(block.get("order"), default=999999),
            self._bbox_top(block),
            self._bbox_left(block),
        )

    def _global_block_sort_key(self, block: dict) -> tuple:
        return (
            self._safe_int(block.get("page"), default=1),
            *self._block_sort_key(block),
        )

    def _bbox_top(self, block: dict) -> float:
        bbox = block.get("bbox") or {}
        return self._safe_float(
            bbox.get("top", bbox.get("y0", 0.0)),
            default=0.0,
        )

    def _bbox_bottom(self, block: dict) -> float:
        bbox = block.get("bbox") or {}
        return self._safe_float(
            bbox.get("bottom", bbox.get("y1", 0.0)),
            default=0.0,
        )

    def _bbox_left(self, block: dict) -> float:
        bbox = block.get("bbox") or {}
        return self._safe_float(
            bbox.get("x0", bbox.get("left", 0.0)),
            default=0.0,
        )

    def _normalize_text(self, value: Any) -> str:
        text = str(value or "").casefold()
        text = text.replace("résumé", "resume")
        text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_digits(self, value: Any) -> str:
        return re.sub(r"\D", "", str(value or ""))

    def _normalize_email(self, value: Any) -> str:
        match = re.search(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            str(value or ""),
            re.IGNORECASE,
        )
        return match.group(0).lower() if match else ""

    def _safe_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _empty_result(
        self,
        *,
        ordered_text: str,
        layout_blocks: list[dict],
    ) -> dict:
        return {
            "status": "no_layout_blocks",
            "ordered_text": ordered_text,
            "preliminary_ordered_text": ordered_text,
            "layout_blocks": layout_blocks,
            "removed_block_count": 0,
            "removed_blocks": [],
            "detected_pages": [],
            "duplicate_contact_evidence": [],
            "document_issues": [],
            "mode": "post_contact_layout_aware_cleaning",
        }
