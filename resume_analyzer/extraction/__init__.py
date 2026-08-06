"""Canonical document extraction capability."""

from .backend import ExtractionBackend
from .document_backend import DocumentExtractionBackend

# Compatibility class name for callers migrating from resume_analyzer.extractors.
LegacyExtractorBackend = DocumentExtractionBackend

__all__ = ["DocumentExtractionBackend", "ExtractionBackend", "LegacyExtractorBackend"]
