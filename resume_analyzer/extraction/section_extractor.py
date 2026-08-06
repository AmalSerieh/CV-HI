# =====================================================================
# 📂 section_extractor.py - استخراج أقسام السيرة الذاتية
# =====================================================================
# المسؤولية:
# - تقسيم CV إلى أقسام منظمة
# - حفظ heading الأصلي
# - حساب words/confidence
# - دعم fuzzy matching + aliases
# =====================================================================

import re

from rapidfuzz import fuzz

try:
    from .text_cleaner import TextCleaner
except ImportError:
    from text_cleaner import TextCleaner

try:
    from .cv_sections import (
        OPTIONAL_SECTIONS,
        REQUIRED_SECTIONS,
        SECTION_KEYWORDS,
    )
except ImportError:
    try:
        from cv_sections import (
            OPTIONAL_SECTIONS,
            REQUIRED_SECTIONS,
            SECTION_KEYWORDS,
        )
    except ImportError:
        # Self-contained fallback for isolated regression tests and minimal
        # deployments. The project-provided registry still takes precedence.
        SECTION_KEYWORDS = {
            "summary": ["summary", "profile", "objective"],
            "experience": ["experience", "work experience", "employment history"],
            "education": ["education", "academic background"],
            "skills": ["skills", "technical skills", "core competencies"],
            "projects": ["projects", "selected projects"],
            "certifications": ["certifications", "certificates"],
            "languages": ["languages", "language skills"],
            "achievements": ["achievements", "awards", "honors"],
            "interests": ["interests", "hobbies"],
            "volunteer": ["volunteer", "community service"],
            "courses": ["courses", "training"],
            "internships": ["internships", "internship experience"],
            "leadership": ["leadership", "leadership experience"],
        }
        REQUIRED_SECTIONS = ["summary", "experience", "education", "skills"]
        OPTIONAL_SECTIONS = [
            "projects", "certifications", "languages", "achievements",
            "interests", "volunteer", "courses", "internships", "leadership",
        ]


class SectionExtractor:
    """
    استخراج أقسام السيرة الذاتية.

    يرجع result بهذا الشكل:

    {
        "sections": {
            "summary": {
                "heading": "PROFESSIONAL SUMMARY",
                "content": "...",
                "words": 25,
                "confidence": 100
            },
            ...
        },
        "found_sections": ["summary", "experience", "education"],
        "missing_required": ["skills"],
        "section_order": ["contact_header", "summary", "experience"],
        "total_words": 150
    }
    """

    SHORT_ALIASES = {
        "summary": [
            "profile",
            "professional profile",
            "personal profile",
            "career profile",
            "summary",
            "professional summary",
            "profile summary",
            "career summary",
            "about me",
            "objective",
            "career objective",
            "qualifications",
            "qualifications summary",
            "summary of qualifications",
            "value offered",
            "my story",
            "نبذة",
            "الملخص",
            "الملخص المهني",
            "الملف الشخصي",
        ],

        "experience": [
            "experience",
            "work experience",
            "work experiences",
            "work exp",
            "professional experience",
            "professional experiences",
            "professional exp",
            "prof exp",
            "employment",
            "employment history",
            "career experience",
            "relevant experience",
            "related experience",
            "related accounting experience",
            "relevant accounting experience",
            "accounting experience",
            "work history",
            "exp",
            "الخبرة",
            "الخبرة المهنية",
            "الخبرات العملية",
        ],

        "education": [
            "education",
            "academic background",
            "academic history",
            "academics",
            "educational background",
            "academic qualifications",
            "educational qualifications",
            "التعليم",
            "المؤهلات العلمية",
            "الخلفية الأكاديمية",
        ],

        "skills": [
            "skills",
            "technical skills",
            "tech skills",
            "core skills",
            "key skills",
            "skills summary",
            "technical expertise",
            "technologies",
            "tools",
            "tools and technologies",
            "tools & technologies",
            "المهارات",
            "المهارات التقنية",
        ],

        "projects": [
            "projects",
            "selected projects",
            "personal projects",
            "academic projects",
            "project experience",
            "key projects",
            "المشاريع",
            "المشروعات",
        ],

        "certifications": [
            "certifications",
            "certification",
            "certificates",
            "certs",
            "licenses",
            "licences",
            "licenses and certifications",
            "licenses & certifications",
            "credentials",
            "الشهادات",
            "الشهادات المهنية",
        ],

        "languages": [
            "languages",
            "language",
            "language skills",
            "linguistic skills",
            "اللغات",
        ],

        "achievements": [
            "achievements",
            "accomplishments",
            "awards",
            "honors",
            "awards and honors",
            "awards & honors",
            "key achievements",
        ],

        "courses": [
            "courses",
            "coursework",
            "relevant coursework",
            "training",
            "trainings",
        ],

        "internships": [
            "internship",
            "internships",
            "internship experience",
            "trainee experience",
        ],

        "volunteer": [
            "volunteer",
            "volunteering",
            "volunteer experience",
            "community service",
        ],

        "leadership": [
            "leadership",
            "leadership experience",
            "communication and leadership",
            "communication and leadership experience",
            "leadership and activities",
            "leadership and involvement",
        ],
        "additional_info": [
            "additional information",
            "additional info",
            "extra information",
            "extra info",
            "معلومات إضافية",
        ],
    }

    STRONG_ANCHORS = {
        "projects": {
            "project",
            "projects",
            "portfolio",
            "المشاريع",
            "المشروعات",
        },
        "skills": {"skill", "skills", "competencies", "المهارات"},
        "experience": {"experience", "employment", "الخبرة", "الخبرات"},
        "education": {"education", "academic", "التعليم", "المؤهلات"},
        "certifications": {
            "certification",
            "certifications",
            "certificate",
            "certificates",
            "certs",
            "credentials",
            "الشهادات",
        },
        "languages": {"language", "languages", "اللغات"},
    }
    AMBIGUOUS_ALIASES = {
        "my story": ("summary", 82, "ambiguous_section_heading"),
        "نبذة": ("summary", 84, "ambiguous_section_heading"),
    }

    def __init__(
        self,
        min_content_words: int = 2,
        include_empty_sections: bool = True,
        fuzzy_threshold: int = 92,
        cleaner: TextCleaner | None = None,
    ):
        self.required_sections = list(REQUIRED_SECTIONS)
        self.optional_sections = list(OPTIONAL_SECTIONS)

        self.min_content_words = min_content_words
        self.include_empty_sections = include_empty_sections
        self.fuzzy_threshold = fuzzy_threshold

        self.cleaner = cleaner or TextCleaner()

        self.section_keywords = self._build_section_keywords()
        self.heading_lookup = self._build_heading_lookup()

    # ================================================================
    # 📂 Main extraction
    # ================================================================

    def extract_sections(
        self,
        text: str,
        min_content_words: int | None = None,
        include_empty_sections: bool | None = None,
        *,
        layout_blocks: list[dict] | None = None,
        page_layouts: list[dict] | None = None,
    ) -> dict:
        """
        تقسيم CV إلى أقسام.

        min_content_words:
            أقل عدد كلمات حتى نعتبر القسم موجود فعلاً.

        include_empty_sections:
            True  => يرجع كل الأقسام حتى الفارغة.
            False => يرجع فقط الأقسام الموجودة + contact_header.
        """

        text = self._ensure_text(text)
        text = self._prepare_text(text)

        if not text:
            return self._empty_result()

        min_words = (
            self.min_content_words
            if min_content_words is None
            else min_content_words
        )

        keep_empty = (
            self.include_empty_sections
            if include_empty_sections is None
            else include_empty_sections
        )

        sections = self._init_sections()

        current_section = "contact_header"
        section_order = ["contact_header"]
        detected_headings = []

        line_records = self._ordered_layout_records(layout_blocks, page_layouts)
        page_layout_by_number = {
            int(page.get("page") or 0): page for page in (page_layouts or [])
        }
        if line_records:
            lines = [record["text"] for record in line_records]
        else:
            lines = text.splitlines()
        i = 0
        section_warnings: list[str] = []
        continuation_page = None
        continuation_section = None

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            matched = self._detect_heading(lines, i, line_records=line_records)

            if line_records and i > 0:
                previous_record = line_records[i - 1]
                current_record = line_records[i]
                page_changed = previous_record.get("page") != current_record.get("page")
                column_changed = previous_record.get("column") != current_record.get("column")
                page_layout = page_layout_by_number.get(
                    int(current_record.get("page") or 0), {}
                )
                parallel_column_changed = bool(
                    column_changed
                    and previous_record.get("zone_id") == current_record.get("zone_id")
                    and {
                        str(previous_record.get("column")),
                        str(current_record.get("column")),
                    }.issubset({"left", "right"})
                    and page_layout.get("layout") == "two_column"
                    and float(page_layout.get("confidence") or 0.0) >= 0.65
                )
                semantic_stream_changed = page_changed or parallel_column_changed
                if page_changed:
                    continuation_page = current_record.get("page")
                    continuation_section = (
                        current_section
                        if current_section != "contact_header"
                        else None
                    )
                if semantic_stream_changed:
                    self._finalize_section(sections, current_section)
                    can_continue = bool(
                        continuation_section
                        and matched is None
                        and current_record.get("page") == continuation_page
                        and (page_changed or parallel_column_changed)
                    )
                    if can_continue and continuation_section is not None:
                        current_section = continuation_section
                        section_data = sections[current_section]
                        if section_data.get("content", "").strip():
                            section_data["content"] = (
                                section_data["content"].rstrip() + "\n"
                            )
                        # A page may contain several independent streams.
                        # Carry the prior semantic section into the first
                        # unheaded continuation stream only; do not reuse it
                        # for later columns, footers, or decorations.
                        continuation_section = None
                    else:
                        current_section = "contact_header"

            if matched:
                self._finalize_section(sections, current_section)

                current_section = matched["section"]

                if current_section not in sections:
                    sections[current_section] = self._new_section()

                section_data = sections[current_section]

                # A resume may use more than one heading for the same
                # semantic section, for example:
                #   Qualifications Summary
                #   Value Offered
                # Preserve the first heading as the primary heading and keep
                # every source heading as evidence.
                self._append_source_heading(
                    section_data,
                    matched["heading"],
                )

                if not section_data.get("heading"):
                    section_data["heading"] = matched["heading"]

                if line_records:
                    for source_index in range(i, i + matched["consumed_lines"]):
                        if source_index < len(line_records):
                            self._append_layout_source(
                                section_data,
                                line_records[source_index],
                            )

                section_data["confidence"] = max(
                    int(section_data.get("confidence", 0) or 0),
                    int(matched["confidence"] or 0),
                )

                # When returning to an already populated semantic section,
                # add an explicit line boundary. Without this, text can become
                # "teams and projects.Expert relationship builder".
                if section_data.get("content", "").strip():
                    section_data["content"] = (
                        section_data["content"].rstrip()
                        + "\n"
                    )

                detected_headings.append({
                    "line_index": i,
                    "heading": matched["heading"],
                    "section": current_section,
                    "confidence": matched["confidence"],
                    "page": self._record_value(line_records, i, "page"),
                    "block_id": self._record_value(line_records, i, "id"),
                    "column": self._record_value(line_records, i, "column"),
                    "zone_id": self._record_value(line_records, i, "zone_id"),
                    "warning": matched.get("warning"),
                })
                if matched.get("warning"):
                    section_warnings.append(
                        f"{matched['warning']}:{current_section}:{matched['heading']}"
                    )

                if current_section not in section_order:
                    section_order.append(current_section)

                i += matched["consumed_lines"]
                continue

            section_data = sections[current_section]
            section_data["content"] += line + "\n"
            if line_records:
                self._append_layout_source(section_data, line_records[i])
            i += 1

        self._finalize_section(sections, current_section)
        self._repair_visual_template_sections(sections)

        found_sections = [
            section_name
            for section_name in section_order
            if section_name != "contact_header"
            and section_name in sections
            and sections[section_name]["words"] >= min_words
        ]

        missing_required = [
            section
            for section in self.required_sections
            if section not in found_sections
        ]

        if keep_empty:
            output_sections = sections
        else:
            output_sections = {
                section_name: sections[section_name]
                for section_name in ["contact_header"] + found_sections
                if section_name in sections
            }

        return {
            "sections": output_sections,
            "found_sections": found_sections,
            "missing_required": missing_required,
            "section_order": [
                section_name
                for section_name in section_order
                if section_name in output_sections
            ],
            "total_words": sum(
                data["words"]
                for name, data in output_sections.items()
                if name != "contact_header"
            ),
            "detected_headings": detected_headings,
            "warnings": list(dict.fromkeys(section_warnings)),
        }

    # ================================================================
    # 🔍 Heading detection
    # ================================================================

    def _detect_heading(
        self,
        lines: list[str],
        index: int,
        *,
        line_records: list[dict] | None = None,
    ) -> dict | None:
        """
        يكتشف heading من:
        - السطر الحالي فقط
        - أو دمج السطر الحالي مع السطر التالي بشرط أنهم قصار
        """

        single = lines[index].strip()

        combined_candidate = None
        current_record = line_records[index] if line_records else None
        if (
            current_record
            and current_record.get("probable_table_cell")
            and float(current_record.get("heading_probability") or 0.0) < 0.7
        ):
            return None
        if (
            current_record
            and line_records is not None
            and index > 0
            and single.endswith((".", "،", "؛"))
        ):
            previous_record = line_records[index - 1]
            neighbors = previous_record.get("neighbors") or {}
            continuation_ids = {
                str(value) for value in neighbors.get("likely_continuation") or []
            }
            if (
                str(current_record.get("id") or "") in continuation_ids
                and float(current_record.get("heading_probability") or 0.0) < 0.5
            ):
                return None

        # Multi-line headings must be evaluated first. Otherwise a heading
        # such as "Volunteer" + "Experience" is consumed as two unrelated
        # headings and its content leaks back into the work-experience section.
        if index + 1 < len(lines):
            next_line = lines[index + 1].strip()

            if self._can_combine_heading_lines(single, next_line) and (
                not line_records
                or self._layout_records_can_combine(
                    line_records[index],
                    line_records[index + 1],
                )
            ):
                combined = f"{single} {next_line}".strip()

                combined_candidate = {
                    "original": combined,
                    "normalized": self._normalize_heading(combined),
                    "consumed_lines": 2,
                }

        single_candidate = None
        if self._is_heading_like(single):
            single_candidate = {
                "original": single,
                "normalized": self._normalize_heading(single),
                "consumed_lines": 1,
            }

        candidates = []
        if (
            combined_candidate
            and combined_candidate["normalized"] in self.heading_lookup
        ):
            candidates.append(combined_candidate)
        if single_candidate:
            candidates.append(single_candidate)

        for candidate in candidates:
            result = self._match_heading(str(candidate["normalized"]))

            if result:
                return {
                    "section": result["section"],
                    "heading": candidate["original"],
                    "confidence": result["confidence"],
                    "consumed_lines": candidate["consumed_lines"],
                    "warning": result.get("warning"),
                }

        return None

    def _match_heading(self, normalized_heading: str) -> dict | None:
        """
        مطابقة heading:
        1. exact match مع keywords + aliases
        2. fuzzy match بعتبة عالية
        """

        if not normalized_heading:
            return None

        exact = self.heading_lookup.get(normalized_heading)

        if exact:
            ambiguous = self.AMBIGUOUS_ALIASES.get(normalized_heading)
            if ambiguous:
                return {
                    "section": ambiguous[0],
                    "confidence": ambiguous[1],
                    "warning": ambiguous[2],
                }
            return {
                "section": exact,
                "confidence": 100,
            }

        tokens = set(normalized_heading.split())
        anchor_matches = [
            section
            for section, anchors in self.STRONG_ANCHORS.items()
            if tokens & anchors
        ]
        if len(anchor_matches) == 1:
            section = anchor_matches[0]
            warning = (
                "mixed_section_heading"
                if section == "certifications" and len(tokens) >= 3
                else "nonstandard_section_heading"
            )
            return {
                "section": section,
                "confidence": 80 if warning == "mixed_section_heading" else 86,
                "warning": warning,
            }

        best_match = None

        for section_name, keywords in self.section_keywords.items():
            for keyword in keywords:
                normalized_keyword = self._normalize_heading(keyword)

                score = max(
                    fuzz.ratio(normalized_heading, normalized_keyword),
                    fuzz.token_sort_ratio(normalized_heading, normalized_keyword),
                )

                if score >= self.fuzzy_threshold:
                    if best_match is None or score > best_match["confidence"]:
                        best_match = {
                            "section": section_name,
                            "confidence": round(score),
                        }

        return best_match

    def _normalize_heading(self, text: str) -> str:
        if not text:
            return ""

        text = text.lower().strip()

        text = text.replace("&", " and ")

        # إزالة bullets أو رموز من البداية
        text = re.sub(r"^[\s•*\-–—_/\\]+", "", text)

        # إزالة رموز من النهاية
        text = re.sub(r"[\s:|•*\-–—_/\\\.]+$", "", text)

        # Prof. Exp. => prof exp
        text = re.sub(r"[\.]+", " ", text)

        # إزالة الرموز غير المهمة
        text = re.sub(r"[^\w\s]+", " ", text)

        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _is_heading_like(self, line: str) -> bool:
        """
        يمنع اعتبار أول سطر محتوى كأنه heading.
        """

        if not line:
            return False

        stripped = line.strip()
        lower = stripped.lower()

        if len(stripped) > 70:
            return False

        if "@" in stripped or "http" in lower or "www." in lower:
            return False

        if re.search(r"\+?\d[\d\s().-]{6,}", stripped):
            return False

        if stripped.startswith(("•", "-", "*", "–", "—")):
            return False

        # غالباً محتوى وليس heading
        if stripped.endswith(".") and len(stripped.split()) > 2:
            return False

        # مثال:
        # Languages: English Spanish
        # هذا محتوى وليس heading
        if ":" in stripped:
            before, after = stripped.split(":", 1)

            if after.strip() and len(after.strip().split()) >= 2:
                return False

            if len(before.strip().split()) > 5:
                return False

        words = [
            value
            for value in re.findall(r"[\w\u0600-\u06ff]+", stripped, flags=re.UNICODE)
            if not value.isdigit()
        ]

        if not words:
            return False

        if len(words) > 7:
            return False

        # لو فيه سنوات غالباً experience line وليس heading
        if re.search(r"\b(19|20)\d{2}\b", stripped):
            return False

        # لو فيه pipe غالباً contact أو job line
        if "|" in stripped:
            return False

        return True

    def _can_combine_heading_lines(self, first: str, second: str) -> bool:
        """
        يسمح بحالات مثل:
        WORK
        EXPERIENCES

        ويمنع:
        EXPERIENCE
        Senior Software Engineer | Google | 2020
        """

        if not first or not second:
            return False

        if not self._is_heading_fragment(first):
            return False

        if not self._is_heading_fragment(second):
            return False

        combined = f"{first} {second}"

        if len(combined) > 60:
            return False

        if len(re.findall(r"[A-Za-z]+", combined)) > 5:
            return False

        return True

    def _is_heading_fragment(self, line: str) -> bool:
        line = line.strip()
        lower = line.lower()

        if not line:
            return False

        if len(line) > 35:
            return False

        if "@" in line or "http" in lower or "www." in lower:
            return False

        if "|" in line:
            return False

        if line.startswith(("•", "-", "*", "–", "—")):
            return False

        if re.search(r"\d", line):
            return False

        words = [
            value
            for value in re.findall(r"[\w\u0600-\u06ff]+", line, flags=re.UNICODE)
            if not value.isdigit()
        ]

        if not (1 <= len(words) <= 3):
            return False

        return True

    @staticmethod
    def _record_value(
        line_records: list[dict] | None,
        index: int,
        key: str,
    ):
        if not line_records or not 0 <= index < len(line_records):
            return None
        return line_records[index].get(key)

    @staticmethod
    def _stream_key(record: dict) -> tuple:
        return (
            record.get("page"),
            record.get("zone_id"),
            record.get("column"),
        )

    def _ordered_layout_records(
        self,
        layout_blocks: list[dict] | None,
        page_layouts: list[dict] | None,
    ) -> list[dict]:
        if not layout_blocks or not page_layouts:
            return []
        by_id = {
            str(block.get("id")): block
            for block in layout_blocks
            if str(block.get("id") or "")
        }
        output: list[dict] = []
        for page in sorted(page_layouts, key=lambda item: int(item.get("page") or 0)):
            for block_id in page.get("block_ids") or []:
                block = by_id.get(str(block_id))
                if (
                    not block
                    or block.get("is_repeated_header_footer")
                    or block.get("excluded_from_entities")
                    or block.get("is_template_residue")
                ):
                    continue
                text = str(block.get("text") or "").strip()
                if not text:
                    continue
                has_discretionary_wrap = text.endswith("\u00ad")
                record = dict(block)
                record["text"] = self.cleaner.clean(text).strip()
                if has_discretionary_wrap and record["text"]:
                    # Cleaning an individual layout block cannot see the next
                    # line, so retain the discretionary wrap marker until the
                    # complete section is finalized.
                    record["text"] = record["text"].rstrip() + "\u00ad"
                if record["text"]:
                    output.append(record)
        return output

    @staticmethod
    def _layout_records_can_combine(first: dict, second: dict) -> bool:
        if first.get("probable_table_cell") or second.get("probable_table_cell"):
            return False
        if (
            first.get("page") != second.get("page")
            or first.get("zone_id") != second.get("zone_id")
            or first.get("column") != second.get("column")
        ):
            return False
        first_box = first.get("bbox") or {}
        second_box = second.get("bbox") or {}
        left_delta = abs(float(first_box.get("x0", 0.0)) - float(second_box.get("x0", 0.0)))
        vertical_gap = float(second_box.get("top", 0.0)) - float(
            first_box.get("bottom", 0.0)
        )
        return left_delta <= 8.0 and -2.0 <= vertical_gap <= 18.0

    @staticmethod
    def _append_layout_source(section_data: dict, record: dict) -> None:
        block_id = str(record.get("id") or "")
        if block_id:
            block_ids = section_data.setdefault("block_ids", [])
            if block_id not in block_ids:
                block_ids.append(block_id)
        for source_key, record_key in (
            ("pages", "page"),
            ("columns", "column"),
            ("zones", "zone_id"),
        ):
            value = record.get(record_key)
            if value is None or value == "":
                continue
            values = section_data.setdefault(source_key, [])
            if value not in values:
                values.append(value)

    # ================================================================
    # 🧱 Helpers
    # ================================================================

    def _build_section_keywords(self) -> dict:
        """
        دمج SECTION_KEYWORDS من cv_sections.py مع aliases مختصرة.
        """

        keywords = {
            section: list(values)
            for section, values in SECTION_KEYWORDS.items()
        }

        known_sections = set(keywords)
        known_sections.update(self.required_sections)
        known_sections.update(self.optional_sections)

        for section_name, aliases in self.SHORT_ALIASES.items():
            # Aliases are authoritative. This allows a new section such as
            # leadership even before cv_sections.py is updated.
            keywords.setdefault(section_name, [])

            for alias in aliases:
                if alias not in keywords[section_name]:
                    keywords[section_name].append(alias)

        return keywords

    def _build_heading_lookup(self) -> dict:
        lookup = {}

        for section_name, keywords in self.section_keywords.items():
            for keyword in keywords:
                normalized = self._normalize_heading(keyword)

                if normalized:
                    lookup[normalized] = section_name

        return lookup

    def _repair_visual_template_sections(self, sections: dict) -> None:
        """
        Defensive semantic repair for positioned DOCX templates.

        Some Word templates store text boxes in XML order rather than visual
        order. The text extractor normally reconstructs the visual order, but
        this step prevents obvious semantic leakage when coordinates are not
        available.
        """
        def content(name: str) -> str:
            value = sections.get(name, {})
            return str(value.get("content", "") if isinstance(value, dict) else value or "")

        def set_content(name: str, value: str) -> None:
            section = sections.setdefault(name, self._new_section())
            section["content"] = value.strip()
            self._finalize_section(sections, name)

        experience = content("experience")
        interests = content("interests")
        education = content("education")
        languages = content("languages")
        summary = content("summary")
        header = content("contact_header")

        role_placeholder_re = re.compile(
            r"(?is)\bjob\s+title\b.*?\bcompany\s+name\b.*?"
            r"\b(?:key\s+)?responsibilit(?:y|ies)\b"
        )
        objective_instruction_re = re.compile(
            r"(?i)\bdescribe\s+in\s+a\s+few\s+lines\b|"
            r"\bintroduction\s+to\s+your\s+cover\s+letter\b|"
            r"\byour\s+career\s+goals\b"
        )
        language_pair_re = re.compile(
            r"(?i)\b[A-Za-z][A-Za-z .'-]{1,30}\s*[-–—:]\s*"
            r"(?:A1|A2|B1|B2|C1|C2|native|fluent|advanced|intermediate|beginner)\b"
        )
        contact_line_re = re.compile(
            r"(?i:@|\+?\d[\d ()\-]{7,}|\b(?:linkedin|github)\b)"
            r"|^[A-Z][A-Z &/\-]{2,40}$"
        )

        # Placeholder role slots belong to Experience, not Hobbies/Interests.
        if interests and role_placeholder_re.search(interests):
            placeholder_lines = [
                line for line in interests.splitlines()
                if role_placeholder_re.search(line)
            ]
            remaining = [
                line for line in interests.splitlines()
                if line not in placeholder_lines
            ]
            if placeholder_lines:
                merged = "\n".join(
                    value for value in [experience.strip(), *placeholder_lines]
                    if value
                )
                set_content("experience", merged)
                set_content("interests", "\n".join(remaining))
                experience = merged
                interests = "\n".join(remaining)

        # Language pairs that leaked into Education are moved to Languages.
        if education:
            education_lines = education.splitlines()
            leaked = [line for line in education_lines if language_pair_re.search(line)]
            if leaked:
                clean_education = [line for line in education_lines if line not in leaked]
                set_content("education", "\n".join(clean_education))
                set_content(
                    "languages",
                    "\n".join(value for value in [languages.strip(), *leaked] if value),
                )
                languages = "\n".join(value for value in [languages.strip(), *leaked] if value)

        # Hobbies/interests phrases that leaked into Languages are restored.
        if languages and not language_pair_re.search(languages):
            hobby_lines = [
                line for line in languages.splitlines()
                if not re.search(r"(?i)\b(?:language|languages)\b", line)
            ]
            if hobby_lines:
                set_content("languages", "")
                set_content(
                    "interests",
                    "\n".join(value for value in [interests.strip(), *hobby_lines] if value),
                )
                interests = "\n".join(value for value in [interests.strip(), *hobby_lines] if value)

        # Objective instruction text is summary/template content, not experience.
        if experience:
            experience_lines = experience.splitlines()
            objective_lines = [line for line in experience_lines if objective_instruction_re.search(line)]
            if objective_lines:
                clean_experience = [line for line in experience_lines if line not in objective_lines]
                set_content("experience", "\n".join(clean_experience))
                set_content(
                    "summary",
                    "\n".join(value for value in [summary.strip(), *objective_lines] if value),
                )
                experience = "\n".join(clean_experience)

        # Contact/header fragments should not be rejected as work experience.
        if experience and not role_placeholder_re.search(experience):
            lines = experience.splitlines()
            contact_like = [line for line in lines if contact_line_re.search(line.strip())]
            non_contact = [line for line in lines if line not in contact_like]
            has_real_role_evidence = bool(
                re.search(r"(?i)\b(?:19|20)\d{2}\b|\b(?:present|current)\b", experience)
                and re.search(
                    r"(?i)\b(?:managed|developed|created|led|performed|implemented|"
                    r"designed|coordinated|built|worked|delivered|supported)\b",
                    experience,
                )
            )
            if contact_like and not has_real_role_evidence:
                set_content("contact_header", "\n".join(value for value in [header.strip(), *contact_like] if value))
                set_content("experience", "\n".join(non_contact))

    def _prepare_text(self, text: str) -> str:
        if not text:
            return ""

        text = self.cleaner.clean(text)

        # تحويل المسافات الكبيرة إلى line break
        # مفيد لحالات مثل:
        # English (Native)      Spanish (Fluent)
        text = re.sub(r"[ \t]{3,}", "\n", text)

        # تنظيف الأسطر وإزالة النسخ التقنية المتجاورة. لا نحذف
        # التكرار الحقيقي غير المتجاور، لأن مسؤوليتين مختلفتين قد تتطابقان.
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]
        deduplicated: list[str] = []
        for line in lines:
            normalized = self._normalize_heading(line)
            if (
                deduplicated
                and normalized
                and normalized == self._normalize_heading(deduplicated[-1])
            ):
                continue
            deduplicated.append(line)

        return "\n".join(deduplicated)

    def _ensure_text(self, text: str) -> str:
        if text is None:
            return ""

        if isinstance(text, dict):
            raise TypeError(
                "Expected string, got dict. "
                "Use extracted['text'] or extracted['raw_text'] instead."
            )

        if not isinstance(text, str):
            raise TypeError(f"Expected str, got {type(text).__name__}")

        return text

    def _init_sections(self) -> dict:
        sections = {
            key: self._new_section()
            for key in self.section_keywords
        }

        sections["contact_header"] = {
            "heading": "Contact Header",
            "source_headings": ["Contact Header"],
            "content": "",
            "words": 0,
            "confidence": 100,
        }

        return sections

    def _new_section(self) -> dict:
        return {
            "heading": "",
            "source_headings": [],
            "content": "",
            "words": 0,
            "confidence": 0,
            "block_ids": [],
            "pages": [],
            "columns": [],
            "zones": [],
        }

    def _append_source_heading(
        self,
        section_data: dict,
        heading: str,
    ) -> None:
        heading = str(heading or "").strip()

        if not heading:
            return

        source_headings = section_data.setdefault(
            "source_headings",
            [],
        )
        normalized = self._normalize_heading(heading)
        existing = {
            self._normalize_heading(value)
            for value in source_headings
        }

        if normalized not in existing:
            source_headings.append(heading)

    def _finalize_section(self, sections: dict, section_name: str) -> None:
        if section_name not in sections:
            return

        content = sections[section_name]["content"].strip()
        content = re.sub(
            r"(?<=\w)\u00ad[ \t]*\n[ \t]*(?=\w)",
            "",
            content,
        )
        content = content.replace("\u00ad", "")
        sections[section_name]["content"] = content

        sections[section_name]["words"] = (
            len(re.findall(r"\b\w+\b", content))
            if content
            else 0
        )

    def _empty_result(self) -> dict:
        return {
            "sections": {},
            "found_sections": [],
            "missing_required": self.required_sections.copy(),
            "section_order": [],
            "total_words": 0,
            "warnings": [],
        }

    # ================================================================
    # 📊 Preview / stats / report
    # ================================================================

    def get_section_preview(
        self,
        sections_data: dict,
        max_chars: int = 150,
    ) -> dict:
        """
        يقبل:
        - result كامل فيه key اسمه sections
        - أو sections dict مباشرة
        """

        sections = self._get_sections_dict(sections_data)

        previews = {}

        for section_name, data in sections.items():
            content = data.get("content", "").strip()

            if content or section_name == "contact_header":
                previews[section_name] = {
                    "heading": data.get("heading", ""),
                    "source_headings": data.get(
                        "source_headings",
                        [],
                    ),
                    "words": data.get("words", 0),
                    "confidence": data.get("confidence", 0),
                    "preview": (
                        content[:max_chars] + "..."
                        if len(content) > max_chars
                        else content
                    ),
                }

        return previews

    def get_section_stats(self, sections_data: dict) -> dict:
        sections = self._get_sections_dict(sections_data)

        stats = {}

        for section_name, data in sections.items():
            content = data.get("content", "").strip()

            if not content:
                continue

            stats[section_name] = {
                "heading": data.get("heading", ""),
                "source_headings": data.get(
                    "source_headings",
                    [],
                ),
                "words": data.get("words", 0),
                "chars": len(content),
                "lines": len(content.splitlines()),
                "bullets": (
                    content.count("•")
                    + content.count("-")
                    + content.count("*")
                ),
            }

        return stats

    def print_report(self, result: dict) -> None:
        sections = result.get("sections", {})
        found = result.get("found_sections", [])
        missing = result.get("missing_required", [])
        section_order = result.get("section_order", [])

        print("\n" + "=" * 70)
        print("                    📂 CV SECTIONS REPORT")
        print("=" * 70)

        print(f"\n📊 Found Sections ({len(found)} data sections + header):")
        print("-" * 70)

        for section_name in section_order:
            if section_name not in sections:
                continue

            if section_name not in found and section_name != "contact_header":
                continue

            data = sections[section_name]
            conf = f"[{data['confidence']}%]" if data["confidence"] else "[0%]"

            print(
                f"   ✅ {section_name:<18} → "
                f"\"{data['heading']:<24}\" "
                f"{conf:>7} "
                f"({data['words']:>3} words)"
            )

        if missing:
            print("\n❌ Missing Required Sections:")
            print("-" * 70)

            suggestions_map = {
                "summary": "Add: Summary, Profile, or Professional Summary",
                "experience": "Add: Experience, Work Experience, or Employment History",
                "education": "Add: Education or Academic Background",
                "skills": "Add: Skills, Technical Skills, or Core Skills",
            }

            for section in missing:
                print(
                    f"   ❌ {section:<18} → "
                    f"{suggestions_map.get(section, '')}"
                )

        print("\n📝 Section Previews:")
        print("-" * 70)

        previews = self.get_section_preview(sections)

        for section_name, preview_data in previews.items():
            if preview_data["words"] <= 0:
                continue

            print(
                f"\n   [{section_name.upper()}] "
                f"\"{preview_data['heading']}\" "
                f"({preview_data['words']} words)"
            )
            print(f"   {'─' * 60}")
            print(f"   {preview_data['preview']}")

        print("\n📊 Overall Stats:")
        print("-" * 70)
        print(f"   Total Data Sections:  {len(found)}")
        print(f"   Total Words:          {result.get('total_words', 0)}")
        print(f"   Missing Required:     {len(missing)}")

        print("\n" + "=" * 70)

    def _get_sections_dict(self, data: dict) -> dict:
        if not data:
            return {}

        if "sections" in data and isinstance(data["sections"], dict):
            return data["sections"]

        return data

    # ================================================================
    # 🔁 Optional legacy compatibility
    # ================================================================

    def to_legacy_tuple(self, result: dict) -> tuple[dict, list, dict]:
        """
        للملفات القديمة التي كانت تتوقع:
        sections, found_sections, section_headings

        sections هنا تكون:
        {
            "summary": "content text",
            ...
        }
        """

        sections_data = result.get("sections", {})

        plain_sections = {
            name: data.get("content", "")
            for name, data in sections_data.items()
        }

        section_headings = {
            name: data.get("heading", "")
            for name, data in sections_data.items()
        }

        return (
            plain_sections,
            result.get("found_sections", []),
            section_headings,
        )


# =====================================================================
# 🧪 اختبار
# =====================================================================

if __name__ == "__main__":
    extractor = SectionExtractor(
        min_content_words=2,
        include_empty_sections=True,
    )

    sample_cv = """
    John A. Smith
    Senior Software Engineer
    john@example.test | +1-555-123-4567

    PROFESSIONAL SUMMARY
    Experienced software engineer with 8+ years in web development.
    Skilled in Python, JavaScript, and cloud technologies.

    WORK
    EXPERIENCES
    Senior Software Engineer | Google | 2020-Present
    • Developed microservices handling 1M+ requests/day
    • Led team of 5 engineers for cloud migration project

    EDUCATION
    M.Sc. Computer Science | Stanford University | 2017
    B.Sc. Software Engineering | MIT | 2015

    TECHNICAL SKILLS
    Languages: Python, JavaScript, C++, Java
    Frameworks: React, Node.js, Django, Flask
    Cloud: AWS, Azure, Docker, Kubernetes

    LANGUAGES
    English (Native)      Spanish (Fluent)

    ACHIEVEMENTS
    • Employee of the Year 2022
    """

    result = extractor.extract_sections(sample_cv)
    extractor.print_report(result)

    print("\nFound:", result["found_sections"])
    print("Missing:", result["missing_required"])
