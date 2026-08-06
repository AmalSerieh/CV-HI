"""Deprecated compatibility import for :mod:`resume_analyzer.extraction`."""

import warnings

warnings.warn(
    "resume_analyzer.extractors is deprecated; use resume_analyzer.extraction.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.extraction import *  # noqa: E402,F403
from resume_analyzer.extraction import __all__ as __all__  # noqa: E402
