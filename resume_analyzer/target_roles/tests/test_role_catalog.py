from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resume_analyzer.target_roles.exceptions import InvalidCatalogError
from resume_analyzer.target_roles.role_catalog import RoleCatalog


class RoleCatalogTests(unittest.TestCase):
    def test_bundled_catalog_is_valid_and_complete(self) -> None:
        catalog = RoleCatalog.load()
        self.assertGreaterEqual(len(catalog.roles), 25)
        self.assertEqual(len(catalog.role_ids), len(set(catalog.role_ids)))
        self.assertIn("backend_engineer", catalog.role_ids)
        self.assertIn("human_resources_specialist", catalog.role_ids)

    def test_entries_have_names_and_signals(self) -> None:
        for role in RoleCatalog.load().roles:
            with self.subTest(role=role.id):
                self.assertTrue(role.name_en)
                self.assertTrue(role.name_ar)
                self.assertTrue(role.aliases or role.required_signals or role.preferred_signals)

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaisesRegex(InvalidCatalogError, "cannot load"):
                RoleCatalog.load(path)

    def test_duplicate_role_ids_are_rejected(self) -> None:
        entry = {
            "id": "test_role",
            "name_en": "Test",
            "name_ar": "اختبار",
            "aliases": ["Tester"],
            "required_signals": [],
            "preferred_signals": [],
            "experience_keywords": [],
            "project_keywords": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(
                json.dumps({"roles": [entry, entry]}, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(InvalidCatalogError, "duplicate role IDs"):
                RoleCatalog.load(path)

    def test_missing_required_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"roles": [{"id": "broken"}]}), encoding="utf-8")
            with self.assertRaisesRegex(InvalidCatalogError, "missing"):
                RoleCatalog.load(path)


if __name__ == "__main__":
    unittest.main()
