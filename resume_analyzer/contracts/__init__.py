"""Optional protocol seams for canonical analysis capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from resume_analyzer.schemas import ATSResult, PipelineReport, RecommendationBatch, RewriteResult


@runtime_checkable
class RecommendationProvider(Protocol):
    def recommend(self, report: PipelineReport | Mapping[str, Any]) -> RecommendationBatch: ...


@runtime_checkable
class ATSAnalyzerProvider(Protocol):
    def analyze(
        self, report: PipelineReport, *, job_description: str | None = None
    ) -> ATSResult: ...


@runtime_checkable
class RewriteProvider(Protocol):
    def rewrite(self, report: PipelineReport) -> RewriteResult: ...


# Compatibility protocol names retained for older imports.
ATSScorer = ATSAnalyzerProvider
ResumeRewriter = RewriteProvider


__all__ = [
    "ATSAnalyzerProvider",
    "ATSScorer",
    "RecommendationProvider",
    "ResumeRewriter",
    "RewriteProvider",
]
