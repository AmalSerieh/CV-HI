from __future__ import annotations

import copy
import unittest

from resume_analyzer.target_roles.target_role_suggester import (
    TargetRoleSuggester,
    suggest_target_roles,
)
from resume_analyzer.target_roles.tests.helpers import load_fixture, suggested_roles


class TargetRoleSuggesterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suggester = TargetRoleSuggester()

    def test_english_backend(self) -> None:
        case = load_fixture("english/backend_engineer.json")
        result = self.suggester.suggest(case["input"])
        self.assertEqual(result["target_role"]["primary"]["role_id"], "backend_engineer")

    def test_arabic_ai(self) -> None:
        case = load_fixture("arabic/ai_engineer.json")
        result = self.suggester.suggest(case["input"])
        self.assertEqual(result["target_role"]["primary"]["role_id"], "ai_engineer")
        self.assertIn(result["target_role"]["language"], {"ar", "mixed"})

    def test_mixed_full_stack(self) -> None:
        case = load_fixture("mixed/full_stack_mixed.json")
        result = self.suggester.suggest(case["input"])
        self.assertEqual(result["target_role"]["primary"]["role_id"], "full_stack_developer")

    def test_accounting(self) -> None:
        case = load_fixture("english/accountant.json")
        self.assertEqual(
            self.suggester.suggest(case["input"])["target_role"]["primary"]["role_id"],
            "accountant",
        )

    def test_configurable_top_k(self) -> None:
        case = load_fixture("english/backend_engineer.json")
        result = self.suggester.suggest(case["input"], top_k=1)
        self.assertEqual(len(suggested_roles(result)), 1)

    def test_minimum_confidence(self) -> None:
        result = self.suggester.suggest({"skills": ["Python", "SQL"]}, minimum_confidence=0.95)
        self.assertTrue(result["target_role"]["insufficient_evidence"])

    def test_no_input_mutation(self) -> None:
        value = {
            "skills": ["JS", "ReactJS"],
            "experience": [{"title": "Frontend Developer"}],
        }
        original = copy.deepcopy(value)
        suggest_target_roles(value)
        self.assertEqual(value, original)

    def test_no_duplicate_roles(self) -> None:
        case = load_fixture("english/multi_domain.json")
        roles = [
            item["role_id"]
            for item in suggested_roles(self.suggester.suggest(case["input"], top_k=10))
        ]
        self.assertEqual(len(roles), len(set(roles)))

    def test_empty_resume_is_insufficient(self) -> None:
        target = self.suggester.suggest({})["target_role"]
        self.assertTrue(target["insufficient_evidence"])
        self.assertIsNone(target["primary"])

    def test_stable_output(self) -> None:
        case = load_fixture("english/data_analyst.json")
        self.assertEqual(
            self.suggester.suggest(case["input"]), self.suggester.suggest(case["input"])
        )


if __name__ == "__main__":
    unittest.main()
