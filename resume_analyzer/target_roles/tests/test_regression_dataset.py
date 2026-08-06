from __future__ import annotations

import json
import unittest
from typing import ClassVar

from resume_analyzer.target_roles.exceptions import InvalidPipelineInputError
from resume_analyzer.target_roles.target_role_suggester import TargetRoleSuggester
from resume_analyzer.target_roles.tests.helpers import fixture_paths, suggested_roles


class RegressionDatasetTests(unittest.TestCase):
    suggester: ClassVar[TargetRoleSuggester]

    @classmethod
    def setUpClass(cls) -> None:
        cls.suggester = TargetRoleSuggester()

    def test_dataset_has_required_language_and_edge_case_counts(self) -> None:
        cases = [json.loads(path.read_text(encoding="utf-8")) for path in fixture_paths()]
        counts = {
            language: sum(case["language"] == language for case in cases)
            for language in ("en", "ar", "mixed")
        }
        self.assertGreaterEqual(len(cases), 20)
        self.assertGreaterEqual(counts["en"], 7)
        self.assertGreaterEqual(counts["ar"], 7)
        self.assertGreaterEqual(counts["mixed"], 3)
        incomplete = sum(
            case["should_be_insufficient"]
            or "only_" in case["case_id"]
            or "no_skills" in case["case_id"]
            for case in cases
        )
        self.assertGreaterEqual(incomplete, 3)

    def test_every_fixture(self) -> None:
        for path in fixture_paths():
            case = json.loads(path.read_text(encoding="utf-8"))
            case_id = case["case_id"]
            with self.subTest(case_id=case_id):
                if case.get("expected_error"):
                    with self.assertRaises(InvalidPipelineInputError, msg=case_id):
                        self.suggester.suggest(case["input"])
                    continue
                result = self.suggester.suggest(case["input"], top_k=3)
                target = result["target_role"]
                self.assertEqual(
                    target["insufficient_evidence"],
                    case["should_be_insufficient"],
                    case_id,
                )
                if case["should_be_insufficient"]:
                    self.assertIsNone(target["primary"], case_id)
                    continue
                roles = suggested_roles(result)
                role_ids = [item["role_id"] for item in roles]
                if case.get("strict_top1"):
                    self.assertEqual(role_ids[0], case["strict_top1"], case_id)
                else:
                    self.assertIn(role_ids[0], case["expected_top_roles"], case_id)
                self.assertTrue(set(role_ids).intersection(case["expected_top_roles"]), case_id)
                primary_evidence = {item["value"] for item in roles[0]["evidence"]}
                for expected in case["required_evidence"]:
                    self.assertIn(
                        expected,
                        primary_evidence,
                        f"{case_id}: missing evidence {expected!r}",
                    )


if __name__ == "__main__":
    unittest.main()
