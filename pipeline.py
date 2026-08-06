"""Preferred public import for the resume pipeline."""

from resume_analyzer.config import PipelineConfig
from resume_analyzer.pipeline import ResumePipeline

__all__ = ["PipelineConfig", "ResumePipeline"]
