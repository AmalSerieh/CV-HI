"""
scoring_engine/master_scorer.py
Central Master Compiler incorporating academic weights across all 7 evaluation modules.
"""

from .contact_scorer import ContactScorer
from .section_scorer import SectionScorer
from .summary_scorer import SummaryScorer
from .projects_scorer import ProjectsScorer
from .skills_scorer import SkillsScorer
from .experience_scorer import ExperienceScorer
from .achievements_scorer import AchievementsScorer

class MasterScorer:
    """
    النظام المركزي لتجميع التقييمات (Master Compiler)
    يقوم بجمع التقارير المستقلة وتطبيق نظام الأوزان الأكاديمي لاستخراج النتيجة النهائية.
    Contact: 5%
    Section: 5%
    Summary: 10%
    Projects: 10%
    Skills: 20%
    Experience: 25%
    Achievements: 25%
    """

    WEIGHTS = {
        "Contact": 0.05,
        "Section": 0.05,
        "Summary": 0.10,
        "Projects": 0.10,
        "Skills": 0.20,
        "Experience": 0.25,
        "Achievements": 0.25
    }

    def __init__(self, parsed_json: dict):
        self.parsed_json = parsed_json or {}

    def generate_report(self) -> dict:
        contact_res = ContactScorer(self.parsed_json).generate_report()
        section_res = SectionScorer(self.parsed_json).generate_report()
        summary_res = SummaryScorer(self.parsed_json).generate_report()
        projects_res = ProjectsScorer(self.parsed_json).generate_report()
        skills_res = SkillsScorer(self.parsed_json).generate_report()
        exp_res = ExperienceScorer(self.parsed_json).generate_report()
        ach_res = AchievementsScorer(self.parsed_json).generate_report()

        raw_reports = {
            "Contact": contact_res,
            "Section": section_res,
            "Summary": summary_res,
            "Projects": projects_res,
            "Skills": skills_res,
            "Experience": exp_res,
            "Achievements": ach_res
        }

        final_score = 0.0
        breakdown = {}

        for module_name, weight in self.WEIGHTS.items():
            report = raw_reports[module_name]
            raw_score = report.get("score", 0.0)
            max_score = report.get("max_score", 100.0)

            normalized_score = (raw_score / max_score) * 100.0 if max_score > 0 else 0.0
            points_earned = normalized_score * weight
            final_score += points_earned

            mod_info = {
                "score": raw_score,
                "raw_score": raw_score,
                "max_score": max_score,
                "percentage": round(normalized_score),
                "normalized_100": round(normalized_score, 1),
                "weight_percentage": f"{int(weight * 100)}%",
                "points_earned": round(points_earned, 1),
                "status": report.get("status"),
                "status_ar": report.get("status_ar"),
                "academic_references": report.get("academic_references", [])
            }
            breakdown[module_name.lower()] = mod_info
            breakdown[module_name.capitalize()] = mod_info

        overall_score = round(final_score, 1)

        all_penalties = (
            contact_res.get("penalties_applied", [])
            + section_res.get("penalties_applied", [])
            + summary_res.get("penalties_applied", [])
            + projects_res.get("penalties_applied", [])
            + skills_res.get("penalties_applied", [])
            + exp_res.get("penalties_applied", [])
            + ach_res.get("penalties_applied", [])
        )

        all_missing = (
            contact_res.get("missing_elements", [])
            + section_res.get("missing_elements", [])
            + summary_res.get("missing_elements", [])
            + projects_res.get("missing_elements", [])
            + skills_res.get("missing_elements", [])
            + exp_res.get("missing_elements", [])
            + ach_res.get("missing_elements", [])
        )

        status_en = "Excellent" if overall_score >= 85 else "Good" if overall_score >= 70 else "Fair" if overall_score >= 50 else "Needs Improvement"
        status_ar = "ممتاز" if overall_score >= 85 else "جيد" if overall_score >= 70 else "متوسط" if overall_score >= 50 else "يحتاج تحسين"

        return {
            "overall_score": overall_score,
            "max_score": 100.0,
            "overall_status": status_en,
            "overall_status_ar": status_ar,
            "score_breakdown": breakdown,
            "detailed_reports": raw_reports,
            "all_penalties": all_penalties,
            "all_missing_elements": all_missing,
            "system_message": "Master API Response generated successfully."
        }
