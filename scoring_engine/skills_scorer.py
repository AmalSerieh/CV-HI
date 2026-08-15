"""
scoring_engine/skills_scorer.py
SkillsScorer class for intrinsic skills quality evaluation.
"""

import re

class SkillsScorer:
    """
    نظام تقييم جودة المهارات (Intrinsic Skills Quality) بدون وصف وظيفي (JD).
    التقييم الكلي: 100 نقطة.
    المراجع: Taqdeem, Resumk, Jobseeker, Basmah Aljuhani, ETFC-KSA.
    """

    FLUFF_WORDS = {
        "working under pressure", "hard worker", "computer skills", "fast learner",
        "ms office", "microsoft office", "internet", "typing", "multitasking",
        "العمل تحت الضغط", "إجادة الحاسب", "العمل بروح الفريق", "سرعة التعلم", "تعدد المهام"
    }

    def __init__(self, parsed_json: dict):
        self.data = parsed_json or {}
        self.skills_data = self.data.get("skills", {})
        if isinstance(self.skills_data, list):
            self.skills_list = self.skills_data
            self.hard_skills = self.skills_list
        else:
            self.skills_list = self.skills_data.get("all_skills", []) or self.data.get("entities", {}).get("skills", [])
            self.hard_skills = self.skills_data.get("hard_skills", self.skills_list)

        self.sections_data = self.data.get("sections", {}).get("sections", {})
        self.experience_data = self.data.get("experience", {})

        self.total_score = 0.0
        self.details = {}
        self.applied_deductions = []
        self.missing_elements = []

    def _eval_specificity(self):
        score = 20.0
        if len(self.hard_skills) >= 3:
            score += 10.0

        fluff_found = []
        for skill in self.skills_list:
            if str(skill).lower().strip() in self.FLUFF_WORDS:
                score -= 10.0
                fluff_found.append(skill)

        score = max(0.0, min(30.0, score))
        self.total_score += score

        if fluff_found:
            self.applied_deductions.append({
                "section": "Skills",
                "reason": f"Found generic fluff skill phrases: {fluff_found}",
                "penalty": -10.0 * len(fluff_found),
                "reference": "Taqdeem.net Skills Guide"
            })

        this_status = "Excellent" if score == 30 else "Poor" if fluff_found else "Good"
        self.details["Specificity & Naming"] = {
            "score": score,
            "max": 30.0,
            "hard_skills_count": len(self.hard_skills),
            "fluff_words_penalized": fluff_found,
            "status": this_status
        }

    def _eval_structure(self):
        score = 0.0
        skills_section = self.sections_data.get("skills", {})
        heading = skills_section.get("heading", "")
        if heading and re.search(r"(?i)skill|مهار", heading):
            score += 5.0

        categorized_count = self.skills_data.get("categorized_count", 0) if isinstance(self.skills_data, dict) else 0
        if categorized_count > 0:
            score += 10.0

        if len(self.skills_list) > 0:
            score += 10.0

        self.total_score += score
        self.details["Structure & Categorization"] = {
            "score": score,
            "max": 25.0,
            "is_categorized": categorized_count > 0,
            "heading_found": heading
        }

    def _eval_focus(self):
        score = 0.0
        count = len(self.skills_list)

        if 6 <= count <= 12:
            score = 20.0
        elif 13 <= count <= 18:
            score = 10.0
        else:
            score = 0.0
            penalty = -20.0 if count > 18 else -10.0
            self.applied_deductions.append({
                "section": "Skills",
                "reason": f"Skill count ({count}) is outside the optimal range (6-12). Leads to lack of focus.",
                "penalty": penalty,
                "reference": "Basmah Aljuhani & Taqdeem CV Guide"
            })

        self.total_score += score
        self.details["Focus & Brevity"] = {
            "score": score,
            "max": 20.0,
            "total_skills": count
        }

    def _eval_evidence(self):
        projects_data = self.data.get("projects", {})
        experience_text = str(self.experience_data.get("raw_experience_text", ""))
        projects_text = str(projects_data.get("raw_projects_text", ""))
        combined_text = (experience_text + " " + projects_text).lower()

        if not self.skills_list or not combined_text.strip():
            score = 0.0
            proven_skills = []
        else:
            proven_skills = []
            for skill in self.skills_list:
                pattern = r"(?<![a-z0-9])" + re.escape(str(skill).lower()) + r"(?![a-z0-9])"
                if re.search(pattern, combined_text):
                    proven_skills.append(skill)

            ratio = len(proven_skills) / len(self.skills_list)
            score = round(ratio * 25.0, 1)

        self.total_score += score
        self.details["Evidence in Experience"] = {
            "score": score,
            "max": 25.0,
            "proven_skills_count": len(proven_skills),
            "proven_skills_list": proven_skills
        }

    def generate_report(self) -> dict:
        self._eval_specificity()
        self._eval_structure()
        self._eval_focus()
        self._eval_evidence()

        if len(self.skills_list) < 6:
            self.missing_elements.append("Diverse Technical Skills (6-12 recommended)")

        return {
            "section_name": "Skills Quality (Intrinsic Evaluation)",
            "section_name_ar": "المهارات والتقنيات",
            "score": round(self.total_score, 1),
            "max_score": 100.0,
            "percentage": int(self.total_score),
            "status": "Excellent" if self.total_score >= 85 else "Good" if self.total_score >= 65 else "Needs Improvement",
            "status_ar": "ممتاز" if self.total_score >= 85 else "جيد" if self.total_score >= 65 else "يحتاج تحسين",
            "evaluation_axes": self.details,
            "missing_elements": self.missing_elements,
            "penalties_applied": self.applied_deductions,
            "academic_references": [
                "[Taqdeem.net] Specificity & Naming: Write technical skills explicitly and remove fluff.",
                "[Jobseeker & Resumk] Structure & Categorization: Clear headings, categorized into Hard/Soft, bullet points.",
                "[Taqdeem & Basmah Aljuhani] Focus & Brevity: Ideal count is 6-12 skills.",
                "[Taqdeem & ETFC-KSA] Evidence in Experience: Skills must be proven in experience bullet points."
            ]
        }
