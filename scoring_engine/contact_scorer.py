"""
scoring_engine/contact_scorer.py
ContactScorer class for evaluating contact information from parsed JSON.
"""

class ContactScorer:
    """
    نظام تقييم قسم معلومات التواصل (Contact Information)
    التقييم الكلي: 10 نقاط.
    المراجع المعتمدة: Purdue OWL, Resume Worded, Sabbar, ThinkIN.
    """

    def __init__(self, parsed_json: dict):
        self.data = parsed_json or {}
        self.contact_data = self.data.get("contact", {}) or self.data.get("entities", {}).get("contact", {})
        self.diagnostics = self.data.get("diagnostics", {})

        # إعداد النتائج (من 10)
        self.score = 0.0
        self.details = {}
        self.missing_elements = []
        self.applied_deductions = []

    def _evaluate_elements(self):
        """تقييم العناصر الخمسة الأساسية (كل عنصر بـ 2 نقطة ليكون المجموع 10)"""

        # 1. الاسم الكامل (Full Name) - المرجع: Purdue OWL
        name = self.contact_data.get("name")
        if name and str(name).strip().lower() not in ["none", "null", ""]:
            self.score += 2.0
            self.details["Name"] = {"status": "Found", "value": name, "points": 2.0}
        else:
            self.missing_elements.append("Full Name")
            self.details["Name"] = {"status": "Missing", "value": None, "points": 0.0}

        # 2. رقم الهاتف (Phone Number) - المرجع: Sabbar & Purdue OWL
        phone = self.contact_data.get("phone")
        if phone:
            self.score += 2.0
            self.details["Phone"] = {"status": "Found", "value": phone, "points": 2.0}
        else:
            self.missing_elements.append("Phone Number")
            self.details["Phone"] = {"status": "Missing", "value": None, "points": 0.0}

        # 3. البريد الإلكتروني (Email) - المرجع: Resume Worded & Purdue OWL
        email = self.contact_data.get("email")
        if email and "@" in str(email):
            self.score += 2.0
            self.details["Email"] = {"status": "Found", "value": email, "points": 2.0}
        else:
            self.missing_elements.append("Email Address")
            self.details["Email"] = {"status": "Missing", "value": None, "points": 0.0}

        # 4. رابط لينكدإن (LinkedIn) - المرجع: Resume Worded & Sabbar
        linkedin = self.contact_data.get("linkedin")
        if linkedin:
            self.score += 2.0
            self.details["LinkedIn"] = {"status": "Found", "value": linkedin, "points": 2.0}
        else:
            self.missing_elements.append("LinkedIn Profile")
            self.details["LinkedIn"] = {"status": "Missing", "value": None, "points": 0.0}

        # 5. الموقع (Location) - المرجع: Resume Worded
        location = self.contact_data.get("location") or self.contact_data.get("candidate_location")
        if location:
            self.score += 2.0
            self.details["Location"] = {"status": "Found", "value": location, "points": 2.0}
        else:
            self.missing_elements.append("Location (City, Country)")
            self.details["Location"] = {"status": "Missing", "value": None, "points": 0.0}

    def _apply_deductions(self):
        """تطبيق الخصومات (Penalties) لتنسيقات الـ ATS الخاطئة"""

        # 1. التحقق مما إذا كانت البيانات في الـ Header/Footer (خصم 1.5 نقطة) - المرجع: ThinkIN
        text_warnings = self.data.get("text_extraction", {}).get("warnings", [])
        resolved_warnings = self.data.get("legacy_extraction_quality", {}).get("resolved_warnings", [])
        all_warnings = text_warnings + resolved_warnings

        header_footer_detected = any("removed_repeated_header_footer_blocks" in str(w) or "header_footer" in str(w) for w in all_warnings)

        if header_footer_detected:
            self.score -= 1.5
            self.applied_deductions.append({
                "section": "Contact Information",
                "reason": "Contact info potentially inside Header/Footer (ATS risk).",
                "penalty": -1.5,
                "reference": "ThinkIN ATS Guide"
            })

        # 2. التحقق من وجود صناديق نصية (Text Boxes) (خصم 1.5 نقطة) - المرجع: Resumly
        layout_diagnostics = self.diagnostics.get("layout", {})
        text_box_count = layout_diagnostics.get("text_box_count", 0)

        if text_box_count > 0:
            self.score -= 1.5
            self.applied_deductions.append({
                "section": "Contact Information",
                "reason": f"Detected {text_box_count} Text Box(es) which break ATS parsing.",
                "penalty": -1.5,
                "reference": "Resumly Formatting Best Practices"
            })

        # لا يمكن للتقييم أن يكون تحت الصفر
        if self.score < 0:
            self.score = 0.0

    def generate_report(self) -> dict:
        """إرجاع النتيجة النهائية لهذا القسم بتنسيق JSON"""
        self._evaluate_elements()
        self._apply_deductions()

        return {
            "section_name": "Contact Information",
            "section_name_ar": "معلومات التواصل",
            "score": round(self.score, 1),
            "max_score": 10.0,
            "percentage": int((self.score / 10.0) * 100),
            "status": "Excellent" if self.score >= 8.0 else "Good" if self.score >= 5.0 else "Needs Improvement",
            "elements": self.details,
            "missing_elements": self.missing_elements,
            "penalties_applied": self.applied_deductions,
            "academic_references": [
                "[Purdue OWL] Contact Information Formatting guidelines.",
                "[Resume Worded] ATS passability and required contact formats.",
                "[Sabbar] Middle East & ATS CV standards.",
                "[ThinkIN] ATS parsing risks with Headers/Footers."
            ]
        }
