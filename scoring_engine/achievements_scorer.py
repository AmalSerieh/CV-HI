"""
scoring_engine/achievements_scorer.py
AchievementsScorer class for evaluating quantified impact (XYZ Formula) from parsed JSON.
"""

class AchievementsScorer:
    """
    نظام تقييم الإنجازات والأرقام (Quantified Impact)
    التقييم الكلي: 100 نقطة.
    المرجع: Google re:Work (XYZ Formula), Resume Worded (Impact).
    """

    def __init__(self, parsed_json: dict):
        self.data = parsed_json or {}

        # استخراج المقاييس من قسم (evidence_reconciliation)
        self.evidence_data = self.data.get("evidence_reconciliation", {})
        self.metrics = self.evidence_data.get("document_metrics", [])

        self.experience_data = self.data.get("experience", {})
        self.experiences = self.data.get("experience", []) if isinstance(self.data.get("experience"), list) else self.experience_data.get("experiences", [])

        # النتائج
        self.total_score = 0.0
        self.details = {}
        self.applied_deductions = []

    def _eval_metrics_volume(self):
        """
        1. حجم المقاييس (40 نقطة)
        كل مقياس (رقم/نسبة/عملة) يعطي 8 نقاط، بحد أقصى 40.
        """
        metric_count = len(self.metrics)
        score = min(40.0, metric_count * 8.0)

        self.total_score += score
        self.details["Metrics Volume (Quantification)"] = {
            "score": score,
            "max": 40.0,
            "metrics_found": metric_count,
            "status": "Excellent" if score == 40 else "Good" if score >= 20 else "Needs Improvement"
        }

    def _eval_metrics_distribution(self):
        """
        2. توزيع المقاييس على الخبرات (30 نقطة)
        هل تم استخدام الأرقام في وظيفة واحدة فقط أم في معظم الوظائف؟
        """
        score = 0.0
        total_roles = len(self.experiences)
        roles_with_metrics = sum(1 for exp in self.experiences if exp.get("metrics") or any(c in str(exp) for c in ['%', '$']))

        if total_roles > 0:
            ratio = roles_with_metrics / total_roles
            score = round(ratio * 30.0, 1)
        elif total_roles == 0 and len(self.metrics) > 0:
            # إذا وجدت مقاييس في المشاريع ولكن لا يوجد خبرات
            score = 30.0

        self.total_score += score
        self.details["Metrics Distribution Across Roles"] = {
            "score": score,
            "max": 30.0,
            "roles_with_metrics": roles_with_metrics,
            "total_roles": total_roles,
            "status": "Excellent" if score >= 20 else "Needs Improvement"
        }

    def _eval_metrics_diversity(self):
        """
        3. تنوع المقاييس (30 نقطة)
        هل المقاييس متنوعة؟ (نسب مئوية، كميات، عملات، فترات زمنية)
        """
        score = 0.0
        found_types = set()

        for m in self.metrics:
            m_type = m.get("metric_type") if isinstance(m, dict) else "quantity"
            if m_type:
                found_types.add(m_type)

        # كل نوع مختلف من المقاييس يعطي 10 نقاط، بحد أقصى 30
        score = min(30.0, len(found_types) * 10.0)

        self.total_score += score
        self.details["Metric Types Diversity"] = {
            "score": score,
            "max": 30.0,
            "types_found": list(found_types),
            "status": "Excellent" if score == 30 else "Good" if score >= 10 else "Poor"
        }

    def _apply_deductions(self):
        """الخصومات: إذا كان المرشح يمتلك خبرات متعددة ولم يذكر أي رقم"""
        if len(self.experiences) >= 2 and len(self.metrics) == 0:
            self.total_score -= 20.0
            self.applied_deductions.append({
                "section": "Achievements",
                "reason": "Resume lists multiple experiences but contains ZERO quantified achievements.",
                "penalty": -20.0,
                "reference": "Google re:Work XYZ Formula - Missing 'Measured by [Y]'"
            })

        if self.total_score < 0:
            self.total_score = 0.0

    def generate_report(self) -> dict:
        """توليد التقرير النهائي"""
        self._eval_metrics_volume()
        self._eval_metrics_distribution()
        self._eval_metrics_diversity()
        self._apply_deductions()

        # جلب بعض الأمثلة للعرض
        examples = []
        for m in self.metrics[:3]:
            if isinstance(m, dict):
                evidence = m.get("evidence", [])
                if isinstance(evidence, list) and len(evidence) > 0 and isinstance(evidence[0], dict):
                    examples.append(evidence[0].get("text", str(m.get("value"))))
                else:
                    examples.append(str(m.get("value")))
            else:
                examples.append(str(m))

        return {
            "section_name": "Achievements & Quantification (XYZ Formula)",
            "section_name_ar": "الإنجازات والأرقام الكمية",
            "score": round(self.total_score, 1),
            "max_score": 100.0,
            "percentage": int(self.total_score),
            "status": "Excellent" if self.total_score >= 80 else "Good" if self.total_score >= 50 else "Needs Improvement",
            "evaluation_axes": self.details,
            "metric_examples_extracted": examples,
            "missing_elements": ["Quantified Impact Metrics"] if len(self.metrics) == 0 else [],
            "penalties_applied": self.applied_deductions,
            "academic_references": [
                "[Google re:Work] XYZ Formula: Accomplished [X] as measured by [Y], by doing [Z].",
                "[Resume Worded] Quantified Impact: Strong resumes use numbers, percentages, and currencies to prove scale."
            ]
        }
