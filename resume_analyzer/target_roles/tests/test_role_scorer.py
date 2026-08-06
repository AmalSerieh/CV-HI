from __future__ import annotations

import math
import unittest

from resume_analyzer.target_roles.config import ScoringConfig
from resume_analyzer.target_roles.normalizer import SkillAliasResolver
from resume_analyzer.target_roles.pipeline_adapter import PipelineAdapter
from resume_analyzer.target_roles.role_catalog import RoleCatalog
from resume_analyzer.target_roles.role_scorer import LexicalRoleScorer


class RoleScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.aliases = SkillAliasResolver.from_json()
        self.catalog = RoleCatalog.load()
        self.scorer = LexicalRoleScorer(self.catalog, self.aliases, ScoringConfig())
        self.adapter = PipelineAdapter(self.aliases)

    def test_scores_are_finite_and_bounded(self) -> None:
        profile = self.adapter.adapt({"skills": ["Python", "SQL", "REST API"]})
        for score in self.scorer.score_all(profile):
            self.assertTrue(math.isfinite(score.confidence))
            self.assertGreaterEqual(score.confidence, 0.0)
            self.assertLessEqual(score.confidence, 1.0)

    def test_clear_backend_profile_orders_backend_first(self) -> None:
        profile = self.adapter.adapt(
            {
                "summary": "Backend Engineer",
                "skills": ["Python", "REST API", "SQL", "PostgreSQL", "Docker"],
                "experience": [
                    {
                        "title": "Backend Developer",
                        "bullets": ["Built authentication APIs"],
                    }
                ],
            }
        )
        scores = sorted(
            self.scorer.score_all(profile),
            key=lambda item: (-item.confidence, item.role_id),
        )
        self.assertEqual(scores[0].role_id, "backend_engineer")

    def test_duplicate_signals_and_evidence_are_removed(self) -> None:
        profile = self.adapter.adapt(
            {"skills": ["JS", "javascript", "JS"], "summary": "Frontend Developer"}
        )
        score = self.scorer.score(profile, self.catalog.get("frontend_developer"))
        self.assertEqual(len(score.matched_signals), len(set(score.matched_signals)))
        keys = [(item.source, item.path, item.normalized) for item in score.evidence]
        self.assertEqual(len(keys), len(set(keys)))

    def test_breakdown_is_valid_and_sums_to_confidence(self) -> None:
        profile = self.adapter.adapt({"skills": ["Power BI", "SQL", "DAX", "Dashboard"]})
        score = self.scorer.score(profile, self.catalog.get("business_intelligence_analyst"))
        breakdown = dict(score.score_breakdown)
        self.assertEqual(set(breakdown), set(ScoringConfig().weights))
        self.assertAlmostEqual(sum(breakdown.values()), score.confidence, places=4)

    def test_weak_evidence_does_not_produce_high_confidence(self) -> None:
        profile = self.adapter.adapt({"skills": ["Python"]})
        highest = max(item.confidence for item in self.scorer.score_all(profile))
        self.assertLess(highest, 0.20)

    def test_deterministic_results(self) -> None:
        profile = self.adapter.adapt(
            {"skills": ["SQL", "Excel", "Power BI"], "summary": "Data Analyst"}
        )
        self.assertEqual(self.scorer.score_all(profile), self.scorer.score_all(profile))


if __name__ == "__main__":
    unittest.main()
