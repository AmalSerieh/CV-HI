from __future__ import annotations

import json
from pathlib import Path

import pytest

from resume_analyzer import PipelineConfig, ResumePipeline
from resume_analyzer.ai.providers import AIProviderTimeout, MockProvider
from resume_analyzer.extraction.contact import ContactResolver
from resume_analyzer.extraction.data_quality import CanonicalDataQualityAnalyzer
from resume_analyzer.extraction.education_extractor import EducationExtractor
from resume_analyzer.extraction.experience_extractor import ExperienceExtractor
from resume_analyzer.extraction.projects_extractor import ProjectsExtractor
from resume_analyzer.recommendations import RecommendationEngine
from resume_analyzer.recommendations.parser import ResponseParser
from resume_analyzer.recommendations.prompts import PromptBuilder
from resume_analyzer.rewriting import ResumeRewriter
from resume_analyzer.rewriting.contracts import BulletProposal, SkillsProposal, SummaryProposal
from resume_analyzer.schemas import PipelineReport
from tests.report_fixtures import make_report

FIXTURE = Path("tests/fixtures/anonymized_real_resume_structure.txt")


@pytest.fixture(scope="module")
def anonymized_report() -> dict:
    config = PipelineConfig(
        enable_ocr=False,
        enable_recommendations=False,
        enable_rewrites=False,
        use_spacy=False,
        use_sbert=False,
        allow_model_download=False,
    )
    return ResumePipeline(config).analyze_text(
        FIXTURE.read_text(encoding="utf-8"),
        document_name="anonymized-structure.txt",
    )


def test_anonymized_project_segmentation_has_three_real_projects(anonymized_report) -> None:
    projects = anonymized_report["entities"]["projects"]
    assert [item["name"] for item in projects] == [
        "Northstar Marketplace Platform",
        "Insight Agentic BI Platform",
        "AI-Powered Tools & Automation Projects",
    ]
    assert [item["role"] for item in projects] == [
        "Backend Developer",
        "AI Engineer",
        "Software Engineer",
    ]
    assert projects[0]["start_date"] == "Jan 2024"
    assert projects[0]["end_date"] == "Present"
    assert "commercial operations." in projects[0]["description"]
    assert "analytics dashboards and reporting workflows." in projects[0]["description"]
    assert "Implementing analytics and dashboard features" in projects[1]["description"]
    assert all(item["description"] for item in projects)
    assert not any(item["name"] in {"Jan", "Mar"} for item in projects)


def test_arabic_project_header_and_continuation_are_preserved() -> None:
    extractor = ProjectsExtractor(use_spacy=False, use_sbert=False, allow_model_download=False)
    result = extractor.extract(
        {
            "sections": {
                "projects": {
                    "content": (
                        "منصة وصل | مطور برمجيات\n2024\n"
                        "طورت منصة تجارة إلكترونية باستخدام Python و FastAPI.\n"
                        "إعداد لوحات متابعة للعمليات."
                    )
                }
            }
        }
    )
    assert len(result["projects"]) == 1
    assert result["projects"][0]["title"] == "منصة وصل"
    assert "إعداد لوحات" in result["projects"][0]["description"]


def test_unlabeled_structured_project_fallback_requires_project_evidence() -> None:
    extractor = ProjectsExtractor(
        use_spacy=False,
        use_sbert=False,
        allow_model_download=False,
    )
    result = extractor.extract(
        {
            "text": (
                "PROFESSIONAL SUMMARY\n"
                "Software engineer experienced in delivery work.\n"
                "Inventory Management Platform | Backend Developer\n"
                "2024\n"
                "Built inventory APIs using Python and PostgreSQL."
            ),
            "sections": {"summary": {"content": "Software engineer experienced in delivery work."}},
        }
    )

    assert [item["title"] for item in result["projects"]] == ["Inventory Management Platform"]


@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("System", "QuickBooks"),
        ("Application", "Microsoft Access"),
    ],
)
def test_skill_labels_do_not_become_fallback_projects(
    label: str,
    value: str,
) -> None:
    extractor = ProjectsExtractor(
        use_spacy=False,
        use_sbert=False,
        allow_model_download=False,
    )
    text = (
        "SKILLS\n"
        f"{label}: {value}\n"
        "Microsoft Excel\n"
        "EXPERIENCE\n"
        "Accountant | Example Firm\n"
        "2022 - Present\n"
        "Created monthly reports using Excel."
    )

    result = extractor.extract(
        {
            "text": text,
            "sections": {
                "skills": {"content": f"{label}: {value}\nMicrosoft Excel"},
                "experience": {
                    "content": (
                        "Accountant | Example Firm\n"
                        "2022 - Present\n"
                        "Created monthly reports using Excel."
                    )
                },
            },
        }
    )

    assert result["projects"] == []


def test_repository_link_in_contact_header_does_not_become_project() -> None:
    extractor = ProjectsExtractor(
        use_spacy=False,
        use_sbert=False,
        allow_model_download=False,
    )
    text = (
        "JANE DOE\n"
        "https://github.com/jane-example/resume\n"
        "SUMMARY\n"
        "Software engineer building reliable services.\n"
        "EXPERIENCE\n"
        "Software Engineer | Example Firm\n"
        "2022 - Present\n"
        "Built internal APIs using Python."
    )

    result = extractor.extract(
        {
            "text": text,
            "sections": {
                "summary": {"content": "Software engineer building reliable services."},
                "experience": {
                    "content": (
                        "Software Engineer | Example Firm\n"
                        "2022 - Present\n"
                        "Built internal APIs using Python."
                    )
                },
            },
        }
    )

    assert result["projects"] == []


@pytest.mark.parametrize(
    "role",
    ["Project Manager", "Application Developer", "System Analyst"],
)
def test_project_like_job_titles_do_not_become_projects(role: str) -> None:
    extractor = ProjectsExtractor(
        use_spacy=False,
        use_sbert=False,
        allow_model_download=False,
    )
    experience = (
        f"{role} | Example Corp\n"
        "2022 - Present\n"
        "Developed operational workflows using Jira and Excel."
    )

    result = extractor.extract(
        {
            "text": f"EXPERIENCE\n{experience}",
            "sections": {"experience": {"content": experience}},
        }
    )

    assert result["projects"] == []


def test_key_projects_inside_experience_remain_discoverable() -> None:
    extractor = ProjectsExtractor(
        use_spacy=False,
        use_sbert=False,
        allow_model_download=False,
    )
    experience = (
        "Software Engineer | Example Firm\n"
        "2022 - Present\n"
        "Key Projects: Inventory Platform | Backend Developer\n"
        "2024\n"
        "Built inventory APIs using Python and PostgreSQL."
    )

    result = extractor.extract(
        {
            "text": f"EXPERIENCE\n{experience}",
            "sections": {"experience": {"content": experience}},
        }
    )

    assert [item["title"] for item in result["projects"]] == ["Inventory Platform"]


def test_experience_wraps_deduplicate_and_preserve_technologies(anonymized_report) -> None:
    first = anonymized_report["entities"]["experience"][0]
    assert first["responsibilities"] == [
        "Designed event-driven services with Python, FastAPI and PostgreSQL.",
        "Coordinated containerized deployments and improved release reliability.",
    ]
    assert set(first["technologies"]) >= {"Python", "FastAPI", "PostgreSQL"}


def test_company_first_wrapped_responsibilities_keep_every_action() -> None:
    fixture = json.loads(
        Path("tests/fixtures/sales_current_output.json").read_text(encoding="utf-8")
    )
    experience_text = fixture["sections"]["sections"]["experience"]["content"]
    result = ExperienceExtractor(
        use_spacy=False,
        use_sbert=False,
        allow_model_download=False,
    ).extract({"sections": {"experience": {"content": experience_text}}})

    assert len(result["experiences"]) == 8
    first = result["experiences"][0]["responsibilities"]
    assert len(first) == 5
    assert [item.split(maxsplit=1)[0] for item in first] == [
        "Hired",
        "Generated",
        "Produced",
        "Provided",
        "Negotiated",
    ]
    assert first[0].endswith(
        "developed strategies to optimize revenue and satisfy corporate sales goals."
    )
    assert first[-1].endswith("garner comprehensive sales and customer service support.")


def test_arabic_wrapped_bullet_joins_at_conjunction() -> None:
    extractor = ExperienceExtractor(use_spacy=False, use_sbert=False, allow_model_download=False)
    text = "• نسقت عمليات النشر و\nحسنت موثوقية الإصدارات.\n• طورت واجهات Python."
    assert extractor._extract_responsibilities_from_bullets(text) == [
        "نسقت عمليات النشر و حسنت موثوقية الإصدارات.",
        "طورت واجهات Python.",
    ]


def test_skill_precision_aliases_and_categories(anonymized_report) -> None:
    skills = anonymized_report["entities"]["skills"]
    values = {item["value"] for item in skills}
    assert not values & {
        "Backend &",
        "AIpowered automation",
        "planning",
        "operations",
        "account management",
        "Presentation",
        "Programming",
    }
    assert {"PostgreSQL", "Speech-to-Text", "Prompt Engineering"} <= values
    assert "AI-powered automation" in values
    categories = {item["value"]: item["category"] for item in skills}
    assert categories["React"] == "frontend"
    assert categories["FastAPI"] == "backend"
    assert categories["PostgreSQL"] == "databases"
    assert categories["Git"] == "tools"


def test_wrapped_coursework_and_combined_contact_header_are_preserved(
    anonymized_report,
) -> None:
    education = anonymized_report["entities"]["education"][0]
    assert "Software Testing, UML, and Design Patterns" in education["description"]
    contact = anonymized_report["entities"]["contact"]
    assert contact["location"] == "Amman, Jordan"
    assert contact["portfolio"] is None


def test_generic_business_skills_require_explicit_category() -> None:
    from resume_analyzer.extraction.skills_extractor import SkillsExtractor

    extractor = SkillsExtractor(use_spacy=False, use_sbert=False, allow_model_download=False)
    result = extractor.extract(
        {
            "sections": {
                "skills": {
                    "content": (
                        "Business/Domain Knowledge: Planning, Operations, Account Management\n"
                        "Soft Skills: Presentation Skills"
                    )
                }
            }
        }
    )
    categories = result["categorized_skills"]
    assert set(categories["business_domain"]) == {"Planning", "Operations", "Account Management"}
    assert result["soft_skills"] == ["Presentation Skills"]


def test_aipowered_alias_requires_a_dedicated_skills_item() -> None:
    from resume_analyzer.extraction.skills_extractor import SkillsExtractor

    extractor = SkillsExtractor(use_spacy=False, use_sbert=False, allow_model_download=False)
    dedicated = extractor.extract(
        {"sections": {"skills": {"content": "AI & Data: AIpowered automation, Prompt Engineering"}}}
    )
    assert "AI-powered automation" in dedicated["hard_skills"]

    prose_only = extractor.extract(
        {
            "sections": {
                "experience": {
                    "content": "Discussed AIpowered automation during planning meetings."
                }
            }
        }
    )
    assert "AI-powered automation" not in prose_only["hard_skills"]

    access_control = extractor.extract(
        {
            "sections": {
                "experience": {"content": "Implemented role-based access control for the API."}
            }
        }
    )
    assert "Microsoft Access" not in access_control["hard_skills"]


def test_education_field_specialization_and_unrelated_ai(anonymized_report) -> None:
    education = anonymized_report["entities"]["education"][0]
    assert education["degree"] == "Bachelor"
    assert education["field"] == "Informatics Engineering"
    assert education["specialization"] == "Software Engineering"
    assert education["institution"] == "Example Technical University"
    extractor = EducationExtractor(use_spacy=False)
    result = extractor.extract(
        {
            "text": "Summary\nArtificial Intelligence engineer\nEducation\n"
            "Bachelor's Degree in Informatics Engineering - Software Engineering\n"
            "Example Technical University\n2016 - 2021",
            "sections": {
                "education": {
                    "content": (
                        "Bachelor's Degree in Informatics Engineering - Software Engineering\n"
                        "Example Technical University\n2016 - 2021"
                    )
                }
            },
        }
    )
    assert result["education"][0]["field"] == "Informatics Engineering"
    assert result["education"][0]["specialization"] == "Software Engineering"


def test_arabic_education_entry() -> None:
    result = EducationExtractor(use_spacy=False).extract(
        {
            "sections": {
                "education": {
                    "content": (
                        "بكالوريوس في هندسة المعلوماتية - هندسة البرمجيات\n"
                        "جامعة المثال التقنية\n2018 - 2022"
                    )
                }
            }
        }
    )
    assert result["education"][0]["degree"] == "Bachelor"
    assert result["education"][0]["field"] == "Informatics Engineering"
    assert result["education"][0]["specialization"] == "Software Engineering"
    assert result["education"][0]["institution"] == "جامعة المثال التقنية"


def test_header_title_and_pdf_annotation_links() -> None:
    text = (
        "Jordan Example\nPython Backend Engineer\nAmman, Jordan\n"
        "jordan@example.test | +1 555-010-0142\nLinkedIn | GitHub | Portfolio"
    )
    result = ContactResolver().resolve(
        text=text,
        file_links=[
            "https://linkedin.com/in/jordan-example",
            "https://github.com/jordan-example",
            "https://jordan-example.dev/projects",
        ],
    )
    assert result["job_title"] == "Python Backend Engineer"
    assert result["location"] == "Amman, Jordan"
    assert result["linkedin"].startswith("https://linkedin.com/")
    assert result["github"].startswith("https://github.com/")
    assert result["portfolio"] == "https://jordan-example.dev/projects"


def test_technology_name_is_not_treated_as_a_portfolio_url() -> None:
    result = ContactResolver().resolve(
        text=(
            "Jordan Example\nPython Backend Engineer\n"
            "Amman,Jordan,+1 555-010-0142,jordan@example.test\n"
            "Built APIs with Node.js and role-based access control."
        )
    )
    assert result["location"] == "Amman, Jordan"
    assert result["portfolio"] is None


def test_data_quality_is_separate_from_ats_and_detects_integrity_defects() -> None:
    data = make_report().to_json_dict()
    data["entities"]["skills"][0]["value"] = "Backend &"
    data["entities"]["skills"][0]["category"] = None
    data["entities"]["experience"][0]["responsibilities"] = [
        "Designed services with Python,",
        "Maintained APIs.",
        "Maintained APIs",
    ]
    data["entities"]["projects"][0]["name"] = "Developing a platform using Python"
    data["entities"]["projects"][0]["description"] = ""
    report = PipelineReport.model_validate(data)
    ats_before = report.ats.model_dump()
    quality = CanonicalDataQualityAnalyzer().analyze(report)
    assert quality.status in {"needs_review", "poor"}
    assert quality.score < 90
    assert {item.code for item in quality.issues} >= {
        "malformed_skill_fragments",
        "truncated_experience_bullets",
        "duplicate_experience_bullets",
        "phantom_project_titles",
        "empty_project_descriptions",
    }
    assert report.ats.model_dump() == ats_before


def test_recommendation_timeout_has_no_timeout_retry_and_prompt_is_compact() -> None:
    report = make_report(education=[])
    provider = MockProvider(AIProviderTimeout("synthetic timeout"))
    engine = RecommendationEngine(
        provider,
        retries=3,
        retry_timeouts=False,
        max_output_tokens=224,
        prompt_builder=PromptBuilder(),
    )
    result = engine.recommend(report)
    assert result.source == "fallback"
    assert len(provider.calls) == 1
    request = PromptBuilder().build_request(report)
    schema = ResponseParser.response_schema(
        provider="ollama", model="gemma3:4b", evidence_ids=list(request.evidence_ids)
    )
    assert len(request.prompt) < 3_000
    assert len(request.evidence_ids) <= 16
    assert len(json.dumps(schema, separators=(",", ":"))) < 1_000
    assert "recommendations" not in schema["properties"]


def test_projection_telemetry_is_not_promoted_to_user_warnings() -> None:
    assert (
        ResumePipeline._public_recommendation_warning("recommendation_projection_skills_truncated")
        is None
    )
    assert (
        ResumePipeline._public_recommendation_warning(
            "rejected:rec-primary:optional_social_link_requires_low_severity"
        )
        is None
    )
    code, message = ResumePipeline._public_recommendation_warning(
        "ai_unavailable:AIProviderTimeout:synthetic timeout"
    )
    assert code == "AI_PROVIDER_TIMEOUT"
    assert "deterministic" in message


@pytest.mark.parametrize(
    ("section", "response", "expected_component"),
    [
        ("summary", '{"improved":"unterminated', "summary"),
        ("skills", '{"groups":[{"group":"Tools","items":["Python"', "skills_section"),
    ],
)
def test_truncated_rewrite_json_is_explicit(section, response, expected_component) -> None:
    result = ResumeRewriter(MockProvider(response), retries=0, sections=(section,)).rewrite(
        make_report()
    )
    assert result.status == "partial"
    assert result.rejected_rewrites[0].code == "MODEL_OUTPUT_TRUNCATED"
    assert result.rejected_rewrites[0].candidate is None
    assert any(
        notice.code == "MODEL_OUTPUT_TRUNCATED" and notice.component == expected_component
        for notice in result.notices
    )


def test_summary_no_op_and_rejection_never_create_proposed_text() -> None:
    report = make_report()
    evidence = [
        item.id
        for item in report.evidence
        if item.field_path.startswith(
            ("entities.summary", "entities.skills", "entities.experience", "entities.projects")
        )
    ][:16]
    response = json.dumps(
        {
            "improved": "  Python developer  building APIs . ",
            "changes": [],
            "evidence_ids": evidence,
        }
    )
    unchanged = ResumeRewriter(MockProvider(response), retries=0, sections=("summary",)).rewrite(
        report
    )
    assert unchanged.summary.status == "unchanged"
    assert unchanged.summary.improved is None
    assert unchanged.notices[0].code == "NO_MATERIAL_CHANGE"
    rejected = ResumeRewriter(MockProvider("not-json"), retries=0, sections=("summary",)).rewrite(
        report
    )
    assert rejected.summary.status == "rejected"
    assert rejected.summary.improved is None


def test_verbose_third_person_summary_rewrite_is_no_material_change() -> None:
    report = make_report(
        summary="Artificial Intelligence Engineer with hands-on model delivery experience."
    )
    evidence = [
        item.id
        for item in report.evidence
        if item.field_path.startswith(
            ("entities.summary", "entities.skills", "entities.experience", "entities.projects")
        )
    ][:16]
    response = json.dumps(
        {
            "improved": (
                "An Artificial Intelligence Engineer possesses hands-on "
                "model delivery experience."
            ),
            "changes": ["Changed the opening."],
            "evidence_ids": evidence,
        }
    )

    result = ResumeRewriter(MockProvider(response), retries=0, sections=("summary",)).rewrite(
        report
    )

    assert result.summary.status == "unchanged"
    assert result.summary.improved is None
    assert result.notices[0].code == "NO_MATERIAL_CHANGE"


def test_compact_contracts_and_operation_specific_output_budgets() -> None:
    report = make_report(summary="Python developer creating APIs.")
    summary_ids = [
        item.id
        for item in report.evidence
        if item.field_path.startswith(
            ("entities.summary", "entities.skills", "entities.experience", "entities.projects")
        )
    ][:16]
    responses = [
        json.dumps(
            {
                "improved": "Python developer building APIs.",
                "changes": ["Improved clarity."],
                "evidence_ids": summary_ids,
            }
        ),
        json.dumps(
            {
                "improved": "Developed APIs using Python.",
                "changes": ["Used a direct verb."],
                "evidence_ids": report.entities.experience[0].evidence_ids,
            }
        ),
        json.dumps(
            {
                "groups": [
                    {"group": "Programming", "items": ["Python"]},
                    {"group": "Databases", "items": ["SQL", "PostgreSQL"]},
                ],
                "removed_duplicates": [],
            }
        ),
    ]
    provider = MockProvider(responses)
    result = ResumeRewriter(
        provider,
        retries=0,
        sections=("summary", "experience", "skills"),
        max_bullets=1,
        summary_max_output_tokens=384,
        bullet_max_output_tokens=256,
        skills_max_output_tokens=768,
    ).rewrite(report)
    assert result.status == "complete"
    assert [call["max_output_tokens"] for call in provider.calls] == [384, 256, 768]
    assert set(SummaryProposal.model_json_schema()["properties"]) == {
        "improved",
        "evidence_ids",
        "changes",
    }
    assert set(BulletProposal.model_json_schema()["properties"]) == {
        "improved",
        "evidence_ids",
        "changes",
    }
    assert set(SkillsProposal.model_json_schema()["properties"]) == {"groups", "removed_duplicates"}
    assert "original" not in provider.calls[0]["response_schema"]["properties"]
    assert "used evidence ID" not in provider.calls[0]["prompt"]
    summary_schema_ids = set(
        provider.calls[0]["response_schema"]["properties"]["evidence_ids"]["items"]["enum"]
    )
    assert 1 <= len(summary_schema_ids) <= 8
    assert summary_schema_ids <= {item.id for item in report.evidence}
    assert set(
        provider.calls[1]["response_schema"]["properties"]["evidence_ids"]["items"]["enum"]
    ) == set(report.entities.experience[0].evidence_ids)


def test_bullet_prompt_does_not_expose_sibling_bullet_text() -> None:
    report = make_report(
        experience=[
            {
                "job_title": "Software Engineer",
                "company": "Example Labs",
                "responsibilities": ["Built the API.", "Maintained the deployment pipeline."],
                "technologies": ["Python"],
            }
        ]
    )
    prompt = ResumeRewriter(MockProvider("{}"), retries=0).bullet_improver.prompt_builder.bullet(
        report,
        experience_index=0,
        bullet_index=0,
        bullet_kind="responsibility",
        evidence_ids=report.entities.experience[0].evidence_ids,
        language="en",
    )
    assert "Built the API." in prompt
    assert "Maintained the deployment pipeline." not in prompt


def test_skills_rewrite_preserves_omitted_supported_items() -> None:
    report = make_report(skills=["Python", "SQL", "Docker"])
    response = json.dumps(
        {
            "groups": [{"group": "Programming", "items": ["Python", "SQL"]}],
            "removed_duplicates": [],
        }
    )
    result = ResumeRewriter(MockProvider(response), retries=0, sections=("skills",)).rewrite(report)
    assert result.skills_section.status == "improved"
    assert result.rejected_rewrites == []
    assert result.skills_section.improved_groups[-1].model_dump() == {
        "group": "Other Skills",
        "items": ["Docker"],
    }
    assert result.skills_section.requires_review is True
    assert "application preserved" in result.skills_section.warnings[0]


def test_large_skills_section_uses_bounded_deterministic_grouping() -> None:
    report = make_report(skills=[f"Supported Skill {index}" for index in range(30)])
    provider = MockProvider(AIProviderTimeout("must not be called"))
    result = ResumeRewriter(
        provider,
        retries=0,
        sections=("skills",),
        skills_ai_max_items=24,
    ).rewrite(report)
    grouped = [item for group in result.skills_section.improved_groups for item in group.items]
    assert provider.calls == []
    assert result.status == "complete"
    assert result.skills_section.method == "deterministic"
    assert grouped == [item.value for item in report.entities.skills]
    assert any(
        notice.code == "SKILLS_DETERMINISTIC_FALLBACK_APPLIED" and notice.severity == "information"
        for notice in result.notices
    )


def test_deterministic_skills_grouping_uses_specific_canonical_categories() -> None:
    expected = [
        "HTML5",
        "CSS3",
        "REST APIs",
        "ClickHouse",
        "Metabase",
        "Dagster",
        "Whisper",
        "Ollama",
        "OpenRouter",
        "LLM APIs",
        "LangChain",
        "TimesFM",
        "AI-powered automation",
        "forecasting",
        "RBAC",
        *[f"Supported Skill {index}" for index in range(10)],
    ]
    report = make_report(skills=expected)
    result = ResumeRewriter(
        MockProvider(AIProviderTimeout("must not be called")),
        retries=0,
        sections=("skills",),
        skills_ai_max_items=24,
    ).rewrite(report)
    grouped = {group.group: group.items for group in result.skills_section.improved_groups}
    assert {"HTML5", "CSS3"} <= set(grouped["Frontend"])
    assert "REST APIs" in grouped["Backend"]
    assert "ClickHouse" in grouped["Databases"]
    assert {"Metabase", "Dagster", "forecasting"} <= set(grouped["Data / Analytics"])
    assert {
        "Whisper",
        "Ollama",
        "OpenRouter",
        "LLM APIs",
        "LangChain",
        "TimesFM",
        "AI-powered automation",
    } <= set(grouped["AI / ML"])
    assert "RBAC" in grouped["Methods"]


def test_skills_timeout_falls_back_without_a_second_model_request() -> None:
    report = make_report(skills=["Python", "SQL", "Docker"])
    provider = MockProvider(AIProviderTimeout("synthetic timeout"))
    result = ResumeRewriter(
        provider,
        retries=3,
        retry_timeouts=False,
        sections=("skills",),
    ).rewrite(report)
    assert len(provider.calls) == 1
    assert result.status == "partial"
    assert result.skills_section.status == "improved"
    assert result.skills_section.method == "deterministic"
    assert result.rejected_rewrites[0].code == "AI_PROVIDER_TIMEOUT"


def _bullet_responses(report, count: int) -> list[str]:
    evidence = report.entities.experience[0].evidence_ids
    return [
        json.dumps(
            {
                "improved": f"Developed API {index} using Python.",
                "changes": ["Used a direct verb."],
                "evidence_ids": evidence,
            }
        )
        for index in range(count)
    ]


def test_bullet_limit_is_informational_and_specific_selection_is_supported() -> None:
    bullets = [f"Worked on API {index} using Python." for index in range(5)]
    report = make_report(
        experience=[
            {
                "job_title": "Software Engineer",
                "company": "Example Labs",
                "responsibilities": bullets,
                "technologies": ["Python"],
            }
        ]
    )
    capped = ResumeRewriter(
        MockProvider(_bullet_responses(report, 3)),
        retries=0,
        sections=("experience",),
        max_bullets=3,
    ).rewrite(report)
    assert capped.status == "partial"
    assert capped.warnings == []
    assert capped.bullet_stats.model_dump() == {
        "total_eligible": 5,
        "selected": 3,
        "processed": 3,
        "skipped": 2,
    }
    assert capped.notices[0].code == "BULLET_REWRITE_LIMIT_APPLIED"
    assert capped.notices[0].severity == "information"

    selected = ResumeRewriter(
        MockProvider(_bullet_responses(report, 2)),
        retries=0,
        sections=("experience",),
        bullet_selection=(1, 3),
        max_bullets=3,
    ).rewrite(report)
    assert [item.bullet_index for item in selected.experience_bullets] == [1, 3]
    assert selected.bullet_stats.selected == 2


def test_json_export_round_trip_equivalence(tmp_path) -> None:
    report = make_report()
    target = tmp_path / "canonical.json"
    ResumePipeline.export(report, target)
    assert json.loads(target.read_text(encoding="utf-8")) == report.to_json_dict()


def test_complete_pdf_pipeline_extracts_annotation_links(tmp_path) -> None:
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "anonymized-resume.pdf"
    document = fitz.open()
    page = document.new_page()
    lines = [
        "Jordan Example",
        "Python Backend Engineer",
        "Amman, Jordan",
        "jordan@example.test | +1 555-010-0142",
        "LinkedIn GitHub Portfolio",
        "SUMMARY",
        "Python backend engineer building APIs.",
        "SKILLS",
        "Python, FastAPI, PostgreSQL",
        "EXPERIENCE",
        "Software Engineer | Example Labs",
        "2022 - Present",
        "- Built APIs using Python and FastAPI.",
        "EDUCATION",
        "Bachelor's Degree in Informatics Engineering - Software Engineering",
        "Example Technical University",
        "2016 - 2021",
        "PROJECTS",
        "Northstar Platform | Backend Developer",
        "2024",
        "Built a marketplace API using Python and PostgreSQL.",
    ]
    y = 40
    for line in lines:
        page.insert_text((40, y), line, fontsize=10)
        y += 18
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(40, 105, 95, 120),
            "uri": "https://linkedin.com/in/jordan-example",
        }
    )
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(100, 105, 150, 120),
            "uri": "https://github.com/jordan-example",
        }
    )
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(155, 105, 220, 120),
            "uri": "https://jordan-example.dev/projects",
        }
    )
    document.save(path)
    document.close()

    result = ResumePipeline(
        PipelineConfig(
            enable_ocr=False,
            enable_recommendations=False,
            enable_rewrites=False,
            use_spacy=False,
            use_sbert=False,
        )
    ).analyze(str(path))
    contact = result["entities"]["contact"]
    assert contact["job_title"] == "Python Backend Engineer"
    assert contact["linkedin"].startswith("https://linkedin.com/")
    assert contact["github"].startswith("https://github.com/")
    assert contact["portfolio"] == "https://jordan-example.dev/projects"
    assert result["data_quality"]["status"] in {"good", "needs_review"}
