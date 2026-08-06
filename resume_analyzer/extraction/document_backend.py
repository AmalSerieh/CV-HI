"""Canonical document extraction backend."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from resume_analyzer.schemas import PipelineMessage, PipelineReport

from ..config import PipelineConfig
from ..exceptions import (
    DependencyUnavailableError,
    DocumentExtractionError,
    InvalidDocumentError,
)
from ..schema_migration import SchemaMigrator
from .certifications import CertificationsExtractor


class DocumentExtractionBackend:
    """Run the repository's extraction algorithms behind one typed boundary."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        migrator: SchemaMigrator | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.migrator = migrator or SchemaMigrator(
            include_document_path=self.config.include_document_path
        )

    def extract(self, file_path: str) -> PipelineReport:
        path = Path(file_path).expanduser()
        if not path.exists() or not path.is_file():
            raise InvalidDocumentError(f"Resume file does not exist: {path}")
        extension = path.suffix.casefold()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise InvalidDocumentError(
                f"Unsupported resume type {extension!r}; expected PDF or DOCX"
            )
        size_bytes = path.stat().st_size
        if size_bytes > self.config.max_document_bytes:
            raise InvalidDocumentError(
                f"Resume file exceeds {self.config.max_document_bytes} bytes"
            )

        try:
            from .text_extractor import TextExtractor
        except ModuleNotFoundError as exc:
            raise DependencyUnavailableError(
                f"Document extraction dependency is unavailable: {exc.name}"
            ) from exc

        extractor = TextExtractor(
            enable_ocr=self.config.enable_ocr,
            ocr_language=self.config.ocr_language,
            tesseract_cmd=self.config.tesseract_cmd,
        )
        extracted = extractor.extract(str(path))
        if not extracted.get("success"):
            raise DocumentExtractionError(
                str(extracted.get("error") or "No readable text was extracted")
            )
        extracted_text = str(extracted.get("ordered_text") or extracted.get("text") or "")
        if len(extracted_text) > self.config.max_document_characters:
            raise InvalidDocumentError(
                f"Extracted resume text exceeds {self.config.max_document_characters} characters"
            )
        return self._normalize_text_result(
            text=extracted_text,
            raw_text=str(extracted.get("raw_text") or extracted.get("text") or ""),
            document_name=path.name,
            document_path=str(path.resolve()) if self.config.include_document_path else None,
            size_bytes=size_bytes,
            text_extraction=extracted,
        )

    def extract_text(self, text: str, *, document_name: str = "inline.txt") -> PipelineReport:
        if not isinstance(text, str) or not text.strip():
            raise InvalidDocumentError("Inline resume text must be a non-empty string")
        if len(text) > self.config.max_document_characters:
            raise InvalidDocumentError(
                f"Inline resume text exceeds {self.config.max_document_characters} characters"
            )
        return self._normalize_text_result(
            text=text,
            raw_text=text,
            document_name=document_name,
            document_path=None,
            size_bytes=len(text.encode("utf-8")),
            text_extraction={
                "success": True,
                "pages": 1,
                "words": len(text.split()),
                "chars": len(text),
                "layout": "unknown",
                "engine": "unknown",
                "quality_score": 80,
                "ocr_used": False,
                "warnings": [],
            },
        )

    def _normalize_text_result(
        self,
        *,
        text: str,
        raw_text: str,
        document_name: str,
        document_path: str | None,
        size_bytes: int,
        text_extraction: dict[str, Any],
    ) -> PipelineReport:
        stage_messages: list[PipelineMessage] = []

        try:
            from .section_extractor import SectionExtractor
            from .text_cleaner import TextCleaner
        except ModuleNotFoundError as exc:
            raise DependencyUnavailableError(
                f"Core extraction dependency is unavailable: {exc.name}"
            ) from exc

        cleaned = TextCleaner().clean(text)
        section_result = self._stage(
            "sections",
            lambda: SectionExtractor().extract_sections(
                cleaned,
                layout_blocks=list(text_extraction.get("raw_layout_blocks") or []),
                page_layouts=list(text_extraction.get("page_layouts") or []),
            ),
            {},
            stage_messages,
        )
        section_warnings = list(section_result.get("warnings") or [])
        if section_warnings:
            extraction_warnings = text_extraction.setdefault("warnings", [])
            extraction_warnings.extend(
                warning for warning in section_warnings if warning not in extraction_warnings
            )
        section_payload = {
            "sections": section_result.get("sections", {}),
            "cleaned_text": cleaned,
            "text": cleaned,
            "raw_text": raw_text,
        }

        contact = self._stage(
            "contact", lambda: self._contact(cleaned, raw_text, text_extraction), {}, stage_messages
        )
        skills = self._stage("skills", lambda: self._skills(section_result), {}, stage_messages)
        education = self._stage(
            "education", lambda: self._education(section_payload), {}, stage_messages
        )
        experience = self._stage(
            "experience", lambda: self._experience(section_payload), {}, stage_messages
        )
        projects = self._stage(
            "projects", lambda: self._projects(section_payload), {}, stage_messages
        )
        languages = self._stage(
            "languages", lambda: self._languages(section_payload), {}, stage_messages
        )
        certifications = self._stage(
            "certifications",
            lambda: CertificationsExtractor().extract({"sections": section_result}),
            [],
            stage_messages,
        )
        layout_blocks = list(text_extraction.get("raw_layout_blocks") or [])
        if layout_blocks:
            from .structured_entities import StructuredEntityAssembler

            assembler = StructuredEntityAssembler(
                layout_blocks=layout_blocks,
                sections=section_result,
            )
            experience = assembler.experience(experience)
            projects = assembler.projects(projects)
            education = assembler.education(education)
            skills = assembler.skills(skills)
            certifications = assembler.certifications(certifications)

        legacy = {
            "success": True,
            "file": {
                "path": document_path,
                "name": document_name,
                "extension": Path(document_name).suffix.casefold(),
                "size_bytes": size_bytes,
            },
            "text_extraction": text_extraction,
            "sections": section_result,
            "contact": contact,
            "skills": skills,
            "education": education,
            "experience": experience,
            "projects": projects,
            "languages": languages,
            "certifications": certifications,
        }
        result = self.migrator.from_extraction_modules(legacy).report.to_json_dict()
        result["warnings"].extend(message.model_dump(mode="json") for message in stage_messages)
        if stage_messages:
            result["extraction"]["status"] = "degraded"
            result["module_status"]["extraction"] = {
                "status": "degraded",
                "provider": "legacy_adapters",
                "detail": f"{len(stage_messages)} extractor stage(s) degraded",
            }
        else:
            result["module_status"]["extraction"]["provider"] = "legacy_adapters"
        canonical = PipelineReport.model_validate(result)
        from .data_quality import CanonicalDataQualityAnalyzer

        quality_analyzer = CanonicalDataQualityAnalyzer()
        quality = quality_analyzer.analyze(canonical)
        annotated_experience = quality_analyzer.annotate_experience_reviews(
            canonical,
            quality,
        )
        result = canonical.to_json_dict()
        result["entities"]["experience"] = [
            item.model_dump(mode="json") for item in annotated_experience
        ]
        result["data_quality"] = quality.model_dump(mode="json")
        return PipelineReport.model_validate(result)

    def _stage(
        self,
        name: str,
        operation: Callable[[], Any],
        default: Any,
        messages: list[PipelineMessage],
    ) -> Any:
        try:
            return operation()
        except ModuleNotFoundError as exc:
            raise DependencyUnavailableError(
                f"Dependency {exc.name!r} is required by extractor stage {name!r}"
            ) from exc
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            messages.append(
                PipelineMessage(
                    stage=name,
                    code="extractor_stage_failed",
                    message=f"{type(exc).__name__}: {exc}",
                    recoverable=True,
                )
            )
            return default

    @staticmethod
    def _contact(text: str, raw_text: str, extraction: dict[str, Any]) -> dict[str, Any]:
        from .contact import ContactResolver

        contact_lines: list[str] = []
        contact_ocr_text = str(extraction.get("contact_ocr_text") or "").strip()
        if contact_ocr_text:
            contact_lines.append(contact_ocr_text)
        for link in extraction.get("links") or []:
            value = str(link or "").strip()
            lowered = value.casefold()
            if lowered.startswith("mailto:"):
                contact_lines.append(value[7:].split("?", 1)[0])
            elif lowered.startswith("tel:"):
                contact_lines.append(f"Phone: {value[4:].split('?', 1)[0]}")

        ordered_lines = text.splitlines()
        insertion = min(3, len(ordered_lines))
        augmented_ordered = "\n".join(
            ordered_lines[:insertion] + contact_lines + ordered_lines[insertion:]
        )
        augmented_raw = "\n".join(value for value in [raw_text, *contact_lines] if value)
        layout_blocks = list(extraction.get("raw_layout_blocks") or [])
        layout_blocks.extend(extraction.get("contact_ocr_blocks") or [])
        return ContactResolver().resolve(
            text=augmented_ordered,
            raw_text=augmented_raw,
            layout_blocks=layout_blocks,
            file_links=list(extraction.get("links") or []),
        )

    def _skills(self, sections: dict[str, Any]) -> dict[str, Any]:
        from .skills_extractor import SkillsExtractor

        return SkillsExtractor(
            use_spacy=self.config.use_spacy,
            use_sbert=self.config.use_sbert,
            allow_model_download=self.config.allow_model_download,
        ).extract(sections)

    def _education(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .education_extractor import EducationExtractor

        return EducationExtractor(use_spacy=self.config.use_spacy).extract(payload)

    def _experience(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .experience_extractor import ExperienceExtractor

        return ExperienceExtractor(
            use_spacy=self.config.use_spacy,
            use_sbert=self.config.use_sbert,
            allow_model_download=self.config.allow_model_download,
        ).extract(payload)

    def _projects(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .projects_extractor import ProjectsExtractor

        return ProjectsExtractor(
            use_spacy=self.config.use_spacy,
            use_sbert=self.config.use_sbert,
            allow_model_download=self.config.allow_model_download,
        ).extract(payload)

    @staticmethod
    def _languages(payload: dict[str, Any]) -> dict[str, Any]:
        from .languages_extractor import LanguagesExtractor

        return LanguagesExtractor().extract(payload)
