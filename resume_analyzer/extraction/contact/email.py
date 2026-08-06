from __future__ import annotations

import re
from typing import Any


class EmailExtractor:
    """Extract normal and style-split email addresses with evidence."""

    STRICT_RE = re.compile(
        r"(?i)(?<![A-Z0-9._%+-])"
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,24}"
        r"(?![A-Z0-9._%+-])"
    )
    SPACED_RE = re.compile(
        r"(?i)(?<![A-Z0-9._%+-])"
        r"(?P<local>[A-Z0-9._%+-]{1,64})\s*@\s*"
        r"(?P<domain>[A-Z0-9-]+(?:\s*\.\s*[A-Z0-9-]+)+)"
        r"(?![A-Z0-9._%+-])"
    )

    def _line_index(self, ordered: str, raw_value: str, normalized: str) -> int | None:
        for index, line in enumerate(ordered.splitlines()):
            if raw_value in line or normalized in line.replace(" ", ""):
                return index
        return None

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
        candidates: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        seen: set[str] = set()

        for match in self.STRICT_RE.finditer(raw_text):
            value = match.group(0)
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            line_index = self._line_index(ordered, value, value)
            score = 100
            if anchor_line is not None and line_index is not None:
                score += max(0, 20 - abs(line_index - anchor_line) * 4)
            candidates.append({
                "value": value,
                "raw_value": value,
                "normalization": None,
                "score": score,
                "line_index": line_index,
                "source": {
                    "text": value,
                    "page": 1,
                    "block_id": None,
                    "line_index": line_index,
                },
            })

        for match in self.SPACED_RE.finditer(raw_text):
            raw_value = match.group(0)
            domain = re.sub(r"\s+", "", match.group("domain"))
            normalized = f"{match.group('local')}@{domain}"
            if not self.STRICT_RE.fullmatch(normalized):
                rejected.append({
                    "value": raw_value,
                    "reason": "invalid_after_style_whitespace_normalization",
                })
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            line_index = self._line_index(ordered, raw_value, normalized)
            score = 94
            if anchor_line is not None and line_index is not None:
                score += max(0, 20 - abs(line_index - anchor_line) * 4)
            candidates.append({
                "value": normalized,
                "raw_value": raw_value,
                "normalization": "removed_internal_style_whitespace",
                "score": score,
                "line_index": line_index,
                "source": {
                    "text": raw_value,
                    "normalized_text": normalized,
                    "page": 1,
                    "block_id": None,
                    "line_index": line_index,
                },
            })

        candidates.sort(key=lambda item: int(item.get("score", 0) or 0), reverse=True)
        return {"accepted": candidates, "rejected": rejected}
