"""Typed public failures for the canonical pipeline."""


class ResumePipelineError(RuntimeError):
    """Base class for expected pipeline failures."""


class InvalidDocumentError(ResumePipelineError):
    """The supplied path or document type is invalid."""


class DocumentExtractionError(ResumePipelineError):
    """A supported document could not be read."""


class DependencyUnavailableError(ResumePipelineError):
    """A required or explicitly enabled optional dependency is unavailable."""


class ReportExportError(ResumePipelineError):
    """A validated report could not be exported."""
