from __future__ import annotations

import unittest

from resume_analyzer.target_roles.target_role_suggester import suggest_target_roles
from resume_analyzer.target_roles.tests.helpers import load_fixture


class ArabicSupportTests(unittest.TestCase):
    def test_arabic_machine_learning_role(self) -> None:
        case = load_fixture("arabic/machine_learning_engineer.json")
        self.assertEqual(
            suggest_target_roles(case["input"])["target_role"]["primary"]["role_id"],
            "machine_learning_engineer",
        )

    def test_arabic_nlp_role(self) -> None:
        case = load_fixture("arabic/nlp_engineer.json")
        self.assertEqual(
            suggest_target_roles(case["input"])["target_role"]["primary"]["role_id"],
            "nlp_engineer",
        )

    def test_arabic_general_business_role(self) -> None:
        case = load_fixture("arabic/customer_support.json")
        self.assertEqual(
            suggest_target_roles(case["input"])["target_role"]["primary"]["role_id"],
            "customer_support_representative",
        )

    def test_arabic_with_english_terms(self) -> None:
        case = load_fixture("mixed/arabic_english_ai.json")
        target = suggest_target_roles(case["input"])["target_role"]
        self.assertEqual(target["primary"]["role_id"], "ai_engineer")
        self.assertEqual(target["language"], "mixed")


if __name__ == "__main__":
    unittest.main()
