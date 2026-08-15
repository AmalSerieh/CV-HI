"""
scoring_engine/summary_scorer.py
SummaryScorer class for evaluating professional summary presence, length (3-4 lines), and tone.
"""

class SummaryScorer:
    """
    نظام تقييم الملخص المهني (Professional Summary)
    التقييم الكلي: 100 نقطة.
    المراجع: تقرير المعايير العربية المعتمدة، وإرشادات كتابة السيرة الذاتية (3-4 أسطر).
    """

    def __init__(self, parsed_json: dict):
        self.data = parsed_json or {}

        self.sections_data = self.data.get("sections", {}).get("sections", {})
        self.summary_section = self.sections_data.get("summary", {})
        self.summary_text = str(self.data.get("summary", "") or self.data.get("entities", {}).get("summary", "") or self.summary_section.get("content", "")).strip()

        self.total_score = 0.0
        self.details = {}
        self.applied_deductions = []
        self.missing_elements = []

    def _eval_existence(self):
        if self.summary_text:
            score = 40.0
            status = "Found"
        else:
            score = 0.0
            status = "Missing"
            self.missing_elements.append("Comprehensive Professional Summary")
            self.applied_deductions.append({
                "section": "Summary",
                "reason": "Professional Summary is entirely missing.",
                "penalty": -40.0,
                "reference": "Standard CV Guidelines - Missing Core Section"
            })

        self.total_score += score
        self.details["Summary Existence"] = {
            "score": score,
            "max": 40.0,
            "status": status
        }

    def _eval_length(self):
        words = len(self.summary_text.split())
        score = 0.0

        if words == 0:
            score = 0.0
        elif 30 <= words <= 85:
            score = 30.0
        elif words > 85:
            score = 15.0
            self.applied_deductions.append({
                "section": "Summary",
                "reason": f"Summary is too long ({words} words). It should be a concise 3-4 lines.",
                "penalty": -15.0,
                "reference": "CV Writing Standards (Brevity)"
            })
        else:
            score = 15.0
            self.applied_deductions.append({
                "section": "Summary",
                "reason": f"Summary is too short ({words} words). It should adequately highlight skills in 3-4 lines.",
                "penalty": -15.0,
                "reference": "CV Writing Standards (Brevity)"
            })

        self.total_score += score
        self.details["Length & Brevity (3-4 lines)"] = {
            "score": score,
            "max": 30.0,
            "word_count": words
        }

    def _eval_tone_and_quality(self):
        content = f" {self.summary_text.lower()} "
        score = 30.0 if self.summary_text else 0.0

        if self.summary_text:
            first_person_pronouns = [" i ", " me ", " my ", " mine ", " أنا ", " لي "]

            for pronoun in first_person_pronouns:
                if pronoun in content:
                    score -= 10.0
                    self.applied_deductions.append({
                        "section": "Summary",
                        "reason": "Detected first-person pronouns (I, me, my, أنا). A professional summary should avoid them.",
                        "penalty": -10.0,
                        "reference": "Professional Resume Tone Guidelines"
                    })
                    break

        self.total_score += max(0.0, score)
        self.details["Content Quality & Tone"] = {
            "score": max(0.0, score),
            "max": 30.0
        }

    def generate_report(self) -> dict:
        self._eval_existence()
        self._eval_length()
        self._eval_tone_and_quality()

        self.total_score = max(0.0, self.total_score)

        return {
            "section_name": "Professional Summary Quality",
            "section_name_ar": "الملخص المهني",
            "score": round(self.total_score, 1),
            "max_score": 100.0,
            "percentage": int(self.total_score),
            "status": "Excellent" if self.total_score >= 85 else "Good" if self.total_score >= 60 else "Needs Improvement",
            "status_ar": "ممتاز" if self.total_score >= 85 else "جيد" if self.total_score >= 60 else "يحتاج تحسين",
            "evaluation_axes": self.details,
            "missing_elements": self.missing_elements,
            "penalties_applied": self.applied_deductions,
            "academic_references": [
                "[Standard CV Guidelines] The summary is a core section highlighting skills and achievements.",
                "[Brevity Standards] A summary must be concise, typically 3-4 lines (30-85 words).",
                "[Professional Tone] Resumes should be written without first-person pronouns (I, me, my)."
            ]
        }
