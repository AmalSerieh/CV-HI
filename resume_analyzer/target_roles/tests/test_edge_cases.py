from __future__ import annotations

import unittest

from resume_analyzer.target_roles.exceptions import InvalidPipelineInputError
from resume_analyzer.target_roles.target_role_suggester import suggest_target_roles


class EdgeCaseTests(unittest.TestCase):
    def test_null_fields_are_safe(self) -> None:
        target = suggest_target_roles({"summary": None, "skills": None, "experience": None})[
            "target_role"
        ]
        self.assertTrue(target["insufficient_evidence"])

    def test_invalid_field_type_is_clear(self) -> None:
        with self.assertRaisesRegex(InvalidPipelineInputError, "skills"):
            suggest_target_roles({"skills": 3})

    def test_one_weak_signal_is_insufficient(self) -> None:
        self.assertTrue(
            suggest_target_roles({"skills": ["Python"]})["target_role"]["insufficient_evidence"]
        )

    def test_unknown_fields_do_not_crash(self) -> None:
        target = suggest_target_roles({"future_schema_field": {"nested": [1, 2]}})["target_role"]
        self.assertTrue(target["insufficient_evidence"])

    def test_invalid_top_k(self) -> None:
        with self.assertRaisesRegex(ValueError, "top_k"):
            suggest_target_roles({}, top_k=0)


if __name__ == "__main__":
    unittest.main()
