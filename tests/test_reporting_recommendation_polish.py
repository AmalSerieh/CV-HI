from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path

from resume_analyzer.extraction.reporting_policy import print_resume_pipeline_report
from resume_analyzer.extraction.result_quality_refiner import refine_resume_result

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


def load_template() -> dict:
    return json.loads(
        (
            FIXTURES
            / "accounting_template_latest_output.json"
        ).read_text(
            encoding="utf-8"
        )
    )


def test_placeholder_recommendations_are_precise() -> None:
    result = refine_resume_result(
        copy.deepcopy(load_template()),
        copy_result=False,
    )

    messages = [
        str(item.get("message") or "")
        for item in result.get(
            "recommendations",
            [],
        )
    ]

    assert not any(
        "is missing: duration" in message
        for message in messages
    )
    assert not any(
        "graduation date was not provided"
        in message.casefold()
        for message in messages
    )
    assert (
        'Replace the graduation date placeholder '
        '"Month 20XX" with the actual graduation date.'
        in messages
    )
    assert (
        "Replace all 9 detected date placeholders "
        "with actual dates."
        in messages
    )


def test_placeholder_duration_warnings_are_resolved() -> None:
    result = refine_resume_result(
        copy.deepcopy(load_template()),
        copy_result=False,
    )

    warnings = set(
        result["extraction_quality"].get(
            "warnings",
            [],
        )
    )
    resolved = set(
        result["extraction_quality"].get(
            "resolved_warnings",
            [],
        )
    )

    for index in (1, 2, 3, 4):
        warning = (
            f"experience_{index}"
            "_duration_unresolved"
        )
        assert warning not in warnings


def test_console_report_uses_clear_labels() -> None:
    result = refine_resume_result(
        copy.deepcopy(load_template()),
        copy_result=False,
    )

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        print_resume_pipeline_report(result)

    output = stream.getvalue()

    assert "🏆 Resume Score: 60/100" in output
    assert (
        "🔎 Extraction Quality: "
        "needs_review | 91/100"
        in output
    )
    assert (
        "📋 Source Readiness:    "
        "template_incomplete | 35/100"
        in output
    )
    assert "Professional Roles:   4" in output
    assert "Volunteer Roles:      1" in output
    assert "Total Experience Entries: 5" in output
    assert (
        "Professional Duration: "
        "not computable — placeholder dates"
        in output
    )
    assert (
        "Email:      email@email.com (placeholder)"
        in output
    )
    assert (
        "Phone:      555-555-5555 (placeholder)"
        in output
    )
    assert (
        "Missing Standalone Sections: ['skills']"
        in output
    )
    assert (
        "Validated Volunteer Duration: 2 months"
        in output
    )
    assert "Missing Required:" not in output
    assert "Total Validated Duration: 2 months" not in output
    assert "Experience Count:" not in output
    assert "Professional Experience: 0 months" not in output
    assert "Data Quality:" not in output


def test_real_contact_values_are_not_marked_placeholder() -> None:
    result = refine_resume_result(
        copy.deepcopy(load_template()),
        copy_result=False,
    )
    result["contact"]["email_status"] = "validated"
    result["contact"]["phone_status"] = "validated"
    result["summary"]["email"] = "candidate@example.org"
    result["summary"]["phone"] = "+1 250 555 0101"

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        print_resume_pipeline_report(result)

    output = stream.getvalue()

    assert (
        "Email:      candidate@example.org"
        in output
    )
    assert (
        "Email:      candidate@example.org "
        "(placeholder)"
        not in output
    )
    assert (
        "Phone:      +1 250 555 0101"
        in output
    )
    assert (
        "Phone:      +1 250 555 0101 "
        "(placeholder)"
        not in output
    )


def test_normal_professional_duration_keeps_total_label() -> None:
    result = refine_resume_result(
        copy.deepcopy(load_template()),
        copy_result=False,
    )
    result["summary"][
        "professional_duration_status"
    ] = "computed"
    result["summary"][
        "professional_experience_months"
    ] = 36
    result["summary"][
        "volunteer_experience_months"
    ] = 2
    result["summary"][
        "total_validated_experience_months"
    ] = 38

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        print_resume_pipeline_report(result)

    output = stream.getvalue()

    assert "Total Validated Duration: 38 months" in output
    assert "Validated Volunteer Duration:" not in output


def test_missing_sections_label_is_structurally_accurate() -> None:
    result = refine_resume_result(
        copy.deepcopy(load_template()),
        copy_result=False,
    )

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        print_resume_pipeline_report(result)

    output = stream.getvalue()

    assert (
        "Missing Standalone Sections: ['skills']"
        in output
    )
    assert "Missing Required:" not in output


if __name__ == "__main__":
    test_placeholder_recommendations_are_precise()
    test_placeholder_duration_warnings_are_resolved()
    test_console_report_uses_clear_labels()
    test_real_contact_values_are_not_marked_placeholder()
    test_normal_professional_duration_keeps_total_label()
    test_missing_sections_label_is_structurally_accurate()

    print(
        "Reporting and recommendation polish: PASSED"
    )
