from __future__ import annotations

import copy
import re
from typing import Any


class ResumeEvidenceReconciler:
    """
    Reconcile cross-section evidence after the field extractors run.

    This module does not invent skills, metrics, or experience periods.
    Every addition includes exact source evidence from the resume.
    """

    MONTH_TO_NUM = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    MONTH_PATTERN = (
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    )

    SECTIONS_TO_SCAN = (
        "skills",
        "summary",
        "experience",
        "leadership",
        "projects",
        "volunteer",
    )

    SOFT_SKILL_PATTERNS = {
        "communication": [
            r"\bcommunication skills?\b",
            r"\bcommunicat(?:e|ed|es|ing|ion)\b",
        ],
        "teamwork": [
            r"\bteam\s*work\b",
            r"\bteam\s+playing\b",
            r"\bteam\s+player\b",
            r"\bteam members?\b",
            r"\bcollaborat(?:e|ed|es|ing|ion)\b",
        ],
        "leadership": [
            r"\bleadership\b",
            r"\bled\b",
            r"\bleading\b",
        ],
        "mentoring": [
            r"\bpeer mentor\b",
            r"\bmentor(?:ed|ing|ship)?\b",
            r"\bmentees?\b",
        ],
        "organizational skills": [
            r"\borganizational skills?\b",
            r"\borganisation skills?\b",
            r"\bplanning year[-\s]round activities\b",
        ],
        "attention to detail": [
            r"\battention to detail\b",
        ],
        "problem solving": [
            r"\bproblem[-\s]solving\b",
        ],
        "negotiation": [
            r"\bnegotiat(?:e|es|ed|ing|ion|ions)\b",
        ],
        "coaching": [
            r"\bcoach(?:es|ed|ing)?\b",
        ],
        "conflict resolution": [
            r"\bconflict resolution\b",
            r"\bresolved conflicts?\b",
        ],
        "customer service": [
            r"\bcustomer service\b",
            r"\bclient satisfaction\b",
        ],
        "presentation skills": [
            r"\bpresentations?\b",
            r"\bpublic speaking\b",
        ],
    }

    SOFT_CANONICAL = {
        "communication": "Communication",
        "teamwork": "Teamwork",
        "leadership": "Leadership",
        "mentoring": "Mentoring",
        "coaching": "Coaching",
        "presentation skills": "Presentation",
        "presentation": "Presentation",
        "organizational skills": "Organizational Skills",
        "attention to detail": "Attention to Detail",
        "problem solving": "Problem Solving",
        "negotiation": "Negotiation",
        "conflict resolution": "Conflict Resolution",
        "customer service": "Customer Service",
    }

    INVALID_SKILLS = {
        "provider", "kpi", "kpis", "other internal systems",
        "/problem", "problem",
    }

    def reconcile(
        self,
        *,
        payload: dict,
        skills_result: dict,
        experience_result: dict,
    ) -> dict:
        sections = payload.get("sections", {}) or {}

        soft_skill_evidence = self._scan_soft_skills(
            sections
        )
        document_metrics = self._scan_document_metrics(
            sections
        )
        leadership = self._extract_leadership_experience(
            sections
        )

        reconciled_skills = self._reconcile_skills(
            skills_result,
            soft_skill_evidence,
            sections,
        )
        reconciled_experience = self._reconcile_experience(
            experience_result,
            document_metrics,
            leadership,
        )

        return {
            "skills": reconciled_skills,
            "experience": reconciled_experience,
            "soft_skill_evidence": soft_skill_evidence,
            "document_metrics": document_metrics,
            "leadership_experience": leadership,
            "quality_flags": {
                "skills_evidence_conflict": False,
                "metrics_evidence_conflict": False,
            },
            "mode": "cross_section_evidence_reconciliation",
        }

    def _scan_soft_skills(
        self,
        sections: dict,
    ) -> list[dict]:
        evidence = []

        for section_name in self.SECTIONS_TO_SCAN:
            content = self._section_content(
                sections.get(section_name)
            )

            if not content:
                continue

            for skill, patterns in (
                self.SOFT_SKILL_PATTERNS.items()
            ):
                for pattern in patterns:
                    match = re.search(
                        pattern,
                        content,
                        re.IGNORECASE,
                    )

                    if not match:
                        continue

                    evidence.append({
                        "skill": skill,
                        "section": section_name,
                        "evidence": self._evidence_line(
                            content,
                            match.start(),
                            match.end(),
                        ),
                    })
                    break

        return self._unique_evidence(
            evidence,
            keys=("skill", "section", "evidence"),
        )

    def _scan_document_metrics(
        self,
        sections: dict,
    ) -> list[dict]:
        evidence = []

        for section_name in self.SECTIONS_TO_SCAN:
            content = self._section_content(
                sections.get(section_name)
            )

            if not content:
                continue

            for metric in self._extract_metrics(content):
                evidence.append({
                    "value": metric["value"],
                    "type": metric["type"],
                    "section": section_name,
                    "evidence": self._evidence_line(
                        content,
                        metric["start"],
                        metric["end"],
                    ),
                })

        return self._unique_evidence(
            evidence,
            keys=("value", "section"),
        )

    def _extract_metrics(
        self,
        text: str,
    ) -> list[dict]:
        metric_nouns = (
            r"customers?|clients?|users?|employees?|students?|"
            r"patients?|orders?|transactions?|records?|reports?|"
            r"invoices?|accounts?|cases?|projects?|guests?|"
            r"famil(?:y|ies)|seniors?|members?|tickets?|"
            r"payments?|returns?|applications?|calls?|locations?|stores?|"
            r"branches?|sites?|campaigns?|contracts?|agencies?|vendors?|"
            r"product[ \t]+representatives?|products?|representatives?|chains?"
        )
        number_words = (
            r"one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
            r"seventeen|eighteen|nineteen|twenty|thirty|forty|"
            r"fifty|sixty|seventy|eighty|ninety|hundred|thousand"
        )

        patterns = [
            (
                "ranking",
                r"\btop[ \t]+\d+(?:\.\d+)?[ \t]*%"
                r"[ \t]+of[ \t]+(?:their|the|his|her)[ \t]+"
                r"[^,.;\n]{1,45}",
            ),
            (
                "duration",
                r"\b\d+(?:\.\d+)?[ \t]*[- ][ \t]*"
                r"(?:month|year|week|day)s?[ \t]+"
                r"(?:program|project|engagement|contract|placement|term)\b",
            ),
            (
                "percentage",
                r"\b\d+(?:\.\d+)?[ \t]*%",
            ),
            (
                "currency",
                (
                    r"(?:\b(?:up[ \t]+to|over|more[ \t]+than|"
                    r"approximately|about)[ \t]+)?"
                    r"(?:USD|CAD|EUR|GBP)?[ \t]*[$€£][ \t]*"
                    r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
                    r"[ \t]*(?:[KMB]|thousand|million|billion)?\+?"
                ),
            ),
            (
                "quantity",
                (
                    rf"\b(?:over|more[ \t]+than|up[ \t]+to|"
                    rf"approximately|about|nearly|around)?[ \t]*"
                    rf"\d+(?:,\d{{3}})*(?:\.\d+)?\+?"
                    rf"(?:[- \t]+[A-Za-z][A-Za-z.-]*){{0,4}}"
                    rf"[- \t]+(?:{metric_nouns})\b"
                ),
            ),
            (
                "quantity_words",
                (
                    rf"\b(?:over|more[ \t]+than|up[ \t]+to|"
                    rf"approximately|about|nearly|around)?[ \t]*"
                    rf"(?:{number_words})"
                    rf"(?:[- \t]+(?:{number_words})){{0,3}}"
                    rf"[ \t]+(?:major[ \t]+|active[ \t]+|new[ \t]+|"
                    rf"retail[ \t]+|local[ \t]+|physical[ \t]+|"
                    rf"online[ \t]+)?(?:{metric_nouns})\b"
                ),
            ),
        ]

        found: list[dict] = []

        # Scan one visual line at a time. This prevents a year at the end
        # of one line from combining with a title noun on the next line.
        for line_match in re.finditer(r"[^\n]+", str(text or "")):
            line = line_match.group(0)
            base_offset = line_match.start()

            for metric_type, pattern in patterns:
                for match in re.finditer(
                    pattern,
                    line,
                    re.IGNORECASE,
                ):
                    value = re.sub(
                        r"\s+",
                        " ",
                        match.group(0),
                    ).strip(" ,.;:")

                    if not value:
                        continue

                    if re.search(
                        r"(?i)(?:19|20)?[xy]{2,4}|yyyy|month[ \t]+year",
                        value,
                    ):
                        continue

                    if (
                        metric_type == "quantity"
                        and re.match(r"^(?:19|20)\d{2}\b", value)
                    ):
                        continue

                    value = self._canonical_metric_display(
                        value,
                        metric_type,
                    )

                    found.append({
                        "value": value,
                        "type": metric_type,
                        "start": base_offset + match.start(),
                        "end": base_offset + match.end(),
                    })

        found.sort(
            key=lambda item: (
                item["start"],
                -(item["end"] - item["start"]),
            )
        )

        accepted: list[dict] = []

        for item in found:
            if any(
                item["start"] >= other["start"]
                and item["end"] <= other["end"]
                for other in accepted
            ):
                continue
            accepted.append(item)

        return accepted

    def _canonical_metric_display(
        self,
        value: str,
        metric_type: str,
    ) -> str:
        value = re.sub(r"\s+", " ", str(value)).strip()

        if metric_type != "currency":
            return value

        value = re.sub(
            r"([0-9])\s+([KMB])\b",
            r"\1\2",
            value,
            flags=re.IGNORECASE,
        )

        match = re.search(r"([KMB])\+?$", value, re.IGNORECASE)
        if match:
            suffix = match.group(1).upper()
            value = value[:match.start(1)] + suffix + value[match.end(1):]

        return value

    def _reconcile_skills(
        self,
        result: dict,
        evidence: list[dict],
        sections: dict,
    ) -> dict:
        reconciled = copy.deepcopy(
            result if isinstance(result, dict) else {}
        )

        document_text = "\n".join(
            self._section_content(sections.get(section_name))
            for section_name in self.SECTIONS_TO_SCAN
            if self._section_content(sections.get(section_name))
        )

        candidates = (
            list(reconciled.get("hard_skills", []) or [])
            + list(reconciled.get("soft_skills", []) or [])
            + list(reconciled.get("all_skills", []) or [])
        )

        for item in evidence:
            candidates.append(item.get("skill", ""))

        sanitized = self._sanitize_skill_list(
            candidates,
            document_text=document_text,
        )

        hard_skills: list[str] = []
        soft_skills: list[str] = []

        for value in sanitized:
            canonical_soft = self._canonical_soft_skill(value)
            if canonical_soft:
                if canonical_soft.casefold() not in {
                    item.casefold() for item in soft_skills
                }:
                    soft_skills.append(canonical_soft)
            else:
                hard_skills.append(value)

        hard_skills = self._semantic_dedupe_skills(hard_skills)
        all_skills = hard_skills + soft_skills

        reconciled["hard_skills"] = hard_skills
        reconciled["soft_skills"] = soft_skills
        reconciled["all_skills"] = all_skills
        reconciled["soft_count"] = len(soft_skills)
        reconciled["hard_count"] = len(hard_skills)
        reconciled["total_count"] = len(all_skills)

        categorized = self._sanitize_categorized_skills(
            reconciled.get("categorized_skills", {}) or {},
            document_text=document_text,
        )
        hard_keys = {item.casefold() for item in hard_skills}
        categorized = {
            category: [
                value for value in values
                if value.casefold() in hard_keys
            ]
            for category, values in categorized.items()
        }
        categorized = {
            category: values
            for category, values in categorized.items()
            if values
        }
        reconciled["categorized_skills"] = categorized

        categorized_hard = sum(
            len(values or [])
            for category, values in categorized.items()
            if category != "other"
        )
        categorized_ratio = (
            categorized_hard / len(hard_skills)
            if hard_skills
            else 0.0
        )
        sector_rate = float(
            (reconciled.get("sector_match", {}) or {}).get(
                "match_rate",
                0,
            )
            or 0
        )

        skills_score = round(
            min(60, len(hard_skills) * 4)
            + min(18, len(soft_skills) * 3)
            + min(12, sector_rate * 0.12)
            + min(5, categorized_ratio * 5)
        )
        reconciled["skills_score"] = max(0, min(95, skills_score))
        reconciled["skills_quality"] = {
            "status": "ok" if len(soft_skills) >= 2 else "degraded",
            "score": reconciled["skills_score"],
            "warnings": [] if len(soft_skills) >= 2 else [
                "soft_skill_evidence_insufficient"
            ],
        }

        reconciled["soft_skill_evidence"] = evidence
        reconciled["sections_scanned"] = list(self.SECTIONS_TO_SCAN)
        reconciled["skill_filtering"] = {
            "mode": "evidence_aware_postprocessing",
            "removed_false_positives": self._skill_false_positives(
                result,
                hard_skills,
                all_skills,
            ),
        }

        recommendations = []
        for rec in reconciled.get("recommendations", []) or []:
            message = str(rec.get("message", ""))
            rec_type = str(rec.get("type", ""))
            generic_soft_recommendation = (
                rec_type in {"soft", "soft_skills"}
                or (
                    "communication" in message.lower()
                    and "leadership" in message.lower()
                    and "teamwork" in message.lower()
                )
            )
            if generic_soft_recommendation and len(soft_skills) >= 2:
                continue
            recommendations.append(rec)

        if len(soft_skills) >= 2:
            recommendations.append({
                "severity": "good",
                "type": "soft_skills_detected",
                "message": (
                    "Soft-skill evidence was detected across the "
                    "summary, experience, and leadership sections."
                ),
                "evidence": evidence,
            })

        reconciled["recommendations"] = self._unique_recommendations(
            recommendations
        )
        return reconciled

    def _canonical_soft_skill(self, value: str) -> str | None:
        normalized = re.sub(
            r"\s+",
            " ",
            str(value or "").strip(" ,;/"),
        ).casefold()

        aliases = {
            "communications": "communication",
            "team work": "teamwork",
            "team leadership": "leadership",
            "professional presentation": "presentation skills",
            "presentations": "presentation skills",
        }
        normalized = aliases.get(normalized, normalized)
        return self.SOFT_CANONICAL.get(normalized)

    def _semantic_dedupe_skills(
        self,
        values: list[str],
    ) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()

        for value in values:
            key = value.casefold()
            if key and key not in seen:
                seen.add(key)
                unique.append(value)

        def tokens(value: str) -> set[str]:
            normalized = re.sub(
                r"[&/\\-]+",
                " ",
                value.casefold(),
            )
            return {
                token
                for token in normalized.split()
                if token not in {"and", "of", "the"}
            }

        token_sets = [tokens(value) for value in unique]
        remove: set[int] = set()

        for index, _value in enumerate(unique):
            current = token_sets[index]
            for other_index, other in enumerate(unique):
                if index == other_index:
                    continue
                broader = token_sets[other_index]
                if current and current < broader and (
                    len(current) <= 2
                    or any(char in other for char in "&/")
                ):
                    remove.add(index)
                    break

        return [
            value
            for index, value in enumerate(unique)
            if index not in remove
        ]

    def _sanitize_skill_list(
        self,
        values: list,
        *,
        document_text: str,
    ) -> list[str]:
        cleaned: list[str] = []

        for raw_value in values:
            value = re.sub(
                r"\s+",
                " ",
                str(raw_value or ""),
            ).strip(" ,;/\\")
            if not value:
                continue

            expanded = self._expand_skill_value(value)
            for candidate in expanded:
                normalized = candidate.casefold().strip()
                if normalized in self.INVALID_SKILLS:
                    continue
                if not self._skill_has_valid_evidence(
                    candidate,
                    document_text,
                ):
                    continue
                if normalized not in {
                    item.casefold() for item in cleaned
                }:
                    cleaned.append(candidate)

        return cleaned

    def _expand_skill_value(self, value: str) -> list[str]:
        lower = value.casefold()

        compound = {
            "conflict resolution/problem solving": [
                "Conflict Resolution",
                "Problem Solving",
            ],
            "conflict resolution and problem solving": [
                "Conflict Resolution",
                "Problem Solving",
            ],
        }
        if lower in compound:
            return compound[lower]

        if (
            "microsoft" in lower
            and "/" in value
            and any(app in lower for app in (
                "word", "excel", "powerpoint", "access", "project", "outlook"
            ))
        ):
            apps = re.split(r"[/,]", value)
            expanded = []
            for app in apps:
                app = re.sub(
                    r"^microsoft\s+",
                    "",
                    app.strip(),
                    flags=re.IGNORECASE,
                )
                canonical_apps = {
                    "word": "Microsoft Word",
                    "excel": "Microsoft Excel",
                    "powerpoint": "Microsoft PowerPoint",
                    "access": "Microsoft Access",
                    "project": "Microsoft Project",
                    "outlook": "Microsoft Outlook",
                }
                canonical = canonical_apps.get(app.casefold())
                if canonical:
                    expanded.append(canonical)
            return expanded

        return [value]

    def _skill_has_valid_evidence(
        self,
        skill: str,
        document_text: str,
    ) -> bool:
        normalized = skill.strip().casefold()
        if normalized in self.INVALID_SKILLS:
            return False
        if normalized in {"technology", "technologies", "tech"}:
            return False
        if normalized == "go":
            return bool(re.search(
                r"\b(?:golang|go\s+(?:programming|developer|engineer|language|backend)|"
                r"programming\s+in\s+go)\b",
                document_text,
                re.IGNORECASE,
            ))
        if normalized == "automation":
            non_company_lines = [
                line
                for line in document_text.splitlines()
                if "automation" in line.casefold()
                and not re.search(
                    r"\b(?:inc\.?|llc\.?|ltd\.?|corp\.?|corporation|company)\b",
                    line,
                    re.IGNORECASE,
                )
            ]
            return bool(non_company_lines)
        return True

    def _sanitize_categorized_skills(
        self,
        categorized: dict,
        *,
        document_text: str,
    ) -> dict:
        return {
            category: self._sanitize_skill_list(
                list(values or []),
                document_text=document_text,
            )
            for category, values in categorized.items()
        }

    def _skill_false_positives(
        self,
        original: dict,
        hard_skills: list[str],
        all_skills: list[str],
    ) -> list[str]:
        before = {
            str(value).casefold(): str(value)
            for value in (
                list(original.get("hard_skills", []) or [])
                + list(original.get("all_skills", []) or [])
            )
            if value
        }
        after = {
            str(value).casefold()
            for value in hard_skills + all_skills
            if value
        }
        return [before[key] for key in before if key not in after]


    def _reconcile_experience(
        self,
        result: dict,
        document_metrics: list[dict],
        leadership: dict,
    ) -> dict:
        reconciled = copy.deepcopy(
            result if isinstance(result, dict) else {}
        )

        reconciled["document_metrics"] = (
            document_metrics
        )
        reconciled["leadership_experience_months"] = (
            leadership.get("months", 0)
        )
        reconciled["leadership_experience_years"] = (
            leadership.get("years", 0)
        )
        reconciled["leadership_periods"] = (
            leadership.get("periods", [])
        )
        reconciled["leadership_merged_periods"] = (
            leadership.get("merged_periods", [])
        )

        recommendations = []

        for rec in reconciled.get(
            "recommendations",
            [],
        ) or []:
            if (
                document_metrics
                and rec.get("type") in {
                    "missing_metrics",
                    "metrics_detected",
                    "metrics_partial",
                    "document_metrics_detected",
                }
            ):
                continue

            recommendations.append(rec)

        if document_metrics:
            recommendations.append({
                "severity": "good",
                "type": "metrics_detected",
                "message": (
                    "Several measurable achievements were detected "
                    "in the resume."
                ),
                "evidence": document_metrics,
            })

            experiences = reconciled.get(
                "experiences",
                [],
            ) or []
            without_metrics = [
                index
                for index, item in enumerate(
                    experiences,
                    start=1,
                )
                if not item.get("metrics")
            ]

            if without_metrics:
                recommendations.append({
                    "severity": "low",
                    "type": "metrics_partial",
                    "message": (
                        "Add quantified results only to entries "
                        "that do not already contain them, and only "
                        "when you have factual numbers: "
                        f"{without_metrics}."
                    ),
                })

        reconciled["recommendations"] = (
            self._unique_recommendations(
                recommendations
            )
        )

        return reconciled

    def _extract_leadership_experience(
        self,
        sections: dict,
    ) -> dict:
        content = self._section_content(
            sections.get("leadership")
        )

        if not content:
            return {
                "months": 0,
                "years": 0,
                "periods": [],
                "merged_periods": [],
                "source_section": "leadership",
            }

        pattern = re.compile(
            rf"\b(?P<start_month>{self.MONTH_PATTERN})\.?\s+"
            rf"(?P<start_year>(?:19|20)\d{{2}})\s*"
            rf"(?:-|–|—|to)\s*"
            rf"(?P<end_month>{self.MONTH_PATTERN})\.?\s+"
            rf"(?P<end_year>(?:19|20)\d{{2}})\b",
            re.IGNORECASE,
        )

        periods = []

        for match in pattern.finditer(content):
            start = (
                int(match.group("start_year")),
                self._month_number(
                    match.group("start_month")
                ),
            )
            end = (
                int(match.group("end_year")),
                self._month_number(
                    match.group("end_month")
                ),
            )

            if (
                not start[1]
                or not end[1]
                or end < start
            ):
                continue

            periods.append({
                "start_date": (
                    f"{self._month_label(start[1])} "
                    f"{start[0]}"
                ),
                "end_date": (
                    f"{self._month_label(end[1])} "
                    f"{end[0]}"
                ),
                "duration_months": self._months_between(
                    start,
                    end,
                ),
                "evidence": match.group(0),
                "_start": start,
                "_end": end,
            })

        merged = self._merge_periods([
            (item["_start"], item["_end"])
            for item in periods
        ])
        months = sum(
            self._months_between(start, end)
            for start, end in merged
        )

        public_periods = [
            {
                key: value
                for key, value in item.items()
                if not key.startswith("_")
            }
            for item in periods
        ]
        public_merged = [
            {
                "start_date": (
                    f"{self._month_label(start[1])} "
                    f"{start[0]}"
                ),
                "end_date": (
                    f"{self._month_label(end[1])} "
                    f"{end[0]}"
                ),
                "duration_months": self._months_between(
                    start,
                    end,
                ),
            }
            for start, end in merged
        ]

        return {
            "months": months,
            "years": round(months / 12, 1) if months else 0,
            "periods": public_periods,
            "merged_periods": public_merged,
            "source_section": "leadership",
        }

    def _merge_periods(
        self,
        periods: list[
            tuple[tuple[int, int], tuple[int, int]]
        ],
    ) -> list[
        tuple[tuple[int, int], tuple[int, int]]
    ]:
        if not periods:
            return []

        periods = sorted(periods)
        merged = [periods[0]]

        for start, end in periods[1:]:
            last_start, last_end = merged[-1]

            if self._month_index(start) <= (
                self._month_index(last_end) + 1
            ):
                merged[-1] = (
                    last_start,
                    max(last_end, end),
                )
            else:
                merged.append((start, end))

        return merged

    def _months_between(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> int:
        return (
            (end[0] - start[0]) * 12
            + (end[1] - start[1])
            + 1
        )

    def _month_index(
        self,
        value: tuple[int, int],
    ) -> int:
        return value[0] * 12 + value[1]

    def _month_number(
        self,
        value: str,
    ) -> int | None:
        normalized = str(value or "").lower().rstrip(".")
        return (
            self.MONTH_TO_NUM.get(normalized)
            or self.MONTH_TO_NUM.get(normalized[:3])
        )

    def _month_label(
        self,
        month: int,
    ) -> str:
        labels = {
            1: "Jan", 2: "Feb", 3: "Mar",
            4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep",
            10: "Oct", 11: "Nov", 12: "Dec",
        }
        return labels[month]

    def _section_content(
        self,
        section: Any,
    ) -> str:
        if isinstance(section, dict):
            return str(section.get("content") or "")
        if isinstance(section, str):
            return section
        return ""

    def _evidence_line(
        self,
        text: str,
        start: int,
        end: int,
    ) -> str:
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)

        if line_end < 0:
            line_end = len(text)

        return re.sub(
            r"\s+",
            " ",
            text[line_start:line_end],
        ).strip()

    def _unique_evidence(
        self,
        items: list[dict],
        *,
        keys: tuple[str, ...],
    ) -> list[dict]:
        seen = set()
        result = []

        for item in items:
            key = tuple(
                str(item.get(name, "")).lower()
                for name in keys
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    def _unique_recommendations(
        self,
        recommendations: list[dict],
    ) -> list[dict]:
        seen = set()
        result = []

        for rec in recommendations:
            key = (
                str(rec.get("type", "")).lower(),
                str(rec.get("message", "")).lower(),
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(rec)

        return result
