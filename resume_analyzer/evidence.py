"""Stable evidence identifiers and registry helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any, Literal

from resume_analyzer.schemas import EvidenceRecord, SourceReference


def _canonical_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class EvidenceRegistry:
    """Build a de-duplicated registry whose IDs remain stable across runs."""

    def __init__(self, existing: Iterable[EvidenceRecord | dict[str, Any]] = ()) -> None:
        self._items: dict[str, EvidenceRecord] = {}
        for item in existing:
            record = (
                item if isinstance(item, EvidenceRecord) else EvidenceRecord.model_validate(item)
            )
            self._items[record.id] = record

    @staticmethod
    def stable_id(*, kind: str, field_path: str, value: Any) -> str:
        material = f"{kind}\x1f{field_path}\x1f{_canonical_value(value)}".encode()
        return f"ev-{hashlib.sha256(material).hexdigest()[:16]}"

    def register(
        self,
        *,
        field_path: str,
        value: str | int | float | bool | None,
        extractor: str,
        kind: Literal["present", "missing", "rejected", "layout", "quality", "rule"] = "present",
        confidence: float = 1.0,
        page: int | None = None,
        block_id: str | None = None,
        section: str | None = None,
        column: str | None = None,
        zone_id: str | None = None,
        source_field: str | None = None,
        parent_evidence_ids: Iterable[str] = (),
    ) -> str:
        evidence_id = self.stable_id(kind=kind, field_path=field_path, value=value)
        record = EvidenceRecord(
            id=evidence_id,
            kind=kind,
            field_path=field_path,
            value=value,
            source=SourceReference(
                extractor=extractor,
                field_path=field_path,
                page=page,
                block_id=block_id,
                section=section,
                column=column,
                zone_id=zone_id,
                source_field=source_field,
            ),
            confidence=max(0.0, min(1.0, float(confidence))),
            parent_evidence_ids=list(dict.fromkeys(parent_evidence_ids)),
        )
        current = self._items.get(evidence_id)
        if current is not None and current != record:
            raise ValueError(f"Evidence ID collision for {evidence_id}")
        self._items[evidence_id] = record
        return evidence_id

    def missing(self, field_path: str, *, extractor: str = "pipeline") -> str:
        return self.register(
            field_path=field_path,
            value=None,
            extractor=extractor,
            kind="missing",
            confidence=1.0,
        )

    def contains(self, evidence_id: str) -> bool:
        return evidence_id in self._items

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._items.get(evidence_id)

    def source_for_block(self, block_id: str) -> EvidenceRecord | None:
        return next(
            (
                item
                for item in self._items.values()
                if item.source.block_id == block_id
                and item.source.page is not None
                and item.kind in {"layout", "present"}
            ),
            None,
        )

    def records(self) -> list[EvidenceRecord]:
        return sorted(self._items.values(), key=lambda item: item.id)
