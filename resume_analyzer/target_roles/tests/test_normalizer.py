from __future__ import annotations

import unittest

from resume_analyzer.target_roles.normalizer import SkillAliasResolver, normalize_skill_values
from resume_analyzer.target_roles.text_utils import (
    detect_language,
    normalize_text,
    unique_normalized,
)


class NormalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.aliases = SkillAliasResolver.from_json()

    def test_english_lowercase_whitespace_and_dash(self) -> None:
        self.assertEqual(normalize_text("  ReactJS\u2014UI  "), "reactjs-ui")

    def test_arabic_diacritics_tatweel_and_alef(self) -> None:
        self.assertEqual(normalize_text("إِدَارَةُ الـمَشاريع"), "ادارة المشاريع")

    def test_aliases_are_resolved(self) -> None:
        self.assertEqual(
            normalize_skill_values(["JS", "nodejs", "Postgres", "ML"], self.aliases),
            ("javascript", "node.js", "postgresql", "machine learning"),
        )

    def test_arabic_alias_matches_english_signal(self) -> None:
        self.assertTrue(self.aliases.signal_matches("machine learning", "خبرة في تعلم آلي"))

    def test_null_and_empty_text(self) -> None:
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text("   "), "")

    def test_duplicate_values_are_removed(self) -> None:
        self.assertEqual(unique_normalized(("Python", " python ", "PYTHON")), ("Python",))

    def test_mixed_language_detection(self) -> None:
        self.assertEqual(detect_language(["مهندس Python"]), "mixed")
        self.assertEqual(detect_language(["مهندس بيانات"]), "ar")
        self.assertEqual(detect_language(["Data Analyst"]), "en")

    def test_non_string_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            normalize_text(42)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
