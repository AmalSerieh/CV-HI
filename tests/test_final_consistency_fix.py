from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from resume_analyzer.ats import ATSAnalyzer
from resume_analyzer.extraction.data_quality import CanonicalDataQualityAnalyzer
from resume_analyzer.schemas import DataQualityInfo, PipelineReport
from tests.report_fixtures import make_report


def _codes(result) -> set[str]:
    return {item.code for item in result.issues}


def _strengths(result) -> set[str]:
    return {item.code for item in result.strengths}


def _contact_report(
    email_source: str = "selectable_text",
    phone_source: str = "selectable_text",
    *,
    email: str | None = "jane@example.com",
    phone: str | None = "+1 555 111 2222",
    scope: str = "none",
    ocr_status: str = "not_needed",
    fields: list[str] | None = None,
) -> PipelineReport:
    data = make_report().to_json_dict()
    used = scope != "none"
    data["entities"]["contact"]["email"] = email
    data["entities"]["contact"]["phone"] = phone
    data["entities"]["contact"]["source_types"].update(
        email=email_source,
        phone=phone_source,
    )
    data["extraction"]["ocr_used"] = used
    data["extraction"]["ocr_usage"] = {
        "used": used,
        "scope": scope,
        "pages": [1] if used else [],
        "fields": fields or [],
    }
    visual = data["extraction"]["visual_metadata"]
    visual["contact_ocr_used"] = scope in {"contact_header", "mixed"}
    visual["contact_ocr_status"] = ocr_status
    return PipelineReport.model_validate(data)


def _quality(report: PipelineReport) -> DataQualityInfo:
    return CanonicalDataQualityAnalyzer().analyze(report)


def _grounded_clean_report() -> PipelineReport:
    data = make_report().to_json_dict()
    entity_prefixes = (
        "entities.skills",
        "entities.education",
        "entities.experience",
        "entities.projects",
        "entities.languages",
        "entities.certifications",
    )
    for evidence in data["evidence"]:
        if evidence["kind"] == "present" and evidence["field_path"].startswith(entity_prefixes):
            evidence["source"]["page"] = 1
            evidence["source"]["block_id"] = "p1_b1"
    return PipelineReport.model_validate(data)


def _experience_report(responsibilities: list[str], *, parsing_review: bool = False):
    report = make_report(
        experience=[
            {
                "job_title": "Engineer",
                "company": "Acme",
                "responsibilities": responsibilities,
                "confidence": 0.94,
                "needs_review": parsing_review,
            },
            {
                "job_title": "Intern",
                "company": "Other",
                "responsibilities": ["Maintained documented APIs."],
                "confidence": 0.93,
            },
        ]
    )
    analyzer = CanonicalDataQualityAnalyzer()
    quality = analyzer.analyze(report)
    return report, quality, analyzer.annotate_experience_reviews(report, quality)


def test_selectable_core_contacts_receive_full_accessibility_credit() -> None:
    result = ATSAnalyzer().analyze(_contact_report())
    assert result.score_breakdown.contact_accessibility == 5


def test_ocr_only_core_contacts_receive_partial_accessibility_credit() -> None:
    result = ATSAnalyzer().analyze(
        _contact_report("ocr", "ocr", scope="full_document", ocr_status="complete")
    )
    assert result.score_breakdown.contact_accessibility == 3


def test_mixed_text_and_ocr_contact_receives_partial_high_credit() -> None:
    result = ATSAnalyzer().analyze(
        _contact_report(
            "selectable_text",
            "ocr",
            scope="contact_header",
            ocr_status="complete",
            fields=["phone"],
        )
    )
    assert result.score_breakdown.contact_accessibility == 4


def test_text_email_with_missing_phone_is_deducted() -> None:
    result = ATSAnalyzer().analyze(_contact_report(phone_source="missing", phone=None))
    assert result.score_breakdown.contact_accessibility == 3


def test_missing_email_and_phone_receive_severe_contact_deduction() -> None:
    result = ATSAnalyzer().analyze(_contact_report("missing", "missing", email=None, phone=None))
    assert result.score_breakdown.contact_accessibility == 0


def test_image_only_optional_social_link_does_not_reduce_core_contact_score() -> None:
    data = _contact_report().to_json_dict()
    data["entities"]["contact"]["source_types"]["linkedin"] = "image_only_unrecovered"
    data["extraction"]["visual_metadata"]["image_only_contact_fields"] = ["linkedin"]
    result = ATSAnalyzer().analyze(PipelineReport.model_validate(data))
    assert result.score_breakdown.contact_accessibility == 5


def test_annotation_only_linkedin_does_not_make_missing_core_contacts_accessible() -> None:
    report = _contact_report("missing", "missing", email=None, phone=None)
    result = ATSAnalyzer().analyze(report)
    assert report.entities.contact.source_types["linkedin"] == "annotation"
    assert result.score_breakdown.contact_accessibility == 0
    assert "CONTACT_TEXT_ACCESSIBLE" not in _strengths(result)


def test_docx_text_contacts_receive_full_credit() -> None:
    data = _contact_report().to_json_dict()
    data["document"]["extension"] = ".docx"
    data["document"]["name"] = "resume.docx"
    result = ATSAnalyzer().analyze(PipelineReport.model_validate(data))
    assert result.score_breakdown.contact_accessibility == 5


def test_scanned_resume_keeps_valid_contact_but_loses_full_accessibility() -> None:
    report = _contact_report("ocr", "ocr", scope="full_document", ocr_status="complete")
    result = ATSAnalyzer().analyze(report)
    assert report.entities.contact.email == "jane@example.com"
    assert result.score_breakdown.contact_accessibility < 5


def test_ocr_contact_never_emits_selectable_contact_strength() -> None:
    result = ATSAnalyzer().analyze(
        _contact_report("ocr", "ocr", scope="contact_header", ocr_status="complete")
    )
    assert "CONTACT_TEXT_ACCESSIBLE" not in _strengths(result)


def test_selectable_required_contact_emits_accessible_strength() -> None:
    assert "CONTACT_TEXT_ACCESSIBLE" in _strengths(ATSAnalyzer().analyze(_contact_report()))


def test_contact_strength_and_image_only_issue_are_mutually_exclusive() -> None:
    data = _contact_report("image_only_unrecovered").to_json_dict()
    data["extraction"]["visual_metadata"]["image_only_contact_fields"] = ["email"]
    result = ATSAnalyzer().analyze(PipelineReport.model_validate(data))
    assert "IMAGE_ONLY_CONTACT_INFORMATION" in _codes(result)
    assert "CONTACT_TEXT_ACCESSIBLE" not in _strengths(result)


def test_single_column_strength_and_multi_column_risk_are_mutually_exclusive() -> None:
    result = ATSAnalyzer().analyze(make_report(layout="two_column", reading_order="unknown"))
    assert "MULTI_COLUMN_READING_ORDER_RISK" in _codes(result)
    assert "SINGLE_COLUMN_LAYOUT" not in _strengths(result)


def test_no_ocr_produces_no_ocr_issue() -> None:
    codes = _codes(ATSAnalyzer().analyze(_contact_report()))
    assert not {code for code in codes if "OCR" in code}


def test_contact_region_ocr_produces_only_contact_specific_warning() -> None:
    result = ATSAnalyzer().analyze(
        _contact_report("ocr", "ocr", scope="contact_header", ocr_status="complete")
    )
    assert "CONTACT_OCR_REVIEW_REQUIRED" in _codes(result)
    assert "OCR_REVIEW_REQUIRED" not in _codes(result)


def test_full_document_ocr_produces_document_wide_warning() -> None:
    result = ATSAnalyzer().analyze(
        _contact_report("ocr", "ocr", scope="full_document", ocr_status="complete")
    )
    assert "OCR_REVIEW_REQUIRED" in _codes(result)


def test_partial_page_ocr_uses_page_specific_warning_and_pages() -> None:
    data = _contact_report(scope="page").to_json_dict()
    result = ATSAnalyzer().analyze(PipelineReport.model_validate(data))
    issue = next(item for item in result.issues if item.code == "PAGE_OCR_REVIEW_REQUIRED")
    assert issue.pages == [1]
    assert "OCR_REVIEW_REQUIRED" not in _codes(result)


def test_failed_contact_ocr_is_reported_without_global_ocr_claim() -> None:
    result = ATSAnalyzer().analyze(_contact_report(scope="contact_header", ocr_status="failed"))
    assert "CONTACT_OCR_FAILED" in _codes(result)
    assert "OCR_REVIEW_REQUIRED" not in _codes(result)


def test_ocr_usage_schema_rejects_used_ocr_without_scope() -> None:
    data = make_report().to_json_dict()
    data["extraction"]["ocr_usage"] = {
        "used": True,
        "scope": "none",
        "pages": [],
        "fields": [],
    }
    with pytest.raises(ValidationError):
        PipelineReport.model_validate(data)


def test_high_experience_content_issue_propagates_to_only_affected_entry() -> None:
    _, _, experiences = _experience_report(["Built APIs with Python,"])
    assert experiences[0].content_needs_review is True
    assert experiences[1].content_needs_review is False


def test_multiple_medium_experience_issues_propagate() -> None:
    _, _, experiences = _experience_report(
        ["Increased throughput 300%.", "Increased throughput 300%."]
    )
    assert experiences[0].content_needs_review is True


def test_isolated_low_content_suggestion_does_not_mark_parser_failure() -> None:
    _, _, experiences = _experience_report(["Worked with a team."])
    assert experiences[0].content_needs_review is False
    assert experiences[0].parsing_needs_review is False
    assert experiences[0].needs_review is False
    assert experiences[0].review_reasons


def test_content_review_does_not_reduce_structural_confidence() -> None:
    report, _, experiences = _experience_report(["Built APIs with Python,"])
    assert experiences[0].confidence == report.entities.experience[0].confidence == 0.94


def test_experience_review_reasons_map_by_evidence_id() -> None:
    report, quality, experiences = _experience_report(["Built APIs with Python,"])
    first_evidence = set(report.entities.experience[0].evidence_ids)
    issue = next(item for item in quality.issues if item.code == "truncated_experience_bullets")
    assert first_evidence.intersection(issue.evidence_ids)
    assert any("truncated_experience_bullets" in item for item in experiences[0].review_reasons)
    assert experiences[1].review_reasons == []


def test_legacy_parsing_review_remains_separate_from_content_review() -> None:
    _, _, experiences = _experience_report(
        ["Maintained documented APIs."],
        parsing_review=True,
    )
    assert experiences[0].parsing_needs_review is True
    assert experiences[0].content_needs_review is False
    assert experiences[0].needs_review is True


def test_parsing_breakdown_exists_with_all_ten_dimensions() -> None:
    quality = _quality(_grounded_clean_report())
    assert quality.breakdown is not None
    assert len(quality.breakdown.dimensions) == 10


def test_parsing_breakdown_recomputes_reported_score() -> None:
    quality = _quality(make_report())
    breakdown = quality.breakdown
    assert breakdown is not None
    subtotal = round(sum(item.score * item.weight for item in breakdown.dimensions.values()))
    total = subtotal + sum(item.points for item in breakdown.adjustments)
    assert subtotal == breakdown.weighted_subtotal
    assert total == breakdown.total == quality.parsing_integrity_score


def test_every_quality_issue_maps_to_at_least_one_dimension() -> None:
    report, quality, _ = _experience_report(
        ["Built APIs with Python,", "Increased throughput 300%."]
    )
    assert report.entities.experience
    assert quality.issues
    assert all(item.dimensions for item in quality.issues)


def test_clean_grounded_resume_remains_perfect() -> None:
    quality = _quality(_grounded_clean_report())
    assert quality.score == 100
    assert quality.status == "good"
    assert quality.breakdown is not None
    assert not quality.breakdown.adjustments


def test_bad_resume_remains_needs_review() -> None:
    data = make_report().to_json_dict()
    data["entities"]["skills"][0]["value"] = "Backend &"
    data["entities"]["experience"][0]["responsibilities"] = ["Built APIs with Python,"]
    quality = _quality(PipelineReport.model_validate(data))
    assert quality.status in {"needs_review", "poor"}
    assert quality.score < 90


def test_weak_dimension_cap_is_an_explicit_adjustment() -> None:
    quality = _quality(make_report())
    assert quality.breakdown is not None
    adjustment = quality.breakdown.adjustments[0]
    assert adjustment.code.startswith("weak_dimension_review_cap_")
    assert adjustment.points < 0
    assert adjustment.trigger_dimension


def test_breakdown_issue_codes_are_not_duplicated() -> None:
    quality = _quality(make_report())
    assert quality.breakdown is not None
    for detail in quality.breakdown.dimensions.values():
        assert len(detail.issue_codes) == len(set(detail.issue_codes))


def test_ocr_contact_uncertainty_appears_in_contact_breakdown() -> None:
    data = _contact_report(
        "ocr",
        "ocr",
        scope="contact_header",
        ocr_status="partial",
    ).to_json_dict()
    data["extraction"]["visual_metadata"]["contact_readability"] = "partially_readable"
    quality = _quality(PipelineReport.model_validate(data))
    detail = quality.breakdown.dimensions["contact_integrity"]
    assert detail.score < 100
    assert "contact_readability_limited" in detail.issue_codes


def test_breakdown_is_deterministic_and_does_not_duplicate_penalties() -> None:
    report = make_report()
    first = _quality(report)
    second = _quality(deepcopy(report))
    assert first == second
