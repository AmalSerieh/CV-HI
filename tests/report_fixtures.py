from __future__ import annotations

from copy import deepcopy
from typing import Any

from resume_analyzer import SchemaMigrator
from resume_analyzer.schemas import PipelineReport


def make_report(**overrides: Any) -> PipelineReport:
    blocks = overrides.pop(
        "blocks",
        [
            {
                "id": "p1_b0",
                "page": 1,
                "text": "Jane Doe | jane@example.com | +1 555 111 2222",
                "bbox": {"x0": 40, "top": 30, "x1": 520, "bottom": 45},
                "column": "single",
                "order": 0,
                "engine": "pymupdf",
                "block_type": "line",
                "is_repeated_header_footer": False,
            },
            {
                "id": "p1_b1",
                "page": 1,
                "text": "• Worked on APIs using Python.",
                "bbox": {"x0": 50, "top": 180, "x1": 420, "bottom": 195},
                "column": "single",
                "order": 1,
                "engine": "pymupdf",
                "block_type": "line",
                "is_repeated_header_footer": False,
            },
        ],
    )
    visual = {
        "status": "complete",
        "source": "synthetic_test_metadata",
        "has_images": False,
        "image_count": 0,
        "icon_count": 0,
        "candidate_photo_detected": False,
        "decorative_image_count": 0,
        "image_only_contact_fields": [],
        "text_box_count": 0,
        "drawing_count": 0,
        "shape_count": 0,
        "table_count": 0,
        "has_color": False,
        "detected_color_count": 1,
        "contrast_status": "good",
        "ats_color_risk": "low",
        "font_sizes": [10.0, 12.0],
        "font_names": ["Arial"],
        "small_font_count": 0,
        "overlap_count": 0,
        "hidden_text_count": 0,
        "white_text_count": 0,
        "duplicate_ratio": 0.0,
        "repeated_header_footer_count": 0,
    }
    visual.update(overrides.pop("visual", {}))
    sections = overrides.pop(
        "sections",
        {
            "summary": {
                "heading": "Professional Summary",
                "content": "Python developer building APIs.",
            },
            "skills": {"heading": "Skills", "content": "Python, SQL, Postgres"},
            "experience": {
                "heading": "Experience",
                "content": "Software Engineer | Acme Corp | 2021 - Present\nWorked on APIs using Python.",
            },
            "education": {
                "heading": "Education",
                "content": "BSc Computer Science | Example University | 2020",
            },
        },
    )
    contact = overrides.pop(
        "contact",
        {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+1 555 111 2222",
            "linkedin": "https://linkedin.com/in/jane-doe",
        },
    )
    skills = overrides.pop("skills", ["Python", "SQL", "Postgres"])
    experience = overrides.pop(
        "experience",
        [
            {
                "job_title": "Software Engineer",
                "company": "Acme Corp",
                "start_date": "2021",
                "end_date": "Present",
                "current": True,
                "responsibilities": ["Worked on APIs using Python."],
                "achievements": [],
                "technologies": ["Python", "SQL"],
                "confidence": 0.95,
            }
        ],
    )
    education = overrides.pop(
        "education",
        [
            {
                "degree": "BSc Computer Science",
                "institution": "Example University",
                "end_date": "2020",
                "confidence": 0.95,
            }
        ],
    )
    projects = overrides.pop(
        "projects",
        [
            {
                "name": "API Project",
                "description": "Built a Python API.",
                "technologies": ["Python"],
                "confidence": 0.9,
            }
        ],
    )
    layout = overrides.pop("layout", "single_column")
    reading_order = overrides.pop("reading_order", "top_to_bottom")
    quality_score = overrides.pop("quality_score", 95)
    words = overrides.pop("words", 160)
    chars = overrides.pop("chars", 1_200)
    ocr_used = overrides.pop("ocr_used", False)
    extraction_warnings = overrides.pop("extraction_warnings", [])
    success = overrides.pop("success", True)
    links = overrides.pop("links", ["https://linkedin.com/in/jane-doe"])
    payload = {
        "success": success,
        "file": {"name": "synthetic-resume.pdf", "extension": ".pdf", "size_bytes": 2048},
        "text_extraction": {
            "success": success,
            "status": "ok" if success else "failed",
            "pages": 1,
            "words": words,
            "chars": chars,
            "quality_score": quality_score,
            "layout": layout,
            "reading_order": reading_order,
            "engine": "ocr" if ocr_used else "pymupdf",
            "ocr_used": ocr_used,
            "ocr_available": True,
            "raw_layout_blocks": blocks,
            "page_layouts": [
                {
                    "page": 1,
                    "width": 612,
                    "height": 792,
                    "layout": layout if layout != "mixed" else "unknown",
                    "reading_order": reading_order,
                    "split_x": None,
                    "confidence": 0.95,
                    "engine": "ocr" if ocr_used else "pymupdf",
                    "block_ids": [item["id"] for item in blocks],
                    "warnings": extraction_warnings,
                }
            ],
            "visual_metadata": visual,
            "warnings": extraction_warnings,
            "links": links,
        },
        "sections": {
            "sections": sections,
            "section_order": list(sections),
            "detected_headings": [
                value.get("heading") for value in sections.values() if value.get("heading")
            ],
        },
        "contact": contact,
        "skills": {"all_skills": skills},
        "experience": {"experiences": experience},
        "education": {"education": education},
        "projects": {"projects": projects},
        "languages": {"languages": []},
        "certifications": [],
    }
    payload.update(deepcopy(overrides))
    return SchemaMigrator().migrate(payload).report
