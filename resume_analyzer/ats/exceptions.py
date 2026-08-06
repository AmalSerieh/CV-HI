"""Typed ATS analysis failures."""


class ATSAnalysisError(RuntimeError):
    """Base class for expected ATS analysis failures."""


class InvalidJobDescriptionError(ATSAnalysisError, ValueError):
    """The optional job description violates the bounded input contract."""
