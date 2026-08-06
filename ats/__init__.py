"""Deprecated compatibility import for :mod:`resume_analyzer.ats`."""

import warnings

warnings.warn(
    "Import ATS capabilities from resume_analyzer.ats; top-level ats is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.ats import *  # noqa: E402,F403
from resume_analyzer.ats import __all__ as __all__  # noqa: E402
