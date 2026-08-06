"""Validate that canonical entity evidence is local to the asserted field."""

from __future__ import annotations

from dataclasses import dataclass

from resume_analyzer.schemas import PipelineReport


@dataclass(frozen=True)
class EvidenceCoherenceFinding:
    code: str
    entity_path: str
    evidence_ids: tuple[str, ...]
    detail: str
    confidence: float


class EvidenceCoherenceValidator:
    """Check page, block, section, and column coherence without inferring facts."""

    _SECTION_COLLECTIONS = {
        "skills": "skills",
        "education": "education",
        "experience": "experience",
        "projects": "projects",
        "languages": "languages",
        "certifications": "certifications",
    }

    @staticmethod
    def _source_records(evidence, evidence_ids):
        """Resolve compact derived-evidence chains to their source records."""

        resolved = []
        visited: set[str] = set()

        def visit(evidence_id: str) -> None:
            if evidence_id in visited:
                return
            visited.add(evidence_id)
            record = evidence.get(evidence_id)
            if record is None:
                return
            if record.parent_evidence_ids:
                for parent_id in record.parent_evidence_ids:
                    visit(parent_id)
                return
            resolved.append(record)

        for evidence_id in evidence_ids:
            visit(evidence_id)
        return resolved

    def validate(self, report: PipelineReport) -> list[EvidenceCoherenceFinding]:
        evidence = {item.id: item for item in report.evidence}
        blocks = {item.id: item for item in report.extraction.layout_blocks}
        findings: list[EvidenceCoherenceFinding] = []

        for collection_name, section_name in self._SECTION_COLLECTIONS.items():
            collection = getattr(report.entities, collection_name)
            section = report.extraction.sections.get(section_name)
            allowed_blocks = set(section.block_ids if section else [])
            for index, entity in enumerate(collection):
                path = f"entities.{collection_name}[{index}]"
                records = self._source_records(evidence, entity.evidence_ids)
                source_blocks = [
                    blocks[record.source.block_id]
                    for record in records
                    if record.source.block_id in blocks
                ]
                source_ids = {block.id for block in source_blocks}
                if allowed_blocks and source_ids - allowed_blocks:
                    invalid_ids = tuple(
                        record.id
                        for record in records
                        if record.source.block_id in source_ids - allowed_blocks
                    )
                    findings.append(
                        EvidenceCoherenceFinding(
                            code="evidence_section_mismatch",
                            entity_path=path,
                            evidence_ids=invalid_ids,
                            detail=(
                                f"Evidence for {path} points outside the {section_name} section."
                            ),
                            confidence=0.99,
                        )
                    )

                columns = {
                    block.column
                    for block in source_blocks
                    if block.column not in {"full_width", "single", "unknown"}
                }
                if len(columns) > 1:
                    findings.append(
                        EvidenceCoherenceFinding(
                            code="evidence_cross_column",
                            entity_path=path,
                            evidence_ids=tuple(record.id for record in records),
                            detail=(
                                f"Evidence for {path} spans parallel columns: "
                                f"{', '.join(sorted(columns))}."
                            ),
                            confidence=0.98,
                        )
                    )

                pages = {block.page for block in source_blocks}
                if section and section.pages and pages - set(section.pages):
                    findings.append(
                        EvidenceCoherenceFinding(
                            code="evidence_page_mismatch",
                            entity_path=path,
                            evidence_ids=tuple(record.id for record in records),
                            detail=f"Evidence for {path} points outside its section pages.",
                            confidence=0.99,
                        )
                    )

        coordinate_free = report.extraction.engine in {"docx", "docx_ooxml"}
        for field, evidence_ids in report.entities.contact.evidence_ids.items():
            if not getattr(report.entities.contact, field):
                continue
            for evidence_id in evidence_ids:
                record = evidence.get(evidence_id)
                block_id = record.source.block_id if record else None
                block = blocks.get(block_id) if block_id else None
                if block is None:
                    continue
                if coordinate_free and block.bbox is None:
                    continue
                top = block.bbox.top if block.bbox else 9999.0
                if block.page != 1 or (
                    block.zone_kind != "header" and top > 180.0
                ):
                    findings.append(
                        EvidenceCoherenceFinding(
                            code="contact_evidence_outside_header",
                            entity_path=f"entities.contact.{field}",
                            evidence_ids=(evidence_id,),
                            detail=(
                                f"Contact evidence for {field} is outside the page-one "
                                "contact region."
                            ),
                            confidence=0.97,
                        )
                    )
        return findings
