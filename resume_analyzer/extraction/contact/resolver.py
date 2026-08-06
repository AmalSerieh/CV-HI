from __future__ import annotations

import re
from typing import Any

from .email import EmailExtractor
from .job_title import JobTitleExtractor
from .links import LinkExtractor
from .phone import PhoneExtractor


class ContactResolver:
    """
    Resolve candidate identity as one ranked contact cluster.

    It does not choose the first email/phone. It scores candidate contacts by:
    - proximity to a plausible person name
    - personal vs institutional/template address
    - presence in ordered_text
    - repeated header/footer evidence
    - position near the top of the resume
    """

    BLOCKED_NAME_PHRASES = {
        "resume writing",
        "résumé writing",
        "sample resume",
        "sample résumé",
        "career",
        "career centre",
        "career center",
        "career services",
        "profile",
        "education",
        "experience",
        "work experience",
        "related accounting experience",
        "communication and leadership",
        "communication and leadership experience",
        "page 1 of 2",
        "page 2 of 2",
    }

    PLACEHOLDER_NAME_PHRASES = {
        "student name", "candidate name", "applicant name",
        "your name", "full name", "first name last name",
        "name surname",
    }

    TEMPLATE_HEADING_PATTERN = re.compile(
        r"(?i)\b(?:resume|résumé|cv|curriculum vitae)\b"
        r".{0,30}\b(?:sample|template|example|demo)\b"
        r"|\b(?:sample|template|example|demo)\b"
        r".{0,30}\b(?:resume|résumé|cv)\b"
    )

    PLACEHOLDER_EMAIL_PATTERN = re.compile(
        r"(?i)^(?:email|name|student|candidate|yourname|user)@"
        r"(?:email|example|test|sample)\.(?:com|org|net|ca)$"
        r"|^[^@]+@example\.(?:com|org|net)$"
    )

    INSTITUTION_WORDS = {
        "university",
        "college",
        "school",
        "institute",
        "academy",
        "career",
        "department",
        "faculty",
        "services",
        "centre",
        "center",
    }

    SECTION_HEADINGS = {
        "profile",
        "summary",
        "professional summary",
        "education",
        "experience",
        "work experience",
        "related accounting experience",
        "skills",
        "projects",
        "languages",
        "certifications",
        "communication and leadership",
        "communication and leadership experience",
    }

    LOCATION_PATTERN = re.compile(
        r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.' -]{1,45},\s*"
        r"(?:[A-Z]{2,3}|[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.' -]{2,35})$"
    )
    INLINE_LOCATION_PATTERN = re.compile(
        r"(?<![\w])"
        r"([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.' -]{1,45})\s*,\s*"
        r"([A-Z]{2,3}|[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.' -]{2,35})"
        r"(?=\s*(?:[,|•·]|$))"
    )
    INLINE_ARABIC_LOCATION_PATTERN = re.compile(
        r"(?<![\w])([\u0600-\u06ff][\u0600-\u06ff.' -]{1,45})\s*[،,]\s*"
        r"([\u0600-\u06ff][\u0600-\u06ff.' -]{2,35})"
        r"(?=\s*(?:[,،|•·]|$))"
    )

    NAME_PATTERN = re.compile(
        r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+"
        r"(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+){1,3}$"
    )
    ROLE_TITLE_PATTERN = re.compile(
        r"(?i)^(?:senior|junior|lead|principal|chief|assistant|associate|"
        r"graphic|product|project|accounting|administrative|software|data|"
        r"marketing|sales|operations|financial|customer|human resources|hr)?\s*"
        r"(?:designer|manager|director|analyst|developer|engineer|assistant|"
        r"accountant|bookkeeper|specialist|coordinator|consultant|representative|"
        r"administrator|officer|advisor|executive|intern|trainee)$"
    )

    GENERIC_TEMPLATE_PHRASES = (
        "job title",
        "company name",
        "key responsibility or achievement",
        "describe in a few lines",
        "your career goals",
        "introduction to your cover letter",
    )
    NON_LOCATION_SECTION_HEADINGS = {
        "skills",
        "technical skills",
        "core skills",
        "core competencies",
        "technologies",
        "tools",
        "coursework",
        "relevant coursework",
    }
    NON_LOCATION_TERMS = {
        "python",
        "java",
        "javascript",
        "typescript",
        "react",
        "docker",
        "sql",
        "web",
        "software",
        "networks",
        "business",
        "leadership",
        "communication",
        "operations",
        "planning",
    }

    def __init__(
        self,
        email_extractor: EmailExtractor | None = None,
        phone_extractor: PhoneExtractor | None = None,
        link_extractor: Any = None,
        name_extractor: Any = None,
        location_extractor: Any = None,
        job_title_extractor: Any = None,
    ) -> None:
        self.email_extractor = email_extractor or EmailExtractor()
        self.phone_extractor = phone_extractor or PhoneExtractor()
        self.link_extractor = link_extractor or LinkExtractor(self.email_extractor)
        self.name_extractor = name_extractor
        self.location_extractor = location_extractor
        self.job_title_extractor = job_title_extractor or JobTitleExtractor()

    def resolve(
        self,
        *,
        text: str,
        raw_text: str | None = None,
        layout_blocks: list[Any] | None = None,
        file_links: list[str] | None = None,
    ) -> dict:
        ordered_text = str(text or "")
        raw_text = str(raw_text or ordered_text)
        layout_blocks = layout_blocks or []
        template_signals = self._detect_template_signals(
            ordered_text,
            raw_text,
        )
        file_links = file_links or []

        initial_emails = self.email_extractor.extract_candidates(
            raw_text,
            ordered_text=ordered_text,
            layout_blocks=layout_blocks,
        )
        initial_phones = self.phone_extractor.extract_candidates(
            raw_text,
            ordered_text=ordered_text,
            layout_blocks=layout_blocks,
        )

        name_result = self._rank_names(
            ordered_text=ordered_text,
            raw_text=raw_text,
            layout_blocks=layout_blocks,
            email_candidates=initial_emails["accepted"],
            phone_candidates=initial_phones["accepted"],
        )

        selected_name = (
            name_result["accepted"][0]
            if name_result["accepted"]
            else None
        )
        selected_name_score = (
            int(
                selected_name.get(
                    "score",
                    0,
                )
                or 0
            )
            if selected_name
            else 0
        )
        selected_name_line = (
            selected_name.get(
                "line_index"
            )
            if selected_name
            else None
        )
        selected_name_line_number = (
            int(selected_name_line)
            if selected_name_line is not None
            else 99
        )

        if (
            template_signals
            and selected_name
            and (
                selected_name_score < 80
                or selected_name_line_number > 5
            )
        ):
            name_result["rejected"].append({
                **selected_name,
                "type": "name",
                "reason": "low_confidence_name_inside_template_body",
            })
            selected_name = None
        anchor_line = (
            selected_name.get("line_index")
            if selected_name
            else None
        )

        emails = self.email_extractor.extract_candidates(
            raw_text,
            ordered_text=ordered_text,
            layout_blocks=layout_blocks,
            anchor_line=anchor_line,
        )
        phones = self.phone_extractor.extract_candidates(
            raw_text,
            ordered_text=ordered_text,
            layout_blocks=layout_blocks,
            anchor_line=anchor_line,
        )

        selected_email = emails["accepted"][0] if emails["accepted"] else None
        selected_phone = phones["accepted"][0] if phones["accepted"] else None

        contact_lines = [
            value
            for value in [
                anchor_line,
                selected_email.get("line_index") if selected_email else None,
                selected_phone.get("line_index") if selected_phone else None,
            ]
            if value is not None
        ]

        location_result = self._rank_locations(
            ordered_text=ordered_text,
            layout_blocks=layout_blocks,
            anchor_lines=contact_lines,
        )
        selected_location = (
            location_result["accepted"][0]
            if location_result["accepted"]
            else None
        )
        if (
            template_signals
            and selected_location
            and int(selected_location.get("score", 0) or 0) < 30
        ):
            location_result["rejected"].append({
                **selected_location,
                "type": "location",
                "reason": "template_location_not_in_contact_cluster",
            })
            selected_location = None

        links_result = self._extract_links(
            ordered_text,
            file_links,
        )
        job_title = self._extract_optional(
            self.job_title_extractor,
            ordered_text,
            keys=["job_title", "title", "role"],
        )
        if job_title and job_title.isupper():
            special = {"AI", "BI", "UI", "UX", "QA", "HR", "IT", "SQL", "Python"}
            job_title = " ".join(
                word.upper() if word.upper() in special - {"Python"}
                else "Python" if word.upper() == "PYTHON"
                else word.capitalize()
                for word in job_title.split()
            )
        if not job_title:
            job_title = self._infer_job_title_from_header(
                ordered_text=ordered_text,
                selected_name=selected_name,
                selected_email=selected_email,
                selected_phone=selected_phone,
            )

        raw_rejected_candidates = (
            name_result["rejected"]
            + emails["rejected"]
            + phones["rejected"]
            + location_result["rejected"]
        )
        rejected_candidates: list[dict] = []
        rejected_index: dict[
            tuple[str, str, str],
            int,
        ] = {}
        for item in raw_rejected_candidates:
            key = (
                str(
                    item.get(
                        "type",
                        "",
                    )
                ).casefold(),
                str(
                    item.get(
                        "value",
                        "",
                    )
                ).casefold(),
                str(
                    item.get(
                        "reason",
                        "",
                    )
                ).casefold(),
            )
            if key in rejected_index:
                existing = rejected_candidates[
                    rejected_index[key]
                ]
                existing["occurrence_count"] = (
                    int(
                        existing.get(
                            "occurrence_count",
                            1,
                        )
                        or 1
                    )
                    + 1
                )
                continue
            copied = dict(item)
            copied["occurrence_count"] = 1
            rejected_index[key] = len(
                rejected_candidates
            )
            rejected_candidates.append(copied)

        confidence = {
            "name": self._score_to_confidence(selected_name),
            "email": self._score_to_confidence(selected_email),
            "phone": self._score_to_confidence(selected_phone),
            "location": self._score_to_confidence(selected_location),
        }

        quality = self._build_quality(
            selected_name=selected_name,
            selected_email=selected_email,
            selected_phone=selected_phone,
            rejected_candidates=rejected_candidates,
        )
        email_placeholder = bool(
            selected_email
            and self._is_placeholder_email(
                selected_email.get("value")
            )
        )
        phone_placeholder = bool(
            selected_phone
            and self._is_placeholder_phone(
                selected_phone.get("value")
            )
        )
        placeholder_name = bool(
            self._first_placeholder_name(
                ordered_text
            )
            and not selected_name
        )
        has_placeholder_contact = bool(
            placeholder_name
            or email_placeholder
            or phone_placeholder
        )

        if has_placeholder_contact:
            quality = {
                "status": "source_placeholder",
                "score": min(
                    25,
                    int(
                        quality.get(
                            "score",
                            25,
                        )
                        or 25
                    ),
                ),
                "warnings": list(dict.fromkeys(
                    list(
                        quality.get(
                            "warnings",
                            [],
                        )
                        or []
                    )
                    + ["resume_template_detected"]
                    + (
                        ["candidate_name_placeholder"]
                        if placeholder_name
                        else []
                    )
                    + (
                        ["candidate_email_placeholder"]
                        if email_placeholder
                        else []
                    )
                    + (
                        ["candidate_phone_placeholder"]
                        if phone_placeholder
                        else []
                    )
                )),
            }
        elif template_signals:
            quality = {
                **quality,
                "status": (
                    "needs_review"
                    if quality.get("status") != "ok"
                    else "ok"
                ),
                "warnings": list(dict.fromkeys(
                    list(
                        quality.get(
                            "warnings",
                            [],
                        )
                        or []
                    )
                    + [
                        "partially_completed_resume_template"
                    ]
                )),
            }

        return {
            "name": selected_name.get("value") if selected_name else None,
            "name_status": (
                "placeholder"
                if template_signals and not selected_name
                else "resolved" if selected_name else "unresolved"
            ),
            "name_placeholder": self._first_placeholder_name(ordered_text),
            "job_title": job_title,
            "email": selected_email.get("value") if selected_email else None,
            "email_raw": selected_email.get("raw_value") if selected_email else None,
            "email_normalization": selected_email.get("normalization") if selected_email else None,
            "email_status": "placeholder" if email_placeholder else "resolved" if selected_email else "unresolved",
            "phone": selected_phone.get("value") if selected_phone else None,
            "phone_raw": selected_phone.get("raw_value") if selected_phone else None,
            "phone_status": "placeholder" if phone_placeholder else "resolved" if selected_phone else "unresolved",
            "location": (
                selected_location.get("value")
                if selected_location
                else None
            ),
            "linkedin": links_result.get("linkedin"),
            "github": links_result.get("github"),
            "portfolio": links_result.get("portfolio"),
            "website": links_result.get("website"),
            "links": links_result.get("links", []),
            "all_emails": [
                item["value"]
                for item in emails["accepted"]
            ],
            "all_phones": [
                item["value"]
                for item in phones["accepted"]
            ],
            "confidence": confidence,
            "quality": quality,
            "evidence": {
                "name": selected_name.get("source") if selected_name else None,
                "email": selected_email.get("source") if selected_email else None,
                "phone": selected_phone.get("source") if selected_phone else None,
                "location": (
                    selected_location.get("source")
                    if selected_location
                    else None
                ),
            },
            "candidates": {
                "names": name_result["accepted"],
                "emails": emails["accepted"],
                "phones": phones["accepted"],
                "locations": location_result["accepted"],
            },
            "rejected_candidates": rejected_candidates,
            "mode": "ranked_layout_aware_contact",
            "template_signals": template_signals,
            "recommendations": self._recommendations(
                selected_email,
                selected_phone,
                links_result,
            ),
        }

    def _rank_names(
        self,
        *,
        ordered_text: str,
        raw_text: str,
        layout_blocks: list[Any],
        email_candidates: list[dict],
        phone_candidates: list[dict],
    ) -> dict:
        lines = ordered_text.splitlines()
        candidate_contact_lines: list[int] = [
            int(item["line_index"])
            for item in email_candidates + phone_candidates
            if item.get("line_index") is not None
        ]

        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for line_index, raw_line in enumerate(lines[:35]):
            line = raw_line.strip()

            if not self._looks_like_person_name(line):
                continue

            normalized = self._normalize_phrase(line)

            if normalized in self.PLACEHOLDER_NAME_PHRASES:
                rejected.append({
                    "value": line,
                    "type": "name",
                    "reason": "placeholder_candidate_name",
                    "score": -100,
                    "source": self._best_source(line, layout_blocks),
                })
                continue

            if self._is_blocked_name(normalized):
                rejected.append({
                    "value": line,
                    "type": "name",
                    "reason": "document/template title",
                    "score": -100,
                    "source": self._best_source(
                        line,
                        layout_blocks,
                    ),
                })
                continue

            score = 0
            reasons = []

            if line_index <= 8:
                score += 35
            elif line_index <= 18:
                score += 15

            if line.isupper():
                score += 12

            if candidate_contact_lines:
                distance = min(
                    abs(line_index - contact_line)
                    for contact_line in candidate_contact_lines
                )

                if distance <= 1:
                    score += 45
                    reasons.append("adjacent_to_contact")
                elif distance <= 3:
                    score += 35
                    reasons.append("near_contact")
                elif distance <= 7:
                    score += 15

            if self._name_matches_email(
                line,
                email_candidates,
            ):
                score += 20
                reasons.append("matches_email_local_part")

            repeated_state = self._repeated_state(
                line,
                layout_blocks,
            )
            source = self._best_source(
                line,
                layout_blocks,
            )

            if repeated_state == "only_repeated":
                rejected.append({
                    "value": line,
                    "type": "name",
                    "reason": "repeated header/footer name",
                    "score": score,
                    "source": source,
                })
                continue

            accepted.append({
                "value": self._normalize_name(line),
                "score": score,
                "line_index": line_index,
                "reasons": reasons,
                "source": source,
            })

        if not accepted:
            fallback = self._extract_optional(
                self.name_extractor,
                ordered_text,
                keys=["name", "full_name", "candidate_name"],
            )

            if fallback and not self._is_blocked_name(
                self._normalize_phrase(fallback)
            ):
                accepted.append({
                    "value": fallback,
                    "score": 20,
                    "line_index": 0,
                    "reasons": ["legacy_name_extractor_fallback"],
                    "source": self._best_source(
                        fallback,
                        layout_blocks,
                    ),
                })

        accepted.sort(
            key=lambda item: (
                item["score"],
                -item["line_index"],
            ),
            reverse=True,
        )

        return {
            "accepted": accepted,
            "rejected": rejected,
        }

    def _rank_locations(
        self,
        *,
        ordered_text: str,
        layout_blocks: list[Any],
        anchor_lines: list[int],
    ) -> dict:
        lines = ordered_text.splitlines()
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for line_index, raw_line in enumerate(lines[:40]):
            line = raw_line.strip()

            for candidate in self._location_candidates(line):
                normalized = self._normalize_phrase(candidate)
                source = self._best_source(candidate, layout_blocks)
                prior_heading = (
                    self._normalize_phrase(lines[line_index - 1])
                    if line_index
                    else ""
                )

                if any(
                    word in normalized.split()
                    for word in self.INSTITUTION_WORDS
                ):
                    rejected.append({
                        "value": candidate,
                        "type": "location",
                        "reason": "institutional line",
                        "score": -20,
                        "source": source,
                    })
                    continue
                candidate_terms = {
                    value
                    for value in re.split(r"[\s,]+", normalized)
                    if value
                }
                if (
                    prior_heading in self.NON_LOCATION_SECTION_HEADINGS
                    or candidate_terms
                    and candidate_terms <= self.NON_LOCATION_TERMS
                ):
                    rejected.append(
                        {
                            "value": candidate,
                            "type": "location",
                            "reason": "non_geographic_list_context",
                            "score": -30,
                            "source": source,
                        }
                    )
                    continue

                score = 10
                distance = (
                    min(abs(line_index - anchor) for anchor in anchor_lines)
                    if anchor_lines
                    else 999
                )
                source_top = float(
                    ((source or {}).get("bbox") or {}).get("top", 9999)
                )
                in_contact_region = (
                    line_index <= 10
                    or (
                        int((source or {}).get("page") or 999) == 1
                        and source_top <= 180.0
                    )
                    or bool(
                        re.search(
                            r"(?i)\b(?:location|address|city|country|"
                            r"الموقع|العنوان|المدينة|الدولة)\b",
                            line,
                        )
                    )
                )
                if not in_contact_region or (anchor_lines and distance > 5):
                    rejected.append(
                        {
                            "value": candidate,
                            "type": "location",
                            "reason": "outside_contact_region",
                            "score": -25,
                            "source": source,
                        }
                    )
                    continue

                if line_index <= 10:
                    score += 25

                if anchor_lines:
                    if distance <= 2:
                        score += 35
                    elif distance <= 5:
                        score += 20

                accepted.append({
                    "value": candidate,
                    "score": score,
                    "line_index": line_index,
                    "reasons": ["near_contact_cluster"],
                    "source": source,
                })

        if not accepted:
            fallback = self._extract_optional(
                self.location_extractor,
                ordered_text,
                keys=["location", "address", "city_country"],
            )

            if fallback:
                source = self._best_source(fallback, layout_blocks)
                source_top = float(
                    ((source or {}).get("bbox") or {}).get("top", 9999)
                )
                if not source or (
                    int(source.get("page") or 999) == 1 and source_top <= 180.0
                ):
                    accepted.append({
                        "value": fallback,
                        "score": 15,
                        "line_index": 0,
                        "reasons": ["legacy_location_extractor_fallback"],
                        "source": source,
                    })

        accepted.sort(
            key=lambda item: (
                item["score"],
                -item["line_index"],
            ),
            reverse=True,
        )

        return {
            "accepted": accepted,
            "rejected": rejected,
        }

    @classmethod
    def _location_candidates(cls, line: str) -> list[str]:
        if cls.LOCATION_PATTERN.fullmatch(line):
            return [re.sub(r"\s*,\s*", ", ", line).strip()]
        values = [
            f"{match.group(1).strip()}, {match.group(2).strip()}"
            for pattern in (
                cls.INLINE_LOCATION_PATTERN,
                cls.INLINE_ARABIC_LOCATION_PATTERN,
            )
            for match in pattern.finditer(line)
        ]
        return list(dict.fromkeys(values))

    def _looks_like_person_name(self, line: str) -> bool:
        if not line or len(line) > 55:
            return False

        if any(character.isdigit() for character in line):
            return False

        if "@" in line or "|" in line or ":" in line or "," in line:
            return False

        if line.lower() in self.SECTION_HEADINGS:
            return False

        if not self.NAME_PATTERN.fullmatch(line):
            return False

        words = self._normalize_phrase(line).split()

        if any(word in self.INSTITUTION_WORDS for word in words):
            return False

        return 2 <= len(words) <= 4

    def _is_blocked_name(self, normalized: str) -> bool:
        if self.TEMPLATE_HEADING_PATTERN.search(normalized):
            return True
        if any(
            phrase == normalized
            or phrase in normalized
            for phrase in self.GENERIC_TEMPLATE_PHRASES
        ):
            return True
        return any(
            phrase == normalized
            or phrase in normalized
            for phrase in self.BLOCKED_NAME_PHRASES
        )

    def _first_placeholder_name(self, text: str) -> str | None:
        for line in str(text or "").splitlines()[:20]:
            normalized = self._normalize_phrase(line)
            if normalized in self.PLACEHOLDER_NAME_PHRASES:
                return line.strip()
        return None

    def _is_placeholder_email(self, value: Any) -> bool:
        return bool(self.PLACEHOLDER_EMAIL_PATTERN.match(str(value or "").strip()))

    def _is_placeholder_phone(self, value: Any) -> bool:
        digits = re.sub(r"\D", "", str(value or ""))
        return bool(
            len(digits) >= 7
            and (
                len(set(digits)) <= 2
                or digits in {
                    "1234567890", "0123456789", "5555555555",
                    "0000000000", "1111111111",
                }
            )
        )

    def _detect_template_signals(
        self,
        ordered_text: str,
        raw_text: str,
    ) -> list[str]:
        combined = "\n".join([ordered_text, raw_text])
        first_lines = [
            line.strip()
            for line in combined.splitlines()[:20]
            if line.strip()
        ]
        signals = []
        if any(self.TEMPLATE_HEADING_PATTERN.search(line) for line in first_lines):
            signals.append("resume_sample_heading")
        if self._first_placeholder_name(combined):
            signals.append("placeholder_candidate_name")
        if any(self._is_placeholder_email(token) for token in re.findall(r"[\w.+-]+@[\w.-]+", combined)):
            signals.append("placeholder_email")
        if re.search(r"(?i)(?:19|20)?[xy]{2,4}|yyyy|month\s+year", combined):
            signals.append("placeholder_dates")
        lowered = combined.casefold()
        matched_generic = [
            phrase for phrase in self.GENERIC_TEMPLATE_PHRASES
            if phrase in lowered
        ]
        if len(matched_generic) >= 2:
            signals.append("generic_template_instructions")
        return list(dict.fromkeys(signals))

    def _name_matches_email(
        self,
        name: str,
        email_candidates: list[dict],
    ) -> bool:
        name_tokens = [
            token.lower()
            for token in re.findall(
                r"[A-Za-zÀ-ÖØ-öø-ÿ]+",
                name,
            )
            if len(token) >= 2
        ]

        for item in email_candidates:
            local_part = item["value"].split("@", 1)[0].lower()
            local_tokens = [
                token
                for token in re.split(r"[._+\-]+", local_part)
                if token
            ]

            matches = sum(
                1
                for token in name_tokens
                if any(
                    candidate.startswith(token[:1])
                    or candidate == token
                    for candidate in local_tokens
                )
            )

            if matches >= 2:
                return True

        return False

    def _extract_links(
        self,
        text: str,
        file_links: list[str],
    ) -> dict:
        links = list(file_links)

        if self.link_extractor is not None:
            try:
                if hasattr(self.link_extractor, "extract_and_categorize"):
                    raw = self.link_extractor.extract_and_categorize(
                        text,
                        file_links=file_links,
                    )
                elif hasattr(self.link_extractor, "extract_all"):
                    raw = self.link_extractor.extract_all(
                        text,
                        file_links=file_links,
                    )
                else:
                    raw = self.link_extractor.extract(text)

                if isinstance(raw, dict):
                    for key in ["links", "all_links", "urls", "results"]:
                        value = raw.get(key)

                        if isinstance(value, list):
                            links.extend(value)

                    for key in ("linkedin", "github", "portfolio", "other"):
                        value = raw.get(key)
                        if isinstance(value, list):
                            links.extend(value)

                    def first(value):
                        return value[0] if isinstance(value, list) and value else value

                    linkedin = first(raw.get("linkedin")) or raw.get("linkedin_url")
                    github = first(raw.get("github")) or raw.get("github_url")
                    portfolio = (
                        first(raw.get("portfolio"))
                        or raw.get("portfolio_url")
                    )
                    website = (
                        raw.get("website")
                        or raw.get("personal_website")
                        or raw.get("site")
                    )
                elif isinstance(raw, list):
                    links.extend(raw)
                    linkedin = github = portfolio = website = None
                else:
                    linkedin = github = portfolio = website = None
            except Exception:
                linkedin = github = portfolio = website = None
        else:
            linkedin = github = portfolio = website = None

        links = self._unique(links)

        linkedin = linkedin or self._find_link(links, "linkedin")
        github = github or self._find_link(links, "github")
        portfolio = portfolio or next(
            (
                link for link in links
                if self.link_extractor is not None
                and hasattr(self.link_extractor, "categorize")
                and self.link_extractor.categorize(link) == "portfolio"
            ),
            None,
        )
        if website is None and self.link_extractor is not None and hasattr(
            self.link_extractor, "extract_website"
        ):
            website = self.link_extractor.extract_website(text, file_links=file_links)
        portfolio = portfolio or website

        return {
            "links": links,
            "linkedin": linkedin,
            "github": github,
            "portfolio": portfolio,
            "website": website,
        }

    def _infer_job_title_from_header(
        self,
        *,
        ordered_text: str,
        selected_name: dict | None,
        selected_email: dict | None,
        selected_phone: dict | None,
    ) -> str | None:
        lines = [line.strip() for line in str(ordered_text or "").splitlines() if line.strip()]
        if not lines:
            return None
        anchors: list[int] = [
            int(item["line_index"])
            for item in (selected_name, selected_email, selected_phone)
            if isinstance(item, dict) and item.get("line_index") is not None
        ]
        center = min(anchors) if anchors else 0
        start = max(0, center - 2)
        end = min(len(lines), center + 10)
        for line in lines[start:end]:
            clean = re.sub(r"\s+", " ", line).strip()
            key = clean.casefold()
            if not clean or "@" in clean or re.search(r"\d{5,}", clean):
                continue
            if key in self.SECTION_HEADINGS or bool(self._first_placeholder_name(clean)):
                continue
            if self.ROLE_TITLE_PATTERN.fullmatch(clean):
                return " ".join(word.capitalize() for word in clean.split())
        return None

    def _extract_optional(
        self,
        extractor: Any,
        text: str,
        *,
        keys: list[str],
    ) -> str | None:
        if extractor is None:
            return None

        try:
            raw = (
                extractor.extract(text)
                if hasattr(extractor, "extract")
                else extractor.extract_all(text)
            )
        except Exception:
            return None

        if isinstance(raw, str):
            return raw.strip() or None

        if isinstance(raw, list):
            return str(raw[0]).strip() if raw else None

        if isinstance(raw, dict):
            for key in keys:
                value = raw.get(key)

                if isinstance(value, str) and value.strip():
                    return value.strip()

        return None

    def _build_quality(
        self,
        *,
        selected_name: dict | None,
        selected_email: dict | None,
        selected_phone: dict | None,
        rejected_candidates: list[dict],
    ) -> dict:
        scores = [
            item.get("score", 0)
            for item in [
                selected_name,
                selected_email,
                selected_phone,
            ]
            if item is not None
        ]

        completeness = sum(
            value is not None
            for value in [
                selected_name,
                selected_email,
                selected_phone,
            ]
        )

        score = round(
            (
                sum(min(100, max(0, value)) for value in scores)
                / max(1, len(scores))
            ) * 0.65
            + (completeness / 3 * 100) * 0.35
        )

        warnings = []

        if not selected_name:
            warnings.append("candidate_name_not_resolved")

        if not selected_email:
            warnings.append("candidate_email_not_resolved")

        if not selected_phone:
            warnings.append("candidate_phone_not_resolved")

        repeated_rejections = sum(
            1
            for item in rejected_candidates
            if "repeated" in str(item.get("reason", "")).lower()
        )

        if repeated_rejections:
            warnings.append(
                f"rejected_repeated_contact_candidates:{repeated_rejections}"
            )

        if score >= 80 and completeness == 3:
            status = "ok"
        elif score >= 55 and completeness >= 2:
            status = "degraded"
        else:
            status = "needs_review"

        return {
            "status": status,
            "score": max(0, min(100, score)),
            "warnings": warnings,
        }

    def _recommendations(
        self,
        selected_email: dict | None,
        selected_phone: dict | None,
        links_result: dict,
    ) -> list[dict]:
        recommendations = []

        if not selected_email:
            recommendations.append({
                "severity": "medium",
                "type": "missing_email",
                "message": "Add a clear personal or professional email address.",
            })

        if not selected_phone:
            recommendations.append({
                "severity": "medium",
                "type": "missing_phone",
                "message": "Add a clear phone number.",
            })

        if not links_result.get("linkedin"):
            recommendations.append({
                "severity": "medium",
                "type": "missing_linkedin",
                "message": "Add a LinkedIn profile if you maintain one.",
            })

        if not recommendations:
            recommendations.append({
                "severity": "good",
                "type": "complete_contact",
                "message": "Candidate contact information is clearly resolved.",
            })

        return recommendations

    def _score_to_confidence(
        self,
        item: dict | None,
    ) -> float:
        if not item:
            return 0.0

        return round(
            max(0.0, min(0.99, item.get("score", 0) / 100)),
            2,
        )

    def _normalize_phrase(self, value: str) -> str:
        value = str(value or "").lower().strip()
        value = value.replace("résumé", "resume")
        value = re.sub(r"[^\w\s]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def _normalize_name(self, value: str) -> str:
        value = re.sub(r"\s+", " ", str(value or "")).strip()

        if value.isupper():
            return value.title()

        return value

    def _block_to_dict(self, block: Any) -> dict:
        if hasattr(block, "model_dump"):
            return block.model_dump(mode="python")
        return block if isinstance(block, dict) else {}

    def _matching_blocks(
        self,
        value: str,
        layout_blocks: list[Any],
    ) -> list[dict]:
        normalized_value = value.lower()
        result = []

        for raw_block in layout_blocks:
            block = self._block_to_dict(raw_block)
            block_text = str(block.get("text") or "").lower()

            if normalized_value in block_text:
                result.append(block)

        return result

    def _repeated_state(
        self,
        value: str,
        layout_blocks: list[Any],
    ) -> str:
        matches = self._matching_blocks(
            value,
            layout_blocks,
        )

        if not matches:
            return "unknown"

        repeated = [
            bool(block.get("is_repeated_header_footer"))
            for block in matches
        ]

        if all(repeated):
            return "only_repeated"

        if any(repeated):
            return "mixed"

        return "not_repeated"

    def _best_source(
        self,
        value: str,
        layout_blocks: list[Any],
    ) -> dict | None:
        matches = self._matching_blocks(
            value,
            layout_blocks,
        )

        if not matches:
            return None

        matches.sort(
            key=lambda block: (
                bool(block.get("is_repeated_header_footer")),
                int(block.get("page") or 999),
                int(block.get("order") or 9999),
            )
        )

        block = matches[0]
        return {
            "page": block.get("page"),
            "text": block.get("text"),
            "bbox": block.get("bbox"),
            "block_id": block.get("id"),
            "is_repeated_header_footer": bool(
                block.get("is_repeated_header_footer")
            ),
        }

    def _find_link(
        self,
        links: list[str],
        word: str,
    ) -> str | None:
        for link in links:
            if word.lower() in str(link).lower():
                return str(link)

        return None

    def _unique(self, values: list[Any]) -> list[str]:
        seen = set()
        result = []

        for value in values:
            value = str(value or "").strip()

            if not value:
                continue

            key = value.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(value)

        return result
