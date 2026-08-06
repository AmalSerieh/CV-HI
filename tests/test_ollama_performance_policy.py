from __future__ import annotations

import json
from copy import deepcopy

import pytest

from resume_analyzer import PipelineConfig, ResumePipeline
from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.providers import (
    AIProviderModelNotFound,
    AIProviderTimeout,
    AIProviderUnavailable,
    MockProvider,
    OllamaProvider,
)
from resume_analyzer.recommendations import RecommendationEngine
from resume_analyzer.recommendations.parser import ResponseParser
from resume_analyzer.recommendations.prompts import PromptBuilder
from resume_analyzer.rewriting import ResumeRewriter
from tests.report_fixtures import make_report


def _recommendation_response(report) -> str:
    request = PromptBuilder().build_request(report)
    schema = ResponseParser.response_schema(
        provider="mock",
        model="mock-v1",
        evidence_ids=list(request.evidence_ids),
        focus_evidence_id=request.focus_evidence_id,
        focus_kind=request.focus_kind,
        focus_area=request.focus_area,
        focus_language=request.focus_language,
        focus_severity=request.focus_severity,
        focus_title=request.focus_title,
        focus_problem=request.focus_problem,
        focus_suggestion=request.focus_suggestion,
    )
    properties = schema["properties"]
    return json.dumps(
        {
            "area": properties["area"]["const"],
            "severity": properties["severity"].get("const", "medium"),
            "title": properties["title"]["const"],
            "problem": properties["problem"]["const"],
            "suggestion": properties["suggestion"]["const"],
            "evidence_ids": [request.focus_evidence_id],
            "conditional": properties["conditional"]["const"],
        }
    )


def _summary_response(report) -> str:
    evidence_ids = [
        item.id
        for item in report.evidence
        if item.field_path.startswith("entities.summary")
        or item.field_path.startswith("entities.skills")
        or item.field_path.startswith("entities.experience")
        or item.field_path.startswith("entities.projects")
    ][:16]
    return json.dumps(
        {
            "original": report.entities.summary,
            "improved": "Python developer building APIs.",
            "evidence_ids": evidence_ids,
            "changes": [],
            "requires_review": False,
        }
    )


def _bullet_response(report) -> str:
    experience = report.entities.experience[0]
    original = experience.responsibilities[0]
    return json.dumps(
        {
            "experience_index": 0,
            "bullet_index": 0,
            "bullet_kind": "responsibility",
            "original": original,
            "improved": original,
            "evidence_ids": experience.evidence_ids,
            "changes": [],
            "requires_review": False,
        }
    )


def _skills_response(report) -> str:
    original = [item.value for item in report.entities.skills]
    evidence_ids = list(
        dict.fromkeys(
            evidence_id for item in report.entities.skills for evidence_id in item.evidence_ids
        )
    )
    return json.dumps(
        {
            "original_items": original,
            "improved_groups": [{"group": "Skills", "items": original}],
            "added_items": [],
            "removed_duplicates": [],
            "evidence_ids": evidence_ids,
            "requires_review": False,
        }
    )


def _pipeline(report, provider):
    client = AIClient(provider, retries=0)
    recommendation_engine = RecommendationEngine(
        provider,
        client=client,
        retries=0,
        max_output_tokens=220,
    )
    rewriter = ResumeRewriter(
        provider,
        client=client,
        retries=0,
        sections=("summary", "experience", "skills"),
        max_bullets=1,
        max_output_tokens=240,
    )

    class Backend:
        def extract(self, _file_path):
            return report

        def extract_text(self, _text, *, document_name="inline.txt"):
            del document_name
            return report

    config = PipelineConfig(
        integrate_target_role=False,
        enable_recommendations=True,
        enable_ats=False,
        enable_rewrites=True,
        ai_provider="none",
        rewrite_sections=("summary", "experience", "skills"),
    )
    pipeline = ResumePipeline(
        config,
        extraction_backend=Backend(),
        recommendation_engine=recommendation_engine,
        resume_rewriter=rewriter,
    )
    return pipeline, client, recommendation_engine, rewriter


def test_timeout_is_not_retried_and_attempt_count_is_truthful() -> None:
    provider = MockProvider(AIProviderTimeout("transport timeout"))
    with pytest.raises(AIProviderTimeout, match=r"attempt 1/1") as captured:
        AIClient(provider, timeout_seconds=1, retries=3).generate(
            "prompt", operation="recommendation"
        )
    assert len(provider.calls) == 1
    assert captured.value.details["attempt"] == 1
    assert captured.value.details["max_attempts"] == 1


def test_retryable_connection_failure_receives_one_bounded_retry() -> None:
    provider = MockProvider([AIProviderUnavailable("connection refused", retryable=True), "{}"])
    response = AIClient(provider, retries=1).generate("prompt")
    assert response.text == "{}"
    assert len(provider.calls) == 2


def test_model_missing_is_not_retried() -> None:
    provider = MockProvider(AIProviderModelNotFound("missing", retryable=False))
    with pytest.raises(AIProviderModelNotFound):
        AIClient(provider, retries=2).generate("prompt")
    assert len(provider.calls) == 1


def test_cancellable_ollama_timeout_closes_connection_before_return(monkeypatch) -> None:
    state = {"closed": False, "requests": 0}

    class Socket:
        def settimeout(self, _timeout):
            pass

    class Response:
        status = 200
        reason = "OK"

        def readline(self, _limit):
            raise TimeoutError("synthetic read deadline")

        def close(self):
            state["closed"] = True

    class Connection:
        sock = Socket()

        def connect(self):
            pass

        def request(self, *_args, **_kwargs):
            state["requests"] += 1

        def getresponse(self):
            return Response()

        def close(self):
            state["closed"] = True

    provider = OllamaProvider("synthetic", cancel_cooldown_seconds=0)
    monkeypatch.setattr(provider, "_connection", lambda: Connection())
    with pytest.raises(AIProviderTimeout, match="http_read") as captured:
        AIClient(provider, retries=2).generate("safe synthetic prompt", operation="rewrite_summary")
    assert state == {"closed": True, "requests": 1}
    assert captured.value.details["request_reached_ollama"] is True
    assert captured.value.details["partial_response_bytes"] == 0


def test_recommendation_projection_is_bounded_deterministic_and_minimal() -> None:
    report = make_report(
        skills=[f"Skill-{index}-" + ("x" * 100) for index in range(40)],
        education=[],
        experience=[
            {
                "job_title": f"Engineer {index}",
                "company": "Synthetic Company",
                "responsibilities": [
                    f"Synthetic bullet {item} " + ("y" * 200) for item in range(8)
                ],
                "technologies": ["Python"],
            }
            for index in range(8)
        ],
    )
    builder = PromptBuilder(
        max_skills=5,
        max_experience_entries=2,
        max_bullets_per_experience=2,
        max_projects=1,
        max_field_characters=80,
        max_total_characters=5_000,
        max_evidence_records=8,
    )
    first = builder.build_request(report)
    second = builder.build_request(report)
    assert first == second
    assert len(first.prompt) <= 5_000
    assert len(first.evidence_ids) <= 8
    assert first.warnings
    assert '"layout_blocks"' not in first.prompt
    assert '"ats"' not in first.prompt
    assert '"rewrites"' not in first.prompt
    projection = json.loads(
        first.prompt.split("<untrusted_resume_data>\n", 1)[1].split(
            "\n</untrusted_resume_data>",
            1,
        )[0]
    )
    assert projection["recommendation_focus"]["field_path"] == "entities.education"


def test_recommendation_projection_detects_arabic_from_canonical_sections() -> None:
    report = make_report(
        sections={
            "summary": {
                "heading": "الملخص",
                "content": "مهندسة برمجيات تطور خدمات موثوقة وتطبيقات عملية.",
            },
            "skills": {"heading": "المهارات", "content": "Python وSQL"},
            "experience": {
                "heading": "الخبرة",
                "content": "طورت خدمات برمجية وكتبت استعلامات للبيانات.",
            },
        },
        summary="مهندسة برمجيات تطور خدمات موثوقة.",
        skills=["Python", "SQL"],
    )
    request = PromptBuilder().build_request(report)
    assert '"detected_language": "ar"' in request.prompt


def test_operation_specific_output_limits_are_forwarded() -> None:
    report = make_report(education=[])
    provider = MockProvider(_recommendation_response(report))
    RecommendationEngine(provider, retries=0, max_output_tokens=220).recommend(report)
    assert provider.calls == [
        {
            "prompt": provider.calls[0]["prompt"],
            "timeout_seconds": 20.0,
            "response_schema": provider.calls[0]["response_schema"],
            "operation": "recommendation",
            "max_output_tokens": 220,
        }
    ]


def test_rewriter_makes_only_the_intended_focused_calls() -> None:
    report = make_report()
    provider = MockProvider(
        [_summary_response(report), _bullet_response(report), _skills_response(report)]
    )
    result = ResumeRewriter(
        provider,
        retries=0,
        sections=("summary", "experience", "skills"),
        max_bullets=1,
        max_output_tokens=240,
    ).rewrite(report)
    assert result.status == "complete"
    assert [call["operation"] for call in provider.calls] == [
        "rewrite_summary",
        "rewrite_bullet",
        "rewrite_skills",
    ]
    assert {call["max_output_tokens"] for call in provider.calls} == {240}
    summary_data = json.loads(
        str(provider.calls[0]["prompt"])
        .split("<untrusted_resume_data>\n")[1]
        .split("\n</untrusted_resume_data>")[0]
    )
    bullet_data = json.loads(
        str(provider.calls[1]["prompt"])
        .split("<untrusted_resume_data>\n")[1]
        .split("\n</untrusted_resume_data>")[0]
    )
    skills_data = json.loads(
        str(provider.calls[2]["prompt"])
        .split("<untrusted_resume_data>\n")[1]
        .split("\n</untrusted_resume_data>")[0]
    )
    assert summary_data["component"] == "summary" and "experience_index" not in summary_data
    assert bullet_data["component"] == "experience_bullet" and "original_items" not in bullet_data
    assert skills_data["component"] == "skills_section" and "protected_context" not in skills_data


def test_pipeline_uses_one_shared_client_and_exact_generation_count() -> None:
    report = make_report(education=[])
    provider = MockProvider(
        [
            _recommendation_response(report),
            _summary_response(report),
            _bullet_response(report),
            _skills_response(report),
        ]
    )
    pipeline, client, engine, rewriter = _pipeline(report, provider)
    result = pipeline.analyze_text("synthetic")
    assert engine.client is client
    assert rewriter.client is client
    assert len(provider.calls) == 4
    assert result["module_status"]["recommendations"]["status"] == "complete"
    assert result["module_status"]["recommendations"]["model"] == provider.model
    assert result["rewrites"]["status"] == "complete"
    assert result["module_status"]["rewrites"]["model"] == provider.model


def test_recommendation_success_is_retained_when_rewrite_times_out() -> None:
    report = make_report(education=[])
    provider = MockProvider(
        [_recommendation_response(report), AIProviderTimeout("rewrite timeout")]
    )
    pipeline, *_ = _pipeline(report, provider)
    result = pipeline.analyze_text("synthetic")
    assert result["module_status"]["recommendations"]["status"] == "complete"
    assert result["rewrites"]["status"] == "partial"
    assert result["rewrites"]["summary"]["status"] == "unavailable"
    assert result["rewrites"]["summary"]["improved"] is None


def test_recommendation_timeout_allows_one_safe_rewrite_after_completion() -> None:
    report = make_report(education=[])
    provider = MockProvider(
        [AIProviderTimeout("recommendation timeout"), _summary_response(report)]
    )
    client = AIClient(provider, retries=0)
    engine = RecommendationEngine(provider, client=client, retries=0)
    rewriter = ResumeRewriter(
        provider,
        client=client,
        retries=0,
        sections=("summary",),
    )
    before = deepcopy(report.to_json_dict())
    recommendation = engine.recommend(report)
    rewrite = rewriter.rewrite(report)
    assert recommendation.source == "fallback"
    assert rewrite.status == "complete"
    assert len(provider.calls) == 2
    assert report.to_json_dict() == before


def test_internal_canonical_extraction_has_no_migration_warning() -> None:
    config = PipelineConfig(
        enable_ocr=False,
        enable_recommendations=False,
        enable_rewrites=False,
        ai_provider="none",
    )
    result = ResumePipeline(config).analyze_text(
        "Jane Example\nSummary\nPython engineer\nSkills\nPython",
        document_name="synthetic.txt",
    )
    assert not [warning for warning in result["warnings"] if warning["stage"] == "migration"]


def test_warmup_is_disabled_by_default_in_automated_pipeline(monkeypatch) -> None:
    from resume_analyzer.pipeline import orchestrator

    class WarmMock(MockProvider):
        def __init__(self):
            super().__init__("{}")
            self.warmups = 0

        def warm_up(self, *, timeout_seconds):
            del timeout_seconds
            self.warmups += 1

    provider = WarmMock()
    monkeypatch.setattr(orchestrator, "build_provider", lambda *_args, **_kwargs: provider)
    config = PipelineConfig(
        enable_ocr=False,
        enable_recommendations=False,
        enable_rewrites=True,
        rewrite_sections=("summary",),
        ai_provider="ollama",
        ai_model="synthetic",
    )
    ResumePipeline(config).analyze_text("Jane Example\nSummary\nPython engineer\nSkills\nPython")
    assert provider.warmups == 0
