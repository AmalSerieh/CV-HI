"""Deprecated compatibility import for :mod:`resume_analyzer`."""

import warnings

warnings.warn(
    "pipeline2 is deprecated; import PipelineConfig and ResumePipeline from resume_analyzer.",
    DeprecationWarning,
    stacklevel=2,
)

from resume_analyzer import PipelineConfig, ResumePipeline  # noqa: E402

__all__ = ["PipelineConfig", "ResumePipeline"]
