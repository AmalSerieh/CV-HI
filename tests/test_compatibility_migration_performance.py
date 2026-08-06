from __future__ import annotations

import time
from copy import deepcopy

import pytest

from pipeline import PipelineConfig, ResumePipeline
from resume_analyzer.ats import ATSAnalyzer
from resume_analyzer.ats.issue_builder import IssueBuilder, IssueDraft
from resume_analyzer.extraction import DocumentExtractionBackend
from resume_analyzer.rewriting import ResumeRewriter
from resume_analyzer.rewriting.parser import RewriteResponseParseError, RewriteResponseParser
from resume_analyzer.rewriting.prompts import RewritePromptBuilder
from resume_analyzer.schema_migration import SchemaMigrator
from resume_analyzer.schemas import PipelineReport
from resume_analyzer.target_roles.config import ScoringConfig
from tests.report_fixtures import make_report


def test_canonical_2_0_migration_is_explicit_private_and_input_immutable() -> None:
    old = make_report().to_json_dict()
    old["schema_version"] = "2.0.0"
    old["document"]["path"] = r"C:\Users\candidate\private-resume.pdf"
    before = deepcopy(old)

    migrated = SchemaMigrator().migrate(old)

    assert old == before
    assert migrated.source_shape == "canonical_2.0.0"
    assert migrated.warnings == ("migrated_schema:2.0.0->2.1.0",)
    assert migrated.report.schema_version == "2.1.0"
    assert migrated.report.document.path is None
    assert migrated.report.ats.status == "not_run"
    assert migrated.report.rewrites.status == "not_run"
    assert any(item.code == "migrated_schema_2_0_0_to_2_1_0" for item in migrated.report.warnings)


def test_canonical_2_0_path_can_be_retained_only_when_explicitly_enabled() -> None:
    old = make_report().to_json_dict()
    old["schema_version"] = "2.0.0"
    old["document"]["path"] = r"C:\private\resume.pdf"
    migrated = SchemaMigrator(include_document_path=True).migrate(old)
    assert migrated.report.document.path == r"C:\private\resume.pdf"


def test_large_ats_inputs_use_bounded_linear_lookup_paths() -> None:
    blocks = [
        {
            "id": f"p1_b{index}",
            "page": 1,
            "text": f"Skill {index} project evidence",
            "bbox": {"x0": 40, "top": 20 + index, "x1": 500, "bottom": 30 + index},
            "column": "single",
            "order": index,
            "engine": "pymupdf",
            "block_type": "line",
            "is_repeated_header_footer": False,
        }
        for index in range(500)
    ]
    report = make_report(blocks=blocks, skills=[f"Skill {index}" for index in range(500)])

    started = time.perf_counter()
    result = ATSAnalyzer().analyze(report, job_description="Skill 1 Skill 200 Skill 499")
    elapsed = time.perf_counter() - started

    assert result.status in {"complete", "partial"}
    assert result.job_match.status == "complete"
    assert elapsed < 5.0


def test_repeated_duplicate_issue_drafts_are_deduplicated_efficiently() -> None:
    report = make_report()
    evidence_id = report.evidence[0].id
    drafts = [IssueDraft("MISSING_EMAIL", (evidence_id,), "stress", 0.9)] * 2_000

    started = time.perf_counter()
    issues = IssueBuilder(report, language="en").build_issues(drafts)
    elapsed = time.perf_counter() - started

    assert len(issues) == 1
    assert elapsed < 2.0


def test_rewriter_honors_bullet_limit_and_requested_sections() -> None:
    report = make_report(
        experience=[
            {
                "job_title": "Engineer",
                "company": "Example Corp",
                "responsibilities": [f"Worked on task {index}." for index in range(100)],
                "technologies": ["Python"],
            }
        ]
    )
    result = ResumeRewriter(None, sections=("experience",), max_bullets=7).rewrite(report)

    assert len(result.experience_bullets) == 7
    assert result.summary.status == "not_run"
    assert result.skills_section.status == "not_run"


def test_document_prompt_and_response_limits_fail_closed(tmp_path) -> None:
    backend = DocumentExtractionBackend(PipelineConfig(max_document_characters=10))
    with pytest.raises(Exception, match="exceeds 10 characters"):
        backend.extract_text("This resume text is too long")

    oversized = tmp_path / "oversized.pdf"
    oversized.write_bytes(b"x" * 20)
    with pytest.raises(Exception, match="exceeds 10 bytes"):
        DocumentExtractionBackend(PipelineConfig(max_document_bytes=10)).extract(str(oversized))

    with pytest.raises(ValueError, match="prompt exceeds"):
        RewritePromptBuilder(max_characters=100).summary(make_report(), [], "en")
    with pytest.raises(RewriteResponseParseError, match="exceeds"):
        RewriteResponseParser(max_characters=10).parse("{" + (" " * 20) + "}", PipelineReport)


def test_injected_modules_do_not_initialize_a_second_provider(monkeypatch) -> None:
    from resume_analyzer.pipeline import orchestrator

    class Recommendations:
        def recommend(self, report):
            raise AssertionError("not called during construction")

    class Rewriter:
        def rewrite(self, report):
            raise AssertionError("not called during construction")

    def fail_provider_initialization(*args, **kwargs):
        raise AssertionError("provider factory must not run for injected modules")

    monkeypatch.setattr(orchestrator, "build_provider", fail_provider_initialization)
    pipeline = ResumePipeline(
        config=PipelineConfig(enable_recommendations=True, enable_rewrites=True),
        recommendation_engine=Recommendations(),
        resume_rewriter=Rewriter(),
    )
    assert pipeline.recommendation_engine is not None
    assert pipeline.resume_rewriter is not None


def test_target_role_primary_result_keeps_documented_evidence_threshold() -> None:
    report = make_report()

    class Backend:
        def extract(self, file_path):
            return report

        def extract_text(self, text, *, document_name="inline.txt"):
            return report

    result = ResumePipeline(
        config=PipelineConfig(enable_recommendations=False), extraction_backend=Backend()
    ).analyze("synthetic.pdf")
    primary = result["target_role"]["primary"]

    assert primary is not None
    unique_evidence = {(item["path"], item["value"].casefold()) for item in primary["evidence"]}
    assert len(unique_evidence) >= ScoringConfig().minimum_unique_evidence
    assert primary["matched_signals"]
    assert all(item["source"] and item["path"] and item["value"] for item in primary["evidence"])


def test_professional_ats_imports_expose_one_canonical_implementation() -> None:
    from resume_analyzer.ats import ATSAnalyzer as ExportedAnalyzer
    from resume_analyzer.ats import JobDescriptionMatcher as ExportedMatcher
    from resume_analyzer.ats.analyzer import ATSAnalyzer as CanonicalAnalyzer
    from resume_analyzer.ats.job_match import JobDescriptionMatcher as CanonicalMatcher

    assert ExportedAnalyzer is CanonicalAnalyzer
    assert ExportedMatcher is CanonicalMatcher


def test_full_cli_returns_nonzero_with_clear_critical_error(capsys) -> None:
    from resume_analyzer.cli import main

    exit_code = main(["missing-synthetic-resume.pdf"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "InvalidDocumentError" in captured.err
    assert "missing-synthetic-resume.pdf" in captured.err
