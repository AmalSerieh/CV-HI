"""
scoring_engine/section_scorer.py
SectionScorer class for evaluating section structure, standard headings, and layout risks.
"""

class SectionScorer:
    """
    نظام تقييم جودة وبنية أقسام السيرة الذاتية (Section Quality & Structure)
    التقييم الكلي: 10 نقاط.
    المراجع المعتمدة: Workday, Greenhouse & Taleo Resume Guide, CIMS, SHRM.
    """

    def __init__(self, parsed_json: dict):
        self.data = parsed_json or {}

        self.sections_data = self.data.get("sections", {})
        self.found_sections = self.sections_data.get("found_sections", []) or list(self.sections_data.keys())
        self.missing_sections = self.sections_data.get("missing_required", [])

        self.layout = self.data.get("text_extraction", {}).get("layout", "single_column")

        self.score = 0.0
        self.details = {}
        self.missing_elements = []
        self.applied_deductions = []

    def _evaluate_core_sections(self):
        core_sections = {
            "summary": "Professional Summary",
            "experience": "Work Experience",
            "education": "Education Background",
            "skills": "Technical/Soft Skills"
        }

        for sec_key, sec_label in core_sections.items():
            if sec_key in self.found_sections or self.data.get(sec_key):
                self.score += 2.5
                self.details[sec_label] = {"status": "Found", "points": 2.5}
            else:
                self.missing_elements.append(sec_label)
                self.details[sec_label] = {"status": "Missing", "points": 0.0}

    def _apply_deductions(self):
        if self.layout not in ["single_column", "unknown"]:
            self.score -= 2.0
            self.applied_deductions.append({
                "section": "Section Structure",
                "reason": f"Detected layout: '{self.layout}'. ATS systems prefer 'single_column'.",
                "penalty": -2.0,
                "reference": "Workday, Greenhouse & Taleo Resume Guide"
            })

        section_quality = self.data.get("section_quality", {})
        invalid_sections = section_quality.get("missing_or_invalid", [])

        if invalid_sections:
            self.score -= 1.5
            self.applied_deductions.append({
                "section": "Section Structure",
                "reason": f"Non-standard or unreadable section headers detected: {invalid_sections}.",
                "penalty": -1.5,
                "reference": "Standard Resume Format Guidelines"
            })

        if self.score < 0:
            self.score = 0.0

    def generate_report(self) -> dict:
        self._evaluate_core_sections()
        self._apply_deductions()

        return {
            "section_name": "Section Quality & Structure",
            "section_name_ar": "جودة وبنية الأقسام",
            "score": round(self.score, 1),
            "max_score": 10.0,
            "percentage": int((self.score / 10.0) * 100),
            "status": "Excellent" if self.score >= 8.0 else "Good" if self.score >= 5.0 else "Needs Improvement",
            "status_ar": "ممتاز" if self.score >= 8.0 else "جيد" if self.score >= 5.0 else "يحتاج تحسين",
            "elements": self.details,
            "missing_elements": self.missing_elements,
            "penalties_applied": self.applied_deductions,
            "academic_references": [
                "[Workday, Greenhouse & Taleo Resume Guide] Single-column format and standard headers requirement.",
                "[Resume Worded] Section Quality and Structure score validation.",
                "[SHRM & CIMS] Standard formatting guidelines for recruiters."
            ]
        }
