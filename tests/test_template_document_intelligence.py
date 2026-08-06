from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import fitz

from resume_analyzer.contracts.analysis_contract import finalize_and_validate
from resume_analyzer.extraction.contact import ContactResolver
from resume_analyzer.extraction.document_intelligence import (
    extract_dynamic_document_style,
)
from resume_analyzer.extraction.education_extractor import EducationExtractor
from resume_analyzer.extraction.evidence_reconciler import ResumeEvidenceReconciler
from resume_analyzer.extraction.experience_extractor import ExperienceExtractor
from resume_analyzer.extraction.result_quality_refiner import refine_resume_result
from resume_analyzer.extraction.skills_extractor import SkillsExtractor
from resume_analyzer.extraction.text_cleaner import TextCleaner

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


def resolve_schema_path() -> Path:
    candidates = [
        ROOT / "resume_analysis_schema_v1_1.json",
        ROOT / "schemas" / "resume_analysis_schema_v1_1.json",
        ROOT.parent / "resume_analysis_schema_v1_1.json",
        ROOT.parent / "schemas" / "resume_analysis_schema_v1_1.json",
        ROOT.parent / "resume_analyzer" / "schemas" / "resume_analysis_schema_v1_1.json",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = "\n".join(f"  - {candidate}" for candidate in candidates)
    raise FileNotFoundError(
        "resume_analysis_schema_v1_1.json was not found.\n"
        "Copy it to the project root or schemas/.\n"
        f"Searched:\n{searched}"
    )


def load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def refined_template() -> dict:
    payload = load_json("accounting_template_current_output.json")
    payload["file"]["path"] = str(FIXTURES / "resume-accounting.pdf")
    return refine_resume_result(copy.deepcopy(payload), copy_result=False)


def test_contact_resolver_rejects_template_identity() -> None:
    payload = load_json("accounting_template_current_output.json")
    contact = ContactResolver().resolve(
        text=payload["extracted_resume_text"]["ordered_text"],
        raw_text=payload["extracted_resume_text"]["raw_text"],
        layout_blocks=payload["layout_data"]["blocks"],
    )
    assert contact["name"] is None
    assert contact["name_status"] == "placeholder"
    assert contact["name_placeholder"] == "Student Name"
    assert contact["email_status"] == "placeholder"
    assert contact["phone_status"] == "placeholder"
    assert contact["location"] is None
    assert contact["quality"]["status"] == "source_placeholder"


def test_template_profile_and_placeholders() -> None:
    result = refined_template()
    profile = result["document_profile"]
    assert profile["is_template"] is True
    assert profile["document_type"] == "resume_template"
    assert {
        "resume_sample_heading",
        "placeholder_candidate_name",
        "placeholder_email",
        "placeholder_phone",
        "placeholder_location",
        "placeholder_dates",
    } <= set(profile["signal_types"])

    placeholders = result["date_placeholders"]
    assert placeholders["count"] == 9
    assert placeholders["counts_by_section"] == {
        "achievements": 2,
        "certifications": 1,
        "education": 1,
        "experience": 4,
        "volunteer": 1,
    }

    contact = result["contact"]
    assert contact["name"] is None
    assert contact["name_placeholder"] == "Student Name"
    assert contact["email_status"] == "placeholder"
    assert contact["phone_status"] == "placeholder"
    assert contact["location"] is None
    assert contact["location_status"] == "unverified_or_placeholder"


def test_dynamic_color_detection_no_fixed_palette() -> None:
    result = refined_template()
    style = result["document_style"]
    assert style["status"] == "ok"
    assert style["has_color"] is True
    assert style["is_multicolor"] is True
    assert style["detected_color_count"] >= 6
    assert style["chromatic_color_count"] >= 3
    assert style["fixed_palette_used"] is False
    assert style["contrast_status"] == "good"
    assert style["ats_color_risk"] == "low"
    assert all(
        isinstance(item["hex"], str) and item["hex"].startswith("#") and len(item["hex"]) == 7
        for item in style["palette"]
    )

    source = inspect.getsource(extract_dynamic_document_style).casefold()
    for forbidden in (
        "#172c56",
        "#fdb913",
        "#0072bc",
        "#00a14b",
        "#e82c2a",
    ):
        assert forbidden not in source


def test_arbitrary_color_pdf_is_discovered() -> None:
    path = ROOT / "fixtures" / "_synthetic_arbitrary_colors.pdf"
    document = fitz.open()
    page = document.new_page(width=320, height=240)
    arbitrary = [
        (0.13, 0.57, 0.31),
        (0.71, 0.22, 0.64),
        (0.24, 0.35, 0.86),
    ]
    page.draw_rect(fitz.Rect(0, 0, 320, 55), color=None, fill=arbitrary[0])
    page.draw_circle(fitz.Point(260, 95), 28, color=arbitrary[1], fill=arbitrary[1])
    page.insert_text((30, 120), "Dynamic palette test", color=arbitrary[2], fontsize=18)
    document.save(path)
    document.close()
    try:
        style = extract_dynamic_document_style(path)
        assert style["has_color"] is True
        assert style["chromatic_color_count"] >= 3
        assert style["fixed_palette_used"] is False
    finally:
        path.unlink(missing_ok=True)


def test_aligned_experience_and_volunteer() -> None:
    result = refined_template()
    experience = result["experience"]
    assert experience["count"] == 5
    assert experience["professional_role_count"] == 4
    assert experience["volunteer_role_count"] == 1
    assert experience["professional_experience_months"] == 0
    assert experience["professional_duration_status"] == ("not_computable_placeholder_dates")
    assert experience["volunteer_experience_months"] == 2
    assert experience["layout_pattern"] == ("single_column_with_aligned_metadata")

    actual = {
        (item["company"], item["job_title"], item["location"], item["volunteer"])
        for item in experience["experiences"]
    }
    expected = {
        (
            "Chartered Professional Accountants Business",
            "Bookkeeper/Accounting Assistant",
            "Victoria, Canada",
            False,
        ),
        (
            "Car Dealership",
            "Administration Assistant (Co-op)",
            "Victoria, Canada",
            False,
        ),
        (
            "Gifts & Souvenir Shop",
            "Sales Associate, Retail Store (Co-op)",
            "Victoria, Canada",
            False,
        ),
        (
            "Marketing Firm",
            "Office Assistant, Marketing Department",
            "City, Country",
            False,
        ),
        (
            "Community Volunteer Tax Program",
            "Tax Preparer",
            "Victoria, Canada",
            True,
        ),
    }
    assert actual == expected
    assert all(
        item["date_status"] == "placeholder_unresolved"
        and item["date_validation"]["valid"] is False
        and item["start_date"] is None
        and item["end_date"] is None
        for item in experience["experiences"]
    )

    activities = experience["undated_volunteer_activities"]
    assert len(activities) == 1
    assert len(activities[0]["responsibilities"]) == 4
    assert activities[0]["duration_months"] == 2


def test_education_pairing_and_placeholder_status() -> None:
    result = refined_template()
    education = result["education"]
    entry = education["education"][0]
    assert entry["degree"] == "Bachelor of Commerce"
    assert entry["field"] == "Service Management"
    assert entry["institution"] == "University of Victoria"
    assert entry["school"] == "Peter B. Gustavson School of Business"
    assert entry["location"] == "Victoria, Canada"
    assert entry["raw_date_text"] == "Month 20XX"
    assert entry["graduation_date_status"] == "placeholder_unresolved"
    assert education["education_score"] >= 88
    assert education["education_quality"]["status"] == "ok"


def test_skill_disambiguation_and_accounting_tools() -> None:
    result = refined_template()
    skills = result["skills"]
    assert not any(value.casefold() == "r" for value in skills["all_skills"])
    assert {
        "Caseware",
        "Taxprep",
        "Microsoft Access",
        "QuickBooks",
        "Microsoft Excel",
        "Microsoft PowerPoint",
        "Apple Keynote",
    } <= set(skills["top_technologies"])
    assert skills["sector"] == "finance_accounting"
    assert skills["role_family"] == "accounting"
    assert skills["current_role"] == "accounting_assistant"
    assert skills["primary_title"] == "Bookkeeper/Accounting Assistant"

    extractor = SkillsExtractor(use_spacy=False, use_sbert=False)
    accepted, rejected = extractor._filter_before_semantic_analysis(
        ["R"],
        {"summary": {"content": "Knowledge of A/P and A/R."}},
    )
    assert accepted == []
    assert rejected[0]["reason"] == ("ambiguous_R_token_without_programming_context")


def test_metric_expansion_and_types() -> None:
    result = refined_template()
    metrics = {
        item["value"]: item["metric_type"]
        for item in result["evidence_reconciliation"]["document_metrics"]
    }
    assert metrics["up to 5 clients"] == "quantity"
    assert metrics["over 100 calls"] == "quantity"
    assert metrics["2-month program"] == "duration"
    assert metrics["top 15% of their class by GPA"] == "ranking"
    assert "120%" in metrics
    assert "$1,200" in metrics
    assert not any("20XX" in value.upper() for value in metrics)

    reconciler = ResumeEvidenceReconciler()
    extracted = reconciler._extract_metrics(
        "Answered over 100 calls. Received recognition after a "
        "2-month program. Ranked in the top 15% of their class by GPA."
    )
    values = {item["value"]: item["type"] for item in extracted}
    assert values["over 100 calls"] == "quantity"
    assert values["2-month program"] == "duration"
    assert values["top 15% of their class by GPA"] == "ranking"


def test_extractor_level_placeholder_records() -> None:
    text = (
        "Chartered Professional Accountants Business\n"
        "Victoria, Canada\n"
        "Bookkeeper/Accounting Assistant\n"
        "20XX-20XX\n"
        "Reconciled bank accounts.\n"
        "Car Dealership\n"
        "Victoria, Canada\n"
        "Administration Assistant (Co-op)\n"
        "20XX-20XX\n"
        "Answered customer calls."
    )
    extractor = ExperienceExtractor(use_spacy=False, use_sbert=False)
    records = extractor._split_placeholder_date_entries(text)
    assert len(records) == 2
    assert all(record["metadata"]["date_status"] == "placeholder_unresolved" for record in records)

    education = EducationExtractor(use_spacy=False)
    entry = education._parse_placeholder_education_section(
        "University of Example (School of Business)\n"
        "Example City, Canada\n"
        "Bachelor of Commerce, Accounting Specialization\n"
        "Month 20XX"
    )
    assert entry is not None
    assert entry["institution"] == "University of Example"
    assert entry["field"] == "Accounting"
    assert entry["graduation_date_status"] == "placeholder_unresolved"


def test_placeholder_records_preserve_wrapped_responsibilities() -> None:
    text = (
        "Accounting Business\n"
        "Victoria, Canada\n"
        "Bookkeeper/Accounting Assistant\n"
        "20XX-20XX\n"
        "• Reconciled five client accounts while maintaining a high degree of\n"
        "accuracy\n"
        "• Built an Excel recording system, saved report\u00ad\n"
        "ing time by 15%\n"
        "Car Dealership\n"
        "Victoria, Canada\n"
        "Administration Assistant (Co-op)\n"
        "20XX-20XX\n"
        "• Introduced customers to the\n"
        "appropriate sales advisor and associate\n"
        "• Showed excellent abilities in customer service\n"
        "Gifts Shop\n"
        "Victoria, Canada\n"
        "Sales Associate, Retail Store (Co-op)\n"
        "20XX-20XX\n"
        "• Achieved seasonal targets established for\n"
        "the summer of 2017"
    )
    extractor = ExperienceExtractor(use_spacy=False, use_sbert=False)

    result = extractor.extract({"sections": {"experience": {"content": text}}})

    assert [item["job_title"] for item in result["experiences"]] == [
        "Bookkeeper/Accounting Assistant",
        "Administration Assistant",
        "Sales Associate",
    ]
    assert [item["employment_type"] for item in result["experiences"]] == [
        None,
        "Co-op",
        "Co-op",
    ]
    assert extractor._normalize_job_title("UI/UX QA Engineer") == ("UI/UX QA Engineer")
    responsibilities = [
        value for item in result["experiences"] for value in item["responsibilities"]
    ]
    assert responsibilities == [
        "Reconciled five client accounts while maintaining a high degree of accuracy",
        "Built an Excel recording system, saved reporting time by 15%",
        "Introduced customers to the appropriate sales advisor and associate",
        "Showed excellent abilities in customer service",
        "Achieved seasonal targets established for the summer of 2017",
    ]
    assert not any("\u00ad" in value for value in responsibilities)


def test_text_cleaner_joins_discretionary_soft_hyphen_wraps() -> None:
    cleaned = TextCleaner().clean(
        "• Built an Excel recording system and reduced report\u00ad\n" "ing time by 15%."
    )

    assert cleaned == ("• Built an Excel recording system and reduced reporting time by 15%.")
    assert "\u00ad" not in cleaned


def test_source_readiness_is_separate_from_extraction_quality() -> None:
    result = refined_template()
    assert result["extraction_quality"]["status"] == "ok"
    assert result["extraction_quality"]["score"] >= 85
    assert result["source_readiness"]["status"] == "template_incomplete"
    assert result["scores"]["status"] == "source_incomplete"
    assert result["scores"]["trusted"] is False
    assert result["scores"]["resume_completeness_score"] <= 60


def test_contract_handles_null_location_evidence() -> None:
    result = refined_template()
    contact = result.setdefault("contact", {})
    contact["location"] = None
    evidence = contact.setdefault("evidence", {})
    evidence["location"] = None

    finalized = finalize_and_validate(
        result,
        resolve_schema_path(),
    )

    assert finalized["contract_validation"]["valid"] is True
    assert finalized["contact"]["location"] is None


def test_final_contract_remains_valid() -> None:
    result = refined_template()
    schema_path = resolve_schema_path()
    finalized = finalize_and_validate(result, schema_path)
    assert finalized["contract_validation"]["valid"] is True
    metric_types = {
        item["value"]: item["metric_type"]
        for item in finalized["evidence_reconciliation"]["document_metrics"]
    }
    assert metric_types["2-month program"] == "duration"
    assert metric_types["top 15% of their class by GPA"] == "ranking"


def test_template_refinement_is_idempotent() -> None:
    first = refined_template()
    second = refine_resume_result(copy.deepcopy(first), copy_result=False)
    assert first == second
