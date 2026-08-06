"""Deprecated compatibility import for :mod:`resume_analyzer.ai.providers`."""

import warnings

warnings.warn(
    "Import providers from resume_analyzer.ai.providers; ai.providers is deprecated.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.ai.providers import *  # noqa: E402,F403
from resume_analyzer.ai.providers import __all__ as __all__  # noqa: E402
