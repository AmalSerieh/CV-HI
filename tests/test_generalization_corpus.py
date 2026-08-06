from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from resume_analyzer.config import PipelineConfig
from resume_analyzer.extraction.contact import ContactResolver
from resume_analyzer.extraction.contact.phone import PhoneExtractor
from resume_analyzer.extraction.section_extractor import SectionExtractor
from resume_analyzer.pipeline import ResumePipeline
from resume_analyzer.schemas import PipelineReport

CORPUS = Path(__file__).with_name("generalization_corpus")


def _pipeline() -> ResumePipeline:
    return ResumePipeline(
        replace(
            PipelineConfig(),
            enable_ocr=False,
            enable_recommendations=False,
            enable_ats=False,
            enable_rewrites=False,
            integrate_target_role=False,
        )
    )


def _write_resume_pdf(path: Path, lines: list[str], *, capitalization: str = "normal") -> None:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    y = 42
    headings = {
        "summary",
        "profile",
        "skills",
        "technical skills",
        "experience",
        "work history",
        "projects",
        "portfolio",
        "education",
    }
    for raw in lines:
        value = raw
        if capitalization == "upper" and raw.casefold() in headings:
            value = raw.upper()
        is_heading = raw.casefold() in headings
        page.insert_text(
            (50, y),
            value,
            fontsize=12 if is_heading else 9.5,
            fontname="hebo" if is_heading else "helv",
        )
        y += 20 if is_heading else 15
    document.save(path)
    document.close()


def _random_resume(seed: int) -> tuple[list[str], dict[str, str]]:
    generator = random.Random(seed)
    first = generator.choice(["Avery", "Morgan", "Riley", "Taylor", "Cameron"])
    last = generator.choice(["Quinn", "Santos", "Bennett", "Khan", "Novak"])
    company = generator.choice(
        ["Northwind Systems", "Blue Oak Labs", "Cedar Analytics", "Orbit Works"]
    )
    project = generator.choice(
        ["Forecast Toolkit", "Inventory Console", "Support Portal", "Metrics Service"]
    )
    start = generator.randint(2018, 2021)
    skill_variants = generator.choice(
        [
            ["Python, SQL, Docker"],
            ["PYTHON, sql, Docker"],
            ["Python, Microsoft Office, React"],
        ]
    )
    return (
        [
            f"{first} {last}",
            "Platform Engineer",
            f"{first.casefold()}.{last.casefold()}@example.test | +1 555 010 {seed:04d}",
            "Portland, OR",
            "Summary",
            "Engineer focused on reliable data services and accessible products.",
            "Technical Skills",
            *skill_variants,
            "Work History",
            "Platform Engineer",
            company,
            f"{start} - Present",
            "- Built reliable APIs with Python and SQL.",
            "- Reduced request latency through measured profiling.",
            "Portfolio",
            project,
            "2024",
            "Built a service for operational reporting and forecasting.",
            "Education",
            "Example Technical University - Bachelor of Computer Science",
            f"{start - 4} - {start}",
        ],
        {
            "name": f"{first} {last}",
            "company": company,
            "project": project,
            "phone": f"+1555010{seed:04d}",
        },
    )


def test_generalization_manifest_covers_development_holdout_and_variation_matrix() -> None:
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))

    assert len(manifest["development"]) >= 30
    assert len(manifest["holdout"]) >= 25
    assert len(manifest["randomized_dimensions"]) >= 14
    assert len(set(manifest["development"] + manifest["holdout"])) == 55


@pytest.mark.parametrize("seed", [101, 202, 303, 404, 505, 606])
def test_seeded_unseen_pdf_resumes_preserve_broad_invariants(tmp_path: Path, seed: int) -> None:
    lines, expected = _random_resume(seed)
    path = tmp_path / f"holdout-{seed}.pdf"
    _write_resume_pdf(path, lines)

    result = _pipeline().analyze(str(path))
    canonical = PipelineReport.model_validate(result)
    known_evidence = {item.id for item in canonical.evidence}
    emitted_evidence = {
        evidence_id
        for collection in (
            canonical.entities.skills,
            canonical.entities.education,
            canonical.entities.experience,
            canonical.entities.projects,
        )
        for item in collection
        for evidence_id in item.evidence_ids
    }

    assert canonical.document.path is None
    assert expected["phone"] == canonical.entities.contact.phone
    assert canonical.entities.contact.name == expected["name"]
    assert len(canonical.entities.experience) == 1
    assert canonical.entities.experience[0].company == expected["company"]
    assert len(canonical.entities.projects) == 1
    assert canonical.entities.projects[0].name == expected["project"]
    assert len(canonical.entities.education) == 1
    normalized_skills = [
        item.normalized or item.value.casefold() for item in canonical.entities.skills
    ]
    assert len(normalized_skills) == len(set(normalized_skills))
    assert emitted_evidence <= known_evidence
    assert not any("C:\\" in str(value) for value in result.values() if isinstance(value, str))


def test_changing_name_and_heading_capitalization_preserves_entity_counts(
    tmp_path: Path,
) -> None:
    lines, _ = _random_resume(707)
    original = tmp_path / "original.pdf"
    variant = tmp_path / "variant.pdf"
    _write_resume_pdf(original, lines)
    changed = [*lines]
    changed[0] = "Devon Mercer"
    changed[2] = "devon.mercer@example.test | +1 555 010 0707"
    _write_resume_pdf(variant, changed, capitalization="upper")

    first = _pipeline().analyze(str(original))
    second = _pipeline().analyze(str(variant))

    for entity in ("experience", "projects", "education"):
        assert len(first["entities"][entity]) == len(second["entities"][entity])
    assert {item["normalized"] for item in first["entities"]["skills"]} == {
        item["normalized"] for item in second["entities"]["skills"]
    }


def test_section_reordering_and_valid_aliases_preserve_classification() -> None:
    original = SectionExtractor().extract_sections(
        "SUMMARY\nReliable platform engineer.\nPROJECTS\nMetrics Service\nSKILLS\nPython"
    )
    variant = SectionExtractor().extract_sections(
        "TECHNICAL SKILLS\nPython\nPORTFOLIO AND SIDE WORK\nMetrics Service\n"
        "ABOUT ME\nReliable platform engineer."
    )

    for section in ("summary", "projects", "skills"):
        assert original["sections"][section]["content"]
        assert variant["sections"][section]["content"]
    assert variant["sections"]["projects"]["confidence"] < 100


def test_unrelated_year_and_skills_list_do_not_create_contact_fields() -> None:
    text = (
        "Avery Quinn\nPlatform Engineer\navery@example.test\n"
        "SKILLS\nPython, SQL\nEDUCATION\n2018/09 - 2022"
    )
    phone = PhoneExtractor().extract_candidates(text, ordered_text=text)
    contact = ContactResolver().resolve(text=text)

    assert phone["accepted"] == []
    assert contact["phone"] is None
    assert contact["location"] is None


def test_real_unicode_arabic_headings_and_mixed_skills_are_classified() -> None:
    result = SectionExtractor().extract_sections(
        "الملخص المهني\nمهندس برمجيات يطور أنظمة موثوقة\n"
        "المهارات\nPython، SQL، Docker\n"
        "الخبرة\nمهندس برمجيات\nشركة تقنية\n2021 - الآن"
    )

    assert result["sections"]["summary"]["content"].startswith("مهندس برمجيات")
    assert "Python" in result["sections"]["skills"]["content"]
    assert result["sections"]["experience"]["content"].startswith("مهندس برمجيات")
