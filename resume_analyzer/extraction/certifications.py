"""Conservative rule-based certification extraction."""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER = re.compile(r"(?i)^(?:certification|certificate|course)(?:\s+name)?$")
_DATE = re.compile(r"\b(?:19|20)\d{2}\b")


class CertificationsExtractor:
    def extract(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        sections = payload.get("sections") if isinstance(payload, dict) else None
        if isinstance(sections, dict) and isinstance(sections.get("sections"), dict):
            sections = sections["sections"]
        if not isinstance(sections, dict):
            return []
        raw = sections.get("certifications") or sections.get("certification") or {}
        if isinstance(raw, dict):
            raw = raw.get("content", "")
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for line in str(raw or "").splitlines():
            clean = re.sub(r"^[\s•*\-–—]+", "", line).strip()
            if len(clean) < 3 or _PLACEHOLDER.fullmatch(clean):
                continue
            parts = [
                part.strip() for part in re.split(r"\s*[|]\s*|\s+[-–—]\s+", clean) if part.strip()
            ]
            name = parts[0]
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            year = _DATE.search(clean)
            issuer = next((part for part in parts[1:] if not _DATE.fullmatch(part)), None)
            output.append(
                {
                    "name": name,
                    "issuer": issuer,
                    "date": year.group(0) if year else None,
                    "confidence": 0.9,
                }
            )
        return output
