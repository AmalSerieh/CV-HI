from __future__ import annotations

from types import SimpleNamespace

import resume_analyzer.extraction.text_extractor as text_extractor_module
from resume_analyzer import SchemaMigrator
from resume_analyzer.extraction.contact.phone import PhoneExtractor
from resume_analyzer.extraction.data_quality import CanonicalDataQualityAnalyzer
from resume_analyzer.extraction.evidence_coherence import EvidenceCoherenceValidator
from resume_analyzer.extraction.layout_graph import build_page_graph
from resume_analyzer.extraction.section_extractor import SectionExtractor
from resume_analyzer.extraction.structured_entities import StructuredEntityAssembler
from resume_analyzer.extraction.text_extractor import TextExtractor


def _block(
    identifier: str,
    text: str,
    x0: float,
    top: float,
    x1: float,
    bottom: float,
    *,
    page: int = 1,
    font_size: float = 10.0,
    font_weight: str = "normal",
) -> dict:
    return {
        "id": identifier,
        "page": page,
        "text": text,
        "bbox": {"x0": x0, "top": top, "x1": x1, "bottom": bottom},
        "column": "unknown",
        "order": 0,
        "engine": "pymupdf",
        "block_type": "line",
        "is_repeated_header_footer": False,
        "font_size": font_size,
        "font_family": "Helvetica",
        "font_weight": font_weight,
        "font_style": "normal",
        "rotation": 0.0,
    }


def test_two_column_rows_are_not_interleaved() -> None:
    blocks = [
        _block("left-heading", "PROFILE", 20, 100, 100, 112, font_weight="bold"),
        _block("right-heading", "EXPERIENCE", 320, 100, 420, 112, font_weight="bold"),
        _block("left-body", "Left summary text", 20, 120, 180, 132),
        _block("right-title", "Software Engineer", 320, 120, 440, 132),
    ]

    plan = build_page_graph(
        blocks,
        page_width=600,
        page_height=800,
        split_x=280,
        confidence=0.9,
    )

    assert plan["reading_order"] == "column_wise"
    assert [item["id"] for item in plan["ordered_blocks"]] == [
        "left-heading",
        "left-body",
        "right-heading",
        "right-title",
    ]


def test_paraphrased_parallel_columns_remain_isolated_after_full_width_header() -> None:
    blocks = [
        _block("name", "CASEY SAMPLE", 30, 30, 330, 55, font_size=20, font_weight="bold"),
        _block("bio", "ABOUT", 30, 130, 90, 142, font_weight="bold"),
        _block("roles", "CAREER HISTORY", 330, 130, 450, 142, font_weight="bold"),
        _block("bio-text", "Product-focused professional", 30, 150, 210, 162),
        _block("role-text", "Platform Developer", 330, 150, 450, 162),
    ]

    plan = build_page_graph(
        blocks,
        page_width=600,
        page_height=800,
        split_x=280,
        confidence=0.88,
    )

    assert plan["zones"][0]["kind"] == "header"
    assert [item["id"] for item in plan["ordered_blocks"]] == [
        "name",
        "bio",
        "bio-text",
        "roles",
        "role-text",
    ]


def test_full_width_middle_zone_preserves_vertical_zone_order() -> None:
    blocks = [
        _block("left", "Left content", 20, 120, 180, 132),
        _block("right", "Right content", 320, 120, 480, 132),
        _block("wide", "EDUCATION", 20, 300, 560, 314, font_weight="bold"),
        _block("left-lower", "Degree", 20, 330, 180, 342),
        _block("right-lower", "2024", 320, 330, 380, 342),
    ]

    plan = build_page_graph(
        blocks,
        page_width=600,
        page_height=800,
        split_x=280,
        confidence=0.86,
    )

    assert [item["id"] for item in plan["ordered_blocks"]] == [
        "left",
        "right",
        "wide",
        "left-lower",
        "right-lower",
    ]
    assert [zone["kind"] for zone in plan["zones"]] == [
        "column_pair",
        "full_width",
        "column_pair",
    ]


def test_full_width_line_keeps_same_row_bullet_companion() -> None:
    blocks = [
        _block("bullet", "•", 42, 130, 48, 142),
        _block(
            "body",
            "Improved processing time by 35% across the organization",
            76,
            130,
            560,
            142,
        ),
    ]

    plan = build_page_graph(
        blocks,
        page_width=600,
        page_height=800,
        split_x=280,
        confidence=0.72,
    )

    assert [item["id"] for item in plan["ordered_blocks"]] == ["bullet", "body"]
    assert plan["zones"][0]["block_ids"] == ["bullet", "body"]


def test_same_column_grid_cells_remain_cells_instead_of_prose() -> None:
    blocks = [
        _block("skill-a", "Leadership", 20, 150, 100, 162),
        _block("skill-b", "Communication", 125, 150, 220, 162),
        _block("role", "Developer", 330, 150, 420, 162),
    ]

    plan = build_page_graph(
        blocks,
        page_width=600,
        page_height=800,
        split_x=280,
        confidence=0.9,
    )

    by_id = {item["id"]: item for item in plan["ordered_blocks"]}
    assert by_id["skill-a"]["probable_table_cell"] is True
    assert by_id["skill-b"]["probable_table_cell"] is True
    assert "skill-b" in by_id["skill-a"]["neighbors"]["same_row"]


def test_single_column_negative_case_stays_top_to_bottom() -> None:
    blocks = [
        _block("second", "Second", 40, 140, 100, 152),
        _block("first", "First", 40, 100, 100, 112),
    ]

    plan = build_page_graph(
        blocks,
        page_width=600,
        page_height=800,
        split_x=None,
        confidence=0.9,
    )

    assert plan["reading_order"] == "top_to_bottom"
    assert [item["id"] for item in plan["ordered_blocks"]] == ["first", "second"]
    assert all(item["column"] == "single" for item in plan["ordered_blocks"])


def test_template_residue_is_flagged_without_matching_ordinary_content() -> None:
    residue = _block(
        "residue",
        "Replace this text with your text here - do not remove",
        8,
        180,
        22,
        560,
    )
    residue["rotation"] = -90.0
    ordinary = _block(
        "ordinary",
        "Built a free online marketplace for local businesses",
        40,
        100,
        330,
        112,
    )

    plan = build_page_graph(
        [ordinary, residue],
        page_width=600,
        page_height=800,
        split_x=None,
        confidence=0.85,
    )
    by_id = {item["id"]: item for item in plan["ordered_blocks"]}

    assert by_id["residue"]["is_template_residue"] is True
    assert by_id["residue"]["excluded_from_entities"] is True
    assert "TEMPLATE_REMNANT_DETECTED" in by_id["residue"]["quality_flags"]
    assert by_id["ordinary"]["is_template_residue"] is False
    assert "TEMPLATE_REMNANT_DETECTED" in plan["warnings"]


def test_page_metrics_flag_small_text_and_sparse_trailing_page() -> None:
    first_blocks = [
        _block(
            f"first-{index}",
            "Substantive resume content " * 4,
            40,
            40 + index * 32,
            540,
            62 + index * 32,
            font_size=7.0,
        )
        for index in range(12)
    ]
    second_blocks = [_block("trailing", "Additional note", 40, 50, 150, 60, page=2, font_size=9.0)]
    pages = [
        {
            "page": 1,
            "width": 600.0,
            "height": 800.0,
            "layout": "single_column",
            "reading_order_risk": "low",
            "blocks": first_blocks,
            "warnings": [],
        },
        {
            "page": 2,
            "width": 600.0,
            "height": 800.0,
            "layout": "single_column",
            "reading_order_risk": "low",
            "blocks": second_blocks,
            "warnings": [],
        },
    ]
    document = [
        SimpleNamespace(get_drawings=lambda: []),
        SimpleNamespace(get_drawings=lambda: []),
    ]

    TextExtractor._augment_page_metrics(pages, document)

    assert "EXCESSIVE_SMALL_TEXT" in pages[0]["warnings"]
    assert pages[1]["sparse_trailing_page"] is True
    assert "SPARSE_TRAILING_PAGE" in pages[1]["warnings"]
    assert pages[1]["whitespace_ratio"] > 0.95


def _sections_from_blocks(blocks: list[dict]) -> dict:
    for index, block in enumerate(blocks):
        block.setdefault("zone_id", "p1_z0")
        block.setdefault("column", "single")
        block.setdefault("probable_table_cell", False)
        block.setdefault("heading_probability", 0.8)
        block["order"] = index
    page_layouts = [{"page": 1, "block_ids": [block["id"] for block in blocks]}]
    return SectionExtractor().extract_sections(
        "\n".join(block["text"] for block in blocks),
        layout_blocks=blocks,
        page_layouts=page_layouts,
    )


def test_nonstandard_adversarial_section_aliases_map_with_warnings() -> None:
    blocks = [
        _block("summary-h", "MY STORY", 30, 100, 130, 112, font_weight="bold"),
        _block("summary-b", "Backend engineer focused on reliable systems.", 30, 120, 280, 132),
        _block(
            "project-h",
            "PROJECTS AND RANDOM WORK",
            30,
            160,
            260,
            172,
            font_weight="bold",
        ),
        _block("project-b", "Inventory Service", 30, 180, 180, 192),
        _block(
            "cert-h",
            "FUN FACTS / CERTS",
            30,
            220,
            210,
            232,
            font_weight="bold",
        ),
        _block("cert-b", "Cloud Certificate - 2024", 30, 240, 220, 252),
    ]

    result = _sections_from_blocks(blocks)

    assert result["sections"]["summary"]["content"].startswith("Backend engineer")
    assert result["sections"]["projects"]["content"] == "Inventory Service"
    assert result["sections"]["certifications"]["content"] == "Cloud Certificate - 2024"
    assert any(
        value.startswith("ambiguous_section_heading:summary") for value in result["warnings"]
    )
    assert any(
        value.startswith("mixed_section_heading:certifications") for value in result["warnings"]
    )


def test_paraphrased_project_anchor_maps_but_ordinary_sentence_does_not() -> None:
    positive = SectionExtractor().extract_sections(
        "PORTFOLIO AND SIDE WORK\nForecasting Toolkit\n2025"
    )
    negative = SectionExtractor().extract_sections(
        "Summary\nI managed projects and random work.\nSkills\nPython"
    )

    assert positive["sections"]["projects"]["content"] == "Forecasting Toolkit\n2025"
    assert negative["sections"]["summary"]["content"] == "I managed projects and random work."
    assert negative["sections"]["projects"]["content"] == ""


def test_grid_skill_cells_are_not_concatenated_into_heading() -> None:
    blocks = [
        _block("skills-h", "SKILLS", 30, 100, 100, 112, font_weight="bold"),
        _block("cell-a", "Leadership", 30, 130, 110, 142),
        _block("cell-b", "Communication", 130, 130, 240, 142),
        _block("experience-h", "EXPERIENCE", 30, 170, 140, 182, font_weight="bold"),
        _block("experience-b", "Developer | Example Co | 2023 - Present", 30, 190, 300, 202),
    ]
    blocks[1]["probable_table_cell"] = True
    blocks[1]["heading_probability"] = 0.18
    blocks[2]["probable_table_cell"] = True
    blocks[2]["heading_probability"] = 0.18

    result = _sections_from_blocks(blocks)

    assert "Leadership\nCommunication" in result["sections"]["skills"]["content"]
    assert result["sections"]["leadership"]["content"] == ""
    assert result["sections"]["experience"]["content"].startswith("Developer")


def test_multi_page_column_continuation_returns_to_prior_semantic_section() -> None:
    blocks = [
        _block("p1-heading", "WORK EXPERIENCE", 30, 100, 170, 112, font_weight="bold"),
        _block("p1-role", "Accountant | Alpha Group | 2020 - 2022", 30, 130, 300, 142),
        _block(
            "p2-cert-heading",
            "CERTIFICATIONS",
            30,
            100,
            160,
            112,
            page=2,
            font_weight="bold",
        ),
        _block("p2-cert", "Excel Certificate", 30, 130, 160, 142, page=2),
        _block("p2-role", "Store Clerk", 330, 100, 450, 112, page=2),
        _block("p2-company", "Retail Group", 330, 120, 430, 132, page=2),
        _block("p2-date", "2022 - 2024", 330, 140, 420, 152, page=2),
    ]
    for index, block in enumerate(blocks):
        block.update(
            {
                "order": index,
                "zone_id": f"p{block['page']}_columns",
                "column": (
                    "single" if block["page"] == 1 else "left" if "cert" in block["id"] else "right"
                ),
                "probable_table_cell": False,
                "heading_probability": 0.8 if "heading" in block["id"] else 0.1,
            }
        )
    result = SectionExtractor().extract_sections(
        "\n".join(block["text"] for block in blocks),
        layout_blocks=blocks,
        page_layouts=[
            {"page": 1, "block_ids": ["p1-heading", "p1-role"]},
            {
                "page": 2,
                "layout": "two_column",
                "confidence": 0.9,
                "block_ids": [
                    "p2-cert-heading",
                    "p2-cert",
                    "p2-role",
                    "p2-company",
                    "p2-date",
                ],
            },
        ],
    )

    assert "Store Clerk" in result["sections"]["experience"]["content"]
    assert "Retail Group" in result["sections"]["experience"]["content"]
    assert "Store Clerk" not in result["sections"]["contact_header"]["content"]


def test_section_layout_records_join_discretionary_word_wraps() -> None:
    blocks = [
        _block("heading", "WORK EXPERIENCE", 30, 100, 170, 112, font_weight="bold"),
        _block("first", "Improved report\u00ad", 30, 130, 180, 142),
        _block("second", "ing time by 15%", 30, 143, 180, 155),
    ]
    for index, block in enumerate(blocks):
        block.update(
            {
                "order": index,
                "zone_id": "p1_z0",
                "column": "single",
                "probable_table_cell": False,
                "heading_probability": 0.8 if block["id"] == "heading" else 0.1,
            }
        )

    result = SectionExtractor().extract_sections(
        "\n".join(block["text"] for block in blocks),
        layout_blocks=blocks,
        page_layouts=[
            {
                "page": 1,
                "layout": "single_column",
                "confidence": 0.9,
                "block_ids": [block["id"] for block in blocks],
            }
        ],
    )

    assert result["sections"]["experience"]["content"] == "Improved reporting time by 15%"


def test_arabic_section_aliases_are_supported() -> None:
    result = SectionExtractor().extract_sections(
        "الملخص المهني\nمهندس برمجيات\nالمشاريع\nمنصة تحليل\n2024"
    )

    assert result["sections"]["summary"]["content"] == "مهندس برمجيات"
    assert result["sections"]["projects"]["content"] == "منصة تحليل\n2024"


def test_education_date_range_is_rejected_as_phone_with_block_evidence() -> None:
    block = _block("education-date", "2018/09 - 2022", 30, 420, 150, 432)
    block.update({"column": "left", "zone_id": "p1_z1", "zone_kind": "column_pair"})

    result = PhoneExtractor().extract_candidates(
        "Education\n2018/09 - 2022",
        ordered_text="Education\n2018/09 - 2022",
        layout_blocks=[block],
    )

    assert result["accepted"] == []
    assert result["rejected"][0]["reason"] == "date_range_not_phone"
    assert result["rejected"][0]["source"]["block_id"] == "education-date"


def test_paraphrased_date_range_rejected_but_header_phone_is_accepted() -> None:
    date_block = _block("job-date", "2020 - 2024", 320, 280, 410, 292)
    date_block.update({"column": "right", "zone_id": "p1_z1", "zone_kind": "column_pair"})
    phone_block = _block("phone", "Mobile: +44 20 7946 0958", 30, 80, 230, 92)
    phone_block.update({"column": "full_width", "zone_id": "p1_z0", "zone_kind": "header"})

    result = PhoneExtractor().extract_candidates(
        "Mobile: +44 20 7946 0958\nExperience\n2020 - 2024",
        ordered_text="Mobile: +44 20 7946 0958\nExperience\n2020 - 2024",
        layout_blocks=[phone_block, date_block],
    )

    assert [item["value"] for item in result["accepted"]] == ["+442079460958"]
    assert any(item["reason"] == "date_range_not_phone" for item in result["rejected"])


def test_coordinate_free_docx_header_phone_is_accepted() -> None:
    block = _block("docx-phone", "Mobile: +1 555 010 0200", 0, 0, 0, 0)
    block.update(
        {
            "page": 1,
            "bbox": None,
            "column": "single",
            "zone_kind": "unknown",
            "engine": "docx",
        }
    )

    result = PhoneExtractor().extract_candidates(
        block["text"],
        ordered_text=block["text"],
        layout_blocks=[block],
    )

    assert [item["value"] for item in result["accepted"]] == ["+15550100200"]


def test_unlabelled_body_identifier_is_not_accepted_as_phone() -> None:
    block = _block("identifier", "Reference ID 1234567890", 40, 500, 210, 512)
    block.update({"column": "single", "zone_id": "p1_z0", "zone_kind": "single"})

    result = PhoneExtractor().extract_candidates(
        block["text"],
        ordered_text=block["text"],
        layout_blocks=[block],
    )

    assert result["accepted"] == []
    assert result["rejected"][0]["reason"] == "outside_contact_region"


def test_page_number_is_not_accepted_as_phone() -> None:
    block = _block("page-number", "Page 2018 / 2022", 500, 770, 580, 782)
    block.update({"column": "single", "zone_id": "p1_footer", "zone_kind": "footer"})

    result = PhoneExtractor().extract_candidates(
        block["text"],
        ordered_text=block["text"],
        layout_blocks=[block],
    )

    assert result["accepted"] == []
    assert result["rejected"][0]["reason"] in {
        "date_range_not_phone",
        "page_number_not_phone",
    }


def test_header_image_triggers_targeted_contact_ocr(monkeypatch) -> None:
    class Page:
        rect = SimpleNamespace(width=600.0, height=800.0)

        @staticmethod
        def get_pixmap(**_kwargs):
            return SimpleNamespace(width=100, height=30, samples=b"pixels")

    class OCR:
        @staticmethod
        def image_to_string(*_args, **_kwargs):
            return "email: alex@example.test | phone: +1 555 010 0200"

    monkeypatch.setattr(text_extractor_module, "OCR_AVAILABLE", True)
    monkeypatch.setattr(text_extractor_module, "pytesseract", OCR())
    monkeypatch.setattr(
        text_extractor_module,
        "Image",
        SimpleNamespace(frombytes=lambda *_args, **_kwargs: object()),
    )
    blocks = [_block("name", "ALEX SAMPLE", 30, 30, 220, 50)]

    result = TextExtractor(enable_ocr=True)._analyze_contact_region(
        Page(),
        blocks,
        [(20.0, 70.0, 580.0, 130.0)],
    )

    assert result["possible_image_only_contact"] is True
    assert result["contact_ocr_used"] is True
    assert result["contact_ocr_status"] == "partial"
    assert result["image_only_contact_fields"] == ["email", "phone"]
    assert result["contact_ocr_blocks"][0]["zone_kind"] == "header"


def test_missing_contacts_without_header_image_do_not_trigger_ocr() -> None:
    page = SimpleNamespace(rect=SimpleNamespace(width=600.0, height=800.0))
    result = TextExtractor(enable_ocr=True)._analyze_contact_region(
        page,
        [_block("name", "ALEX SAMPLE", 30, 30, 220, 50)],
        [],
    )

    assert result["possible_image_only_contact"] is False
    assert result["contact_ocr_used"] is False
    assert result["contact_ocr_status"] == "not_needed"


def _assembler(blocks: list[dict], sections: dict[str, dict]) -> StructuredEntityAssembler:
    return StructuredEntityAssembler(
        layout_blocks=blocks,
        sections={"sections": sections},
    )


def test_two_experience_entries_use_local_title_company_date_groups() -> None:
    blocks = [
        _block("heading", "WORK EXPERIENCE", 320, 100, 450, 112, font_weight="bold"),
        _block("title-1", "Platform Engineer", 320, 130, 450, 142, font_weight="bold"),
        _block("company-1", "Northwind Labs", 320, 145, 430, 157),
        _block("date-1", "2022 - Present", 500, 145, 575, 157),
        _block("bullet-1", "• Built reliable APIs and", 320, 165, 460, 177),
        _block("wrap-1", "reduced latency by 30%", 320, 178, 460, 190),
        _block(
            "bullet-dup", "• Built reliable APIs and reduced latency by 30%.", 320, 192, 560, 204
        ),
        _block("title-2", "Engineering Intern", 320, 220, 450, 232, font_weight="bold"),
        _block("company-2", "Contoso Systems", 320, 235, 440, 247),
        _block("date-2", "Summer 2021", 500, 235, 575, 247),
        _block("bullet-2", "• Added integration tests", 320, 255, 470, 267),
        _block("other-column", "for a company where I can grow", 30, 145, 240, 157),
    ]
    for index, block in enumerate(blocks):
        block.update(
            {
                "order": index,
                "column": "right" if block["id"] != "other-column" else "left",
                "zone_id": "p1_z1",
                "zone_kind": "column_pair",
                "row_id": (
                    "company-row-1"
                    if block["id"] in {"company-1", "date-1"}
                    else "company-row-2" if block["id"] in {"company-2", "date-2"} else block["id"]
                ),
                "bullet_marker": "•" if block["id"].startswith("bullet") else None,
            }
        )
    section_ids = [block["id"] for block in blocks if block["id"] != "other-column"]
    result = _assembler(
        blocks,
        {
            "experience": {
                "heading": "WORK EXPERIENCE",
                "block_ids": section_ids,
            }
        },
    ).experience({})

    assert [(item["job_title"], item["company"]) for item in result["experiences"]] == [
        ("Platform Engineer", "Northwind Labs"),
        ("Engineering Intern", "Contoso Systems"),
    ]
    assert result["experiences"][0]["responsibilities"] == [
        "Built reliable APIs and reduced latency by 30%"
    ]
    assert all("where I can grow" not in str(item) for item in result["experiences"])


def test_project_wrapped_description_is_joined_without_phantom_entries() -> None:
    blocks = [
        _block("heading", "PORTFOLIO AND SIDE WORK", 30, 100, 250, 112),
        _block("name", "Forecasting Toolkit", 30, 130, 180, 142),
        _block("date", "2025", 220, 130, 260, 142),
        _block("description-a", "Created a demand forecasting tool", 30, 150, 260, 162),
        _block("description-b", "for small retail teams", 30, 163, 220, 175),
    ]
    for index, block in enumerate(blocks):
        block.update({"order": index, "row_id": block["id"], "rotation": 0.0})
    result = _assembler(
        blocks,
        {"projects": {"heading": blocks[0]["text"], "block_ids": [b["id"] for b in blocks]}},
    ).projects({})

    assert len(result["projects"]) == 1
    assert result["projects"][0]["name"] == "Forecasting Toolkit"
    assert result["projects"][0]["description"].endswith("for small retail teams")


def test_education_dates_coursework_and_location_are_directional() -> None:
    blocks = [
        _block("heading", "EDUCATION", 30, 100, 120, 112),
        _block(
            "primary",
            "Example University - Bachelor of Information Systems",
            30,
            130,
            360,
            142,
        ),
        _block("dates", "2019/09 - 2023", 30, 150, 160, 162),
        _block("courses", "Analytics, Networks, Business", 30, 170, 260, 182),
        _block("gpa", "GPA: Very Good", 30, 190, 160, 202),
    ]
    for index, block in enumerate(blocks):
        block.update({"order": index, "row_id": block["id"], "rotation": 0.0})
    item = _assembler(
        blocks,
        {"education": {"heading": "EDUCATION", "block_ids": [b["id"] for b in blocks]}},
    ).education({})["education"][0]

    assert item["start_date"] == "2019-09"
    assert item["end_date"] == "2023"
    assert item["location"] is None
    assert item["coursework"] == ["Analytics", "Networks", "Business"]
    assert item["gpa"] == "Very Good"


def test_skill_aliases_merge_and_prose_terms_do_not_enter_dedicated_skills() -> None:
    blocks = [
        _block("heading", "TOOLS & SKILLS", 30, 100, 170, 112),
        _block("python-a", "Python", 30, 130, 90, 142),
        _block("python-b", "PYTHON", 110, 130, 175, 142),
        _block("office-a", "MS Office", 30, 150, 100, 162),
        _block("office-b", "Microsoft Office", 120, 150, 230, 162),
        _block("bad", "Backend &", 30, 170, 100, 182),
    ]
    for index, block in enumerate(blocks):
        block.update({"order": index, "row_id": block["id"], "rotation": 0.0})
    result = _assembler(
        blocks,
        {"skills": {"heading": blocks[0]["text"], "block_ids": [b["id"] for b in blocks]}},
    ).skills(
        {
            "all_skills": [
                {"value": "marketing"},
                {"value": "sales"},
            ]
        }
    )

    assert [item["value"] for item in result["all_skills"]] == [
        "Python",
        "Microsoft Office",
    ]
    assert len(result["all_skills"][0]["source_block_ids"]) == 2


def test_mixed_certification_section_separates_courses_licenses_and_hobbies() -> None:
    blocks = [
        _block("heading", "FACTS / CERTS", 30, 100, 180, 112),
        _block("cert", "• Security Certificate - 2024", 30, 130, 230, 142),
        _block("course", "• Online Python course", 30, 150, 200, 162),
        _block("license", "• Driving license", 30, 170, 170, 182),
        _block("hobby", "• Hobbies: chess, hiking", 30, 190, 210, 202),
    ]
    for index, block in enumerate(blocks):
        block.update({"order": index, "row_id": block["id"], "rotation": 0.0})
    sections = {
        "certifications": {
            "heading": blocks[0]["text"],
            "block_ids": [block["id"] for block in blocks],
        }
    }
    assembler = _assembler(blocks, sections)
    certifications = assembler.certifications([])

    assert [item["name"] for item in certifications] == ["Security Certificate"]
    groups = sections["certifications"]["item_groups"]
    assert groups["courses"] == ["Online Python course"]
    assert groups["licenses"] == ["Driving license"]
    assert groups["interests"] == ["Hobbies: chess, hiking"]


def _incoherent_evidence_report():
    blocks = [
        {
            **_block("right-title", "Platform Engineer", 330, 130, 450, 142),
            "column": "right",
            "zone_id": "p1_columns",
            "zone_kind": "column_pair",
        },
        {
            **_block("right-company", "Example Systems", 330, 148, 450, 160),
            "column": "right",
            "zone_id": "p1_columns",
            "zone_kind": "column_pair",
        },
        {
            **_block("left-summary", "I build products for users", 30, 148, 230, 160),
            "column": "left",
            "zone_id": "p1_columns",
            "zone_kind": "column_pair",
        },
    ]
    payload = {
        "success": True,
        "file": {"name": "synthetic.pdf", "extension": ".pdf"},
        "text_extraction": {
            "success": True,
            "pages": 1,
            "words": 40,
            "chars": 300,
            "quality_score": 90,
            "layout": "two_column",
            "reading_order": "column_wise",
            "engine": "pymupdf",
            "raw_layout_blocks": blocks,
            "page_layouts": [
                {
                    "page": 1,
                    "width": 600,
                    "height": 800,
                    "layout": "two_column",
                    "reading_order": "column_wise",
                    "confidence": 0.9,
                    "engine": "pymupdf",
                    "block_ids": [block["id"] for block in blocks],
                }
            ],
        },
        "sections": {
            "sections": {
                "experience": {
                    "heading": "EXPERIENCE",
                    "content": "Platform Engineer\nExample Systems",
                    "block_ids": ["right-title", "right-company"],
                    "pages": [1],
                    "columns": ["right"],
                    "zones": ["p1_columns"],
                }
            }
        },
        "experience": {
            "experiences": [
                {
                    "job_title": "Platform Engineer",
                    "company": "I build products for users",
                    "start_date": "2022",
                    "end_date": "Present",
                    "confidence": 0.95,
                    "source_block_ids": ["right-title", "left-summary"],
                }
            ]
        },
    }
    return SchemaMigrator().from_extraction_modules(payload).report


def test_evidence_validator_rejects_cross_column_and_wrong_section_sources() -> None:
    findings = EvidenceCoherenceValidator().validate(_incoherent_evidence_report())

    assert {finding.code for finding in findings} >= {
        "evidence_cross_column",
        "evidence_section_mismatch",
    }


def test_data_quality_penalizes_incoherent_evidence_and_cannot_remain_100() -> None:
    quality = CanonicalDataQualityAnalyzer().analyze(_incoherent_evidence_report())

    assert quality.parsing_integrity_score < 90
    assert quality.status in {"needs_review", "poor"}
    assert quality.dimensions.evidence_consistency < 100
    assert {issue.code for issue in quality.issues} >= {
        "evidence_cross_column",
        "evidence_section_mismatch",
    }


def test_confidence_is_calibrated_by_source_quality() -> None:
    project_blocks = [
        _block("project-heading", "PROJECTS AND SIDE WORK", 30, 100, 230, 112),
        _block("project-title", "Forecast Toolkit", 30, 130, 180, 142),
        _block("project-date", "2025", 220, 130, 260, 142),
        _block("project-body", "Built demand forecasts for retailers.", 30, 150, 300, 162),
    ]
    for index, block in enumerate(project_blocks):
        block.update({"order": index, "row_id": block["id"], "rotation": 0.0})
    project = _assembler(
        project_blocks,
        {
            "projects": {
                "heading": project_blocks[0]["text"],
                "block_ids": [block["id"] for block in project_blocks],
            }
        },
    ).projects({})["projects"][0]

    assert 0.7 <= project["confidence"] < 0.9


def test_arabic_current_experience_and_mixed_technical_skill_line() -> None:
    blocks = [
        _block("experience-heading", "الخبرة", 30, 100, 100, 112),
        _block("title", "مهندسة برمجيات", 30, 130, 170, 142),
        _block("company", "شركة تقنية", 30, 148, 140, 160),
        _block("date", "2021 - الآن", 30, 166, 130, 178),
        _block("skills-heading", "المهارات", 300, 100, 380, 112),
        _block("skills", "Python SQL Docker", 300, 130, 450, 142),
    ]
    for index, block in enumerate(blocks):
        block.update({"order": index, "row_id": block["id"], "rotation": 0.0})
    assembler = _assembler(
        blocks,
        {
            "experience": {
                "heading": "الخبرة",
                "block_ids": ["experience-heading", "title", "company", "date"],
            },
            "skills": {
                "heading": "المهارات",
                "block_ids": ["skills-heading", "skills"],
            },
        },
    )

    experience = assembler.experience({})["experiences"][0]
    skills = assembler.skills({})["all_skills"]

    assert experience["job_title"] == "مهندسة برمجيات"
    assert experience["company"] == "شركة تقنية"
    assert experience["start_date"] == "2021"
    assert experience["end_date"] == "Present"
    assert experience["current"] is True
    assert [item["value"] for item in skills] == ["Python", "SQL", "Docker"]
