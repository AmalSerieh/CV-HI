"""Deprecated compatibility import for the legacy analysis contract."""

import warnings

warnings.warn(
    "Import resume_analyzer.contracts.analysis_contract instead.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer.contracts.analysis_contract import *  # noqa: E402,F403
