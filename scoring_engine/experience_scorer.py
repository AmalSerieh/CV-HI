"""
scoring_engine/experience_scorer.py
ExperienceScorer class for evaluating experience quality, action verbs, past tense, and structure.
"""

import re

class ExperienceScorer:
    """
    نظام تقييم جودة وبنية الخبرات المهنية (Experience Quality)
    التقييم الكلي: 100 نقطة.
    المرجع: Resume Worded (Action Verbs & Impact), Google re:Work.
    """

    WEAK_STARTERS = {
        "helped", "assisted", "worked", "handled", "participated",
        "responsible", "duties", "tasked", "doing", "did", "made",
        "ساعدت", "عملت", "كانت مسؤولياتي", "من مهامي", "شاركت"
    }

    IRREGULAR_PAST_VERBS = {
        "led", "built", "grew", "ran", "drove", "won", "taught", "brought",
        "oversaw", "undertook", "wrote", "held", "kept", "gave", "found", "did"
    }

    def __init__(self, parsed_json: dict):
        self.data = parsed_json or {}
        self.experience_data = self.data.get("experience", {})
        self.experiences = self.data.get("experience", []) if isinstance(self.data.get("experience"), list) else self.experience_data.get("experiences", [])

        # النتائج
        self.total_score = 0.0
        self.details = {}
        self.applied_deductions = []
        self.missing_elements = []

        # إحصائيات داخلية
        self.total_bullets = 0
        self.action_verb_bullets = 0
        self.past_tense_bullets = 0
        self.weak_bullets = 0

    def _analyze_bullets(self):
        """تحليل كل نقطة (Bullet point) في قسم الخبرات"""
        for exp in self.experiences:
            responsibilities = exp.get("bullets", []) or exp.get("responsibilities", [])
            self.total_bullets += len(responsibilities)

            for bullet in responsibilities:
                words = re.findall(r"\b[A-Za-zÀ-ÿ]+\b", str(bullet))
                if not words:
                    continue

                first_word = words[0].lower()

                if first_word in self.WEAK_STARTERS or "responsible for" in str(bullet).lower():
                    self.weak_bullets += 1
                else:
                    self.action_verb_bullets += 1

                if first_word.endswith("ed") or first_word in self.IRREGULAR_PAST_VERBS:
                    self.past_tense_bullets += 1

    def _eval_action_verbs(self):
        score = 0.0
        if self.total_bullets > 0:
            ratio = self.action_verb_bullets / self.total_bullets
            score = round(ratio * 40.0, 1)

        self.total_score += score
        self.details["Action Verbs Usage"] = {
            "score": score,
            "max": 40.0,
            "total_bullets": self.total_bullets,
            "strong_action_verbs_found": self.action_verb_bullets,
            "status": "Excellent" if score >= 35 else "Good" if score >= 20 else "Needs Improvement"
        }

    def _eval_past_tense(self):
        score = 0.0
        if self.total_bullets > 0:
            ratio = self.past_tense_bullets / self.total_bullets
            adjusted_ratio = min(1.0, ratio / 0.7)
            score = round(adjusted_ratio * 30.0, 1)

        self.total_score += score
        self.details["Past Tense (Achievements)"] = {
            "score": score,
            "max": 30.0,
            "past_tense_bullets_found": self.past_tense_bullets,
            "status": "Excellent" if score >= 25 else "Good" if score >= 15 else "Needs Improvement"
        }

    def _eval_structure_and_clarity(self):
        score = 30.0
        missing_bullets_roles = 0

        for exp in self.experiences:
            responsibilities = exp.get("bullets", []) or exp.get("responsibilities", [])
            if not responsibilities:
                missing_bullets_roles += 1
                score -= 10.0

        score = max(0.0, score)
        self.total_score += score

        self.details["Structure & Bullet Points"] = {
            "score": score,
            "max": 30.0,
            "roles_missing_bullets": missing_bullets_roles,
            "status": "Excellent" if score == 30 else "Needs Improvement"
        }

    def _apply_deductions(self):
        if self.weak_bullets > 0:
            penalty = min(20.0, self.weak_bullets * 5.0)
            self.total_score -= penalty
            self.applied_deductions.append({
                "section": "Experience",
                "reason": f"Found {self.weak_bullets} bullet(s) starting with weak/passive words (e.g., 'Helped', 'Responsible for').",
                "penalty": -penalty,
                "reference": "Resume Worded (Impact Analysis)"
            })

        if self.total_score < 0:
            self.total_score = 0.0

    def generate_report(self) -> dict:
        if not self.experiences:
            self.missing_elements.append("Work Experience History")
            self.applied_deductions.append({
                "section": "Experience",
                "reason": "No work experience entries found.",
                "penalty": -100.0,
                "reference": "Purdue OWL Career Guidelines"
            })
            return {
                "section_name": "Experience Quality (Impact & Verbs)",
                "section_name_ar": "الخبرات العملية",
                "score": 0.0,
                "max_score": 100.0,
                "percentage": 0,
                "status": "Needs Improvement",
                "status_ar": "يحتاج تحسين",
                "evaluation_axes": {},
                "missing_elements": self.missing_elements,
                "penalties_applied": self.applied_deductions
            }

        self._analyze_bullets()
        self._eval_action_verbs()
        self._eval_past_tense()
        self._eval_structure_and_clarity()
        self._apply_deductions()

        return {
            "section_name": "Experience Quality (Impact & Verbs)",
            "section_name_ar": "الخبرات العملية",
            "score": round(self.total_score, 1),
            "max_score": 100.0,
            "percentage": int(self.total_score),
            "status": "Excellent" if self.total_score >= 85 else "Good" if self.total_score >= 65 else "Needs Improvement",
            "status_ar": "ممتاز" if self.total_score >= 85 else "جيد" if self.total_score >= 65 else "يحتاج تحسين",
            "evaluation_axes": self.details,
            "missing_elements": self.missing_elements,
            "penalties_applied": self.applied_deductions,
            "academic_references": [
                "[Resume Worded] Impact & Action Verbs: Bullet points must start with strong action verbs.",
                "[Resume Worded] Past Tense: Achievements and past responsibilities should be formulated in past tense.",
                "[Standard Industry Practices] Structure: Experience must be formatted as bullet points, not paragraphs."
            ]
        }
