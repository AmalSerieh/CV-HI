from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

from resume_analyzer.extraction.experience_extractor import ExperienceExtractor
from resume_analyzer.extraction.result_quality_refiner import refine_resume_result
from resume_analyzer.extraction.skills_extractor import SkillsExtractor


TEST_FILE = Path(__file__).resolve()
TEST_DIR = TEST_FILE.parent

# Support both valid layouts:
#
# 1. ProjectResume/tests/test_cross_resume_regression_matrix.py
#    ProjectResume/fixtures/
#
# 2. ProjectResume/test_cross_resume_regression_matrix.py
#    ProjectResume/fixtures/
#
# The previous version always used parents[1], which incorrectly resolved
# to <historical-workspace> when the test file was copied to the project root.
_PROJECT_ROOT_CANDIDATES = [
    TEST_DIR,
    TEST_DIR.parent,
]

_FIXTURE_CANDIDATES = []
for candidate_root in _PROJECT_ROOT_CANDIDATES:
    candidate = candidate_root / "fixtures"
    if candidate not in _FIXTURE_CANDIDATES:
        _FIXTURE_CANDIDATES.append(candidate)

FIXTURES = next(
    (
        candidate
        for candidate in _FIXTURE_CANDIDATES
        if candidate.is_dir()
    ),
    _FIXTURE_CANDIDATES[0],
)


def load_json(filename: str) -> dict:
    path = FIXTURES / filename

    if not path.is_file():
        searched = "\n".join(
            f"  - {candidate / filename}"
            for candidate in _FIXTURE_CANDIDATES
        )
        raise FileNotFoundError(
            "Regression fixture was not found.\n"
            f"Missing: {filename}\n"
            "Copy the complete fixtures directory from the patch "
            "next to the test file or to the project root.\n"
            "Searched:\n"
            f"{searched}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def assert_role_payload_preserved(
    before: dict,
    after: dict,
) -> None:
    """Shared attribution is additive; source facts are not removed."""
    assert before.get("job_title") == after.get("job_title")
    assert before.get("company") == after.get("company")
    assert before.get("start_date") == after.get("start_date")
    assert before.get("end_date") == after.get("end_date")
    assert before.get("duration_months") == after.get("duration_months")
    assert before.get("responsibilities") == after.get("responsibilities")
    assert before.get("metrics") == after.get("metrics")


def test_sales_generalization_and_non_destructive_output() -> None:
    original = load_json(
        "sales_current_output.json"
    )
    refined = refine_resume_result(
        copy.deepcopy(original),
        copy_result=False,
    )

    # Previously validated facts stay unchanged.
    assert refined["contact"]["name"] == "Jordan Example"
    assert refined["experience"]["count"] == 8
    assert (
        refined["experience"]["professional_experience_months"]
        == 192
    )
    assert (
        refined["experience"]["volunteer_experience_months"]
        == 0
    )
    assert refined["education"]["count"] == 1
    assert set(
        refined["skills"]["top_technologies"]
    ) == {
        "Microsoft Word",
        "Microsoft Excel",
        "Microsoft PowerPoint",
        "Salesforce",
    }

    for before, after in zip(
        original["experience"]["experiences"],
        refined["experience"]["experiences"],
    ):
        assert_role_payload_preserved(
            before,
            after,
        )

    # Group-level semantics are additive and prevent false attribution.
    groups = refined["experience"]["experience_groups"]

    assert [
        (
            group["group_type"],
            group["role_indexes"],
            group["responsibility_scope"],
        )
        for group in groups
    ] == [
        (
            "employer",
            [4, 5],
            "employer_group",
        ),
        (
            "previous_roles",
            [6, 7, 8],
            "previous_roles_group",
        ),
    ]

    abc_group = groups[0]
    assert abc_group["role_titles"] == [
        "Account Manager",
        "Retail Sales Representative",
    ]
    expected_group_metrics = {
        "100-store chain",
        "10 product representatives",
        "seven new products",
        "$50M",
        "8%",
        "70 new products",
        "75 New Jersey retail stores",
        "20%",
        "5,500 incremental cases shipped to customer",
    }
    assert expected_group_metrics <= set(
        abc_group["metrics"]
    )
    assert "10 product" not in (
        abc_group["metrics"]
    )

    leaked_previous_intro = (
        "Cultivated account management, marketing, "
        "and merchandising skills by building new "
        "business, expanding existing sales"
    )
    assert leaked_previous_intro not in (
        abc_group["responsibilities"]
    )
    assert abc_group["boundary_status"] == (
        "reconciled"
    )
    assert any(
        item["value"] == leaked_previous_intro
        for item in abc_group[
            "excluded_cross_group_responsibilities"
        ]
    )
    assert abc_group["metrics_source"] == (
        "entry_metrics_plus_document_evidence"
    )

    previous_group = groups[1]
    assert previous_group["role_count"] == 3
    assert not previous_group["metrics"]

    for index in (4, 5, 6, 7, 8):
        entry = refined["experience"]["experiences"][
            index - 1
        ]
        assert entry[
            "shared_role_responsibilities"
        ] is True
        assert entry[
            "responsibility_attribution"
        ] == "shared_not_role_specific"

    # No misleading request for metrics on source-summary roles.
    assert not any(
        item.get("type") == "metrics_partial"
        for item in refined["experience"][
            "recommendations"
        ]
    )
    assert not any(
        item.get("type") == "metrics_partial"
        for item in refined["recommendations"]
    )

    # Healthcare is context, not a standalone skill.
    assert "Healthcare" in refined[
        "skills"
    ]["domain_context"]
    assert not any(
        value.casefold() == "healthcare"
        for value in refined[
            "skills"
        ]["hard_skills"]
    )
    assert not any(
        value.casefold() == "healthcare"
        for value in refined[
            "summary"
        ]["top_skills"]
    )


def test_marketing_regression_is_preserved() -> None:
    original = load_json(
        "marketing_current_output.json"
    )
    refined = refine_resume_result(
        copy.deepcopy(original),
        copy_result=False,
    )

    assert refined["contact"]["name"] == "Jordan Example"
    assert refined["experience"]["count"] == 3
    assert (
        refined["experience"]["professional_experience_months"]
        == 240
    )
    assert (
        refined["experience"]["volunteer_experience_months"]
        == 0
    )
    assert refined["education"]["count"] == (
        original["education"]["count"]
    )
    assert set(
        refined["skills"]["top_technologies"]
    ) == set(
        original["skills"]["top_technologies"]
    )

    for before, after in zip(
        original["experience"]["experiences"],
        refined["experience"]["experiences"],
    ):
        assert_role_payload_preserved(
            before,
            after,
        )

    # The marketing resume also has multiple roles at one employer.
    # The new representation clarifies attribution without deleting data.
    assert any(
        group["responsibility_scope"]
        == "employer_group"
        for group in refined[
            "experience"
        ]["experience_groups"]
    )


def test_accounting_regression_is_preserved() -> None:
    original = load_json(
        "accounting_contract_fixture.json"
    )
    refined = refine_resume_result(
        copy.deepcopy(original),
        copy_result=False,
    )

    assert refined["contact"]["name"] == "Mohammed Ali"
    assert refined["experience"]["count"] == 4
    assert (
        refined["experience"]["professional_experience_months"]
        == 25
    )
    assert (
        refined["experience"]["volunteer_experience_months"]
        == 6
    )
    assert refined["education"]["count"] == 2

    # Accounting is a real functional skill and must not be mistaken
    # for industry context.
    assert "Accounting" in refined[
        "skills"
    ]["hard_skills"]
    assert "Accounting" not in refined[
        "skills"
    ]["domain_context"]

    assert set(
        refined["skills"]["top_technologies"]
    ) == {
        "Microsoft Excel",
        "NetSuite",
        "Oracle Database",
        "SAP",
    }


def test_domain_rule_is_exact_not_resume_specific() -> None:
    extractor = SkillsExtractor(
        use_spacy=False,
        use_sbert=False,
    )

    domains, skills = (
        extractor._partition_domain_context([
            "Healthcare",
            "Accounting",
            "Healthcare Analytics",
            "Retail",
        ])
    )

    assert domains == [
        "Healthcare",
        "Retail",
    ]
    assert "Accounting" in skills
    assert "Healthcare Analytics" in skills


def test_shared_group_rule_uses_structure_not_company_names() -> None:
    extractor = ExperienceExtractor(
        use_spacy=False,
        use_sbert=False,
    )

    entries = [
        {
            "job_title": "Regional Manager",
            "company": "Example Holdings",
            "responsibilities_scope":
                "employer_group_shared",
            "employer_group_id":
                "employer_group_generic",
            "responsibilities": [
                "Managed regional operations.",
            ],
            "metrics": [
                "12 locations",
            ],
        },
        {
            "job_title": "Operations Manager",
            "company": "Example Holdings",
            "responsibilities_scope":
                "employer_group_shared",
            "employer_group_id":
                "employer_group_generic",
            "responsibilities": [
                "Managed regional operations.",
            ],
            "metrics": [
                "12 locations",
            ],
        },
    ]

    annotated, groups = (
        extractor._annotate_shared_responsibility_groups(
            entries
        )
    )

    assert len(groups) == 1
    assert groups[0]["company"] == "Example Holdings"
    assert groups[0]["role_indexes"] == [1, 2]
    assert groups[0]["metrics"] == [
        "12 locations",
    ]
    assert all(
        item["shared_role_responsibilities"]
        for item in annotated
    )


def test_generic_boundary_and_metric_enrichment() -> None:
    from resume_analyzer.extraction.result_quality_refiner import (
        _shared_experience_groups,
    )

    shared_narrative = (
        "Built consulting skills across prior roles."
    )

    experience = {
        "experiences": [
            {
                "job_title": "Regional Manager",
                "company": "Example Holdings",
                "responsibilities_scope":
                    "employer_group_shared",
                "employer_group_id":
                    "employer_group_generic",
                "responsibilities": [
                    "Managed a 12-location network.",
                    "Delivered 250 projects.",
                    shared_narrative,
                ],
                "metrics": [
                    "12 location",
                ],
                "raw_text": (
                    "Managed a 12-location network.\n"
                    "Delivered 250 projects.\n"
                    f"{shared_narrative}"
                ),
            },
            {
                "job_title": "Operations Manager",
                "company": "Example Holdings",
                "responsibilities_scope":
                    "employer_group_shared",
                "employer_group_id":
                    "employer_group_generic",
                "responsibilities": [
                    "Managed a 12-location network.",
                    "Delivered 250 projects.",
                    shared_narrative,
                ],
                "metrics": [
                    "12 location",
                ],
                "raw_text": (
                    "Managed a 12-location network.\n"
                    "Delivered 250 projects.\n"
                    f"{shared_narrative}"
                ),
            },
            {
                "job_title": "Advisor",
                "company": "Prior Firm",
                "responsibilities_scope":
                    "prior_roles_shared",
                "shared_responsibility_group_id":
                    "previous_roles_generic",
                "responsibilities": [
                    shared_narrative,
                ],
                "metrics": [],
                "raw_text": shared_narrative,
            },
        ],
        "document_metrics": [
            {
                "value": "12-location network",
                "metric_type": "quantity",
                "evidence": [
                    {
                        "text":
                            "Managed a 12-location network."
                    }
                ],
            },
            {
                "value": "250 projects",
                "metric_type": "quantity",
                "evidence": [
                    {
                        "text":
                            "Delivered 250 projects."
                    }
                ],
            },
        ],
    }

    groups = _shared_experience_groups(
        experience
    )

    employer_group = groups[0]

    assert shared_narrative not in (
        employer_group["responsibilities"]
    )
    assert employer_group["metrics"] == [
        "12-location network",
        "250 projects",
    ]
    assert employer_group["boundary_status"] == (
        "reconciled"
    )


def test_patch_contains_no_resume_specific_hardcoding() -> None:
    sources = "\n".join([
        inspect.getsource(
            SkillsExtractor
        ),
        inspect.getsource(
            ExperienceExtractor
        ),
        inspect.getsource(
            refine_resume_result
        ),
    ]).casefold()

    for forbidden in (
        "jordan example",
        "jordan example",
        "mohammed ali",
        "abc international textiles",
        "mid america automation",
        "example.test",
    ):
        assert forbidden not in sources


def test_refinement_is_idempotent() -> None:
    original = load_json(
        "sales_current_output.json"
    )
    once = refine_resume_result(
        copy.deepcopy(original),
        copy_result=False,
    )
    twice = refine_resume_result(
        copy.deepcopy(once),
        copy_result=False,
    )

    assert once == twice


if __name__ == "__main__":
    test_sales_generalization_and_non_destructive_output()
    test_marketing_regression_is_preserved()
    test_accounting_regression_is_preserved()
    test_domain_rule_is_exact_not_resume_specific()
    test_shared_group_rule_uses_structure_not_company_names()
    test_generic_boundary_and_metric_enrichment()
    test_patch_contains_no_resume_specific_hardcoding()
    test_refinement_is_idempotent()

    print(
        "Cross-resume regression matrix: PASSED"
    )
