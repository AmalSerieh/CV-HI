from __future__ import annotations

import copy
import unittest

from resume_analyzer.target_roles.integration import attach_target_role
from resume_analyzer.target_roles.target_role_suggester import suggest_target_roles


class IntegrationTests(unittest.TestCase):
    def test_attach_preserves_fields_and_inputs(self) -> None:
        pipeline = {
            "success": True,
            "skills": ["SQL", "Excel", "Power BI"],
            "custom": {"keep": 1},
        }
        suggestion = suggest_target_roles(pipeline)
        original_pipeline = copy.deepcopy(pipeline)
        original_suggestion = copy.deepcopy(suggestion)
        merged = attach_target_role(pipeline, suggestion)
        self.assertEqual(merged["custom"], {"keep": 1})
        self.assertIn("target_role", merged)
        self.assertEqual(pipeline, original_pipeline)
        self.assertEqual(suggestion, original_suggestion)

    def test_existing_target_role_is_replaced_on_copy(self) -> None:
        merged = attach_target_role({"target_role": {"old": True}}, {"target_role": {"new": True}})
        self.assertEqual(merged["target_role"], {"new": True})

    def test_unwrapped_target_payload_is_supported(self) -> None:
        merged = attach_target_role({"success": True}, {"primary": None, "alternatives": []})
        self.assertIsNone(merged["target_role"]["primary"])


if __name__ == "__main__":
    unittest.main()
