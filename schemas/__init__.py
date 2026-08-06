"""Deprecated compatibility import for :mod:`resume_analyzer.schemas`."""

import warnings

warnings.warn(
    "Import schemas from resume_analyzer.schemas; the top-level package is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.schemas import *  # noqa: E402,F403
from resume_analyzer.schemas import __all__ as __all__  # noqa: E402
