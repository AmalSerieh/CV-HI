"""Deprecated compatibility import for job-description matching."""

from resume_analyzer.ats import JobDescriptionMatcher

JobMatcher = JobDescriptionMatcher

__all__ = ["JobDescriptionMatcher", "JobMatcher"]
