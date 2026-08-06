from __future__ import annotations

import re

import pytest

from resume_analyzer.extraction.data_quality import CanonicalDataQualityAnalyzer
from resume_analyzer.extraction.evidence_coherence import EvidenceCoherenceValidator
from resume_analyzer.extraction.section_extractor import SectionExtractor
from resume_analyzer.extraction.structured_entities import StructuredEntityAssembler
from resume_analyzer.rewriting.summary import SummaryGenerator
from resume_analyzer.schema_migration import SchemaMigrator
from resume_analyzer.target_roles.config import ScoringConfig
from resume_analyzer.target_roles.normalizer import SkillAliasResolver
from resume_analyzer.target_roles.pipeline_adapter import PipelineAdapter
from resume_analyzer.target_roles.role_catalog import RoleCatalog
from resume_analyzer.target_roles.role_scorer import LexicalRoleScorer
from resume_analyzer.terminology import canonical_technology


def _block(
    block_id: str,
    text: str,
    x0: float,
    top: float,
    x1: float = 560.0,
    bottom: float | None = None,
    *,
    bold: bool = False,
    bullet: bool = False,
    section: str = "single",
) -> dict:
    return {
        "id": block_id,
        "page": 1,
        "text": text,
        "bbox": {
            "x0": x0,
            "top": top,
            "x1": x1,
            "bottom": bottom if bottom is not None else top + 12.0,
        },
        "column": "single",
        "order": 0,
        "engine": "pymupdf",
        "block_type": "line",
        "zone_id": f"zone-{section}",
        "zone_kind": "single",
        "row_id": block_id,
        "font_size": 11.0,
        "font_weight": "bold" if bold else "normal",
        "font_style": "normal",
        "alignment": "left",
        "rotation": 0.0,
        "bullet_marker": "•" if bullet else None,
        "heading_probability": 0.0,
        "neighbors": {},
    }


def _with_continuation(first: dict, second: dict) -> None:
    first["neighbors"] = {"likely_continuation": [second["id"]]}


def _assembler(section: str, blocks: list[dict]) -> StructuredEntityAssembler:
    for index, block in enumerate(blocks):
        block["order"] = index
    return StructuredEntityAssembler(
        layout_blocks=blocks,
        sections={
            "sections": {
                section: {
                    "heading": blocks[0]["text"],
                    "block_ids": [block["id"] for block in blocks],
                }
            }
        },
    )


def _experience_blocks(company: str | None = "Example Research GmbH") -> list[dict]:
    blocks = [
        _block("exp-heading", "EXPERIENCE", 20, 20),
        _block("role", "Machine Learning Engineer", 20, 50),
    ]
    if company is not None:
        blocks.append(_block("company", company, 20, 63))
    blocks.extend(
        [
            _block("bullet-a", "Built an intelligent business intelligence", 42, 76),
            _block("bullet-b", "platform for natural-language analytics.", 42, 89),
            _block("bullet-c", "Designed the backend API.", 42, 102),
            _block("bullet-d", "Designed the React frontend.", 42, 115),
        ]
    )
    _with_continuation(blocks[-4], blocks[-3])
    return blocks


def test_company_requires_coherent_organization_evidence() -> None:
    blocks = _experience_blocks("Analytics Platform")
    blocks.append(_block("kpi-bullet", "Tracked KPIs for reporting.", 42, 128))
    result = _assembler("experience", blocks).experience({})

    assert result["experiences"][0]["company"] is None
    assert all(item["company"] != "KPIs" for item in result["experiences"])


def test_structurally_supported_acronym_company_is_allowed() -> None:
    result = _assembler("experience", _experience_blocks("KPI Solutions GmbH")).experience({})

    assert result["experiences"][0]["company"] == "KPI Solutions GmbH"


def test_missing_company_remains_null() -> None:
    result = _assembler("experience", _experience_blocks(None)).experience({})
    assert result["experiences"][0]["company"] is None


def test_wrapped_responsibility_joins_without_terminal_delimiter() -> None:
    item = _assembler("experience", _experience_blocks()).experience({})["experiences"][0]

    assert item["responsibilities"][0] == (
        "Built an intelligent business intelligence " "platform for natural-language analytics."
    )


def test_complete_independent_responsibilities_do_not_overjoin() -> None:
    item = _assembler("experience", _experience_blocks()).experience({})["experiences"][0]

    assert item["responsibilities"][-2:] == [
        "Designed the backend API.",
        "Designed the React frontend.",
    ]


def test_arabic_wrapped_responsibility_uses_layout_continuation() -> None:
    blocks = [
        _block("h", "الخبرة", 20, 20),
        _block("r", "مهندسة برمجيات", 20, 50),
        _block("c", "شركة الحلول الرقمية", 20, 63),
        _block("a", "طورت منصة تحليل بيانات", 42, 76),
        _block("b", "تدعم التقارير باللغة العربية.", 42, 89),
    ]
    _with_continuation(blocks[-2], blocks[-1])

    item = _assembler("experience", blocks).experience({})["experiences"][0]
    assert item["responsibilities"] == ["طورت منصة تحليل بيانات تدعم التقارير باللغة العربية."]


def test_company_before_title_and_separate_bullet_markers_remain_local() -> None:
    blocks = [
        _block("h", "EXPERIENCE", 20, 20),
        _block("company", "Northwind Retail Group", 20, 50, bold=True),
        _block("location", "Example City, Canada", 340, 50),
        _block("title", "Sales Associate, Retail Store (Co-op)", 20, 63),
        _block("date", "2021 - 2023", 340, 63),
        _block("marker-a", "•", 42, 80, bullet=True),
        _block("body-a", "Improved customer response", 60, 80),
        _block("wrap-a", "times through a new intake workflow.", 60, 93),
        _block("marker-b", "•", 42, 106, bullet=True),
        _block("body-b", "Maintained accurate daily records.", 60, 106),
    ]
    _with_continuation(blocks[6], blocks[7])
    item = _assembler("experience", blocks).experience({})["experiences"][0]

    assert item["job_title"] == "Sales Associate"
    assert item["company"] == "Northwind Retail Group"
    assert item["location"] == "Example City, Canada"
    assert item["employment_type"] == "Co-op"
    assert item["responsibilities"] == [
        "Improved customer response times through a new intake workflow.",
        "Maintained accurate daily records.",
    ]


def _project_blocks() -> list[dict]:
    blocks = [
        _block("projects-heading", "PROJECTS", 20, 20),
        _block("title-a", "Analytics Assistant", 52, 50),
        _block("desc-a", "Built a natural-language analytics assistant.", 30, 63),
        _block(
            "tech-a",
            "Technologies: Python, PostgreSQL, Docker, REST APIs,",
            30,
            76,
        ),
        _block("tech-tail", "Metabase.", 30, 89),
        _block("title-b", "Image Restoration Suite", 52, 112),
        _block("desc-b", "Developed an image restoration model.", 30, 125),
        _block("tech-b", "Technologies: PyTorch, GANs, U-Net, OpenCV.", 30, 138),
    ]
    _with_continuation(blocks[3], blocks[4])
    return blocks


def test_tail_technology_stays_with_previous_project() -> None:
    projects = _assembler("projects", _project_blocks()).projects({})["projects"]

    assert [item["name"] for item in projects] == [
        "Analytics Assistant",
        "Image Restoration Suite",
    ]
    assert "Metabase" in projects[0]["technologies"]


def test_project_descriptions_retain_entry_boundaries() -> None:
    projects = _assembler("projects", _project_blocks()).projects({})["projects"]
    assert "restoration" not in projects[0]["description"].casefold()
    assert "restoration" in projects[1]["description"].casefold()


def test_valid_technology_named_project_requires_header_evidence() -> None:
    blocks = [
        _block("h", "PROJECTS", 20, 20),
        _block("title", "Metabase", 40, 50, bold=True),
        _block("desc", "Built a governed analytics migration.", 20, 63),
    ]
    projects = _assembler("projects", blocks).projects({})["projects"]
    assert [item["name"] for item in projects] == ["Metabase"]


def test_project_role_line_does_not_become_phantom_project() -> None:
    blocks = [
        _block("h", "PROJECTS", 20, 20),
        _block("title", "Research Segmentation Challenge", 20, 50, bold=True),
        _block("role", "Participant", 30, 76),
        _block("desc", "Completed a medical-image segmentation challenge.", 30, 89),
    ]
    projects = _assembler("projects", blocks).projects({})["projects"]

    assert len(projects) == 1
    assert projects[0]["role"] == "Participant"


def test_sentence_like_project_fragment_does_not_start_an_entry() -> None:
    blocks = [
        _block("h", "PROJECTS", 20, 20),
        _block("title", "Customer Portal", 20, 50, bold=True),
        _block("desc", "Built a customer support portal.", 20, 63),
        _block("fragment", "Worked on a platform that helps users", 20, 86),
        _block("fragment-wrap", "with several routine tasks.", 20, 99),
    ]
    projects = _assembler("projects", blocks).projects({})["projects"]

    assert [item["name"] for item in projects] == ["Customer Portal"]


def test_dedicated_skill_lists_recover_and_deduplicate_terms() -> None:
    blocks = [
        _block("h", "TECHNICAL SKILLS", 20, 20),
        _block(
            "ai",
            "Artificial Intelligence: Machine Learning, Deep Learning, RAG, AI Agents",
            20,
            50,
        ),
        _block("cv", "Computer Vision: CNN, U-Net, OpenCV, PyTorch", 20, 63),
        _block("data", "Databases & Streaming: SQL, PostgreSQL, Kafka", 20, 76),
        _block("tools", "Programming & Tools: Python, Docker, PyTorch", 20, 89),
    ]
    skills = _assembler("skills", blocks).skills({})["all_skills"]
    values = [item["value"] for item in skills]

    assert {
        "Artificial Intelligence",
        "Machine Learning",
        "Deep Learning",
        "RAG",
        "AI Agents",
        "Computer Vision",
        "CNN",
        "U-Net",
        "OpenCV",
        "PyTorch",
        "SQL",
        "PostgreSQL",
        "Kafka",
        "Python",
        "Docker",
    }.issubset(values)
    assert values.count("PyTorch") == 1


def test_generic_prose_does_not_inflate_skills() -> None:
    blocks = [
        _block("h", "SKILLS", 20, 20),
        _block("prose", "Helped teams deliver various things for clients.", 20, 50),
    ]
    assert _assembler("skills", blocks).skills({"all_skills": []}) == {"all_skills": []}


@pytest.mark.parametrize(
    ("raw", "display"),
    [
        ("Llms", "LLMs"),
        ("Rag", "RAG"),
        ("Clickhouse", "ClickHouse"),
        ("Rest Apis", "REST APIs"),
        ("Pytorch", "PyTorch"),
        ("Gans", "GANs"),
        ("U-net", "U-Net"),
        ("Patchgan", "PatchGAN"),
        ("Opencv.", "OpenCV"),
        ("Tensorflow", "TensorFlow"),
        ("Bilstm", "BiLSTM"),
        ("Segresnet.", "SegResNet"),
    ],
)
def test_professional_technology_display(raw: str, display: str) -> None:
    assert canonical_technology(raw).display == display


def test_unknown_technology_spelling_is_preserved() -> None:
    term = canonical_technology("QuantumFluxDB.")
    assert term.display == "QuantumFluxDB"
    assert term.known is False


def _report_payload(
    *,
    blocks: list[dict],
    sections: dict,
    experience: dict | None = None,
    projects: dict | None = None,
    skills: dict | None = None,
) -> dict:
    return {
        "success": True,
        "file": {"name": "anonymous.pdf", "extension": ".pdf"},
        "text_extraction": {
            "success": True,
            "pages": 1,
            "words": 80,
            "chars": 600,
            "quality_score": 95,
            "layout": "single_column",
            "reading_order": "top_to_bottom",
            "engine": "pymupdf",
            "raw_layout_blocks": blocks,
            "page_layouts": [
                {
                    "page": 1,
                    "width": 600,
                    "height": 800,
                    "layout": "single_column",
                    "reading_order": "top_to_bottom",
                    "confidence": 0.95,
                    "engine": "pymupdf",
                    "block_ids": [block["id"] for block in blocks],
                }
            ],
        },
        "sections": {"sections": sections},
        "experience": experience or {},
        "projects": projects or {},
        "skills": skills or {},
    }


def test_field_evidence_chains_reach_every_contributing_block() -> None:
    exp_blocks = _experience_blocks()
    project_blocks = _project_blocks()
    skill_blocks = [
        _block("skills-h", "SKILLS", 20, 170, section="skills"),
        _block("skills-v", "AI: PyTorch", 20, 190, section="skills"),
    ]
    blocks = [*exp_blocks, *project_blocks, *skill_blocks]
    experience = _assembler("experience", exp_blocks).experience({})
    projects = _assembler("projects", project_blocks).projects({})
    skills = _assembler("skills", skill_blocks).skills({})
    sections = {
        "experience": {
            "heading": "EXPERIENCE",
            "block_ids": [block["id"] for block in exp_blocks],
            "pages": [1],
            "columns": ["single"],
            "zones": ["zone-single"],
        },
        "projects": {
            "heading": "PROJECTS",
            "block_ids": [block["id"] for block in project_blocks],
            "pages": [1],
            "columns": ["single"],
            "zones": ["zone-single"],
        },
        "skills": {
            "heading": "SKILLS",
            "block_ids": [block["id"] for block in skill_blocks],
            "pages": [1],
            "columns": ["single"],
            "zones": ["zone-skills"],
        },
    }
    report = (
        SchemaMigrator()
        .from_extraction_modules(
            _report_payload(
                blocks=blocks,
                sections=sections,
                experience=experience,
                projects=projects,
                skills=skills,
            )
        )
        .report
    )
    evidence = {item.id: item for item in report.evidence}

    bullet_ids = report.entities.experience[0].field_evidence_ids["responsibilities[0]"]
    bullet_parents = {
        parent_id
        for evidence_id in bullet_ids
        for parent_id in evidence[evidence_id].parent_evidence_ids
    }
    assert {evidence[item].source.block_id for item in bullet_parents} == {
        "bullet-a",
        "bullet-b",
    }
    description_ids = report.entities.projects[0].field_evidence_ids["description"]
    assert all(evidence[item].parent_evidence_ids for item in description_ids)
    skill_id = report.entities.skills[0].field_evidence_ids["value"][0]
    assert evidence[skill_id].parent_evidence_ids


def test_wrong_section_source_cannot_validate_company() -> None:
    blocks = [
        _block("exp-title", "Platform Engineer", 20, 50, section="experience"),
        _block("summary-token", "SQL", 20, 100, section="summary"),
    ]
    experience = {
        "experiences": [
            {
                "job_title": "Platform Engineer",
                "company": "SQL",
                "confidence": 0.8,
                "source_block_ids": ["exp-title", "summary-token"],
                "field_source_block_ids": {
                    "job_title": ["exp-title"],
                    "company": ["summary-token"],
                },
            }
        ]
    }
    sections = {
        "experience": {
            "heading": "EXPERIENCE",
            "block_ids": ["exp-title"],
            "pages": [1],
            "columns": ["single"],
            "zones": ["zone-experience"],
        },
        "summary": {
            "heading": "SUMMARY",
            "block_ids": ["summary-token"],
            "pages": [1],
            "columns": ["single"],
            "zones": ["zone-summary"],
        },
    }
    report = (
        SchemaMigrator()
        .from_extraction_modules(
            _report_payload(blocks=blocks, sections=sections, experience=experience)
        )
        .report
    )

    assert "evidence_section_mismatch" in {
        item.code for item in EvidenceCoherenceValidator().validate(report)
    }


def test_summary_continuation_is_not_promoted_to_heading() -> None:
    blocks = [
        _block("summary-h", "SUMMARY", 20, 20),
        _block("summary-a", "Engineer integrating intelligent solutions with software", 20, 50),
        _block("summary-b", "applications.", 20, 63),
        _block("projects-h", "PROJECTS", 20, 90),
        _block("project", "Forecasting Suite", 20, 110),
    ]
    _with_continuation(blocks[1], blocks[2])
    blocks[0]["heading_probability"] = 0.95
    blocks[3]["heading_probability"] = 0.95
    result = SectionExtractor().extract_sections(
        "\n".join(block["text"] for block in blocks),
        layout_blocks=blocks,
        page_layouts=[
            {
                "page": 1,
                "layout": "single_column",
                "reading_order": "top_to_bottom",
                "confidence": 0.95,
                "block_ids": [block["id"] for block in blocks],
            }
        ],
    )

    assert "applications." in result["sections"]["summary"]["content"]
    assert result["sections"]["programs"]["content"] == ""


def _role_score(role_id: str, skills: list[str]):
    aliases = SkillAliasResolver.from_json()
    catalog = RoleCatalog.load()
    scorer = LexicalRoleScorer(catalog, aliases, ScoringConfig())
    profile = PipelineAdapter(aliases).adapt({"skills": skills})
    return scorer.score(profile, catalog.get(role_id))


@pytest.mark.parametrize(
    ("role_id", "skills"),
    [
        (
            "ai_engineer",
            ["Artificial Intelligence", "Python", "RAG", "LLMs", "Machine Learning"],
        ),
        ("backend_engineer", ["Python", "REST APIs", "SQL", "PostgreSQL"]),
        ("devops_engineer", ["Docker", "Kubernetes", "CI/CD", "Linux"]),
        (
            "computer_vision_engineer",
            ["Computer Vision", "Python", "Deep Learning", "OpenCV", "CNN"],
        ),
    ],
)
def test_supported_skills_contribute_to_target_roles(
    role_id: str,
    skills: list[str],
) -> None:
    score = _role_score(role_id, skills)
    assert dict(score.score_breakdown)["skills"] > 0
    assert score.confidence == pytest.approx(sum(dict(score.score_breakdown).values()))


def test_unrelated_skills_do_not_inflate_ai_role() -> None:
    score = _role_score("ai_engineer", ["Excel", "Accounting", "Customer Service"])
    assert dict(score.score_breakdown)["skills"] == 0


def test_quality_detects_suspicious_company_and_technology_title() -> None:
    blocks = [
        _block("exp-title", "Data Engineer", 20, 20, section="experience"),
        _block("exp-company", "SQL", 20, 33, section="experience"),
        _block("projects-h", "PROJECTS", 20, 80, section="projects"),
        _block("stack", "Technologies: Python,", 30, 100, section="projects"),
        _block("tail", "Kafka", 30, 113, section="projects"),
        _block("desc", "Developed a forecasting workflow.", 30, 126, section="projects"),
    ]
    experience = {
        "experiences": [
            {
                "job_title": "Data Engineer",
                "company": "SQL",
                "confidence": 0.8,
                "source_block_ids": ["exp-title", "exp-company"],
                "field_source_block_ids": {
                    "job_title": ["exp-title"],
                    "company": ["exp-company"],
                },
            }
        ]
    }
    projects = {
        "projects": [
            {
                "name": "Kafka",
                "description": "Developed a forecasting workflow.",
                "confidence": 0.7,
                "source_block_ids": ["tail", "desc"],
                "field_source_block_ids": {
                    "name": ["tail"],
                    "description": ["desc"],
                },
            }
        ]
    }
    sections = {
        "experience": {
            "heading": "EXPERIENCE",
            "block_ids": ["exp-title", "exp-company"],
            "pages": [1],
        },
        "projects": {
            "heading": "PROJECTS",
            "block_ids": ["projects-h", "stack", "tail", "desc"],
            "pages": [1],
        },
    }
    report = (
        SchemaMigrator()
        .from_extraction_modules(
            _report_payload(
                blocks=blocks,
                sections=sections,
                experience=experience,
                projects=projects,
            )
        )
        .report
    )
    quality = CanonicalDataQualityAnalyzer().analyze(report)
    codes = {item.code for item in quality.issues}

    assert {"suspicious_company_type", "technology_only_project_title"} <= codes
    assert quality.dimensions.experience_integrity < 100
    assert quality.dimensions.project_integrity < 100
    assert quality.dimensions.entity_coherence < 100


def test_summary_quality_gate_rejects_verbose_third_person() -> None:
    message = SummaryGenerator._quality_gate(
        "Artificial Intelligence Engineer with hands-on model delivery experience.",
        "An Artificial Intelligence Engineer possesses hands-on model delivery experience.",
    )
    assert message is not None


def test_summary_quality_gate_allows_supported_material_improvement() -> None:
    message = SummaryGenerator._quality_gate(
        "Software engineer.",
        "Software engineer building reliable Python APIs for financial systems.",
    )
    assert message is None


def test_anonymized_regression_contains_no_private_identity_or_path() -> None:
    source = __file__
    text = open(source, encoding="utf-8").read()
    assert not re.search(r"C:\\Users\\[^\\]+\\Downloads", text)
    assert not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
