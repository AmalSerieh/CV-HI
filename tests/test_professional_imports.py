from __future__ import annotations

import importlib
import inspect
import sys

import pytest


def test_main_package_exports_canonical_pipeline():
    from pipeline import ResumePipeline as LegacyPipeline
    from resume_analyzer import ResumePipeline

    assert ResumePipeline is LegacyPipeline


def test_professional_recommendation_path_is_canonical_identity():
    from ai.recommendation_engine import RecommendationEngine as LegacyEngine
    from resume_analyzer.recommendations import RecommendationEngine

    assert RecommendationEngine is LegacyEngine


def test_professional_ats_path_is_canonical_identity():
    from ats import ATSAnalyzer as LegacyAnalyzer
    from resume_analyzer.ats import ATSAnalyzer

    assert ATSAnalyzer is LegacyAnalyzer


def test_professional_rewriting_path_is_canonical_identity():
    from ai.resume_rewriter import ResumeRewriter as LegacyRewriter
    from resume_analyzer.rewriting import ResumeRewriter

    assert ResumeRewriter is LegacyRewriter


def test_professional_schema_path_is_same_model():
    from resume_analyzer.schemas import PipelineReport as ProfessionalReport
    from schemas import PipelineReport

    assert ProfessionalReport is PipelineReport


def test_professional_target_role_api_works():
    from resume_analyzer.target_roles import suggest_target_roles

    result = suggest_target_roles(
        {
            "schema_version": "2.1.0",
            "entities": {
                "summary": "Python API engineer",
                "skills": [{"value": "Python"}, {"value": "SQL"}],
                "experience": [],
                "projects": [],
                "education": [],
                "certifications": [],
            },
        }
    )
    assert "target_role" in result


def test_numbered_model_registry_is_thin_deprecated_wrapper():
    sys.modules.pop("models1.model_registry", None)
    with pytest.warns(DeprecationWarning, match="resume_analyzer.ai.model_registry"):
        legacy = importlib.import_module("models1.model_registry")
    from resume_analyzer.ai.model_registry import ModelRegistry

    assert legacy.ModelRegistry is ModelRegistry


def test_pipeline_runtime_target_role_label_is_professional():
    from resume_analyzer.pipeline.orchestrator import ResumePipeline

    source = inspect.getsource(ResumePipeline._attach_target_role)
    assert "person4" not in source.casefold()
