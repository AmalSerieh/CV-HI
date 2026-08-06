from __future__ import annotations

import re
from typing import Any


class PhoneExtractor:
    PHONE_RE = re.compile(
        r"(?<!\d)(?:\+\s*)?(?:\d[\d .()/-]{7,}\d)(?!\d)"
    )
    DATE_RANGE_RE = re.compile(
        r"(?i)^\s*(?:19|20)\d{2}(?:[/-]\d{1,2})?"
        r"\s*(?:-|–|—|to|until)\s*(?:19|20)\d{2}(?:[/-]\d{1,2})?\s*$"
    )
    PHONE_LABEL_RE = re.compile(
        r"(?i)\b(?:phone|mobile|cell|telephone|tel|contact|whatsapp|"
        r"هاتف|الجوال|موبايل|واتساب)\b"
    )

    def _normalize(self, raw: str) -> str:
        clean = raw.strip()
        has_plus = clean.lstrip().startswith("+")
        digits = re.sub(r"\D", "", clean)
        # In international notation, a trunk zero in parentheses is omitted.
        if has_plus:
            clean_without_spaces = re.sub(r"\s+", "", clean)
            match = re.match(r"\+(\d{1,3})\(0\)(\d+)$", re.sub(r"[^+\d()]", "", clean_without_spaces))
            if match:
                digits = match.group(1) + match.group(2)
            return "+" + digits
        return digits

    def extract_candidates(
        self,
        text: str,
        *,
        ordered_text: str | None = None,
        layout_blocks: list[Any] | None = None,
        anchor_line: int | None = None,
    ) -> dict:
        raw_text = str(text or "")
        ordered = str(ordered_text or raw_text)
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        seen: set[str] = set()

        for match in self.PHONE_RE.finditer(raw_text):
            raw_value = match.group(0).strip()
            if re.search(r"(?i)20XX|19XX|YYYY", raw_value):
                continue
            normalized = self._normalize(raw_value)
            digits = re.sub(r"\D", "", normalized)
            matching_blocks = self._matching_blocks(
                raw_value,
                digits,
                layout_blocks or [],
            )
            source_block = self._best_block(matching_blocks)
            source_text = str((source_block or {}).get("text") or raw_value)
            reason = self._rejection_reason(raw_value, digits, source_text)
            if reason:
                rejected.append(
                    {
                        "type": "phone",
                        "value": raw_value,
                        "reason": reason,
                        "source": self._source(source_block, raw_value, normalized, None),
                    }
                )
                continue
            if not 7 <= len(digits) <= 15:
                rejected.append(
                    {
                        "type": "phone",
                        "value": raw_value,
                        "reason": "invalid_phone_length",
                        "source": self._source(source_block, raw_value, normalized, None),
                    }
                )
                continue
            if digits in seen:
                continue
            line_index = next(
                (index for index, line in enumerate(ordered.splitlines()) if raw_value in line),
                None,
            )
            in_contact_region = self._in_contact_region(source_block, line_index)
            explicitly_labelled = bool(self.PHONE_LABEL_RE.search(source_text))
            if (layout_blocks or ordered_text is not None) and not (
                in_contact_region or explicitly_labelled
            ):
                rejected.append(
                    {
                        "type": "phone",
                        "value": raw_value,
                        "reason": "outside_contact_region",
                        "source": self._source(
                            source_block,
                            raw_value,
                            normalized,
                            line_index,
                        ),
                    }
                )
                continue

            seen.add(digits)
            score = 100
            if anchor_line is not None and line_index is not None:
                score += max(0, 20 - abs(line_index - anchor_line) * 4)
            if in_contact_region:
                score += 25
            if explicitly_labelled:
                score += 15
            accepted.append(
                {
                    "value": normalized,
                    "raw_value": raw_value,
                    "digits": digits,
                    "score": score,
                    "line_index": line_index,
                    "raw_line_index": line_index,
                    "source": self._source(
                        source_block,
                        raw_value,
                        normalized,
                        line_index,
                    ),
                }
            )

        accepted.sort(key=lambda item: int(item.get("score", 0) or 0), reverse=True)
        return {"accepted": accepted, "rejected": rejected}

    @classmethod
    def _rejection_reason(
        cls,
        raw_value: str,
        digits: str,
        source_text: str,
    ) -> str | None:
        compact = re.sub(r"\s+", " ", raw_value).strip()
        if cls.DATE_RANGE_RE.fullmatch(compact):
            return "date_range_not_phone"
        years = re.findall(r"\b(?:19|20)\d{2}\b", compact)
        if len(years) >= 2:
            return "date_range_not_phone"
        if re.search(
            r"\b(?:19|20)\d{2}[/-](?:0?[1-9]|1[0-2])(?:[/-]\d{1,2})?\b",
            compact,
        ):
            return "calendar_date_not_phone"
        if len(digits) == 8:
            year = int(digits[:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return "calendar_date_not_phone"
        if re.search(r"(?i)\b(?:gpa|grade|student\s+id|employee\s+id|page)\b", source_text):
            return "non_phone_numeric_identifier"
        return None

    @staticmethod
    def _block_to_dict(block: Any) -> dict[str, Any]:
        if hasattr(block, "model_dump"):
            return block.model_dump(mode="python")
        return block if isinstance(block, dict) else {}

    @classmethod
    def _matching_blocks(
        cls,
        raw_value: str,
        digits: str,
        layout_blocks: list[Any],
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        raw_key = re.sub(r"\s+", " ", raw_value).casefold()
        for raw_block in layout_blocks:
            block = cls._block_to_dict(raw_block)
            values = [str(block.get("text") or "")]
            values.extend(str(value) for value in block.get("link_annotations") or [])
            for value in values:
                normalized_text = re.sub(r"\s+", " ", value).casefold()
                normalized_digits = re.sub(r"\D", "", value)
                if raw_key in normalized_text or (digits and digits in normalized_digits):
                    matches.append(block)
                    break
        return matches

    @staticmethod
    def _best_block(blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not blocks:
            return None
        return min(
            blocks,
            key=lambda block: (
                0 if block.get("zone_kind") == "header" else 1,
                int(block.get("page") or 999),
                float((block.get("bbox") or {}).get("top", 9999)),
            ),
        )

    @staticmethod
    def _in_contact_region(
        block: dict[str, Any] | None,
        line_index: int | None,
    ) -> bool:
        if block:
            if block.get("zone_kind") == "header":
                return True
            if int(block.get("page") or 999) == 1:
                bbox = block.get("bbox") or {}
                top = float(bbox.get("top", 9999))
                if top <= 180.0:
                    return True
                if (
                    not bbox
                    and line_index is not None
                    and line_index <= 8
                    and block.get("column") in {"single", "full_width", "unknown"}
                ):
                    return True
        return block is None and line_index is not None and line_index <= 8

    @staticmethod
    def _source(
        block: dict[str, Any] | None,
        raw_value: str,
        normalized: str,
        line_index: int | None,
    ) -> dict[str, Any]:
        return {
            "text": str((block or {}).get("text") or raw_value),
            "normalized_text": normalized,
            "page": (block or {}).get("page"),
            "bbox": (block or {}).get("bbox"),
            "block_id": (block or {}).get("id"),
            "column": (block or {}).get("column"),
            "zone_id": (block or {}).get("zone_id"),
            "line_index": line_index,
        }
