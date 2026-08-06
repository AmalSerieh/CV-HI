from __future__ import annotations

import json
import unittest

from resume_analyzer.target_roles.role_catalog import RoleCatalog
from resume_analyzer.target_roles.target_role_suggester import suggest_target_roles
from resume_analyzer.target_roles.tests.helpers import load_fixture, suggested_roles


class OutputContractTests(unittest.TestCase):
    def test_output_is_strict_json_serializable(self) -> None:
        case = load_fixture("arabic/data_analyst.json")
        result = suggest_target_roles(case["input"])
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        self.assertIn("محلل بيانات", encoded)

    def test_required_keys_and_types(self) -> None:
        target = suggest_target_roles(load_fixture("english/backend_engineer.json")["input"])[
            "target_role"
        ]
        self.assertEqual(
            set(target),
            {
                "primary",
                "alternatives",
                "insufficient_evidence",
                "method",
                "language",
                "warnings",
            },
        )
        self.assertIsInstance(target["alternatives"], list)
        self.assertIsInstance(target["warnings"], list)

    def test_roles_and_confidences_are_valid(self) -> None:
        result = suggest_target_roles(
            load_fixture("english/full_stack_developer.json")["input"], top_k=10
        )
        role_ids = set(RoleCatalog.load().role_ids)
        for role in suggested_roles(result):
            self.assertIn(role["role_id"], role_ids)
            self.assertGreaterEqual(role["confidence"], 0.0)
            self.assertLessEqual(role["confidence"], 1.0)
            self.assertIsInstance(role["score_breakdown"], dict)
            self.assertIsInstance(role["evidence"], list)

    def test_insufficient_contract(self) -> None:
        target = suggest_target_roles({})["target_role"]
        self.assertIsNone(target["primary"])
        self.assertEqual(target["alternatives"], [])
        self.assertTrue(target["warnings"])


if __name__ == "__main__":
    unittest.main()
