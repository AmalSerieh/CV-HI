from __future__ import annotations

import copy
import unittest

from resume_analyzer.target_roles.exceptions import InvalidPipelineInputError
from resume_analyzer.target_roles.pipeline_adapter import PipelineAdapter


class PipelineAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = PipelineAdapter()

    def test_real_legacy_pipeline_shape(self) -> None:
        value = {
            "sections": {"sections": {"summary": {"content": "Backend API specialist"}}},
            "skills": {"all_skills": ["Python", "SQL"], "hard_skills": ["Python"]},
            "experience": {
                "experiences": [
                    {
                        "job_title": "Backend Developer",
                        "company": "Example",
                        "responsibilities": ["Built REST APIs"],
                    }
                ]
            },
            "education": {"education": [{"degree": "BSc Computer Science"}]},
            "projects": {
                "projects": [
                    {
                        "name": "API",
                        "description": "Authentication service",
                        "technologies": ["Postgres"],
                    }
                ]
            },
            "languages": {"languages": [{"language": "English", "proficiency": "Fluent"}]},
            "extracted_resume_text": {"analysis_text": "complete source text"},
        }
        profile = self.adapter.adapt(value)
        self.assertEqual(profile.summary, "Backend API specialist")
        self.assertIn("python", profile.skills)
        self.assertEqual(profile.experience_titles, ("Backend Developer",))
        self.assertIn("Built REST APIs", profile.experience_bullets)
        self.assertEqual(profile.extracted_text, "complete source text")

    def test_schema_entities_shape(self) -> None:
        profile = self.adapter.adapt(
            {
                "entities": {
                    "skills": [{"value": "JS"}],
                    "experience": [
                        {
                            "job_title": "Frontend Developer",
                            "responsibilities": ["Built UI"],
                        }
                    ],
                    "projects": [{"name": "Portal", "technologies": ["React"]}],
                }
            }
        )
        self.assertEqual(profile.skills, ("javascript",))
        self.assertEqual(profile.project_technologies, ("React",))

    def test_skills_dictionary_found_shape(self) -> None:
        profile = self.adapter.adapt({"skills": {"found": ["TS", "ReactJS"]}})
        self.assertEqual(profile.skills, ("typescript", "react"))

    def test_experience_dictionary_mapping_shape(self) -> None:
        profile = self.adapter.adapt(
            {
                "experience": {
                    "first": {"role": "QA Engineer", "bullets": ["Created test cases"]},
                    "second": {
                        "position": "Tester",
                        "achievements": ["Automated testing"],
                    },
                }
            }
        )
        self.assertEqual(profile.experience_titles, ("QA Engineer", "Tester"))

    def test_missing_null_and_unknown_fields(self) -> None:
        profile = self.adapter.adapt({"skills": None, "unknown": {"anything": 1}})
        self.assertEqual(profile.skills, ())
        self.assertEqual(profile.language, "unknown")

    def test_contact_and_metadata_are_preserved(self) -> None:
        profile = self.adapter.adapt(
            {
                "contact": {
                    "name": "Test Candidate",
                    "email": {"value": "candidate@example.invalid"},
                },
                "metadata": {"source": "fixture", "pages": 2},
            }
        )
        self.assertEqual(dict(profile.contact)["name"], "Test Candidate")
        self.assertEqual(dict(profile.metadata)["pages"], "2")

    def test_input_is_not_mutated(self) -> None:
        value = {"skills": {"found": ["JS", "JS"]}, "experience": []}
        original = copy.deepcopy(value)
        self.adapter.adapt(value)
        self.assertEqual(value, original)

    def test_invalid_root_type(self) -> None:
        with self.assertRaisesRegex(InvalidPipelineInputError, "dictionary"):
            self.adapter.adapt([])  # type: ignore[arg-type]

    def test_invalid_recognized_field_type(self) -> None:
        with self.assertRaisesRegex(InvalidPipelineInputError, "skills"):
            self.adapter.adapt({"skills": 42})

    def test_invalid_nested_item_type(self) -> None:
        with self.assertRaisesRegex(InvalidPipelineInputError, r"skills\[1\]"):
            self.adapter.adapt({"skills": ["Python", 7]})


if __name__ == "__main__":
    unittest.main()
