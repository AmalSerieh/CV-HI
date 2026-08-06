"""Deprecated compatibility import for :mod:`resume_analyzer.contracts`."""

import warnings

warnings.warn(
    "Import contracts from resume_analyzer.contracts; the top-level package is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.contracts import *  # noqa: E402,F403
from resume_analyzer.contracts import __all__ as __all__  # noqa: E402
