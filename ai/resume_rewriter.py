"""Deprecated compatibility import for the canonical rewrite service."""

import warnings

warnings.warn(
    "Import ResumeRewriter from resume_analyzer.rewriting.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.rewriting import ResumeRewriter  # noqa: E402

__all__ = ["ResumeRewriter"]
