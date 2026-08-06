"""Deprecated compatibility import for the canonical ATS analyzer."""

from resume_analyzer.ats import ATSAnalyzer, ATSScoringPolicy

ATSScorer = ATSAnalyzer

__all__ = ["ATSAnalyzer", "ATSScorer", "ATSScoringPolicy"]
