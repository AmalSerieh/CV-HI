from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _contact_display(
    value: Any,
    status: Any,
) -> str:
    """
    Show source placeholders explicitly without changing stored data.
    """
    display = str(value) if value is not None else "None"
    normalized_status = str(
        status or ""
    ).strip().casefold()

    if normalized_status in {
        "placeholder",
        "source_placeholder",
        "unverified_or_placeholder",
    }:
        return f"{display} (placeholder)"

    return display


def _duration_display(
    months: Any,
    status: Any,
) -> str:
    normalized_status = str(
        status or ""
    ).strip().casefold()

    if normalized_status == (
        "not_computable_placeholder_dates"
    ):
        return "not computable — placeholder dates"

    if normalized_status == (
        "not_computable_template_placeholders"
    ):
        return "not computable — template role placeholders"

    if normalized_status in {
        "not_provided",
        "not_provided_in_source",
    }:
        return "dates not provided"

    if months is None:
        return "not available"

    return f"{_as_int(months)} months"


def print_resume_pipeline_report(
    result: dict,
) -> None:
    """
    Print a source-aware report without changing analysis data.

    The reporter distinguishes:
    - extraction quality;
    - source readiness;
    - professional role count;
    - volunteer role count;
    - duration that cannot be computed because dates are placeholders.
    """
    if not result.get("success"):
        print("\n❌ PIPELINE FAILED")
        print(result.get("error"))
        return

    summary = _as_dict(result.get("summary"))
    contact = _as_dict(result.get("contact"))
    scores = _as_dict(result.get("scores"))
    module_scores = _as_dict(
        scores.get("module_scores")
    )
    applicability = _as_dict(
        scores.get("module_applicability")
    )
    source_readiness = _as_dict(
        result.get("source_readiness")
    )
    quality = _as_dict(
        result.get("extraction_quality")
    )

    print("\n" + "=" * 80)
    print(
        "                    "
        "✅ RESUME PIPELINE REPORT"
    )
    print("=" * 80)

    print(
        f"\n📄 File:          "
        f"{_as_dict(result.get('file')).get('name')}"
    )
    print(
        f"⏱️ Time:          "
        f"{result.get('processing_time_seconds')} sec"
    )

    completeness = scores.get(
        "resume_completeness_score"
    )
    source_status = str(
        source_readiness.get("status")
        or "ready"
    )
    score_label = (
        "Resume Score"
        if source_status != "ready"
        else "Resume Completeness"
    )

    if completeness is None:
        print(
            f"🏆 {score_label}: "
            "needs review (not trusted)"
        )
    else:
        print(
            f"🏆 {score_label}: "
            f"{completeness}/100"
        )

    print(
        "🎯 ATS Score:      "
        "not calculated "
        "(job description required)"
    )

    if not scores.get("trusted", False):
        print(
            f"⚠️ Score Status:  "
            f"{scores.get('status')} "
            f"(raw="
            f"{scores.get('raw_resume_completeness_score')}, "
            f"cap={scores.get('score_cap')})"
        )

    print(
        "🔎 Extraction Quality: "
        f"{quality.get('status', 'unknown')} | "
        f"{quality.get('score', 0)}/100"
    )

    if source_readiness:
        print(
            "📋 Source Readiness:    "
            f"{source_status} | "
            f"{source_readiness.get('score', 0)}/100"
        )

    extraction = _as_dict(
        result.get("text_extraction")
    )
    print(
        "🧾 Extraction:    "
        f"{extraction.get('engine', 'unknown')} | "
        f"{extraction.get('layout', 'unknown')} | "
        "quality "
        f"{extraction.get('quality_score', 0)}/100"
    )

    style = _as_dict(result.get("document_style"))
    assets = _as_dict(result.get("document_assets"))
    duplicate = _as_dict(result.get("duplicate_analysis"))
    profile = _as_dict(result.get("document_profile"))
    ats_structure = _as_dict(result.get("ats_structure"))

    if style or assets or duplicate or profile:
        print("\n🎨 Visual / ATS Structure:")
        print("-" * 80)
        print(
            "   Colors Detected:       "
            + (
                f"yes ({style.get('chromatic_color_count', 0)} chromatic)"
                if style.get("has_color")
                else "no"
            )
        )
        print(
            "   Embedded Images:       "
            f"{_as_int(assets.get('image_count'))}"
        )
        print(
            "   Candidate Photo:       "
            + ("detected" if assets.get("candidate_photo_detected") else "not detected")
        )
        print(
            "   Contact/Decorative Icons: "
            f"{_as_int(assets.get('icon_count'))}"
        )
        text_box_count = _as_int(
            assets.get(
                "text_box_count"
            )
        )
        text_box_text_blocks = _as_int(
            assets.get(
                "text_box_text_block_count"
            )
        )
        print(
            "   Text Boxes:            "
            f"{text_box_count}"
            + (
                " containers "
                f"({text_box_text_blocks} text blocks)"
                if (
                    text_box_text_blocks
                    and text_box_text_blocks
                    != text_box_count
                )
                else ""
            )
        )
        print(
            "   Duplicate Content:     "
            f"{float(duplicate.get('duplicate_ratio', 0) or 0) * 100:.1f}%"
        )
        print(
            "   Template Status:       "
            f"{profile.get('document_type', 'resume')}"
        )
        print(
            "   ATS Visual Risk:       "
            f"{ats_structure.get('risk_level', 'none')}"
        )

    print("\n📊 Module Scores:")
    print("-" * 80)

    for module, score in module_scores.items():
        if applicability.get(module, True):
            print(
                f"   {module.capitalize():12}: "
                f"{score}/100"
            )
        else:
            print(
                f"   {module.capitalize():12}: "
                "optional / not present"
            )

    print("\n👤 Candidate Summary:")
    print("-" * 80)
    print(
        "   Name:       "
        + _contact_display(
            summary.get("name"),
            contact.get("name_status"),
        )
    )
    print(
        "   Email:      "
        + _contact_display(
            summary.get("email"),
            contact.get("email_status"),
        )
    )
    print(
        "   Phone:      "
        + _contact_display(
            summary.get("phone"),
            contact.get("phone_status"),
        )
    )
    print(
        "   Location:   "
        + _contact_display(
            summary.get("location"),
            contact.get("location_status"),
        )
    )
    print(
        f"   Job Title:  "
        f"{summary.get('job_title')}"
    )

    print("\n🧩 Content Summary:")
    print("-" * 80)
    print(
        "   Sections Found:        "
        f"{summary.get('sections_found')}"
    )
    print(
        "   Missing Standalone Sections: "
        f"{summary.get('missing_required_sections')}"
    )

    has_role_breakdown = (
        "professional_role_count" in summary
        or "volunteer_role_count" in summary
    )

    if has_role_breakdown:
        professional_roles = _as_int(
            summary.get("professional_role_count")
        )
        volunteer_roles = _as_int(
            summary.get("volunteer_role_count")
        )
        total_entries = _as_int(
            summary.get(
                "experience_count",
                professional_roles
                + volunteer_roles,
            )
        )

        print(
            "   Professional Roles:   "
            f"{professional_roles}"
        )
        print(
            "   Volunteer Roles:      "
            f"{volunteer_roles}"
        )
        print(
            "   Total Experience Entries: "
            f"{total_entries}"
        )
        placeholder_slots = _as_int(
            (
                result.get(
                    "experience",
                    {},
                )
                or {}
            ).get(
                "placeholder_role_slot_count"
            )
        )
        if placeholder_slots:
            print(
                "   Placeholder Role Slots: "
                f"{placeholder_slots}"
            )
    else:
        print(
            "   Experience Count:      "
            f"{summary.get('experience_count')}"
        )

    print(
        "   Professional Duration: "
        + _duration_display(
            summary.get(
                "professional_experience_months"
            ),
            summary.get(
                "professional_duration_status"
            ),
        )
    )

    volunteer_count = _as_int(
        summary.get(
            "volunteer_activity_count",
            summary.get(
                "volunteer_role_count",
                summary.get(
                    "undated_volunteer_activity_count",
                    0,
                ),
            ),
        )
    )
    volunteer_months = summary.get(
        "volunteer_experience_months"
    )
    volunteer_status = summary.get(
        "volunteer_date_status"
    )

    print(
        "   Volunteer Activities:  "
        f"{volunteer_count}"
    )
    print(
        "   Volunteer Duration:    "
        + _duration_display(
            volunteer_months,
            (
                volunteer_status
                if (
                    not volunteer_months
                    and volunteer_count
                )
                else None
            ),
        )
    )

    print(
        "   Leadership Experience: "
        f"{_as_int(summary.get('leadership_experience_months'))} "
        "months"
    )
    professional_duration_status = str(
        summary.get("professional_duration_status")
        or ""
    ).strip().casefold()
    validated_months = _as_int(
        summary.get(
            "total_validated_experience_months"
        )
    )
    volunteer_validated_months = _as_int(
        summary.get(
            "volunteer_experience_months"
        )
    )

    validated_label = (
        "Validated Volunteer Duration"
        if (
            professional_duration_status
            in {
                "not_computable_placeholder_dates",
                "not_computable_template_placeholders",
            }
            and volunteer_validated_months > 0
            and validated_months
            == volunteer_validated_months
        )
        else "Total Validated Duration"
    )

    print(
        f"   {validated_label}: "
        f"{validated_months} months"
    )
    print(
        "   Education Count:       "
        f"{summary.get('education_count')}"
    )
    print(
        "   Projects Count:        "
        f"{summary.get('projects_count')}"
    )
    print(
        "   Languages Count:       "
        f"{summary.get('languages_count')}"
    )

    if summary.get("top_skills"):
        print(
            "   Top Skills:            "
            + ", ".join(
                summary.get("top_skills")[:12]
            )
        )

    if summary.get("top_technologies"):
        print(
            "   Top Technologies:      "
            + ", ".join(
                summary.get(
                    "top_technologies"
                )[:12]
            )
        )

    recommendations = result.get(
        "recommendations",
        [],
    )

    if recommendations:
        print("\n💡 Recommendations:")
        print("-" * 80)

        for rec in recommendations[:15]:
            icon = {
                "critical": "❌",
                "high": "❌",
                "medium": "⚠️",
                "low": "ℹ️",
                "info": "ℹ️",
                "good": "✅",
            }.get(
                rec.get("severity"),
                "•",
            )

            print(
                f"   {icon} "
                f"[{rec.get('area')}] "
                f"{rec.get('message')}"
            )

    if result.get("errors"):
        print("\n⚠️ Non-blocking Errors:")
        print("-" * 80)

        for module, error in (
            result["errors"].items()
        ):
            print(
                f"   - {module}: "
                f"{error.get('type')} - "
                f"{error.get('message')}"
            )

    if result.get("exported_json"):
        print(
            "\n💾 Exported JSON: "
            f"{result.get('exported_json')}"
        )

    print("\n" + "=" * 80)
