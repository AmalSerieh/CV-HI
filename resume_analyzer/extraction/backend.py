from __future__ import annotations

from typing import Protocol, runtime_checkable

from resume_analyzer.schemas import PipelineReport


@runtime_checkable
class ExtractionBackend(Protocol):
    """Dependency-injection boundary used by ``ResumePipeline``."""

    def extract(self, file_path: str) -> PipelineReport: ...

    def extract_text(self, text: str, *, document_name: str = "inline.txt") -> PipelineReport: ...
