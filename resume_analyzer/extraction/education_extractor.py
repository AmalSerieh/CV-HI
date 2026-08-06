# =====================================================================
# 🎓 education_extractor.py
# =====================================================================
# Professional Education Extractor for CV/Resume Parsing
#
# Responsibilities:
# - Extract education entries from SectionExtractor result OR raw text
# - Works even when there is no explicit Education heading
# - Extracts: degree, field, institution, location, dates, GPA, honors
# - Supports multi-entry education sections
# - Uses Regex + Rule-Based logic + optional spaCy NER
# - No downloads, no internet dependency
# =====================================================================

import re
from typing import Any

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    SPACY_AVAILABLE = False

try:
    from models.model_registry import ModelRegistry
except ImportError:
    ModelRegistry = None


class EducationExtractor:
    """Extract structured education information from CV/resume text."""

    # ================================================================
    # Section headings
    # ================================================================

    EDUCATION_HEADINGS = {
        "education",
        "academic background",
        "qualifications",
        "academic qualifications",
        "education and training",
        "education & training",
        "educational background",
        "education history",
        "academic history",
        "studies",
        "academic record",
        "academic profile",
        "training and education",
        "formation",
    }

    STOP_HEADINGS = {
        "summary", "profile", "objective", "experience", "work experience",
        "professional experience", "employment", "employment history",
        "skills", "technical skills", "projects", "certifications",
        "certificates", "languages", "awards", "achievements",
        "publications", "references", "volunteer", "volunteering",
        "interests", "hobbies", "contact", "personal information",
        "related experience", "related accounting experience",
        "relevant accounting experience", "accounting experience",
        "communication and leadership",
        "communication and leadership experience",
        "leadership", "leadership experience",
        "corporate training", "professional training",
        "training", "courses",
    }

    # ================================================================
    # Degree database
    # ================================================================

    DEGREE_PATTERNS = {
        "PhD": [
            "phd", "ph.d", "ph d", "doctorate", "doctoral",
            "doctor of philosophy", "dphil", "d.phil",
        ],

        "Master": [
            "master", "master's", "masters",
            "master degree", "master's degree",
            "master of science", "master of arts",
            "master of engineering", "master of technology",
            "m.sc", "msc",
            "mba", "m.b.a",
            "meng", "m.eng", "mtech", "m.tech",
            "mfa", "mph",
        ],

        "Bachelor": [
            "bachelor", "bachelor's", "bachelors",
            "bachelor degree", "bachelor's degree",
            "bachelor of science", "bachelor of arts",
            "bachelor of engineering", "bachelor of technology",
            "b.sc", "bsc",
            "b.eng", "beng",
            "b.tech", "btech", "bba", "b.b.a",
            "bcom", "b.com", "undergraduate degree", "بكالوريوس",
        ],

        "Diploma": [
            "diploma", "higher diploma", "graduate diploma",
            "postgraduate diploma", "associate degree",
            "associate of science", "associate of arts",
            "certificate", "professional certificate",
        ],

        "High School": [
            "high school", "secondary school", "secondary education",
            "high school diploma", "ged", "tawjihi", "a-level",
            "a level", "igcse",
        ],
    }

    DEGREE_RANK = {
        "High School": 1,
        "Diploma": 2,
        "Bachelor": 3,
        "Master": 4,
        "PhD": 5,
    }

    # ================================================================
    # Fields database
    # ================================================================

    FIELDS = [
        "informatics engineering",
        "computer science",
        "software engineering",
        "computer engineering",
        "information technology",
        "information systems",
        "cyber security",
        "cybersecurity",
        "artificial intelligence",
        "data science",
        "machine learning",
        "business intelligence",

        "electrical engineering",
        "electronic engineering",
        "electronics engineering",
        "mechanical engineering",
        "civil engineering",
        "industrial engineering",
        "chemical engineering",
        "mechatronics engineering",
        "biomedical engineering",
        "architecture",

        "accounting",
        "finance",
        "financial management",
        "business administration",
        "business management",
        "marketing",
        "economics",
        "human resources",
        "project management",
        "management information systems",

        "medicine",
        "nursing",
        "pharmacy",
        "dentistry",
        "public health",
        "medical laboratory sciences",

        "law",
        "legal studies",
        "education",
        "english literature",
        "translation",
        "graphic design",
        "design",
        "ui ux design",
        "psychology",
        "sociology",
        "mathematics",
        "statistics",
        "physics",
        "chemistry",
        "biology",
        "هندسة المعلوماتية",
        "هندسة البرمجيات",
    ]

    FIELD_SYNONYMS = {
        "it": "Information Technology",
        "cs": "Computer Science",
        "cis": "Computer Information Systems",
        "mis": "Management Information Systems",
        "ai": "Artificial Intelligence",
        "ml": "Machine Learning",
        "cybersecurity": "Cyber Security",
        "cyber security": "Cyber Security",
        "software engineering": "Software Engineering",
        "computer engineering": "Computer Engineering",
        "computer science": "Computer Science",
        "information technology": "Information Technology",
        "data science": "Data Science",
        "informatics engineering": "Informatics Engineering",
        "هندسة المعلوماتية": "Informatics Engineering",
        "هندسة البرمجيات": "Software Engineering",
    }

    # ================================================================
    # Institution logic
    # ================================================================

    INSTITUTION_KEYWORDS = {
        "university", "college", "institute", "school", "academy",
        "faculty", "polytechnic", "campus", "conservatory",
        "seminary", "community college", "جامعة", "كلية", "معهد",
    }

    KNOWN_INSTITUTIONS = {
        "mit": "MIT",
        "stanford": "Stanford University",
        "stanford university": "Stanford University",
        "harvard": "Harvard University",
        "harvard university": "Harvard University",
        "university of jordan": "University of Jordan",
        "german jordanian university": "German Jordanian University",
        "hashemite university": "Hashemite University",
        "jordan university of science and technology": "Jordan University of Science and Technology",
        "depaul university": "DePaul University",
    }

    KNOWN_INSTITUTION_ACRONYMS = {
        "MIT", "UCLA", "NYU", "UCL", "LSE", "NUS", "ETH", "EPFL",
        "USC", "UCSD", "UCSB", "UCI", "CMU", "CALTECH",
    }

    COUNTRY_HINTS = {
        "university of jordan": "Jordan",
        "german jordanian university": "Jordan",
        "hashemite university": "Jordan",
        "jordan university of science and technology": "Jordan",
    }

    # ================================================================
    # GPA / Honors / Dates
    # ================================================================

    HONOR_KEYWORDS = [
        "summa cum laude",
        "magna cum laude",
        "cum laude",
        "dean's list",
        "deans list",
        "first class honors",
        "first class honours",
        "second class honors",
        "second class honours",
        "honors",
        "honours",
        "with distinction",
        "distinction",
        "excellent",
        "very good",
        "good",
        "scholarship",
        "merit",
    ]

    MONTH_PATTERN = (
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    )

    BAD_CONTEXT_WORDS = {
        "worked", "work", "experience", "company", "google", "microsoft",
        "developer", "engineer", "manager", "python", "docker", "aws",
        "react", "javascript", "skills", "project", "developed", "built",
        "implemented", "managed",
    }

    def __init__(self, nlp=None, use_spacy: bool = True):
        self.use_spacy = bool(use_spacy and SPACY_AVAILABLE)
        self.nlp = nlp

        if self.nlp is None and self.use_spacy:
            try:
                if ModelRegistry is not None:
                    self.nlp = ModelRegistry.get_spacy(
                        "en_core_web_sm"
                    )
                elif spacy is not None:
                    self.nlp = spacy.load("en_core_web_sm")
            except (OSError, ImportError, RuntimeError):
                self.nlp = None
                self.use_spacy = False

        self._degree_regex = self._build_degree_regex()
        self._field_regex = self._build_field_regex()

    # ================================================================
    # Public API
    # ================================================================

    def extract(self, parsed_sections_or_text: Any) -> dict:
        """
        Strict source hierarchy:

        1. Trust an explicit Education section.
        2. Otherwise extract a bounded Education section from full text.
        3. Only when no section exists, scan conservative full-text windows.

        A valid explicit Education section is never mixed with full-text
        fallback results.
        """

        full_text = self._get_full_text(parsed_sections_or_text)
        education_text = self._get_education_text(parsed_sections_or_text)
        education_text = self._truncate_at_stop_heading(education_text)

        has_explicit_education_section = bool(
            education_text and len(education_text.split()) >= 3
        )

        if not has_explicit_education_section and full_text:
            extracted_section = self._extract_education_section_from_text(
                full_text
            )

            if extracted_section:
                education_text = self._truncate_at_stop_heading(
                    extracted_section
                )
                has_explicit_education_section = True

        entries = []
        rejected_entries = []

        if has_explicit_education_section:
            candidate_text = self._normalize_text(education_text)
            placeholder_entry = self._parse_placeholder_education_section(
                candidate_text
            )
            if placeholder_entry:
                entries.append(placeholder_entry)

            for raw_entry in (
                []
                if placeholder_entry
                else self._split_into_entries(candidate_text)
            ):
                entry = self._parse_entry(raw_entry)

                if self._is_valid_education_entry(entry):
                    entries.append(entry)
                else:
                    rejected_entries.append({
                        "raw_text": raw_entry,
                        "reason": "failed_strict_education_validation",
                    })

            # If parsing failed, inspect only the bounded education section.
            if not entries:
                for window in self._scan_strict_degree_windows(
                    candidate_text
                ):
                    entry = self._parse_strict_degree_entry(window)

                    if self._is_valid_strict_education_entry(
                        entry,
                        window,
                    ):
                        entries.append(entry)
                    else:
                        rejected_entries.append({
                            "raw_text": window,
                            "reason": "failed_explicit_section_fallback",
                        })

            mode = (
                "placeholder_aware_education_section"
                if placeholder_entry
                else "explicit_education_section"
            )

        else:
            for window in self._scan_full_text_windows(full_text):
                entry = self._parse_entry(window)

                if self._is_valid_education_entry(entry):
                    entries.append(entry)
                else:
                    rejected_entries.append({
                        "raw_text": window,
                        "reason": "failed_full_text_fallback_validation",
                    })

            mode = "strict_full_text_fallback"

        entries = self._deduplicate_entries(entries)
        entries = self._sort_entries(entries)

        highest_degree = self._highest_degree(entries)
        education_score = self._calculate_education_score(entries)
        education_quality = self._build_education_quality(
            entries,
            education_score,
        )
        recommendations = self._generate_recommendations(entries)

        return {
            "education": entries,
            "highest_degree": highest_degree,
            "education_score": education_score,
            "education_quality": education_quality,
            "recommendations": recommendations,
            "count": len(entries),
            "has_education": bool(entries),
            "raw_education_text": education_text or "",
            "rejected_entries": rejected_entries,
            "mode": mode,
            "spacy_available": SPACY_AVAILABLE,
        }

    def _parse_placeholder_education_section(
        self,
        text: str,
    ) -> dict | None:
        """Pair institution, degree, location, and a template date.

        Triggered only when an explicit placeholder such as ``Month 20XX``
        is present, so normal education parsing remains unchanged.
        """
        lines = [
            line.strip()
            for line in str(text or "").splitlines()
            if line.strip()
        ]
        raw_date = next((
            line
            for line in lines
            if re.search(
                r"(?i)(?:month\s+)?(?:19|20)?[xy]{2,4}|yyyy|month\s+year",
                line,
            )
        ), None)
        if not raw_date:
            return None

        institution_line = next((
            line
            for line in lines
            if re.search(
                r"(?i)\b(?:university|college|school|institute|academy)\b",
                line,
            )
            and not re.search(r"(?i)\b(?:bachelor|master|diploma|degree)\b", line)
        ), None)
        degree_line = next((
            line
            for line in lines
            if re.search(
                r"(?i)\b(?:bachelor|master|doctor|diploma|associate degree|certificate)\b",
                line,
            )
        ), None)
        location = next((
            line
            for line in lines
            if re.fullmatch(
                r"[A-Za-zÀ-ÿ .'-]{2,40},\s*[A-Za-zÀ-ÿ .'-]{2,30}",
                line,
            )
        ), None)
        if not institution_line or not degree_line:
            return None

        parenthetical = re.match(
            r"^(.*?)\s*\((.+)\)\s*$",
            institution_line,
        )
        institution = (
            parenthetical.group(1).strip()
            if parenthetical
            else institution_line
        )
        school = (
            parenthetical.group(2).strip()
            if parenthetical
            else None
        )
        parts = [part.strip() for part in degree_line.split(",", 1)]
        degree = parts[0]
        field = None
        if len(parts) > 1:
            field = re.sub(
                r"(?i)\b(?:specialization|specialisation|major|concentration|focus)\b.*$",
                "",
                parts[1],
            ).strip(" ,-:") or parts[1]

        return {
            "degree": degree,
            "field": field,
            "institution": institution,
            "school": school,
            "location": location,
            "start_date": None,
            "end_date": None,
            "graduation_year": None,
            "raw_date_text": raw_date,
            "graduation_date_status": "placeholder_unresolved",
            "date_validation": {
                "valid": False,
                "reason": "template_date_placeholder",
            },
            "gpa": None,
            "honors": None,
            "accreditation": None,
            "description": "",
            "current": False,
            "raw_text": "\n".join(
                value
                for value in (
                    institution_line,
                    location,
                    degree_line,
                    raw_date,
                )
                if value
            ),
            "confidence": 94,
            "field_quality": {
                "status": "ok",
                "score": 88,
                "warnings": [],
                "informational_warnings": [
                    "graduation_date_placeholder_unresolved"
                ],
            },
        }

    def _truncate_at_stop_heading(self, text: str) -> str:
        """Stop education content at the next recognized CV heading."""
        if not text:
            return ""

        collected = []

        for line in str(text).splitlines():
            normalized = self._normalize_heading(line)

            if collected and normalized in self.STOP_HEADINGS:
                break

            collected.append(line)

        return "\n".join(collected).strip()

    def _scan_strict_degree_windows(self, text: str) -> list[str]:
        if not text:
            return []

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        windows = []

        degree_pattern = re.compile(
            r"\b("
            r"bachelor|b\.?sc|bsc|b\.?a|ba|bcom|b\.?com|"
            r"master|m\.?sc|msc|mba|phd|ph\.?d|"
            r"diploma|associate degree|high school|a level|gcse"
            r")\b",
            re.IGNORECASE,
        )

        for index, line in enumerate(lines):
            if not degree_pattern.search(line):
                continue

            start = max(0, index - 2)
            end = min(len(lines), index + 2)

            window = "\n".join(lines[start:end]).strip()

            if window:
                windows.append(window)

        return windows
    def _is_valid_strict_education_entry(self, entry: dict, raw_text: str) -> bool:
        """
        Accept only strong education entries from strict fallback.
        Prevents Awards / Certifications / Experience from becoming education.
        """

        if not isinstance(entry, dict):
            return False

        raw_lower = str(raw_text or "").lower()

        bad_context = [
            "awarded to",
            "scholarship",
            "certificate of appreciation",
            "work experience",
            "office assistant",
            "bookkeeper",
            "sales associate",
            "tax preparer",
            "marketing department",
        ]

        if any(bad in raw_lower for bad in bad_context):
            return False

        degree = entry.get("degree")
        institution = entry.get("institution")
        field = entry.get("field")

        if degree and (institution or field):
            return True

        return False

    def print_report(self, result: dict) -> None:
        print("\n" + "=" * 70)
        print("                    🎓 EDUCATION REPORT")
        print("=" * 70)

        print(f"\n📊 Entries: {result.get('count', 0)}")
        print(f"   Highest Degree: {result.get('highest_degree')}")
        print(f"   Education Score: {result.get('education_score', 0)}")
        print(f"   spaCy Available: {result.get('spacy_available', False)}")

        entries = result.get("education", [])

        if entries:
            print("\n📚 Education Entries:")
            print("-" * 70)

            for idx, entry in enumerate(entries, start=1):
                print(f"\n   #{idx}")
                print(f"   Degree:          {entry.get('degree')}")
                print(f"   Field:           {entry.get('field')}")
                print(f"   Institution:     {entry.get('institution')}")
                print(f"   Location:        {entry.get('location')}")
                print(f"   Start Date:      {entry.get('start_date')}")
                print(f"   End Date:        {entry.get('end_date')}")
                print(f"   Graduation Year: {entry.get('graduation_year')}")
                print(f"   Current:         {entry.get('current')}")
                print(f"   GPA:             {entry.get('gpa')}")
                print(f"   Honors:          {entry.get('honors')}")
                print(f"   Confidence:      {entry.get('confidence')}")

        recs = result.get("recommendations", [])

        if recs:
            print("\n💡 Recommendations:")
            icons = {
                "high": "❌",
                "medium": "⚠️",
                "good": "✅",
            }

            for rec in recs:
                print(f"   {icons.get(rec.get('severity'), '•')} {rec.get('message')}")

        print("\n" + "=" * 70)

    # ================================================================
    # Input handling
    # ================================================================

    def _get_full_text(self, data: Any) -> str:
        if data is None:
            return ""

        if isinstance(data, str):
            return data

        if not isinstance(data, dict):
            return ""

        if isinstance(data.get("text"), str):
            return data["text"]

        if isinstance(data.get("raw_text"), str):
            return data["raw_text"]

        sections = data.get("sections")

        if isinstance(sections, dict):
            parts = []

            for value in sections.values():
                if isinstance(value, dict):
                    content = value.get("content", "")
                    if content:
                        parts.append(content)
                elif isinstance(value, str):
                    parts.append(value)

            return "\n".join(parts)

        return ""

    def _get_education_text(self, data: Any) -> str:
        if not isinstance(data, dict):
            return ""

        sections = data.get("sections", data)

        if not isinstance(sections, dict):
            return ""

        # direct education section
        education = sections.get("education")

        if isinstance(education, dict):
            return education.get("content", "") or ""

        if isinstance(education, str):
            return education

        # flexible heading-like keys
        for key, value in sections.items():
            normalized_key = self._normalize_heading(str(key))

            if normalized_key in self.EDUCATION_HEADINGS:
                if isinstance(value, dict):
                    return value.get("content", "") or ""

                if isinstance(value, str):
                    return value

        return ""

    def _extract_education_section_from_text(self, text: str) -> str:
        if not text:
            return ""

        lines = text.splitlines()
        start_index = None

        for index, line in enumerate(lines):
            normalized = self._normalize_heading(line)

            if normalized in self.EDUCATION_HEADINGS:
                start_index = index + 1
                break

        if start_index is None:
            return ""

        collected = []

        for line in lines[start_index:]:
            normalized = self._normalize_heading(line)

            if normalized in self.STOP_HEADINGS:
                break

            collected.append(line)

        return "\n".join(collected).strip()

    # ================================================================
    # Entry splitting
    # ================================================================

    def _split_into_entries(self, text: str) -> list[str]:
        if not text:
            return []

        text = self._normalize_text(text)

        # split blank blocks first
        blocks = re.split(r"\n\s*\n+", text)

        entries = []

        for block in blocks:
            block = block.strip()

            if not block:
                continue

            entries.extend(self._split_block_lines(block))

        cleaned = []

        for entry in entries:
            entry = self._normalize_text(entry)

            if len(entry) < 3:
                continue

            if self._has_education_signal(entry):
                cleaned.append(entry)

        return cleaned

    def _split_block_lines(self, block: str) -> list[str]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]

        if not lines:
            return []

        if len(lines) == 1:
            return [lines[0]]

        entries = []
        current = []

        for line in lines:
            starts_new = (
                current
                and self._looks_like_new_education_entry(line)
                and self._has_education_signal(" ".join(current))
            )

            if starts_new:
                entries.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            entries.append("\n".join(current))

        return entries

    def _looks_like_new_education_entry(self, line: str) -> bool:
        lower = line.lower()

        if self._extract_degree(line):
            return True

        if self._extract_institution(line) and self._extract_dates(line).get("graduation_year"):
            return True

        if "faculty of" in lower:
            return True

        if self._extract_field(line) and self._extract_institution(line):
            return True

        return False

    def _scan_full_text_windows(self, text: str) -> list[str]:
        """
        Full-text fallback:
        builds small windows around education signals even without Education heading.
        """

        text = self._normalize_text(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        windows = []

        for idx, line in enumerate(lines):
            if self._has_education_signal(line):
                start = max(0, idx - 2)
                end = min(len(lines), idx + 5)
                windows.append("\n".join(lines[start:end]))

        return windows

    # ================================================================
    # Parsing
    # ================================================================

    def _parse_entry(self, raw_text: str) -> dict:
        raw_text = self._normalize_text(raw_text)

        degree = self._extract_degree(raw_text)
        degree_line = next(
            (line for line in raw_text.splitlines() if self._extract_degree(line)),
            raw_text,
        )
        field = self._extract_field(degree_line, degree)
        specialization = self._extract_specialization(degree_line, field)
        institution = self._extract_institution(raw_text)
        dates = self._extract_dates(raw_text)
        gpa = self._extract_gpa(raw_text)
        honors = self._extract_honors(raw_text)
        accreditation = self._extract_accreditation(raw_text)
        location = self._extract_location(raw_text, institution)
        description = self._extract_description(raw_text)

        # infer missing values
        if not field:
            field = self._infer_field_from_faculty(raw_text)

        if not location and institution:
            location = self._infer_location_from_institution(institution)

        current = dates.get("current", False)

        if self._is_expected_graduation(raw_text):
            current = True

        confidence = self._score_entry(
            degree=degree,
            field=field,
            institution=institution,
            dates=dates,
            gpa=gpa,
            honors=honors,
            accreditation=accreditation,
            location=location,
        )

        entry = {
            "degree": degree,
            "field": field,
            "specialization": specialization,
            "institution": institution,
            "location": location,
            "start_date": dates.get("start_date"),
            "end_date": dates.get("end_date"),
            "graduation_year": dates.get("graduation_year"),
            "gpa": gpa,
            "honors": honors,
            "accreditation": accreditation,
            "description": description,
            "current": current,
            "raw_text": raw_text,
            "confidence": confidence,
        }

        entry["field_quality"] = self._build_entry_quality(
            entry
        )

        return entry

    def _extract_specialization(self, text: str, primary_field: str | None) -> str | None:
        for line in text.splitlines():
            parts = re.split(r"\s+(?:-|–|—)\s+", line, maxsplit=1)
            if len(parts) != 2:
                continue
            candidate = self._extract_field(parts[1])
            if candidate and candidate != primary_field:
                return candidate
        match = re.search(
            r"(?i)\b(?:specialization|specialisation|concentration)\s*[:\-]\s*([^\n|;,]{2,80})",
            text,
        )
        if match:
            candidate = self._extract_field(match.group(1)) or self._clean_field(match.group(1))
            if candidate and candidate != primary_field and self._is_valid_field(candidate):
                return self._title_field(candidate)
        return None

    # ================================================================
    # Degree extraction
    # ================================================================

    def _build_degree_regex(self) -> list[tuple[str, re.Pattern]]:
        compiled = []

        for canonical, aliases in self.DEGREE_PATTERNS.items():
            aliases_sorted = sorted(aliases, key=len, reverse=True)

            for alias in aliases_sorted:
                pattern = self._alias_to_pattern(alias)
                compiled.append((canonical, re.compile(pattern, re.IGNORECASE)))

        return compiled

    def _alias_to_pattern(self, alias: str) -> str:
        alias = re.escape(alias.lower())

        # allow optional dots/spaces in abbreviated degrees
        alias = alias.replace(r"\.", r"\.?\s*")
        alias = alias.replace(r"\ ", r"\s+")

        return rf"(?<![a-z0-9]){alias}(?![a-z0-9])"

    def _extract_degree(self, text: str) -> str | None:
        if not text:
            return None

        # Strong, unambiguous degree names and abbreviations.
        for canonical, pattern in self._degree_regex:
            if pattern.search(text):
                return canonical

        # MS/MA/BS/BA/BE are ambiguous. Accept them only when the same
        # entry contains a known academic field. "MS Excel" is rejected.
        has_known_field = any(
            pattern.search(text)
            for _, pattern in self._field_regex
        )

        if has_known_field:
            if re.search(
                r"(?<!\w)m\.?\s*[sa]\.?(?!\w)",
                text,
                re.IGNORECASE,
            ):
                return "Master"

            if re.search(
                r"(?<!\w)b\.?\s*[sae]\.?(?!\w)",
                text,
                re.IGNORECASE,
            ):
                return "Bachelor"

        return None

    # ================================================================
    # Field extraction
    # ================================================================

    def _build_field_regex(self) -> list[tuple[str, re.Pattern]]:
        compiled = []

        for field in sorted(self.FIELDS, key=len, reverse=True):
            pattern = re.escape(field)
            pattern = pattern.replace(r"\ ", r"\s+")
            compiled.append((self._title_field(field), re.compile(rf"\b{pattern}\b", re.IGNORECASE)))

        return compiled

    def _extract_field(self, text: str, degree: str | None = None) -> str | None:
        if not text:
            return None

        # 1. known fields direct match
        for canonical, pattern in self._field_regex:
            if pattern.search(text):
                return canonical

        # 2. Faculty of Information Technology
        faculty = self._infer_field_from_faculty(text)

        if faculty:
            return faculty

        # 3. Master of Science in Artificial Intelligence
        patterns = [
            r"\b(?:master|bachelor|doctor|associate)\s+of\s+(?:science|arts|engineering|technology|business)\s+in\s+([A-Za-z][A-Za-z\s&/\-]{2,80})",
            r"\b(?:bachelor|master|diploma|certificate)\s+(?:of|in)\s+([A-Za-z][A-Za-z\s&/\-]{2,80})",
            r"\b(?:b\.?\s*s\.?\s*c?\.?|b\.?\s*a\.?|m\.?\s*s\.?\s*c?\.?|m\.?\s*a\.?|ph\.?\s*d\.?)\s+(?:in\s+)?([A-Za-z][A-Za-z\s&/\-]{2,80})",
            r"\bmajor\s*[:\-]\s*([A-Za-z][A-Za-z\s&/\-]{2,80})",
            r"\bfield\s*of\s*study\s*[:\-]\s*([A-Za-z][A-Za-z\s&/\-]{2,80})",
            r"\bspecialization\s*[:\-]\s*([A-Za-z][A-Za-z\s&/\-]{2,80})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if not match:
                continue

            candidate = self._clean_field(match.group(1))

            if self._is_valid_field(candidate):
                return self._title_field(candidate)

        return None

    def _infer_field_from_faculty(self, text: str) -> str | None:
        match = re.search(
            r"\bfaculty\s+of\s+([A-Za-z][A-Za-z\s&/\-]{2,80})",
            text,
            re.IGNORECASE,
        )

        if match:
            candidate = self._clean_field(match.group(1))

            if self._is_valid_field(candidate):
                return self._title_field(candidate)

        return None

    def _clean_field(self, value: str) -> str:
        value = str(value).strip()

        value = re.split(
            r"\n|\||,|;|\b(?:university|college|institute|school|academy)\b|\b(?:19|20)\d{2}\b|gpa|cgpa|grade",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        value = re.sub(r"^(in|of|major in|specialization in)\s+", "", value, flags=re.IGNORECASE)
        value = re.sub(r"[^A-Za-z&/\-\s]", " ", value)
        value = re.sub(r"\s+", " ", value)

        return value.strip()

    def _is_valid_field(self, value: str) -> bool:
        if not value:
            return False

        lower = value.lower()
        words = value.split()

        if len(value) < 2 or len(value) > 80:
            return False

        if len(words) > 8:
            return False

        if any(keyword in lower for keyword in self.INSTITUTION_KEYWORDS):
            return False

        blocked = {
            "science", "arts", "engineering", "technology",
            "degree", "education", "graduation", "expected graduation",
        }

        if lower in blocked:
            return False

        return True

    def _title_field(self, field: str) -> str:
        lower = str(field).strip().lower()

        if lower in self.FIELD_SYNONYMS:
            return self.FIELD_SYNONYMS[lower]

        small_words = {"and", "of", "in", "for", "with"}
        words = lower.split()

        result = []

        for word in words:
            if word in small_words:
                result.append(word)
            elif word.upper() in {"IT", "AI", "ML"}:
                result.append(word.upper())
            else:
                result.append(word.capitalize())

        return " ".join(result)

    # ================================================================
    # Institution extraction
    # ================================================================

    def _extract_institution(self, text: str) -> str | None:
        if not text:
            return None

        # known institution canonical
        lower = text.lower()

        for key, canonical in self.KNOWN_INSTITUTIONS.items():
            if re.search(rf"\b{re.escape(key)}\b", lower):
                return canonical

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Prefer full line with university keyword
        for line in lines:
            candidate = self._institution_from_line(line)

            if candidate:
                return candidate

        # Single-line separated entry
        parts = self._split_parts(text)

        for part in parts:
            candidate = self._institution_from_line(part)

            if candidate:
                return candidate

        # Acronyms like MIT, UCLA
        for line in lines:
            candidate = line.strip(" |,-:")

            if self._is_valid_acronym_institution(candidate):
                return candidate

        for part in parts:
            candidate = part.strip(" |,-:")

            if self._is_valid_acronym_institution(candidate):
                return candidate

        # spaCy ORG fallback
        if self.nlp is not None:
            doc = self.nlp(text[:1000])

            for ent in doc.ents:
                if ent.label_ != "ORG":
                    continue

                candidate = self._clean_institution(ent.text)

                if self._is_valid_institution(candidate):
                    return candidate

        return None

    def _institution_from_line(
        self,
        line: str,
    ) -> str | None:
        if not line:
            return None

        stripped = str(line).strip()
        lower = stripped.lower()

        # Preserve complete institution lines before shorter regex fragments
        # can reduce "State University of New Jersey at Holt State College"
        # to only "State University".
        contains_institution_keyword = any(
            keyword in lower
            for keyword in self.INSTITUTION_KEYWORDS
        )
        contains_degree = any(
            pattern.search(stripped)
            for _, pattern in self._degree_regex
        )

        if (
            contains_institution_keyword
            and not contains_degree
            and ":" not in stripped
        ):
            candidate = self._clean_institution(
                stripped
            )

            if self._is_valid_institution(
                candidate
            ):
                return candidate

        patterns = [
            (
                r"\b([A-Z][A-Za-z&.'\-]*"
                r"(?:\s+[A-Z][A-Za-z&.'\-]*){0,7}\s+"
                r"(?:University|College|Institute|School|"
                r"Academy|Polytechnic))\b"
            ),
            (
                r"\b((?:University|College|Institute|School|"
                r"Academy|Polytechnic)\s+of\s+"
                r"[A-Z][A-Za-z&.'\-]*"
                r"(?:\s+[A-Z][A-Za-z&.'\-]*){0,7})\b"
            ),
            (
                r"\b([A-Z][A-Za-z&.'\-]*"
                r"(?:\s+[A-Z][A-Za-z&.'\-]*){0,5}\s+"
                r"Faculty)\b"
            ),
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                stripped,
            )

            if match:
                candidate = (
                    self._clean_institution(
                        match.group(1)
                    )
                )

                if self._is_valid_institution(
                    candidate
                ):
                    return candidate

        if contains_institution_keyword:
            candidate = self._clean_institution(
                stripped
            )

            if self._is_valid_institution(
                candidate
            ):
                return candidate

        return None

    def _clean_institution(self, value: str) -> str:
        value = str(value).strip()

        value = re.sub(
            r"\b(?:gpa|cgpa|grade)\s*[:\-].*$",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(r"\b(?:19|20)\d{2}\b.*$", "", value)
        value = re.sub(r"\([^)]*\)", "", value)

        # Remove a trailing City or City, ST segment while preserving the
        # institution itself. This turns
        # "UNIVERSITY OF SOUTHERN INDIANA, Evansville, IN" into
        # "University of Southern Indiana".
        if any(
            keyword in value.lower()
            for keyword in self.INSTITUTION_KEYWORDS
        ):
            value = re.sub(
                r",\s*[A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){0,3}"
                r"(?:,\s*[A-Z]{2,3})?\s*$",
                "",
                value,
            )

        for _, pattern in self._degree_regex:
            value = pattern.sub("", value)

        value = re.sub(r"^[|,\-:]+", "", value)
        value = re.sub(r"[|,\-:]+$", "", value)
        value = re.sub(r"\s+", " ", value).strip()

        if value.isupper() and len(value.split()) > 1:
            small_words = {"of", "the", "and", "in", "at", "for"}
            value = " ".join(
                word.lower() if word.lower() in small_words else word.title()
                for word in value.split()
            )

        return value


    def _is_valid_institution(self, value: str) -> bool:
        if not value:
            return False

        lower = value.lower()

        if len(value) < 2 or len(value) > 120:
            return False

        if "@" in value or "http" in lower or "www." in lower:
            return False

        if re.search(r"\d{3,}", value):
            return False

        if lower in {"education", "academic background", "degree", "faculty"}:
            return False

        if not (
            any(keyword in lower for keyword in self.INSTITUTION_KEYWORDS)
            or self._is_valid_acronym_institution(value)
            or lower in self.KNOWN_INSTITUTIONS
        ):
            return False

        return True

    def _is_valid_acronym_institution(self, value: str) -> bool:
        """
        Accept acronym-only institutions only from a whitelist.

        This rejects tools and companies such as SAP, AWS, IBM, and ORACLE.
        """
        value = str(value).strip().upper()
        return value in self.KNOWN_INSTITUTION_ACRONYMS

    # ================================================================
    # Location extraction
    # ================================================================

    def _extract_location(
        self,
        text: str,
        institution: str | None = None,
    ) -> str | None:
        """
        Extract education location line-by-line.

        Regex matches are never allowed to cross a newline, preventing
        values such as "York University, Toronto\nGraduated Summa".
        """
        if not text:
            return None

        lines = [
            line.strip(" |;-")
            for line in str(text).splitlines()
            if line.strip(" |;-")
        ]

        # Explicit Location/Campus label.
        explicit_pattern = re.compile(
            r"^(?:location|campus)\s*[:\-]\s*([^\n]{2,60})$",
            re.IGNORECASE,
        )

        for line in lines:
            match = explicit_pattern.search(line)

            if match:
                candidate = self._clean_location(match.group(1))

                if self._is_valid_location(candidate):
                    return candidate

        # Prefer text appearing after the selected institution on
        # the same physical line.
        if institution:
            institution_pattern = re.compile(
                re.escape(institution),
                re.IGNORECASE,
            )

            for line in lines:
                match = institution_pattern.search(line)

                if not match:
                    continue

                suffix = line[match.end():].strip(" ,|-:")
                candidate = self._clean_location(suffix)

                if self._is_valid_location(candidate):
                    return candidate

        # Standalone City, ST or City, Country line.
        location_patterns = [
            re.compile(
                r"^([A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){0,2}),"
                r"\s*([A-Z]{2})$"
            ),
            re.compile(
                r"^([A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){0,2}),"
                r"\s*([A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){0,2})$"
            ),
        ]

        for line in lines:
            if institution and institution.lower() in line.lower():
                continue

            for pattern in location_patterns:
                if not pattern.fullmatch(line):
                    continue

                candidate = self._clean_location(line)

                if self._is_valid_location(candidate):
                    return candidate

        # Conservative NER fallback, evaluated one line at a time.
        if self.nlp is not None:
            for line in lines:
                if institution and institution.lower() in line.lower():
                    continue

                doc = self.nlp(line[:250])

                for ent in doc.ents:
                    if ent.label_ not in {"GPE", "LOC"}:
                        continue

                    candidate = self._clean_location(ent.text)

                    if self._is_valid_location(candidate):
                        return candidate

        return None

    def _clean_location(self, value: str) -> str:
        value = str(value or "").strip()

        if not value:
            return ""

        value = value.splitlines()[0]
        value = re.split(
            r"\b(?:graduated|achieved|gpa|cgpa|grade|honou?rs?|"
            r"summa|magna|cum laude|dean(?:'s)? list)\b",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        value = re.sub(r"^[,|:\-\s]+", "", value)
        value = re.sub(r"[,|:\-\s]+$", "", value)
        value = re.sub(r"\s+", " ", value)

        return value.strip()

    def _infer_location_from_institution(self, institution: str) -> str | None:
        if not institution:
            return None

        lower = institution.lower()

        for key, country in self.COUNTRY_HINTS.items():
            if key in lower:
                return country

        return None

    def _is_valid_location(self, value: str) -> bool:
        if not value:
            return False

        value = self._clean_location(value)
        lower = value.lower()

        if not value or "\n" in value or "\r" in value:
            return False

        if "@" in value or "http" in lower or "www." in lower:
            return False

        if re.search(r"\d{3,}", value):
            return False

        if len(value) > 60 or len(value.split()) > 6:
            return False

        blocked_fragments = {
            "university", "college", "school", "institute", "academy",
            "graduated", "achieved", "gpa", "cgpa", "grade",
            "honor", "honour", "summa", "magna", "cum laude",
            "bachelor", "master", "diploma", "certificate",
        }

        if any(fragment in lower for fragment in blocked_fragments):
            return False

        return bool(re.search(r"[A-Za-z\u0600-\u06FF]", value))

    # ================================================================
    # Dates extraction
    # ================================================================

    def _extract_dates(self, text: str) -> dict:
        result = {
            "start_date": None,
            "end_date": None,
            "graduation_year": None,
            "current": False,
        }

        if not text:
            return result

        month_year = rf"(?:{self.MONTH_PATTERN})\.?\s+(?:19|20)\d{{2}}"
        numeric_month_year = r"(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}"
        year = r"(?:19|20)\d{2}"
        placeholder_year = r"(?:19|20)[Xx]{2}"
        date_unit = rf"(?:{month_year}|{numeric_month_year}|{year}|{placeholder_year})"

        # Sep 2020 - Jun 2024 / 2019 - 2023 / 2019 - Present
        range_pattern = re.compile(
            rf"\b({date_unit})\s*(?:-|–|—|to)\s*((?:{date_unit})|present|current|now)\b",
            re.IGNORECASE,
        )

        match = range_pattern.search(text)

        if match:
            start_date = self._normalize_date(match.group(1))
            end_raw = match.group(2)

            if end_raw.lower() in {"present", "current", "now"}:
                end_date = "Present"
                current = True
                graduation_year = None
            else:
                end_date = self._normalize_date(end_raw)
                current = False
                graduation_year = self._year_from_date(end_date)

            result["start_date"] = start_date
            result["end_date"] = end_date
            result["graduation_year"] = graduation_year
            result["current"] = current

            return result

        # Expected Graduation 2026 / Expected 2026
        expected = re.search(
            r"\b(?:expected|anticipated)\s+(?:graduation\s+)?((?:19|20)\d{2})\b",
            text,
            re.IGNORECASE,
        )

        if expected:
            year_value = expected.group(1)
            result["end_date"] = year_value
            result["graduation_year"] = year_value
            result["current"] = True
            return result

        # Graduated 2023
        graduated = re.search(
            r"\b(?:graduated|graduation|completed|class of)\s+((?:19|20)\d{2})\b",
            text,
            re.IGNORECASE,
        )

        if graduated:
            year_value = graduated.group(1)
            result["end_date"] = year_value
            result["graduation_year"] = year_value
            result["current"] = False
            return result

        # Single month/year or year
        single_date = re.search(rf"\b({month_year}|{numeric_month_year}|{year})\b", text, re.IGNORECASE)

        if single_date:
            date_text = self._normalize_date(single_date.group(1))
            result["end_date"] = date_text
            result["graduation_year"] = self._year_from_date(date_text)
            result["current"] = False

        return result

    def _normalize_date(self, value: str) -> str:
        value = str(value).strip()
        value = re.sub(r"\s+", " ", value)
        return value

    def _year_from_date(self, value: str | None) -> str | None:
        if not value:
            return None

        match = re.search(r"(19|20)\d{2}", value)

        return match.group(0) if match else None

    def _is_expected_graduation(self, text: str) -> bool:
        return bool(re.search(r"\b(expected|anticipated)\b", text, re.IGNORECASE))

    # ================================================================
    # GPA / Honors
    # ================================================================

    def _extract_gpa(self, text: str) -> dict | None:
        """
        Extract structured GPA/grade evidence.

        Supports:
        - GPA of 8.1 out of 9.0
        - GPA: 3.8/4.0
        - CGPA 3.7
        - 88%
        - Grade: A
        """
        if not text:
            return None

        text = str(text)

        scaled_patterns = [
            re.compile(
                r"\b(?:gpa|cgpa)\s*(?:of\s+|[:\-]?\s*)"
                r"(\d+(?:\.\d{1,3})?)\s*"
                r"(?:/|out\s+of)\s*"
                r"(\d+(?:\.\d{1,3})?)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(\d+(?:\.\d{1,3})?)\s*/\s*"
                r"(4(?:\.0)?|5(?:\.0)?|9(?:\.0)?|10(?:\.0)?)\b",
                re.IGNORECASE,
            ),
        ]

        for pattern in scaled_patterns:
            match = pattern.search(text)

            if not match:
                continue

            value = float(match.group(1))
            scale = float(match.group(2))

            if not self._is_valid_gpa_pair(value, scale):
                continue

            return {
                "value": value,
                "scale": scale,
                "display": (
                    f"{self._format_number(value)}/"
                    f"{self._format_number(scale)}"
                ),
                "source_text": match.group(0).strip(),
                "type": "gpa",
            }

        plain_match = re.search(
            r"\b(?:gpa|cgpa)\s*(?:of\s+|[:\-]?\s*)"
            r"(\d+(?:\.\d{1,3})?)\b",
            text,
            re.IGNORECASE,
        )

        if plain_match:
            value = float(plain_match.group(1))

            if 0 <= value <= 10:
                return {
                    "value": value,
                    "scale": None,
                    "display": self._format_number(value),
                    "source_text": plain_match.group(0).strip(),
                    "type": "gpa",
                }

        percent_match = re.search(
            r"\b(\d{1,3}(?:\.\d+)?)\s*%",
            text,
        )

        if percent_match:
            value = float(percent_match.group(1))

            if 0 <= value <= 100:
                return {
                    "value": value,
                    "scale": 100.0,
                    "display": f"{self._format_number(value)}%",
                    "source_text": percent_match.group(0).strip(),
                    "type": "percentage",
                }

        grade_match = re.search(
            r"\bgrade\s*[:\-]?\s*"
            r"(excellent|very good|good|[A-F][+-]?)\b",
            text,
            re.IGNORECASE,
        )

        if grade_match:
            value = grade_match.group(1).strip()

            return {
                "value": value,
                "scale": None,
                "display": value,
                "source_text": grade_match.group(0).strip(),
                "type": "grade",
            }

        return None

    def _is_valid_gpa_pair(
        self,
        value: float,
        scale: float,
    ) -> bool:
        return (
            scale > 0
            and scale <= 20
            and value >= 0
            and value <= scale
        )

    def _format_number(self, value: float) -> str:
        if float(value).is_integer():
            return f"{value:.1f}"

        return f"{value:g}"

    def _extract_honors(self, text: str) -> str | None:
        if not text:
            return None

        lower = text.lower()
        found = []
        occupied_spans = []

        for honor in sorted(self.HONOR_KEYWORDS, key=len, reverse=True):
            for match in re.finditer(
                rf"\b{re.escape(honor)}\b",
                lower,
            ):
                span = match.span()

                if any(
                    span[0] >= used[0] and span[1] <= used[1]
                    for used in occupied_spans
                ):
                    continue

                occupied_spans.append(span)
                found.append(self._title_honor(honor))

        return ", ".join(self._unique(found)) if found else None

    def _title_honor(self, honor: str) -> str:
        special = {
            "dean's list": "Dean's List",
            "deans list": "Dean's List",
            "summa cum laude": "Summa Cum Laude",
            "magna cum laude": "Magna Cum Laude",
            "cum laude": "Cum Laude",
            "first class honors": "First Class Honors",
            "second class honors": "Second Class Honors",
            "excellent": "Excellent",
            "very good": "Very Good",
        }

        return special.get(honor.lower(), honor.title())

    # ================================================================
    # Validation / scoring
    # ================================================================

    def _has_education_signal(self, text: str) -> bool:
        if not text:
            return False

        return bool(
            self._extract_degree(text)
            or self._extract_field(text)
            or self._extract_institution(text)
            or self._extract_gpa(text)
            or self._extract_honors(text)
            or re.search(r"\bfaculty\s+of\b", text, re.IGNORECASE)
        )

    def _is_valid_education_entry(self, entry: dict) -> bool:
        if not entry:
            return False

        if entry.get("confidence", 0) < 45:
            return False

        raw = (entry.get("raw_text") or "").lower()

        degree = entry.get("degree")
        field = entry.get("field")
        institution = entry.get("institution")
        graduation_year = entry.get("graduation_year")
        gpa = entry.get("gpa")
        honors = entry.get("honors")

        bad_hits = sum(
            1
            for word in self.BAD_CONTEXT_WORDS
            if re.search(rf"\b{re.escape(word)}\b", raw)
        )

        strong_signals = sum(bool(value) for value in [
            degree,
            field,
            institution,
            graduation_year,
            gpa,
            honors,
        ])

        if bad_hits >= 2 and strong_signals < 3:
            return False

        if degree and (field or institution):
            return True

        # Institution by itself is no longer enough.
        if institution and (field or graduation_year or gpa or honors):
            return True

        if field and graduation_year:
            return True

        return False

    def _extract_accreditation(self, text: str) -> str | None:
        if not text:
            return None

        patterns = [
            r"\bAACSB\s+Accredited(?:\s+College\s+of\s+Business)?\b",
            r"\b(?:ABET|ACBSP|EQUIS|AMBA)\s+Accredited\b",
            r"\bAccredited\s+(?:College|School|Program|Programme)\s+of\s+[A-Za-z&'\- ]+",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return re.sub(r"\s+", " ", match.group(0)).strip()

        return None

    def _score_entry(
        self,
        degree,
        field,
        institution,
        dates,
        gpa,
        honors,
        accreditation,
        location,
    ) -> int:
        """Score extraction quality, not optional source completeness."""
        score = 0

        if degree:
            score += 30
        if institution:
            score += 30
        if field:
            score += 20

        if degree and institution and field:
            score += 8

        has_start = bool(dates.get("start_date"))
        has_end = bool(
            dates.get("end_date")
            or dates.get("graduation_year")
        )

        if has_start and has_end:
            score += 7
        elif has_end:
            score += 6
        elif has_start:
            score += 3

        if location:
            score += 3
        if accreditation:
            score += 4
        if gpa:
            score += 2
        if honors:
            score += 2

        return min(score, 96)

    def _calculate_education_score(
        self,
        entries: list[dict],
    ) -> int:
        if not entries:
            return 0

        entry_scores = [
            int(
                (entry.get("field_quality", {}) or {}).get(
                    "score",
                    entry.get("confidence", 0),
                )
                or 0
            )
            for entry in entries
        ]

        average_score = round(
            sum(entry_scores) / len(entry_scores)
        )

        consistency_bonus = (
            1
            if len(entries) >= 2
            and all(
                entry.get("degree")
                and entry.get("institution")
                for entry in entries
            )
            else 0
        )

        penalties = sum(
            min(
                12,
                len(
                    (entry.get("field_quality", {}) or {}).get(
                        "warnings",
                        [],
                    )
                ) * 3,
            )
            for entry in entries
        )

        return max(
            0,
            min(
                95,
                average_score + consistency_bonus - penalties,
            ),
        )

    def _build_entry_quality(self, entry: dict) -> dict:
        warnings: list[str] = []
        informational_warnings: list[str] = []
        raw_text = str(entry.get("raw_text") or "")

        if not entry.get("degree"):
            warnings.append("missing_degree")

        if not entry.get("institution"):
            warnings.append("missing_institution")

        if not (
            entry.get("graduation_year")
            or entry.get("end_date")
        ):
            informational_warnings.append(
                "graduation_date_not_provided_in_source"
            )
            entry["graduation_date_status"] = (
                "not_provided_in_source"
            )
        else:
            entry["graduation_date_status"] = "provided"

        if (
            re.search(
                r"\b(?:gpa|cgpa)\b",
                raw_text,
                re.IGNORECASE,
            )
            and not entry.get("gpa")
        ):
            warnings.append("gpa_evidence_not_extracted")

        location = str(entry.get("location") or "")

        if location and not self._is_valid_location(location):
            warnings.append("location_contaminated")

        score = int(entry.get("confidence", 0) or 0)

        return {
            "status": "degraded" if warnings else "ok",
            "score": score,
            "warnings": warnings,
            "informational_warnings": informational_warnings,
        }

    def _build_education_quality(
        self,
        entries: list[dict],
        education_score: int,
    ) -> dict:
        warnings: list[str] = []
        informational_warnings: list[str] = []

        for index, entry in enumerate(entries, start=1):
            field_quality = entry.get("field_quality", {}) or {}

            for warning in field_quality.get("warnings", []) or []:
                warnings.append(
                    f"education_entry_{index}:{warning}"
                )

            for warning in field_quality.get(
                "informational_warnings",
                [],
            ) or []:
                informational_warnings.append(
                    f"education_entry_{index}:{warning}"
                )

        if not entries:
            status = "needs_review"
        elif warnings or education_score < 80:
            status = "degraded"
        else:
            status = "ok"

        return {
            "status": status,
            "score": education_score,
            "warnings": warnings,
            "informational_warnings": informational_warnings,
            "entry_count": len(entries),
        }

    # ================================================================
    # Output helpers
    # ================================================================

    def _highest_degree(self, entries: list[dict]) -> str | None:
        degrees = [entry.get("degree") for entry in entries if entry.get("degree")]

        if not degrees:
            return None

        return max(degrees, key=lambda degree: self.DEGREE_RANK.get(degree, 0))

    def _sort_entries(self, entries: list[dict]) -> list[dict]:
        def key(entry):
            degree_rank = self.DEGREE_RANK.get(entry.get("degree"), 0)
            year = entry.get("graduation_year") or "0"

            try:
                year_value = int(year)
            except Exception:
                year_value = 0

            return degree_rank, year_value

        return sorted(entries, key=key, reverse=True)

    def _deduplicate_entries(self, entries: list[dict]) -> list[dict]:
        seen = set()
        result = []

        for entry in entries:
            key = (
                (entry.get("degree") or "").lower(),
                (entry.get("field") or "").lower(),
                (entry.get("institution") or "").lower(),
                str(entry.get("graduation_year") or ""),
            )

            # Avoid discarding entries that have only weak empty key
            if key == ("", "", "", ""):
                continue

            if key not in seen:
                seen.add(key)
                result.append(entry)

        return result

    def _generate_recommendations(self, entries: list[dict]) -> list[dict]:
        if not entries:
            return [{
                "severity": "high",
                "type": "missing",
                "message": "Education information is missing or unclear.",
            }]

        recommendations: list[dict] = []

        for index, entry in enumerate(entries, start=1):
            missing_required: list[str] = []

            if (
                not entry.get("degree")
                and not entry.get("field")
                and not entry.get("institution")
            ):
                missing_required.append("degree")

            if not entry.get("institution"):
                missing_required.append("institution")

            if missing_required:
                recommendations.append({
                    "severity": "medium",
                    "type": "incomplete_entry",
                    "message": (
                        f"Education entry #{index} is missing: "
                        f"{', '.join(missing_required)}."
                    ),
                })

            raw_date_text = str(
                entry.get("raw_date_text")
                or ""
            ).strip()
            placeholder_date = (
                entry.get("graduation_date_status")
                == "placeholder_unresolved"
                or bool(
                    raw_date_text
                    and re.search(
                        r"(?i)(?:19|20)?[xy]{2,4}|"
                        r"yyyy|month\s+(?:20xx|year)",
                        raw_date_text,
                    )
                )
            )

            if placeholder_date:
                recommendations.append({
                    "severity": "high",
                    "type":
                        "placeholder_graduation_date",
                    "message": (
                        "Replace the graduation date "
                        f'placeholder "{raw_date_text}" '
                        "with the actual graduation date."
                    ),
                })
            elif not (
                entry.get("graduation_year")
                or entry.get("end_date")
            ):
                recommendations.append({
                    "severity": "low",
                    "type": "source_optional_missing",
                    "message": (
                        f"Education entry #{index}: graduation "
                        "date was not provided in the source resume."
                    ),
                })

        if not recommendations:
            recommendations.append({
                "severity": "good",
                "type": "complete",
                "message": "Education section looks complete.",
            })

        return recommendations

    def _empty_result(self) -> dict:
        return {
            "education": [],
            "highest_degree": None,
            "education_score": 0,
            "education_quality": {
                "status": "needs_review",
                "score": 0,
                "warnings": ["no_valid_education_entries"],
                "entry_count": 0,
            },
            "recommendations": [
                {
                    "severity": "high",
                    "type": "empty",
                    "message": "No clear education information found.",
                }
            ],
            "count": 0,
            "has_education": False,
            "raw_education_text": "",
            "rejected_entries": [],
            "mode": "empty",
            "spacy_available": SPACY_AVAILABLE,
        }

    # ================================================================
    # General cleaning helpers
    # ================================================================

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""

        text = str(text)

        text = text.replace("–", "-").replace("—", "-")
        text = text.replace("•", "\n")
        text = re.sub(r"[ \t]{3,}", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _normalize_heading(self, text: str) -> str:
        text = str(text).lower().strip()
        text = text.replace("&", " and ")
        text = re.sub(r"[:|•*\-_/\\\.]+$", "", text)
        text = re.sub(r"[^\w\s]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_parts(self, text: str) -> list[str]:
        parts = re.split(r"\s+\|\s+|\s+-\s+|;|,", text)
        return [part.strip() for part in parts if part.strip()]

    def _extract_description(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        desc_lines = []
        coursework_started = False

        for line in lines:
            lower = line.lower()

            if self._extract_degree(line):
                continue

            if self._extract_institution(line):
                continue

            if self._extract_dates(line).get("graduation_year") or self._extract_dates(line).get("start_date"):
                continue

            if self._extract_gpa(line):
                continue

            if self._extract_honors(line):
                continue

            if "relevant coursework" in lower or "coursework" in lower:
                desc_lines.append(line)
                coursework_started = True
                continue

            if coursework_started:
                desc_lines[-1] = f"{desc_lines[-1].rstrip()} {line.lstrip()}"

        return " ".join(desc_lines).strip()

    def _unique(self, items: list) -> list:
        seen = set()
        result = []

        for item in items:
            if not item:
                continue

            item = str(item).strip()

            if not item:
                continue

            key = item.lower()

            if key not in seen:
                seen.add(key)
                result.append(item)

        return result

    def _parse_strict_degree_entry(self, raw_text: str) -> dict:
        raw_text = str(raw_text or "").strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        degree = None
        field = None
        institution = None

        joined = " ".join(lines)

        if re.search(r"\bbachelor\b|\bb\.?com\b|\bbcom\b", joined, re.IGNORECASE):
            degree = "Bachelor"

        field_match = re.search(
            r"bachelor\s+of\s+([^,\n]+)(?:,\s*([^,\n]+))?",
            joined,
            re.IGNORECASE,
        )

        if field_match:
            main_field = field_match.group(1).strip()
            sub_field = field_match.group(2).strip() if field_match.group(2) else ""

            field = main_field

            if sub_field:
                field = f"{main_field}, {sub_field}"

        for line in lines:
            if re.search(r"\buniversity\b|\bcollege\b|\bschool\b", line, re.IGNORECASE):
                institution = re.sub(r"\s*\([^)]*$", "", line).strip()
                break

        return {
            "degree": degree,
            "field": field,
            "institution": institution,
            "location": None,
            "start_date": None,
            "end_date": None,
            "graduation_year": None,
            "gpa": None,
            "honors": None,
            "description": "",
            "current": False,
            "raw_text": raw_text,
            "confidence": 75 if degree and institution else 55,
        }


# =====================================================================
# 🧪 اختبار
# =====================================================================

if __name__ == "__main__":
    extractor = EducationExtractor(use_spacy=True)

    test_cases = [
        {
            "name": "Example 1",
            "text": """
            Bachelor of Computer Science
            University of Jordan
            2019 - 2023
            GPA: 3.8/4.0
            """,
        },
        {
            "name": "Example 2",
            "text": """
            B.Sc. Computer Engineering
            German Jordanian University
            Expected Graduation 2026
            """,
        },
        {
            "name": "Example 3",
            "text": """
            Master of Science in Artificial Intelligence
            MIT
            2021
            """,
        },
        {
            "name": "Example 4",
            "text": """
            Faculty of Information Technology
            Hashemite University
            """,
        },
        {
            "name": "No Heading Full CV",
            "text": """
            Jordan Example
            Software Engineer
            jordan@example.test

            Bachelor of Computer Science
            Example University
            2019 - 2023

            Skills
            Python
            Docker
            """,
        },
    ]

    for case in test_cases:
        print("\n\n" + "#" * 70)
        print(case["name"])
        print("#" * 70)

        result = extractor.extract(case["text"])
        extractor.print_report(result)
