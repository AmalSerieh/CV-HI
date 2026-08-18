"""Explicit migration from supported legacy report shapes to schema 2.1.0."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resume_analyzer.schemas import (
    SCHEMA_VERSION,
    ATSResult,
    ComponentStatus,
    ContactInfo,
    ContactSourceType,
    DocumentInfo,
    EducationItem,
    Entities,
    ExperienceItem,
    ExtractionInfo,
    LanguageItem,
    ModuleStatus,
    OCRScope,
    OCRUsage,
    PipelineMessage,
    PipelineReport,
    ProjectItem,
    QualityInfo,
    RewriteResult,
    SectionRecord,
    SkillItem,
    VisualMetadata,
)
from resume_analyzer.schemas.report_schema import CertificationItem, TargetRoleInfo

from .evidence import EvidenceRegistry


@dataclass(frozen=True)
class MigrationResult:
    report: PipelineReport
    source_shape: str
    warnings: tuple[str, ...]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _scalar(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        return value.get("value")
    return value


def _text(value: Any) -> str:
    value = _scalar(value)
    return "" if value is None else str(value).strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _confidence(value: Any, default: float = 0.75) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number > 1:
        number /= 100
    return max(0.0, min(1.0, number))


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


class SchemaMigrator:
    """Migrate canonical, strict-entities, analysis.facts, and top-level reports."""

    def __init__(self, *, include_document_path: bool = False) -> None:
        self.include_document_path = include_document_path

    @staticmethod
    def _layout_block_lookup(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
        extraction = _first_mapping(raw.get("extraction"), raw.get("text_extraction"))
        values = [
            *_sequence(extraction.get("raw_layout_blocks")),
            *_sequence(extraction.get("contact_ocr_blocks")),
        ]
        return {
            _text(block.get("id")): dict(block)
            for block in values
            if isinstance(block, Mapping) and _text(block.get("id"))
        }

    @staticmethod
    def _grounded_evidence(
        *,
        registry: EvidenceRegistry,
        path: str,
        data: Mapping[str, Any],
        block_lookup: Mapping[str, Mapping[str, Any]],
        snapshot: str,
        extractor: str,
        confidence: float,
    ) -> list[str]:
        source_ids = [
            _text(value) for value in _sequence(data.get("source_block_ids")) if _text(value)
        ]
        evidence_ids: list[str] = []
        for block_id in dict.fromkeys(source_ids):
            block = block_lookup.get(block_id)
            if not block:
                continue
            existing_source = registry.source_for_block(block_id)
            if existing_source is not None:
                evidence_ids.append(existing_source.id)
                continue
            block_text = _text(block.get("text"))
            if not block_text:
                continue
            page_value = block.get("page")
            page = page_value if isinstance(page_value, int) and page_value >= 1 else None
            evidence_ids.append(
                registry.register(
                    field_path=f"extraction.layout_blocks[{block_id}].text",
                    value=block_text,
                    extractor=extractor,
                    confidence=confidence,
                    page=page,
                    block_id=block_id,
                    column=_optional_text(block.get("column")),
                    zone_id=_optional_text(block.get("zone_id")),
                )
            )
        if evidence_ids:
            return evidence_ids
        return [
            registry.register(
                field_path=path,
                value=snapshot,
                extractor=extractor,
                confidence=confidence,
            )
        ]

    @staticmethod
    def _field_evidence(
        *,
        registry: EvidenceRegistry,
        path: str,
        value: str | int | float | bool | None,
        source_block_ids: list[str],
        block_lookup: Mapping[str, Mapping[str, Any]],
        extractor: str,
        confidence: float,
        section: str,
        source_field: str,
    ) -> list[str]:
        """Link a canonical field to compact, reusable layout-block evidence."""

        parent_ids: list[str] = []
        for block_id in dict.fromkeys(source_block_ids):
            block = block_lookup.get(block_id)
            if not block:
                continue
            existing_source = registry.source_for_block(block_id)
            if existing_source is not None:
                parent_ids.append(existing_source.id)
                continue
            block_text = _text(block.get("text"))
            if not block_text:
                continue
            page_value = block.get("page")
            page = page_value if isinstance(page_value, int) and page_value >= 1 else None
            parent_ids.append(
                registry.register(
                    field_path=f"extraction.layout_blocks[{block_id}].text",
                    value=block_text,
                    extractor=_optional_text(block.get("engine")) or "layout_text",
                    confidence=confidence,
                    page=page,
                    block_id=block_id,
                    section=section,
                    column=_optional_text(block.get("column")),
                    zone_id=_optional_text(block.get("zone_id")),
                )
            )
        if not parent_ids:
            return [
                registry.register(
                    field_path=path,
                    value=value,
                    extractor=extractor,
                    confidence=confidence,
                    section=section,
                    source_field=source_field,
                )
            ]
        return [
            registry.register(
                field_path=path,
                value=value,
                extractor=f"{extractor}_canonicalization",
                confidence=confidence,
                section=section,
                source_field=source_field,
                parent_evidence_ids=parent_ids,
            )
        ]

    @staticmethod
    def _field_source_ids(
        data: Mapping[str, Any],
        field: str,
    ) -> list[str]:
        field_sources = _mapping(data.get("field_source_block_ids"))
        selected = [_text(value) for value in _sequence(field_sources.get(field)) if _text(value)]
        if selected:
            return list(dict.fromkeys(selected))
        return [_text(value) for value in _sequence(data.get("source_block_ids")) if _text(value)]

    @staticmethod
    def _contact_source(
        *,
        contact_raw: Mapping[str, Any],
        field: str,
        value: str,
        block_lookup: Mapping[str, Mapping[str, Any]],
    ) -> tuple[int | None, str | None]:
        raw_evidence = _mapping(_mapping(contact_raw.get("evidence")).get(field))
        block_id = _optional_text(raw_evidence.get("block_id"))
        if block_id and block_id in block_lookup:
            block = block_lookup[block_id]
            page_value = block.get("page")
            return (
                page_value if isinstance(page_value, int) and page_value >= 1 else None,
                block_id,
            )
        normalized = " ".join(value.casefold().split())
        for candidate_id, block in block_lookup.items():
            block_text = " ".join(_text(block.get("text")).casefold().split())
            if normalized and (
                normalized in block_text
                or block_text in normalized
                or re.sub(r"\D", "", normalized)
                and re.sub(r"\D", "", normalized) == re.sub(r"\D", "", block_text)
            ):
                page_value = block.get("page")
                return (
                    page_value if isinstance(page_value, int) and page_value >= 1 else None,
                    candidate_id,
                )
        page_value = raw_evidence.get("page")
        page = page_value if isinstance(page_value, int) and page_value >= 1 else None
        return page, block_id

    @staticmethod
    def _contact_source_type(
        *,
        raw: Mapping[str, Any],
        field: str,
        value: str | None,
        block_id: str | None,
        block_lookup: Mapping[str, Mapping[str, Any]],
    ) -> ContactSourceType:
        extraction = _first_mapping(raw.get("extraction"), raw.get("text_extraction"))
        visual = _mapping(extraction.get("visual_metadata"))
        if not value:
            return (
                "image_only_unrecovered" if visual.get("possible_image_only_contact") else "missing"
            )

        block = _mapping(block_lookup.get(block_id)) if block_id else {}
        engine = str(block.get("engine") or "").casefold()
        if engine == "ocr" or str(block_id or "").startswith("p1_contact_ocr_"):
            return "ocr"

        links = [_text(item) for item in _sequence(extraction.get("links")) if _text(item)]
        links.extend(
            _text(item) for item in _sequence(block.get("link_annotations")) if _text(item)
        )
        normalized = value.casefold()
        if any(
            normalized in link.casefold()
            or (
                field == "phone"
                and re.sub(r"\D", "", normalized)
                and re.sub(r"\D", "", normalized) in re.sub(r"\D", "", link)
            )
            for link in links
        ):
            return "annotation"
        if field in {
            _text(item) for item in _sequence(visual.get("image_only_contact_fields"))
        } and not visual.get("contact_ocr_used"):
            return "image_only_unrecovered"
        if extraction.get("ocr_used") and (str(extraction.get("engine") or "").casefold() == "ocr"):
            return "ocr"
        if block:
            return "selectable_text"
        if visual.get("contact_ocr_used"):
            return "ocr"
        if field in {"email", "phone", "name", "location", "job_title"}:
            return "selectable_text"
        return "inferred"

    @staticmethod
    def _ocr_usage(
        *,
        value: Mapping[str, Any],
        visual: VisualMetadata,
        raw_blocks: list[Mapping[str, Any]],
        page_layouts: list[Mapping[str, Any]],
    ) -> OCRUsage:
        contact_used = visual.contact_ocr_used
        used = bool(value.get("ocr_used") or contact_used)
        if not used:
            return OCRUsage()

        ocr_pages = {
            page
            for block in raw_blocks
            if str(block.get("engine") or "").casefold() == "ocr"
            and isinstance((page := block.get("page")), int)
            and page >= 1
        }
        ocr_pages.update(
            page_number
            for page_layout in page_layouts
            if str(page_layout.get("engine") or "").casefold() == "ocr"
            and isinstance((page_number := page_layout.get("page")), int)
            and page_number >= 1
        )
        document_pages = {
            page_number
            for page_layout in page_layouts
            if isinstance((page_number := page_layout.get("page")), int) and page_number >= 1
        }
        if ocr_pages and document_pages and ocr_pages >= document_pages:
            scope: OCRScope = "full_document"
        elif ocr_pages and contact_used:
            scope = "mixed"
        elif ocr_pages:
            scope = "page"
        elif contact_used:
            scope = "contact_header"
        elif str(value.get("engine") or "").casefold() == "ocr":
            scope = "full_document"
        else:
            scope = "unknown"

        pages = sorted(ocr_pages)
        if contact_used and 1 not in pages:
            pages.append(1)
            pages.sort()
        return OCRUsage(
            used=True,
            scope=scope,
            pages=pages,
            fields=(list(visual.image_only_contact_fields) if contact_used else []),
        )

    def from_extraction_modules(self, payload: Mapping[str, Any]) -> MigrationResult:
        """Build the canonical report for trusted internal extractor output.

        The extractor modules still expose their established module dictionaries,
        so this method deliberately shares the battle-tested field mapping with
        external migration. Internal data is not a legacy import, however, and
        must not emit a user-facing migration warning.
        """
        migrated = self.migrate(payload)
        data = migrated.report.to_json_dict()
        data["warnings"] = [
            warning
            for warning in data["warnings"]
            if not (
                warning.get("stage") == "migration"
                and warning.get("code", "").startswith("migrated_from_")
            )
        ]
        report = PipelineReport.model_validate(data)
        retained = tuple(
            warning for warning in migrated.warnings if not warning.startswith("migrated_from:")
        )
        return MigrationResult(report, "internal_extraction_modules", retained)

    def migrate(self, payload: Mapping[str, Any]) -> MigrationResult:
        if not isinstance(payload, Mapping):
            raise TypeError("Pipeline input must be a mapping")
        raw = deepcopy(dict(payload))
        if raw.get("schema_version") == SCHEMA_VERSION:
            report = PipelineReport.model_validate(raw)
            return MigrationResult(report, "canonical", ())
        if raw.get("schema_version") == "2.0.0":
            return self._upgrade_v2_0(raw)

        facts = _mapping(_mapping(raw.get("analysis")).get("facts"))
        strict_entities = _mapping(raw.get("entities"))
        if strict_entities:
            shape = "strict_entities"
            source = strict_entities
        elif facts:
            shape = "analysis.facts"
            source = facts
        else:
            shape = "legacy_top_level"
            source = raw

        warnings = [f"migrated_from:{shape}"]
        recognized_top_level = {
            "success",
            "schema_version",
            "pipeline_version",
            "document",
            "file",
            "extraction",
            "text_extraction",
            "entities",
            "analysis",
            "contact",
            "sections",
            "summary",
            "skills",
            "education",
            "experience",
            "projects",
            "languages",
            "certifications",
            "quality",
            "data_quality",
            "target_role",
            "recommendations",
            "ats",
            "rewrites",
            "warnings",
            "errors",
            "module_status",
        }
        dropped_top_level = sorted(set(raw) - recognized_top_level)
        if dropped_top_level:
            warnings.append("legacy_fields_not_carried:" + ",".join(dropped_top_level))
        if shape == "analysis.facts":
            recognized_fact_fields = {
                "source_document",
                "contact",
                "sections",
                "summary",
                "skills",
                "education",
                "experience",
                "projects",
                "languages",
                "certifications",
            }
            dropped_facts = sorted(set(facts) - recognized_fact_fields)
            if dropped_facts:
                warnings.append("legacy_fact_fields_not_carried:" + ",".join(dropped_facts))
        registry = EvidenceRegistry()
        sections = self._sections(raw, source, registry)
        document = self._document(raw, source)
        extraction = self._extraction(raw, source, sections, registry)
        entities = self._entities(raw, source, registry)
        quality, missing_evidence = self._quality(raw, entities, registry)

        for evidence_id in missing_evidence:
            # Evidence is already in the registry; this loop documents that
            # missing facts are deliberately retained, not fabricated values.
            if not registry.contains(evidence_id):
                raise AssertionError("Missing evidence registration failed")

        target_role = None
        target_payload = raw.get("target_role")
        if isinstance(target_payload, Mapping):
            try:
                target_role = TargetRoleInfo.model_validate(target_payload)
            except ValueError:
                warnings.append("legacy_target_role_omitted:invalid_contract")

        if raw.get("recommendations"):
            warnings.append("legacy_recommendations_omitted:missing_grounded_contract")

        message_models = [
            PipelineMessage(stage="migration", code=value.replace(":", "_"), message=value)
            for value in warnings
        ]
        report = PipelineReport(
            document=document,
            extraction=extraction,
            entities=entities,
            quality=quality,
            evidence=registry.records(),
            target_role=target_role,
            recommendations=[],
            ats=ATSResult(status="not_run"),
            rewrites=RewriteResult(status="not_run"),
            warnings=message_models,
            errors=[],
            module_status=ModuleStatus(
                extraction=ComponentStatus(
                    status="complete" if extraction.status == "ok" else "degraded"
                ),
                target_role=ComponentStatus(status="complete" if target_role else "not_run"),
                recommendations=ComponentStatus(status="not_run"),
            ),
        )
        return MigrationResult(report, shape, tuple(warnings))

    def _upgrade_v2_0(self, raw: dict[str, Any]) -> MigrationResult:
        upgraded = deepcopy(raw)
        upgraded["schema_version"] = SCHEMA_VERSION
        upgraded["ats"] = ATSResult(status="not_run").model_dump(mode="json")
        upgraded["rewrites"] = RewriteResult(status="not_run").model_dump(mode="json")
        document = _mapping(upgraded.get("document"))
        if not self.include_document_path:
            document["path"] = None
        upgraded["document"] = document

        registry = EvidenceRegistry(upgraded.get("evidence") or [])
        extraction = _mapping(upgraded.get("extraction"))
        evidence_ids = _mapping(extraction.get("evidence_ids"))

        def register(key: str, value: Any, kind: str = "quality") -> None:
            if value is None or value == "":
                return
            normalized_value = value if isinstance(value, (str, int, float, bool)) else str(value)
            evidence_id = registry.stable_id(
                field_path=key,
                value=normalized_value,
                kind=kind,
            )
            if not registry.contains(evidence_id):
                evidence_id = registry.register(
                    field_path=key,
                    value=normalized_value,
                    extractor="schema_migration_2_0",
                    kind=kind,
                    confidence=1.0,
                )
            evidence_ids.setdefault(key, []).append(evidence_id)

        register("document.layout", document.get("layout"), "layout")
        register("extraction.quality_score", extraction.get("quality_score"), "quality")
        register("extraction.ocr_used", bool(extraction.get("ocr_used")), "quality")
        extraction["evidence_ids"] = {
            key: list(dict.fromkeys(values)) for key, values in evidence_ids.items()
        }
        upgraded["extraction"] = extraction
        upgraded["evidence"] = [item.model_dump(mode="json") for item in registry.records()]
        warning = PipelineMessage(
            stage="migration",
            code="migrated_schema_2_0_0_to_2_1_0",
            message="Canonical schema 2.0.0 was upgraded to 2.1.0.",
            recoverable=True,
        ).model_dump(mode="json")
        upgraded.setdefault("warnings", []).append(warning)
        report = PipelineReport.model_validate(upgraded)
        return MigrationResult(report, "canonical_2.0.0", ("migrated_schema:2.0.0->2.1.0",))

    def _document(self, raw: dict[str, Any], source: dict[str, Any]) -> DocumentInfo:
        value = _first_mapping(raw.get("document"), raw.get("file"), source.get("source_document"))
        source_path = _optional_text(value.get("path"))
        path = source_path if self.include_document_path else None
        name = _text(value.get("name")) or (Path(source_path).name if source_path else "unknown")
        extension = _text(value.get("extension")) or Path(name).suffix.lower()
        extraction = _first_mapping(raw.get("extraction"), raw.get("text_extraction"))
        return DocumentInfo(
            name=name,
            extension=extension,
            path=path,
            pages=max(0, int(extraction.get("pages") or value.get("pages") or 0)),
            size_bytes=value.get("size_bytes"),
            layout=(
                str(extraction.get("layout") or value.get("layout") or "unknown")
                if str(extraction.get("layout") or value.get("layout") or "unknown")
                in {"single_column", "two_column", "mixed", "unknown"}
                else "unknown"
            ),
        )

    def _sections(
        self, raw: dict[str, Any], source: dict[str, Any], registry: EvidenceRegistry
    ) -> dict[str, SectionRecord]:
        container = _first_mapping(source.get("sections"), raw.get("sections"))
        values = _mapping(container.get("sections")) or container
        block_lookup = self._layout_block_lookup(raw)
        output: dict[str, SectionRecord] = {}
        for key, item in values.items():
            data = _mapping(item)
            content = _text(data.get("content") if data else item)
            if key in {"found_sections", "missing_required", "section_order", "detected_headings"}:
                continue
            evidence_ids: list[str] = []
            heading = _optional_text(data.get("heading") or data.get("detected_heading"))
            section_blocks = [
                block_lookup[block_id]
                for block_id in (_text(value) for value in _sequence(data.get("block_ids")))
                if block_id in block_lookup
            ]
            if heading:
                heading_block = next(
                    (block for block in section_blocks if _text(block.get("text")) == heading),
                    None,
                )
                heading_page_value = heading_block.get("page") if heading_block else None
                evidence_ids.append(
                    registry.register(
                        field_path=f"extraction.sections.{key}.heading",
                        value=heading,
                        extractor=(
                            "layout_section_ontology" if heading_block else "legacy_migration"
                        ),
                        kind="layout",
                        confidence=_confidence(data.get("confidence"), 0.8),
                        page=heading_page_value if isinstance(heading_page_value, int) else None,
                        block_id=_optional_text((heading_block or {}).get("id")),
                    )
                )
            if content:
                content_block = next(
                    (block for block in section_blocks if _text(block.get("text")) != heading),
                    None,
                )
                content_page_value = content_block.get("page") if content_block else None
                evidence_ids.append(
                    registry.register(
                        field_path=f"extraction.sections.{key}.content",
                        value=content,
                        extractor=(
                            "layout_section_ontology" if content_block else "legacy_migration"
                        ),
                        confidence=_confidence(data.get("confidence"), 0.8),
                        page=content_page_value if isinstance(content_page_value, int) else None,
                        block_id=_optional_text((content_block or {}).get("id")),
                    )
                )
            output[str(key)] = SectionRecord(
                key=str(key),
                heading=heading,
                content=content,
                words=len(content.split()),
                confidence=_confidence(data.get("confidence"), 0.8 if content else 0.0),
                evidence_ids=evidence_ids,
                block_ids=[
                    _text(value) for value in _sequence(data.get("block_ids")) if _text(value)
                ],
                pages=[
                    int(value)
                    for value in _sequence(data.get("pages"))
                    if isinstance(value, int) and value >= 1
                ],
                columns=[_text(value) for value in _sequence(data.get("columns")) if _text(value)],
                zones=[_text(value) for value in _sequence(data.get("zones")) if _text(value)],
                mixed_content=bool(data.get("mixed_content", False)),
                item_groups={
                    str(group): [_text(value) for value in _sequence(values) if _text(value)]
                    for group, values in _mapping(data.get("item_groups")).items()
                },
                warnings=[
                    _text(value) for value in _sequence(data.get("warnings")) if _text(value)
                ],
            )
        return output

    def _extraction(
        self,
        raw: dict[str, Any],
        source: dict[str, Any],
        sections: dict[str, SectionRecord],
        registry: EvidenceRegistry,
    ) -> ExtractionInfo:
        value = _first_mapping(raw.get("extraction"), raw.get("text_extraction"))
        success = value.get("success", raw.get("success", True))
        status = str(value.get("status") or ("ok" if success else "failed"))
        if status not in {"ok", "degraded", "failed"}:
            status = "degraded"
        quality_score = int(value.get("quality_score") or 0)
        engine = str(value.get("engine") or "unknown")
        if engine not in {"pymupdf", "pdfplumber", "ocr", "docx", "docx_ooxml", "mixed", "unknown"}:
            engine = "unknown"
        reading_order = str(value.get("reading_order") or "unknown")
        reading_order = {
            "visual_top_to_bottom": "top_to_bottom",
            "column_aware_visual_order": "column_wise",
        }.get(reading_order, reading_order)
        if reading_order not in {"top_to_bottom", "row_wise", "column_wise", "mixed", "unknown"}:
            reading_order = "unknown"

        raw_blocks = [
            item for item in _sequence(value.get("raw_layout_blocks")) if isinstance(item, Mapping)
        ]
        page_layouts = [
            item for item in _sequence(value.get("page_layouts")) if isinstance(item, Mapping)
        ]
        section_container = _first_mapping(source.get("sections"), raw.get("sections"))
        section_order = [
            _text(item) for item in _sequence(section_container.get("section_order")) if _text(item)
        ] or list(sections)
        detected_headings: list[str] = []
        for item in _sequence(section_container.get("detected_headings")):
            if isinstance(item, Mapping):
                heading = _text(item.get("heading") or item.get("text") or item.get("raw"))
            else:
                heading = _text(item)
            if heading:
                detected_headings.append(heading)

        visual_raw = _first_mapping(
            value.get("visual_metadata"),
            {
                **_mapping(raw.get("document_assets")),
                **_mapping(raw.get("document_style")),
                "duplicate_ratio": _mapping(raw.get("duplicate_analysis")).get("duplicate_ratio"),
            },
        )
        table_count = sum(
            1
            for item in raw_blocks
            if str(item.get("block_type") or "").casefold() in {"table", "table_cell", "cell"}
        )
        repeated_count = sum(bool(item.get("is_repeated_header_footer")) for item in raw_blocks)
        visual_status = str(visual_raw.get("status") or "not_available")
        if visual_status == "ok":
            visual_status = "complete"
        if visual_status not in {"complete", "partial", "cannot_verify", "not_available"}:
            visual_status = "partial"
        visual = VisualMetadata(
            status=visual_status,
            source=str(visual_raw.get("source") or value.get("engine") or "not_available"),
            has_images=visual_raw.get("has_images"),
            image_count=visual_raw.get("image_count"),
            icon_count=visual_raw.get("icon_count"),
            candidate_photo_detected=visual_raw.get("candidate_photo_detected"),
            decorative_image_count=visual_raw.get("decorative_image_count"),
            image_only_contact_fields=[
                _text(item)
                for item in _sequence(visual_raw.get("image_only_contact_fields"))
                if _text(item)
            ],
            possible_image_only_contact=bool(visual_raw.get("possible_image_only_contact", False)),
            contact_readability=str(visual_raw.get("contact_readability") or "unknown"),
            contact_ocr_used=bool(visual_raw.get("contact_ocr_used", False)),
            contact_ocr_status=str(visual_raw.get("contact_ocr_status") or "unknown"),
            contact_ocr_error=_optional_text(visual_raw.get("contact_ocr_error")),
            text_box_count=visual_raw.get("text_box_count"),
            drawing_count=visual_raw.get("drawing_count"),
            shape_count=visual_raw.get("shape_count"),
            table_count=visual_raw.get("table_count", table_count),
            has_color=visual_raw.get("has_color"),
            detected_color_count=visual_raw.get("detected_color_count"),
            contrast_status=str(visual_raw.get("contrast_status") or "unknown"),
            ats_color_risk=str(visual_raw.get("ats_color_risk") or "unknown"),
            font_sizes=sorted(
                {
                    float(item)
                    for item in _sequence(visual_raw.get("font_sizes"))
                    if isinstance(item, (int, float)) and 0 < float(item) < 200
                }
            ),
            font_names=sorted(
                {_text(item) for item in _sequence(visual_raw.get("font_names")) if _text(item)}
            ),
            small_font_count=visual_raw.get("small_font_count"),
            overlap_count=visual_raw.get("overlap_count"),
            hidden_text_count=visual_raw.get("hidden_text_count"),
            white_text_count=visual_raw.get("white_text_count"),
            duplicate_ratio=visual_raw.get("duplicate_ratio"),
            repeated_header_footer_count=int(
                visual_raw.get("repeated_header_footer_count", repeated_count) or 0
            ),
        )
        ocr_usage = self._ocr_usage(
            value=value,
            visual=visual,
            raw_blocks=raw_blocks,
            page_layouts=page_layouts,
        )
        evidence_ids: dict[str, list[str]] = {}

        def register(path: str, evidence_value: Any, kind: str) -> None:
            if evidence_value is None or evidence_value == "":
                return
            if isinstance(evidence_value, (list, tuple, set)):
                evidence_value = " | ".join(str(item) for item in evidence_value)
            evidence_id = registry.register(
                field_path=path,
                value=evidence_value,
                extractor="legacy_text_extraction",
                kind=kind,
                confidence=1.0,
            )
            evidence_ids.setdefault(path, []).append(evidence_id)

        register(
            "document.layout",
            (
                raw.get("document", raw.get("file", {})).get("layout")
                if isinstance(raw.get("document", raw.get("file", {})), Mapping)
                else value.get("layout")
            ),
            "layout",
        )
        register("document.layout", value.get("layout"), "layout")
        register("extraction.reading_order", reading_order, "layout")
        register("extraction.quality_score", max(0, min(100, quality_score)), "quality")
        register("extraction.ocr_used", bool(value.get("ocr_used", False)), "quality")
        register("extraction.ocr_usage.scope", ocr_usage.scope, "quality")
        register("extraction.ocr_usage.pages", ocr_usage.pages, "quality")
        register("extraction.ocr_usage.fields", ocr_usage.fields, "quality")
        register("extraction.section_order", section_order, "layout")
        for index, warning in enumerate(_sequence(value.get("warnings"))):
            register(f"extraction.warnings[{index}]", _text(warning), "quality")
        block_sections = {
            block_id: section_name
            for section_name, section in sections.items()
            for block_id in section.block_ids
        }
        for index, block in enumerate(raw_blocks):
            block_text = _text(block.get("text"))
            if not block_text:
                continue
            page_value = block.get("page")
            page = page_value if isinstance(page_value, int) and page_value >= 1 else None
            path = f"extraction.layout_blocks[{index}].text"
            evidence_id = registry.register(
                field_path=path,
                value=block_text,
                extractor="legacy_text_extraction",
                kind="layout",
                confidence=1.0,
                page=page,
                block_id=_optional_text(block.get("id")),
                section=block_sections.get(_text(block.get("id"))),
                column=_optional_text(block.get("column")),
                zone_id=_optional_text(block.get("zone_id")),
                source_field="text",
            )
            evidence_ids.setdefault(path, []).append(evidence_id)
        visual_summary = (
            f"images={visual.image_count};icons={visual.icon_count};text_boxes={visual.text_box_count};"
            f"tables={visual.table_count};overlaps={visual.overlap_count};"
            f"small_fonts={visual.small_font_count};duplicate_ratio={visual.duplicate_ratio}"
        )
        register("extraction.visual_metadata", visual_summary, "layout")
        return ExtractionInfo(
            status=status,
            quality_score=max(0, min(100, quality_score)),
            word_count=max(0, int(value.get("words") or value.get("word_count") or 0)),
            character_count=max(0, int(value.get("chars") or value.get("character_count") or 0)),
            ocr_used=bool(value.get("ocr_used", False)),
            ocr_available=value.get("ocr_available"),
            ocr_usage=ocr_usage,
            engine=engine,
            reading_order=reading_order,
            links=[_text(item) for item in _sequence(value.get("links")) if _text(item)],
            warnings=[_text(item) for item in _sequence(value.get("warnings")) if _text(item)],
            layout_blocks=raw_blocks,
            page_layouts=page_layouts,
            visual_metadata=visual,
            section_order=section_order,
            detected_headings=list(dict.fromkeys(detected_headings)),
            evidence_ids=evidence_ids,
            sections=sections,
        )

    def _entities(
        self, raw: dict[str, Any], source: dict[str, Any], registry: EvidenceRegistry
    ) -> Entities:
        block_lookup = self._layout_block_lookup(raw)
        contact_raw = _first_mapping(source.get("contact"), raw.get("contact"))
        contact_values: dict[str, str | None] = {}
        contact_evidence: dict[str, list[str]] = {}
        contact_source_types: dict[str, ContactSourceType] = {}
        contact_confidence = _mapping(contact_raw.get("confidence"))
        for field in (
            "name",
            "email",
            "phone",
            "location",
            "job_title",
            "linkedin",
            "github",
            "portfolio",
        ):
            value = _optional_text(contact_raw.get(field))
            contact_values[field] = value
            block_id: str | None = None
            if value:
                page, block_id = self._contact_source(
                    contact_raw=contact_raw,
                    field=field,
                    value=value,
                    block_lookup=block_lookup,
                )
                resolved_confidence = _confidence(
                    contact_confidence.get(field),
                    _confidence(contact_raw.get("confidence"), 0.8),
                )
                if (
                    block_id
                    and str(_mapping(block_lookup.get(block_id)).get("engine") or "").casefold()
                    == "ocr"
                ):
                    resolved_confidence = min(0.82, resolved_confidence)
                contact_evidence[field] = [
                    registry.register(
                        field_path=f"entities.contact.{field}",
                        value=value,
                        extractor=("layout_contact_resolver" if block_id else "legacy_contact"),
                        confidence=resolved_confidence,
                        page=page,
                        block_id=block_id,
                    )
                ]
            else:
                contact_evidence[field] = [
                    registry.missing(f"entities.contact.{field}", extractor="legacy_contact")
                ]
            contact_source_types[field] = self._contact_source_type(
                raw=raw,
                field=field,
                value=value,
                block_id=block_id,
                block_lookup=block_lookup,
            )
        contact = ContactInfo(
            **contact_values,
            source_types=contact_source_types,
            evidence_ids=contact_evidence,
        )

        summary = self._summary(source, raw)
        if summary:
            section_values = _mapping(
                _first_mapping(source.get("sections"), raw.get("sections")).get("sections")
            )
            summary_section = _mapping(section_values.get("summary"))
            self._field_evidence(
                registry=registry,
                path="entities.summary",
                value=summary,
                source_block_ids=[
                    _text(value)
                    for value in _sequence(summary_section.get("block_ids"))
                    if _text(value)
                ],
                block_lookup=block_lookup,
                extractor="layout_grounded_summary",
                confidence=0.9,
                section="summary",
                source_field="summary",
            )

        skills_raw = source.get("skills", raw.get("skills", []))
        skills_map = _mapping(skills_raw)
        skills_values = skills_map.get("all_skills", skills_raw if not skills_map else [])
        skill_categories = {
            _text(value).casefold(): _text(category)
            for category, values in _mapping(skills_map.get("categorized_skills")).items()
            for value in _sequence(values)
            if _text(value)
        }
        for value in _sequence(skills_map.get("soft_skills")):
            if _text(value):
                skill_categories[_text(value).casefold()] = "soft_skills"
        for value in _sequence(skills_map.get("domain_context")):
            if _text(value):
                skill_categories[_text(value).casefold()] = "business_domain"
        skills: list[SkillItem] = []
        seen_skills: set[str] = set()
        for item in _sequence(skills_values):
            data = _mapping(item)
            value = _text(data.get("value") or data.get("name") or item)
            key = value.casefold()
            if not value or key in seen_skills:
                continue
            seen_skills.add(key)
            evidence_ids = self._field_evidence(
                registry=registry,
                path=f"entities.skills[{len(skills)}].value",
                value=value,
                source_block_ids=self._field_source_ids(data, "value"),
                block_lookup=block_lookup,
                extractor=(
                    "layout_grounded_skills" if data.get("source_block_ids") else "legacy_skills"
                ),
                confidence=_confidence(data.get("confidence"), 0.8),
                section="skills",
                source_field="value",
            )
            skills.append(
                SkillItem(
                    value=value,
                    normalized=_optional_text(data.get("normalized")) or key,
                    category=(_optional_text(data.get("category")) or skill_categories.get(key)),
                    confidence=_confidence(data.get("confidence"), 0.8),
                    evidence_ids=evidence_ids,
                    field_evidence_ids={"value": evidence_ids},
                )
            )

        education_raw = source.get("education", raw.get("education", []))
        education_values = _mapping(education_raw).get("education", education_raw)
        education = self._education(_sequence(education_values), registry, block_lookup)

        experience_raw = source.get("experience", raw.get("experience", []))
        experience_values = _mapping(experience_raw).get("experiences", experience_raw)
        experience = self._experience(_sequence(experience_values), registry, block_lookup)

        projects_raw = source.get("projects", raw.get("projects", []))
        project_values = _mapping(projects_raw).get("projects", projects_raw)
        projects = self._projects(_sequence(project_values), registry, block_lookup)

        languages_raw = source.get("languages", raw.get("languages", []))
        language_values = _mapping(languages_raw).get("languages", languages_raw)
        languages = self._languages(_sequence(language_values), registry)

        certification_values = source.get("certifications", raw.get("certifications", []))
        certifications = self._certifications(
            _sequence(certification_values), registry, block_lookup
        )

        return Entities(
            contact=contact,
            summary=summary,
            skills=skills,
            education=education,
            experience=experience,
            projects=projects,
            languages=languages,
            certifications=certifications,
        )

    def _summary(self, source: dict[str, Any], raw: dict[str, Any]) -> str:
        direct = source.get("summary")
        if isinstance(direct, str):
            return direct.strip()
        if isinstance(direct, Mapping):
            structured = direct.get("value") or direct.get("content")
            if structured:
                return _text(structured)
        sections = _mapping(
            _first_mapping(source.get("sections"), raw.get("sections")).get("sections")
        )
        summary_section = _mapping(sections.get("summary"))
        return _text(summary_section.get("content"))

    def _education(
        self,
        values: list[Any],
        registry: EvidenceRegistry,
        block_lookup: Mapping[str, Mapping[str, Any]],
    ) -> list[EducationItem]:
        output: list[EducationItem] = []
        for item in values:
            data = _mapping(item)
            if not data:
                continue
            snapshot = " | ".join(
                filter(
                    None,
                    map(
                        _optional_text,
                        [
                            data.get("degree"),
                            data.get("field"),
                            data.get("specialization"),
                            data.get("institution"),
                        ],
                    ),
                )
            )
            if not snapshot:
                continue
            path = f"entities.education[{len(output)}]"
            extractor = (
                "layout_grounded_education" if data.get("source_block_ids") else "legacy_education"
            )
            confidence = _confidence(data.get("confidence"))
            field_values = {
                "degree": _optional_text(data.get("degree") or data.get("degree_name")),
                "field": _optional_text(data.get("field") or data.get("field_of_study")),
                "specialization": _optional_text(data.get("specialization")),
                "institution": _optional_text(
                    data.get("institution") or data.get("school") or data.get("university")
                ),
                "location": _optional_text(data.get("location")),
                "start_date": _optional_text(data.get("start_date")),
                "end_date": _optional_text(data.get("end_date")),
                "gpa": _optional_text(data.get("gpa")),
            }
            field_evidence_ids = {
                field: self._field_evidence(
                    registry=registry,
                    path=f"{path}.{field}",
                    value=value,
                    source_block_ids=self._field_source_ids(data, field),
                    block_lookup=block_lookup,
                    extractor=extractor,
                    confidence=confidence,
                    section="education",
                    source_field=field,
                )
                for field, value in field_values.items()
                if value is not None
            }
            evidence_ids = list(
                dict.fromkeys(
                    evidence_id for values in field_evidence_ids.values() for evidence_id in values
                )
            )
            if not evidence_ids:
                evidence_ids = self._grounded_evidence(
                    registry=registry,
                    path=path,
                    data=data,
                    block_lookup=block_lookup,
                    snapshot=snapshot,
                    extractor=extractor,
                    confidence=confidence,
                )
            output.append(
                EducationItem(
                    degree=field_values["degree"],
                    field=field_values["field"],
                    specialization=field_values["specialization"],
                    institution=field_values["institution"],
                    location=field_values["location"],
                    start_date=field_values["start_date"],
                    end_date=field_values["end_date"],
                    graduation_year=(
                        data.get("graduation_year")
                        if isinstance(data.get("graduation_year"), int)
                        else None
                    ),
                    gpa=field_values["gpa"],
                    honors=[
                        _text(value) for value in _sequence(data.get("honors")) if _text(value)
                    ],
                    coursework=[
                        _text(value) for value in _sequence(data.get("coursework")) if _text(value)
                    ],
                    description=_text(data.get("description")),
                    confidence=_confidence(data.get("confidence")),
                    needs_review=bool(data.get("needs_review", False)),
                    evidence_ids=evidence_ids,
                    field_evidence_ids=field_evidence_ids,
                )
            )
        return output

    def _experience(
        self,
        values: list[Any],
        registry: EvidenceRegistry,
        block_lookup: Mapping[str, Mapping[str, Any]],
    ) -> list[ExperienceItem]:
        output: list[ExperienceItem] = []
        for item in values:
            data = _mapping(item)
            if not data:
                continue
            responsibilities = [
                _text(value)
                for value in _sequence(data.get("responsibilities") or data.get("bullets"))
                if _text(value)
            ]
            achievements = [
                _text(value) for value in _sequence(data.get("achievements")) if _text(value)
            ]
            snapshot = " | ".join(
                filter(
                    None,
                    [
                        _optional_text(data.get("job_title") or data.get("title")),
                        _optional_text(data.get("company")),
                        *responsibilities,
                        *achievements,
                    ],
                )
            )
            if not snapshot:
                continue
            path = f"entities.experience[{len(output)}]"
            extractor = (
                "layout_grounded_experience"
                if data.get("source_block_ids")
                else "legacy_experience"
            )
            confidence = _confidence(data.get("confidence"))
            scalar_values = {
                "job_title": _optional_text(data.get("job_title") or data.get("title")),
                "company": _optional_text(data.get("company")),
                "location": _optional_text(data.get("location")),
                "start_date": _optional_text(data.get("start_date")),
                "end_date": _optional_text(data.get("end_date")),
            }
            field_values: list[tuple[str, str | int | float | bool | None]] = [
                *scalar_values.items(),
                *[
                    (f"responsibilities[{index}]", value)
                    for index, value in enumerate(responsibilities)
                ],
                *[(f"achievements[{index}]", value) for index, value in enumerate(achievements)],
                *[
                    (f"technologies[{index}]", _text(value))
                    for index, value in enumerate(_sequence(data.get("technologies")))
                    if _text(value)
                ],
            ]
            field_evidence_ids = {
                field: self._field_evidence(
                    registry=registry,
                    path=f"{path}.{field}",
                    value=value,
                    source_block_ids=self._field_source_ids(data, field),
                    block_lookup=block_lookup,
                    extractor=extractor,
                    confidence=confidence,
                    section="experience",
                    source_field=field,
                )
                for field, value in field_values
                if value is not None and value != ""
            }
            evidence_ids = list(
                dict.fromkeys(
                    evidence_id for values in field_evidence_ids.values() for evidence_id in values
                )
            )
            if not evidence_ids:
                evidence_ids = self._grounded_evidence(
                    registry=registry,
                    path=path,
                    data=data,
                    block_lookup=block_lookup,
                    snapshot=snapshot,
                    extractor=extractor,
                    confidence=confidence,
                )
            output.append(
                ExperienceItem(
                    job_title=scalar_values["job_title"],
                    company=scalar_values["company"],
                    location=scalar_values["location"],
                    employment_type=_optional_text(data.get("employment_type")),
                    volunteer=bool(data.get("volunteer") or data.get("is_volunteer")),
                    start_date=scalar_values["start_date"],
                    end_date=scalar_values["end_date"],
                    current=bool(data.get("current") or data.get("is_current")),
                    responsibilities=responsibilities,
                    achievements=achievements,
                    technologies=[
                        _text(value)
                        for value in _sequence(data.get("technologies"))
                        if _text(value)
                    ],
                    metrics=[
                        _text(value) for value in _sequence(data.get("metrics")) if _text(value)
                    ],
                    confidence=_confidence(data.get("confidence")),
                    needs_review=bool(data.get("needs_review", False)),
                    parsing_needs_review=bool(data.get("parsing_needs_review", False)),
                    content_needs_review=bool(data.get("content_needs_review", False)),
                    review_reasons=[
                        _text(value)
                        for value in _sequence(data.get("review_reasons"))
                        if _text(value)
                    ],
                    evidence_ids=evidence_ids,
                    field_evidence_ids=field_evidence_ids,
                )
            )
        return output

    def _projects(
        self,
        values: list[Any],
        registry: EvidenceRegistry,
        block_lookup: Mapping[str, Mapping[str, Any]],
    ) -> list[ProjectItem]:
        output: list[ProjectItem] = []
        for item in values:
            data = _mapping(item)
            if not data:
                continue
            name = _optional_text(data.get("name") or data.get("title"))
            description = _text(data.get("description") or data.get("summary"))
            snapshot = " | ".join(filter(None, [name, description]))
            if not snapshot:
                continue
            path = f"entities.projects[{len(output)}]"
            extractor = (
                "layout_grounded_projects" if data.get("source_block_ids") else "legacy_projects"
            )
            confidence = _confidence(data.get("confidence"))
            technology_values = [
                _text(value)
                for value in _sequence(data.get("technologies") or data.get("skills"))
                if _text(value)
            ]
            field_values: list[tuple[str, str | None]] = [
                ("name", name),
                ("description", description or None),
                ("role", _optional_text(data.get("role"))),
                ("start_date", _optional_text(data.get("start_date"))),
                ("end_date", _optional_text(data.get("end_date"))),
                *[
                    (f"technologies[{index}]", value)
                    for index, value in enumerate(technology_values)
                ],
            ]
            field_evidence_ids = {
                field: self._field_evidence(
                    registry=registry,
                    path=f"{path}.{field}",
                    value=value,
                    source_block_ids=self._field_source_ids(data, field),
                    block_lookup=block_lookup,
                    extractor=extractor,
                    confidence=confidence,
                    section="projects",
                    source_field=field,
                )
                for field, value in field_values
                if value
            }
            evidence_ids = list(
                dict.fromkeys(
                    evidence_id for values in field_evidence_ids.values() for evidence_id in values
                )
            )
            if not evidence_ids:
                evidence_ids = self._grounded_evidence(
                    registry=registry,
                    path=path,
                    data=data,
                    block_lookup=block_lookup,
                    snapshot=snapshot,
                    extractor=extractor,
                    confidence=confidence,
                )
            output.append(
                ProjectItem(
                    name=name,
                    role=_optional_text(data.get("role")),
                    start_date=_optional_text(data.get("start_date")),
                    end_date=_optional_text(data.get("end_date")),
                    current=bool(data.get("current") or data.get("is_current")),
                    description=description,
                    technologies=technology_values,
                    url=_optional_text(data.get("url") or data.get("link")),
                    confidence=_confidence(data.get("confidence")),
                    needs_review=bool(data.get("needs_review", False)),
                    evidence_ids=evidence_ids,
                    field_evidence_ids=field_evidence_ids,
                )
            )
        return output

    def _languages(self, values: list[Any], registry: EvidenceRegistry) -> list[LanguageItem]:
        output: list[LanguageItem] = []
        for item in values:
            data = _mapping(item)
            language = _text(data.get("language") or data.get("name") or item)
            if not language:
                continue
            evidence_id = registry.register(
                field_path=f"entities.languages[{len(output)}]",
                value=language,
                extractor="legacy_languages",
                confidence=_confidence(data.get("confidence")),
            )
            output.append(
                LanguageItem(
                    language=language,
                    proficiency=_optional_text(data.get("proficiency") or data.get("level")),
                    cefr=_optional_text(data.get("cefr")),
                    confidence=_confidence(data.get("confidence")),
                    evidence_ids=[evidence_id],
                )
            )
        return output

    def _certifications(
        self,
        values: list[Any],
        registry: EvidenceRegistry,
        block_lookup: Mapping[str, Mapping[str, Any]],
    ) -> list[CertificationItem]:
        output: list[CertificationItem] = []
        for item in values:
            data = _mapping(item)
            name = _text(data.get("name") or data.get("title") or item)
            if not name:
                continue
            evidence_ids = self._grounded_evidence(
                registry=registry,
                path=f"entities.certifications[{len(output)}]",
                data=data,
                block_lookup=block_lookup,
                snapshot=name,
                extractor=(
                    "layout_grounded_certifications"
                    if data.get("source_block_ids")
                    else "legacy_certifications"
                ),
                confidence=_confidence(data.get("confidence")),
            )
            output.append(
                CertificationItem(
                    name=name,
                    issuer=_optional_text(data.get("issuer")),
                    date=_optional_text(data.get("date")),
                    credential_id=_optional_text(data.get("credential_id")),
                    url=_optional_text(data.get("url")),
                    confidence=_confidence(data.get("confidence")),
                    evidence_ids=evidence_ids,
                )
            )
        return output

    def _quality(
        self, raw: dict[str, Any], entities: Entities, registry: EvidenceRegistry
    ) -> tuple[QualityInfo, list[str]]:
        missing: list[str] = []
        missing_evidence: list[str] = []
        checks = {
            "summary": bool(entities.summary),
            "skills": bool(entities.skills),
            "experience": bool(entities.experience),
            "education": bool(entities.education),
        }
        for name, present in checks.items():
            if not present:
                missing.append(name)
                missing_evidence.append(registry.missing(f"entities.{name}"))
        existing = _mapping(raw.get("quality"))
        score = existing.get("score")
        if not isinstance(score, (int, float)):
            score = round(100 * sum(checks.values()) / len(checks))
        score = max(0, min(100, int(score)))
        status = "good" if score >= 80 else "needs_review" if score >= 50 else "poor"
        return (
            QualityInfo(status=status, score=score, missing_sections=missing, issues=[]),
            missing_evidence,
        )
