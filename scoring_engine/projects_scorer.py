"""
scoring_engine/projects_scorer.py
ProjectsScorer class for evaluating Projects section, proof of work links, and detail quality.
"""

import re

class ProjectsScorer:
    """
    نظام تقييم قسم المشاريع (Projects Evaluation)
    التقييم الكلي: 100 نقطة.
    المراجع: معايير السير الذاتية التقنية (Tech Resume Guidelines)، وأهمية إثبات العمل (Proof of Work).
    """

    def __init__(self, parsed_json: dict):
        self.data = parsed_json or {}

        # استخراج بيانات المشاريع
        self.projects_data = self.data.get("projects", {})
        if isinstance(self.projects_data, list):
            self.projects_list = self.projects_data
            self.raw_text = str(self.projects_list)
        elif isinstance(self.projects_data, dict):
            self.projects_list = self.projects_data.get("projects", [])
            self.raw_text = str(self.projects_data.get("raw_projects_text", ""))
        else:
            self.projects_list = []
            self.raw_text = ""

        self.project_count = len(self.projects_list) or (1 if len(self.raw_text.strip()) > 10 else 0)

        # النتائج
        self.total_score = 0.0
        self.details = {}
        self.applied_deductions = []
        self.missing_elements = []

    def _eval_presence_and_volume(self):
        score = 0.0
        if self.project_count >= 2:
            score = 40.0
        elif self.project_count == 1:
            score = 20.0

        self.total_score += score
        self.details["Presence & Volume"] = {
            "score": score,
            "max": 40.0,
            "projects_estimated_count": self.project_count,
            "status": "Excellent" if score == 40 else "Good" if score > 0 else "Missing"
        }

    def _eval_proof_of_work(self):
        score = 0.0
        links_found = []

        if self.raw_text:
            urls = re.findall(r'(https?://\S+|www\.\S+|github\.com/\S+)', self.raw_text.lower())
            if urls:
                score = 30.0
                links_found = urls
            else:
                self.applied_deductions.append({
                    "section": "Projects",
                    "reason": "Projects mentioned but NO links (GitHub, Live URL) provided to verify the work.",
                    "penalty": -15.0,
                    "reference": "Tech Resume Guidelines (Proof of Work)"
                })

        self.total_score += score
        self.details["Proof of Work (Links)"] = {
            "score": score,
            "max": 30.0,
            "links_found": list(set(links_found)),
            "status": "Excellent" if score == 30 else "Needs Improvement"
        }

    def _eval_description_quality(self):
        score = 0.0
        word_count = len(self.raw_text.split())

        if word_count > 40:
            score = 30.0
        elif word_count > 15:
            score = 15.0
        elif word_count > 0:
            score = 5.0

        self.total_score += score
        self.details["Description Quality & Details"] = {
            "score": score,
            "max": 30.0,
            "estimated_word_count": word_count,
            "status": "Excellent" if score == 30 else "Good" if score > 10 else "Poor"
        }

    def generate_report(self) -> dict:
        if not self.raw_text.strip():
            self.missing_elements.append("Key Projects & Portfolio Showcase")
            self.applied_deductions.append({
                "section": "Projects",
                "reason": "No Projects section detected.",
                "penalty": -20.0,
                "reference": "Tech Resume Guidelines (Proof of Work)"
            })
            return {
                "section_name": "Projects Evaluation",
                "section_name_ar": "المشاريع والأعمال",
                "score": 0.0,
                "max_score": 100.0,
                "percentage": 0,
                "status": "Needs Improvement",
                "status_ar": "يحتاج تحسين",
                "evaluation_axes": {},
                "missing_elements": self.missing_elements,
                "penalties_applied": self.applied_deductions,
                "academic_references": [
                    "[Tech Industry Standards] Projects are crucial substitutes for experience for candidates."
                ]
            }

        self._eval_presence_and_volume()
        self._eval_proof_of_work()
        self._eval_description_quality()

        self.total_score = max(0.0, self.total_score)

        return {
            "section_name": "Projects Evaluation",
            "section_name_ar": "المشاريع والأعمال",
            "score": round(self.total_score, 1),
            "max_score": 100.0,
            "percentage": int(self.total_score),
            "status": "Excellent" if self.total_score >= 80 else "Good" if self.total_score >= 50 else "Needs Improvement",
            "status_ar": "ممتاز" if self.total_score >= 80 else "جيد" if self.total_score >= 50 else "يحتاج تحسين",
            "evaluation_axes": self.details,
            "missing_elements": self.missing_elements,
            "penalties_applied": self.applied_deductions,
            "academic_references": [
                "[Tech Resume Standards] Proof of Work: Projects must include repository links (GitHub/GitLab) or live URLs.",
                "[Content Guidelines] Projects must have adequate descriptions rather than just titles."
            ]
        }
