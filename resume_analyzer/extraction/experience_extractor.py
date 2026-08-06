# =====================================================================
# 💼 experience_extractor.py
# =====================================================================
# Professional Hybrid Experience Extractor:
# - Regex / Rule-Based for exact data: dates, companies, titles, metrics
# - Dictionary for job titles / employment types / action verbs
# - spaCy for ORG / GPE support
# - SBERT for semantic work-experience block detection
# - Supports overlapping experience detection
# - Supports volunteer experience detection
# - Calculates total experience without double-counting overlaps
# =====================================================================

import json
import os
import re
from datetime import datetime
from typing import Any

from resume_analyzer.terminology import canonical_technology

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

try:
    from sentence_transformers import SentenceTransformer, util
    SBERT_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    util = None
    SBERT_AVAILABLE = False

try:
    from .keywords import (
        ALL_KEYWORDS_DATABASE,
        find_keywords_in_text,
        normalize_keyword,
        normalize_keyword_list,
    )
except ImportError:
    from keywords import (
        ALL_KEYWORDS_DATABASE,
        find_keywords_in_text,
        normalize_keyword,
        normalize_keyword_list,
    )


class ExperienceExtractor:
    """Professional Hybrid Work Experience Extractor."""

    EXPERIENCE_HEADINGS = {
        "experience", "work experience", "professional experience",
        "employment history", "career history", "work history",
        "relevant experience", "professional background",
        "career experience", "employment experience",
        "related experience", "related accounting experience",
        "relevant accounting experience", "accounting experience",
        "internships", "internship experience",
    }

    VOLUNTEER_HEADINGS = {
        "volunteer", "volunteering", "volunteer experience",
        "voluntary experience", "community service",
        "social work", "voluntary work",
    }

    STOP_HEADINGS = {
        "summary", "profile", "objective", "education", "academic background",
        "skills", "technical skills", "projects", "personal projects",
        "certifications", "courses", "training", "languages", "awards",
        "achievements", "publications", "references", "interests",
        "contact", "personal information",
        "leadership", "leadership experience",
        "communication and leadership",
        "communication and leadership experience",
    }

    BAD_EXPERIENCE_CONTEXT = {
        "university", "college", "school", "gpa", "cgpa",
        "bachelor", "master", "phd", "diploma",
        "github", "demo", "portfolio",
        "language", "certification", "certificate",
    }
    BAD_EXPERIENCE_PATTERNS = [
        r"(?i)^\s*awarded to\b",
        r"(?i)^\s*university of victoria golden key\b",
        r"(?i)^\s*university of victoria faculty association\b",
        r"(?i)^\s*scholarship\b",
        r"(?i)^\s*honou?r\b",
        r"(?i)^\s*certificate of appreciation\b",
        r"(?i)^\s*copyright\b",
        r"(?i)^\s*and career services\b",
    ]

    JOB_TITLES = {
        # Software / IT
        "software engineer", "software developer", "frontend developer",
        "backend developer", "full stack developer", "mobile developer",
        "web developer", "data analyst", "data scientist",
        "machine learning engineer", "devops engineer", "cloud engineer",
        "qa engineer", "test engineer", "ui ux designer", "product designer",
        "system administrator", "database administrator", "business analyst",
        "technical lead", "team lead", "project manager", "product manager","assurance graduate",

        # Finance / Accounting
        "accountant", "junior accountant", "senior accountant",
        "financial analyst", "finance analyst", "auditor", "internal auditor",
        "external auditor", "tax accountant", "bookkeeper",
        "payroll specialist", "accounts payable specialist",
        "accounts receivable specialist", "finance manager",
        "accounting manager", "budget analyst",

        # Education
        "teacher", "english teacher", "math teacher", "science teacher",
        "instructor", "lecturer", "professor", "teaching assistant",
        "academic tutor", "trainer", "curriculum developer",
        "education coordinator", "school counselor",

        # Healthcare
        "doctor", "physician", "nurse", "registered nurse",
        "pharmacist", "dentist", "medical assistant",
        "lab technician", "laboratory technician",
        "radiology technician", "physiotherapist",
        "clinical researcher", "healthcare assistant",

        # Engineering
        "civil engineer", "mechanical engineer", "electrical engineer",
        "electronic engineer", "industrial engineer", "chemical engineer",
        "site engineer", "project engineer", "quality engineer",
        "maintenance engineer", "planning engineer", "structural engineer",
        "architect", "interior designer",

        # Legal
        "lawyer", "attorney", "legal assistant", "legal advisor",
        "paralegal", "legal consultant", "compliance officer",
        "contract specialist",

        # HR / Administration
        "hr specialist", "human resources specialist", "recruiter",
        "talent acquisition specialist", "hr coordinator", "hr manager",
        "office administrator", "administrative assistant",
        "executive assistant", "operations coordinator", "operations manager",

        # Sales / Marketing / Customer Service
        "sales associate", "sales representative", "sales executive", "sales manager",
        "senior account executive", "new business manager",
        "senior client strategy specialist", "benefits consultant",
        "inside sales representative", "floating sales representative",
        "retail sales representative", "account manager",
        "business development representative",
        "business development manager", "marketing specialist",
        "digital marketing specialist", "marketing manager",
        "social media specialist", "content creator", "seo specialist",
        "customer service representative", "customer support agent",
        "call center agent", "client relations officer",

        # General
        "consultant", "coordinator", "specialist", "assistant",
        "manager", "supervisor", "lead", "analyst", "officer",
        "representative", "intern", "trainee", "volunteer",
        "co-op student", "peer mentor", "finance ambassador",
    }

    JOB_SUFFIXES = {
        "engineer", "developer", "designer", "analyst", "manager",
        "specialist", "coordinator", "consultant", "assistant",
        "officer", "representative", "agent", "teacher", "instructor",
        "lecturer", "professor", "nurse", "doctor", "physician",
        "pharmacist", "dentist", "accountant", "auditor", "bookkeeper",
        "lawyer", "attorney", "paralegal", "architect", "technician",
        "administrator", "supervisor", "lead", "intern", "trainee",
        "volunteer", "researcher", "graduate", "student",
        "mentor", "ambassador", "executive",
    }

    EMPLOYMENT_TYPES = {
        "full-time": "Full-time",
        "full time": "Full-time",
        "part-time": "Part-time",
        "part time": "Part-time",
        "contract": "Contract",
        "contractor": "Contract",
        "freelance": "Freelance",
        "self-employed": "Self-employed",
        "internship": "Internship",
        "intern": "Internship",
        "temporary": "Temporary",
        "remote": "Remote",
        "hybrid": "Hybrid",
        "onsite": "Onsite",
    }

    VOLUNTEER_INDICATORS = {
        "volunteer", "volunteering", "voluntary",
        "community service", "social work", "nonprofit", "ngo",
        "تطوع", "متطوع", "متطوعة", "عمل تطوعي", "خدمة مجتمعية",
    }

    COMPANY_SUFFIXES = {
        "inc", "llc", "ltd", "limited", "corp", "corporation",
        "company", "co", "group", "solutions", "systems",
        "technologies", "technology", "consulting", "bank",
        "hospital", "school", "university", "agency", "center",
        "centre", "institute", "foundation", "organization",
        "organisation","ngo", "nonprofit", "non-profit", "charity",
    }

    ACTION_VERBS = {
        "achieved", "acquired", "administered", "advised", "analyzed",
        "answered", "applied", "assisted", "attended", "audited", "authored",
        "built", "closed", "collaborated", "commended", "communicated",
        "conducted", "contributed", "coordinated", "created", "cultivated",
        "delivered", "deployed", "designed", "developed", "distributed",
        "drafted", "drove", "earned", "ensured", "established", "evaluated",
        "executed", "expanded", "explained", "facilitated", "gained",
        "generated", "handled", "hired", "identified", "implemented",
        "improved", "increased", "initiated", "integrated", "launched", "led",
        "maintained", "managed", "mentored", "monitored", "negotiated",
        "operated", "optimized", "organized", "partnered", "paved",
        "performed", "planned", "prepared", "processed", "produced",
        "provided", "reconciled", "recognized", "reduced", "reported",
        "resolved", "reviewed", "served", "spearheaded", "streamlined",
        "supervised", "supported", "tested", "trained", "transformed",
        "updated", "worked", "wrote", "accurately",
    }

    TITLE_LABELS = {"title", "job title", "position", "role"}
    COMPANY_LABELS = {"company", "employer", "organization", "organisation", "institution", "workplace"}
    LOCATION_LABELS = {"location", "city", "country"}
    DESCRIPTION_LABELS = {
        "description", "responsibilities", "responsibility",
        "duties", "tasks", "achievements", "key achievements",
        "highlights",
    }

    EXPERIENCE_SEMANTIC_DESCRIPTIONS = [
        "work experience job title company employment dates responsibilities achievements",
        "professional experience role employer location duration duties accomplishments",
        "employment history position at company with responsibilities and results",
        "internship experience company role tasks skills achievements",
        "career history job responsibilities managed developed improved supported",
    ]

    NON_EXPERIENCE_SEMANTIC_DESCRIPTIONS = [
        "education degree university gpa graduation academic background",
        "technical skills programming languages tools frameworks list",
        "project portfolio github demo technologies application",
        "languages spoken proficiency native fluent intermediate",
        "certifications courses training awards publications",
        "contact information phone email linkedin address",
    ]

    JOB_ROLE_SEMANTIC_DESCRIPTIONS = [
        "professional job title such as accountant teacher nurse engineer analyst manager specialist",
        "work role or career position in company organization employer",
        "business finance accounting education healthcare engineering sales marketing administration job title",
    ]

    NON_JOB_ROLE_SEMANTIC_DESCRIPTIONS = [
        "company name organization employer institution",
        "project name application platform dashboard system",
        "technical skill programming language framework tool",
        "education degree university college school",
    ]

    NON_LOCATION_TERMS = {
        "remote", "hybrid", "onsite", "present", "current",
        "python", "java", "javascript", "typescript", "react",
        "node.js", "nodejs", "fastapi", "django", "flask",
        "docker", "kubernetes", "aws", "azure", "gcp",
        "sql", "mysql", "postgresql", "mongodb",
        "excel", "power bi", "tableau", "quickbooks",
        "ci/cd", "api", "rest api","jan", "january", "feb", "february", "mar", "march",
        "apr", "april", "may", "jun", "june", "jul", "july",
        "aug", "august", "sep", "sept", "september",
        "oct", "october", "nov", "november", "dec", "december",
        "supporting", "working", "reviewing", "dealing", "offering",
        "preparing", "completing", "checking", "performing",
        "devising", "providing", "responsible", "helping",
        "assisting", "verifying", "maintaining",
    }

    FORCED_TECH_PATTERNS = {
        "Docker": r"\bdocker\b",
        "Power BI": r"\bpower\s*bi\b",
        "FastAPI": r"\bfast\s*api\b|\bfastapi\b",
        "REST API": r"\brest\s*apis?\b",
        "CI/CD": r"\bci\s*/?\s*cd\b",
        "QuickBooks": r"\bquickbooks\b",
        "PostgreSQL": r"\bpostgresql\b|\bpostgres\b",
    }

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

    MONTH_NAMES = set(MONTH_TO_NUM)

    BAD_JOB_TITLE_STARTERS = {
        "answered", "applied", "assisted", "built", "commended",
        "completed", "contributed", "created", "developed", "ensured",
        "explained", "gained", "handled", "helped", "implemented",
        "improved", "initiated", "led", "managed", "performed",
        "prepared", "provided", "received", "reconciled", "resolved",
        "reviewed", "served", "supported", "took", "trained",
        "worked", "acquired", "accurately",
    }

    BAD_JOB_TITLE_PATTERNS = [
        r"(?i)^commended\s+by\b",
        r"(?i)^received\s+.+certificate\b",
        r"(?i)^responsible\s+for\b",
        r"(?i)^worked\s+(?:on|with|at)\b",
        r"(?i)^helped\s+\b",
        r"(?i)^provided\s+\b",
        r"(?i)^served\s+\b",
        r"(?i)^took\s+the\s+initiative\b",
    ]

    NON_COMPANY_TERMS = {
        "apr", "april", "aug", "august", "dec", "december",
        "feb", "february", "jan", "january", "jul", "july",
        "jun", "june", "mar", "march", "may", "nov", "november",
        "oct", "october", "sep", "sept", "september",
        "caseware", "excel", "ms excel", "microsoft excel",
        "oracle", "sap", "taxprep", "netsuite", "quickbooks",
        "simply accounting", "great plains dynamics",
        "focus report", "sunnet system", "powerpoint", "word",
    }

    BULLET_PATTERN = re.compile(r"^\s*[•\-\*►▪●○◦‣∙]\s*")

    METRIC_PATTERN = re.compile(
        r"\b("
        r"\d+(?:\.\d+)?\s*%|"
        r"\d+(?:\.\d+)?\s*(?:k|m|million|thousand)\+?|"
        r"\d+\+?\s*(?:customers|clients|users|employees|students|patients|orders|transactions|records|reports|invoices|accounts|cases|projects)"
        r")\b",
        re.IGNORECASE,
    )

    MONTH_PATTERN = (
        r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    )

    def __init__(
        self,
        use_spacy: bool = True,
        use_sbert: bool = True,
        allow_model_download: bool = True,
        model_path: str | None = None,
        model_name: str = "all-MiniLM-L6-v2",
        semantic_threshold: float = 0.42,
        role_semantic_threshold: float = 0.36,
        min_confidence: int = 35,
        max_experiences: int = 30,
        include_volunteer: bool = True,
    ):
        self.use_spacy = bool(use_spacy and SPACY_AVAILABLE)
        self.nlp = None

        if self.use_spacy:
            try:
                if ModelRegistry is not None:
                    self.nlp = ModelRegistry.get_spacy(
                        "en_core_web_sm"
                    )
                elif spacy is not None:
                    self.nlp = spacy.load(
                        "en_core_web_sm"
                    )
            except (OSError, ImportError, RuntimeError):
                self.nlp = None
                self.use_spacy = False

        self.use_sbert = use_sbert and SBERT_AVAILABLE
        self.allow_model_download = allow_model_download
        self.model_name = model_name
        self.semantic_threshold = semantic_threshold
        self.role_semantic_threshold = role_semantic_threshold
        self.include_volunteer = include_volunteer

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = (
            model_path
            if model_path
            else os.path.join(current_dir, "..", "models", "sbert_model")
        )

        self.sbert_model = None
        self.experience_embeddings = None
        self.non_experience_embeddings = None
        self.job_role_embeddings = None
        self.non_job_role_embeddings = None

        self.min_confidence = min_confidence
        self.max_experiences = max_experiences

        self.known_technologies = self._build_technology_database()
        self.job_titles = self._load_job_titles_database()

        if self.use_sbert:
            self._load_sbert_if_available()

    # ================================================================
    # Public API
    # ================================================================

    def _template_role_slots(self, text: str) -> list[dict]:
        pattern = re.compile(
            r"(?is)\bjob\s+title\b.*?\bcompany\s+name\b.*?"
            r"\b(?:key\s+)?responsibilit(?:y|ies)\b"
        )
        matches = pattern.findall(str(text or ""))
        if not matches:
            return []
        # A broad mirrored DOCX extraction often duplicates every visible
        # object. Detect the common adjacent-pair representation without
        # assuming a fixed template or person.
        normalized_lines = [
            re.sub(r"\s+", " ", line.strip()).casefold()
            for line in str(text or "").splitlines()
            if pattern.search(line)
        ]
        factor = 2 if len(normalized_lines) >= 2 and all(
            normalized_lines[index] == normalized_lines[index + 1]
            for index in range(0, len(normalized_lines) - 1, 2)
        ) else 1
        count = max(1, (len(matches) + factor - 1) // factor)
        return [
            {
                "slot_index": index,
                "job_title_placeholder": "Job Title",
                "company_placeholder": "Company Name",
                "location_placeholder": "Location",
                "date_example": "Jan 2020 - current",
                "responsibility_placeholder_count": 4,
                "status": "unresolved_template_slot",
            }
            for index in range(1, count + 1)
        ]

    def extract(self, parsed_sections_or_text: Any) -> dict:
        """Extract validated professional and dated volunteer experience."""
        full_text = self._get_full_text(parsed_sections_or_text)
        experience_text = self._get_experience_text(parsed_sections_or_text)
        undated_volunteer_activities = self._get_undated_volunteer_activities(
            parsed_sections_or_text
        )
        placeholder_role_slots = self._template_role_slots(
            "\n".join(value for value in [experience_text, full_text] if value)
        )

        if not experience_text and full_text:
            experience_text = self._extract_experience_section_from_text(full_text)

        has_explicit_section = bool(
            experience_text and len(experience_text.split()) >= 3
        )
        candidate_text = experience_text if has_explicit_section else full_text
        candidate_text = self._normalize_text(candidate_text)

        if not candidate_text:
            result = self._empty_result()
            result["undated_volunteer_activities"] = undated_volunteer_activities
            result["placeholder_role_slots"] = placeholder_role_slots
            result["placeholder_role_slot_count"] = len(placeholder_role_slots)
            if placeholder_role_slots:
                result["professional_duration_status"] = "not_computable_template_placeholders"
            return result

        entry_records = self._split_placeholder_date_entries(
            candidate_text
        )
        if not entry_records:
            entry_records = self._split_company_first_entries(candidate_text)
        if not entry_records:
            entry_records = [
                {"raw_text": raw_entry, "metadata": {}}
                for raw_entry in self._split_experience_entries(
                    candidate_text,
                    from_experience_section=has_explicit_section,
                )
            ]

        experiences = []
        rejected_entries = []

        for record in entry_records:
            raw_entry = record["raw_text"]
            metadata = record.get("metadata", {})
            source_employment_type = self._extract_employment_type(
                metadata.get("source_role_line") or raw_entry
            )
            item = self._parse_experience(
                raw_entry,
                employment_type_hint=source_employment_type,
            )
            item.update(metadata)
            errors = self._experience_validation_errors(
                item,
                from_experience_section=has_explicit_section,
            )

            if not errors:
                experiences.append(item)
            else:
                rejected_entries.append({
                    "raw_text": raw_entry,
                    "reasons": errors,
                    "parsed": {
                        "job_title": item.get("job_title"),
                        "company": item.get("company"),
                        "start_date": item.get("start_date"),
                        "end_date": item.get("end_date"),
                        "confidence": item.get("confidence"),
                    },
                })

        if not experiences and full_text and not has_explicit_section:
            for window in self._scan_full_text_windows(full_text):
                item = self._parse_experience(window)
                errors = self._experience_validation_errors(
                    item,
                    from_experience_section=False,
                )
                if not errors:
                    experiences.append(item)
                else:
                    rejected_entries.append({
                        "raw_text": window,
                        "reasons": errors,
                        "parsed": {
                            "job_title": item.get("job_title"),
                            "company": item.get("company"),
                            "start_date": item.get("start_date"),
                            "end_date": item.get("end_date"),
                            "confidence": item.get("confidence"),
                        },
                    })

        experiences = self._deduplicate_experiences(experiences)
        experiences = sorted(
            experiences,
            key=lambda item: (
                item.get("current", False),
                item.get("end_year") or 0,
                item.get("confidence", 0),
            ),
            reverse=True,
        )[: self.max_experiences]

        experiences, experience_groups = (
            self._annotate_shared_responsibility_groups(
                experiences
            )
        )

        for index, item in enumerate(experiences, start=1):
            item["field_quality"] = self._experience_entry_quality(
                item,
                index=index,
            )

        paid_experiences = [item for item in experiences if not item.get("volunteer")]
        volunteer_experiences = [item for item in experiences if item.get("volunteer")]
        professional_months = self._calculate_total_experience_months(paid_experiences)
        volunteer_months = self._calculate_total_experience_months(volunteer_experiences)
        total_months = self._calculate_total_experience_months(experiences)
        overlaps = self._detect_overlapping_experiences(experiences)

        experience_score = self._calculate_experience_score(
            experiences,
            total_months,
            rejected_count=len(rejected_entries),
        )
        experience_quality = self._build_experience_quality(
            experiences=experiences,
            rejected_entries=rejected_entries,
            score=experience_score,
        )

        result = {
            "experiences": experiences,
            "experience_groups": experience_groups,
            "shared_responsibility_group_count": len(
                experience_groups
            ),
            "count": len(experiences),
            "has_experience": bool(experiences),
            "total_experience_months": total_months,
            "total_experience_years": round(total_months / 12, 1) if total_months else 0,
            "professional_experience_months": professional_months,
            "professional_experience_years": round(professional_months / 12, 1) if professional_months else 0,
            "paid_experience_months": professional_months,
            "volunteer_experience_months": volunteer_months,
            "volunteer_experience_years": round(volunteer_months / 12, 1) if volunteer_months else 0,
            "undated_volunteer_activities": undated_volunteer_activities,
            "total_validated_experience_months": total_months,
            "total_validated_experience_years": round(total_months / 12, 1) if total_months else 0,
            "current_position": self._get_current_position(experiences),
            "top_companies": self._get_top_companies(experiences),
            "top_titles": self._get_top_titles(experiences),
            "top_technologies": self._get_top_technologies(experiences),
            "overlapping_experiences": overlaps,
            "overlap_count": len(overlaps),
            "experience_score": experience_score,
            "experience_quality": experience_quality,
            "rejected_entries": rejected_entries,
            "recommendations": self._generate_recommendations(experiences, overlaps),
            "raw_experience_text": experience_text or "",
            "mode": "explicit_experience_section" if has_explicit_section else "strict_full_text_fallback",
            "layout_mode": "employer_group" if self._split_company_first_entries(candidate_text) else "entry_first",
            "extractor_mode": self._get_mode_name(),
            "spacy_available": SPACY_AVAILABLE,
            "sbert_available": SBERT_AVAILABLE,
            "placeholder_role_slots": placeholder_role_slots,
            "placeholder_role_slot_count": len(placeholder_role_slots),
        }
        if placeholder_role_slots and not experiences:
            result["professional_duration_status"] = "not_computable_template_placeholders"
            result["recommendations"] = [{
                "severity": "high",
                "type": "replace_experience_placeholders",
                "message": (
                    f"Replace all {len(placeholder_role_slots)} experience "
                    "placeholder entries with actual roles, companies, dates, "
                    "and measurable achievements."
                ),
            }]
        return result


    def print_report(self, result: dict) -> None:
        print("\n" + "=" * 70)
        print("                    💼 EXPERIENCE REPORT")
        print("=" * 70)

        print(f"\n📊 Experiences Found: {result.get('count', 0)}")
        print(f"   Experience Score: {result.get('experience_score', 0)}")
        quality = result.get("experience_quality", {})
        print(
            f"   Quality Status:   {quality.get('status', 'unknown')} "
            f"({quality.get('score', 0)}/100)"
        )
        print(f"   Rejected Entries: {quality.get('rejected_count', 0)}")
        print(f"   Total Years:      {result.get('total_experience_years', 0)}")
        print(f"   Mode:             {result.get('mode')}")
        print(f"   Current Position: {result.get('current_position')}")

        if result.get("overlap_count", 0):
            print(f"   Overlaps:         {result.get('overlap_count')} concurrent period(s)")

        top_tech = result.get("top_technologies", [])

        if top_tech:
            print(f"   Top Tech:         {', '.join(top_tech[:12])}")

        experiences = result.get("experiences", [])

        if experiences:
            print("\n🏢 Experience Entries:")
            print("-" * 70)

            for idx, item in enumerate(experiences, start=1):
                print(f"\n   #{idx} [{item.get('confidence', 0)}% confidence]")
                print(f"   Title:        {item.get('job_title')}")
                print(f"   Company:      {item.get('company')}")
                print(f"   Location:     {item.get('location')}")
                print(f"   Type:         {item.get('employment_type')}")
                print(f"   Volunteer:    {item.get('volunteer')}")
                print(f"   Dates:        {item.get('start_date')} → {item.get('end_date')}")
                print(f"   Current:      {item.get('current')}")
                print(f"   Duration:     {item.get('duration_months')} months")
                print(f"   Technologies: {', '.join(item.get('technologies', []))}")
                print(f"   Semantic:     {item.get('semantic_score')}")

                if item.get("description"):
                    print(f"   Description:  {item.get('description')[:180]}")

                if item.get("responsibilities"):
                    print("   Responsibilities:")
                    for resp in item.get("responsibilities", [])[:5]:
                        print(f"      - {resp}")

                if item.get("metrics"):
                    print(f"   Metrics:      {', '.join(item.get('metrics'))}")

        overlaps = result.get("overlapping_experiences", [])

        if overlaps:
            print("\n🔁 Overlapping Experiences:")
            for item in overlaps:
                print(
                    f"   - {item.get('experience1')} overlaps with "
                    f"{item.get('experience2')} ({item.get('type')})"
                )

        recs = result.get("recommendations", [])

        if recs:
            print("\n💡 Recommendations:")
            icons = {"high": "❌", "medium": "⚠️", "good": "✅"}

            for rec in recs:
                print(f"   {icons.get(rec.get('severity'), '•')} {rec.get('message')}")

        print("\n" + "=" * 70)

    # ================================================================
    # SBERT
    # ================================================================

    def _load_sbert_if_available(self) -> bool:
        if self._sbert_ready():
            return True

        if not SBERT_AVAILABLE or SentenceTransformer is None:
            return False

        try:
            if ModelRegistry is not None:
                self.sbert_model = ModelRegistry.get_sbert(
                    model_path=self.model_path,
                    fallback_model_name=getattr(
                        self,
                        "model_name",
                        "all-MiniLM-L6-v2",
                    ),
                    allow_download=self.allow_model_download,
                )
            elif os.path.exists(self.model_path):
                self.sbert_model = SentenceTransformer(
                    self.model_path
                )
            elif self.allow_model_download:
                self.sbert_model = SentenceTransformer(
                    self.model_name
                )
                os.makedirs(
                    self.model_path,
                    exist_ok=True,
                )
                self.sbert_model.save(
                    self.model_path
                )
            else:
                return False

        except Exception as exc:
            print(
                f"⚠️ Experience SBERT unavailable: {exc}"
            )
            self.sbert_model = None
            return False

        try:
            self.experience_embeddings = (
                self.sbert_model.encode(
                    self.EXPERIENCE_SEMANTIC_DESCRIPTIONS,
                    convert_to_tensor=True,
                )
            )

            self.non_experience_embeddings = (
                self.sbert_model.encode(
                    self.NON_EXPERIENCE_SEMANTIC_DESCRIPTIONS,
                    convert_to_tensor=True,
                )
            )

            self.job_role_embeddings = (
                self.sbert_model.encode(
                    self.JOB_ROLE_SEMANTIC_DESCRIPTIONS,
                    convert_to_tensor=True,
                )
            )

            self.non_job_role_embeddings = (
                self.sbert_model.encode(
                    self.NON_JOB_ROLE_SEMANTIC_DESCRIPTIONS,
                    convert_to_tensor=True,
                )
            )

            return True

        except Exception as exc:
            print(
                "⚠️ Failed to build experience embeddings: "
                f"{exc}"
            )

            self.experience_embeddings = None
            self.non_experience_embeddings = None
            self.job_role_embeddings = None
            self.non_job_role_embeddings = None

            return False

    def _sbert_ready(self) -> bool:
        return (
            self.sbert_model is not None
            and self.experience_embeddings is not None
            and self.non_experience_embeddings is not None
            and self.job_role_embeddings is not None
            and self.non_job_role_embeddings is not None
            and util is not None
        )

    def _semantic_experience_score(self, text: str) -> float:
        if not text:
            return 0.0

        base_score = 0.0

        if self._sbert_ready():
            embedding = self.sbert_model.encode([text[:1200]], convert_to_tensor=True)

            exp_score = util.cos_sim(
                embedding,
                self.experience_embeddings,
            ).max().item()

            non_exp_score = util.cos_sim(
                embedding,
                self.non_experience_embeddings,
            ).max().item()

            base_score = max(0.0, exp_score - (non_exp_score * 0.35))

        dates = self._extract_dates(text)

        if dates.get("start_date") or dates.get("end_date"):
            base_score = max(base_score, 0.28)

        if self._extract_job_title(text):
            base_score = max(base_score, 0.30)

        if self._extract_company(text):
            base_score = max(base_score, 0.25)

        if any(verb in normalize_keyword(text).split() for verb in self.ACTION_VERBS):
            base_score = max(base_score, 0.26)

        return round(base_score, 3)

    def _semantic_job_role_score(self, title: str) -> float:
        if not title or not self._sbert_ready():
            return 0.0

        embedding = self.sbert_model.encode([title[:200]], convert_to_tensor=True)

        role_score = util.cos_sim(
            embedding,
            self.job_role_embeddings,
        ).max().item()

        non_role_score = util.cos_sim(
            embedding,
            self.non_job_role_embeddings,
        ).max().item()

        final = role_score - (non_role_score * 0.35)

        return round(max(0.0, final), 3)

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

    def _get_experience_text(self, data: Any) -> str:
        if not isinstance(data, dict):
            return ""

        sections = data.get("sections", data)
        if not isinstance(sections, dict):
            return ""

        collected = []
        professional_keys = [
            "experience",
            "work_experience",
            "professional_experience",
            "employment_history",
        ]
        volunteer_keys = [
            "volunteer",
            "volunteering",
            "volunteer_experience",
        ]

        def content_for(key: str) -> str:
            value = sections.get(key)
            if isinstance(value, dict):
                return str(value.get("content") or "").strip()
            if isinstance(value, str):
                return value.strip()
            return ""

        for key in professional_keys:
            content = content_for(key)
            if content and content not in collected:
                collected.append(content)

        # Separate undated activity lists from dated volunteer experience.
        # This prevents "Habitat for Humanity Volunteer; ..." from being
        # appended to the previous paid role and receiving its dates.
        if self.include_volunteer:
            for key in volunteer_keys:
                content = content_for(key)
                if (
                    content
                    and self._contains_experience_date(content)
                    and content not in collected
                ):
                    collected.append(content)

        return "\n\n".join(collected).strip()

    def _contains_experience_date(self, text: str) -> bool:
        if not text:
            return False
        return bool(re.search(
            rf"\b(?:{self.MONTH_PATTERN})\.?\s+(?:19|20)\d{{2}}\b|"
            r"\b(?:19|20)\d{2}\s*(?:-|–|—|to)\s*(?:19|20)\d{2}\b",
            text,
            re.IGNORECASE,
        ))

    def _get_undated_volunteer_activities(self, data: Any) -> list[dict]:
        if not isinstance(data, dict):
            return []

        sections = data.get("sections", data)
        if not isinstance(sections, dict):
            return []

        activities = []
        for key in ("volunteer", "volunteering", "volunteer_experience"):
            value = sections.get(key)
            if isinstance(value, dict):
                content = str(value.get("content") or "").strip()
            elif isinstance(value, str):
                content = value.strip()
            else:
                content = ""

            if not content or self._contains_experience_date(content):
                continue

            normalized = re.sub(r"\s+", " ", content).strip()
            for item in re.split(r"\s*;\s*|\s*•\s*", normalized):
                item = item.strip(" ,.;")
                if item:
                    activities.append({
                        "activity": item,
                        "source_section": "volunteer",
                        "duration_months": None,
                        "date_status": "not_provided",
                    })

        unique = []
        seen = set()
        for item in activities:
            key = item["activity"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique


    def _extract_experience_section_from_text(self, text: str) -> str:
        if not text:
            return ""

        lines = text.splitlines()
        start_index = None

        valid_headings = set(self.EXPERIENCE_HEADINGS)

        if self.include_volunteer:
            valid_headings |= self.VOLUNTEER_HEADINGS

        for index, line in enumerate(lines):
            if self._normalize_heading(line) in valid_headings:
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
    # Splitting
    # ================================================================

    def _is_placeholder_date_line(
        self,
        line: str,
    ) -> bool:
        clean = self._strip_bullet(
            str(line or "")
        ).strip()
        return bool(re.fullmatch(
            r"(?i)(?:month\s+)?(?:19|20)?[xy]{2,4}"
            r"(?:\s*(?:-|–|—|to)\s*(?:19|20)?[xy]{2,4})?",
            clean,
        ))

    def _placeholder_location_line(
        self,
        line: str,
    ) -> bool:
        clean = self._strip_bullet(str(line or "")).strip()
        if not clean or len(clean) > 70:
            return False
        if re.fullmatch(
            r"(?i)(?:city|town)\s*,\s*(?:country|state|province|region)",
            clean,
        ):
            return True
        return bool(re.fullmatch(
            r"[A-Za-zÀ-ÿ .'-]{2,40},\s*[A-Za-zÀ-ÿ .'-]{2,30}",
            clean,
        ))

    def _placeholder_role_line(
        self,
        line: str,
    ) -> bool:
        clean = self._strip_bullet(str(line or "")).strip()
        if not clean or self._is_placeholder_date_line(clean):
            return False
        title = self._clean_job_title(clean)
        return bool(
            self._is_valid_job_title(title)
            or re.search(
                r"(?i)\b(?:assistant|associate|manager|analyst|specialist|"
                r"coordinator|consultant|representative|executive|accountant|"
                r"bookkeeper|auditor|preparer|administrator|intern)\b",
                clean,
            )
        )

    def _placeholder_company_line(
        self,
        line: str,
    ) -> bool:
        clean = self._strip_bullet(str(line or "")).strip()
        words = clean.split()
        if (
            not clean
            or len(clean) > 110
            or len(words) > 12
            or self._is_placeholder_date_line(clean)
            or self._placeholder_location_line(clean)
            or self._placeholder_role_line(clean)
            or self._normalize_heading(clean) in self.STOP_HEADINGS
            or self._normalize_heading(clean) in self.EXPERIENCE_HEADINGS
        ):
            return False
        if self._starts_with_action_verb(clean):
            return False
        return not bool(re.search(r"[.!?;:]$", clean))

    def _split_placeholder_date_entries(
        self,
        text: str,
    ) -> list[dict]:
        """Parse template rows anchored by dates such as ``20XX-20XX``.

        Placeholder dates are structural boundaries, but they never become
        real dates and never contribute fabricated duration.
        """
        lines = [
            line.strip()
            for line in str(text or "").splitlines()
            if line.strip()
        ]
        date_indexes = [
            index
            for index, line in enumerate(lines)
            if self._is_placeholder_date_line(line)
        ]
        if not date_indexes:
            return []

        anchors: list[dict] = []
        for date_index in date_indexes:
            title_index = None
            for candidate in (
                date_index - 1,
                date_index + 1,
                date_index - 2,
            ):
                if (
                    0 <= candidate < len(lines)
                    and self._placeholder_role_line(lines[candidate])
                ):
                    title_index = candidate
                    break
            if title_index is None:
                continue

            boundary = min(date_index, title_index)
            company_index = None
            for candidate in range(
                boundary - 1,
                max(-1, boundary - 6),
                -1,
            ):
                if self._placeholder_company_line(lines[candidate]):
                    company_index = candidate
                    break
            if company_index is None:
                continue

            location_index = next((
                candidate
                for candidate in range(
                    max(0, company_index - 1),
                    min(len(lines), title_index + 2),
                )
                if self._placeholder_location_line(lines[candidate])
            ), None)

            header_indexes = {
                date_index,
                title_index,
                company_index,
            }
            if location_index is not None:
                header_indexes.add(location_index)
            anchors.append({
                "date_index": date_index,
                "title_index": title_index,
                "company_index": company_index,
                "location_index": location_index,
                "entry_start": min(header_indexes),
            })

        anchors.sort(key=lambda item: int(item["date_index"]))
        records: list[dict] = []
        for position, anchor in enumerate(anchors):
            date_index = int(anchor["date_index"])
            title_index = int(anchor["title_index"])
            company_index = int(anchor["company_index"])
            location_index = anchor.get("location_index")
            location = (
                lines[int(location_index)]
                if location_index is not None
                else None
            )
            body_start = max(date_index, title_index) + 1
            next_boundary = (
                int(anchors[position + 1]["entry_start"])
                if position + 1 < len(anchors)
                else len(lines)
            )
            # Once the structural anchors are known, every line between this
            # header and the next one is body text. Broad company/title
            # heuristics used here previously discarded valid continuations
            # such as "accuracy" and even whole action-led bullets.
            body_lines = lines[body_start:max(body_start, next_boundary)]

            job_title = self._normalize_job_title(
                self._clean_job_title(lines[title_index])
            )
            company = self._clean_company(lines[company_index])
            raw_date = lines[date_index]
            normalized = [
                f"Title: {job_title}",
                f"Company: {company}",
            ]
            if location:
                normalized.append(f"Location: {location}")
            normalized.append(raw_date)
            normalized.extend(body_lines)

            records.append({
                "raw_text": "\n".join(normalized),
                "metadata": {
                    "raw_date_text": raw_date,
                    "date_status": "placeholder_unresolved",
                    "date_validation": {
                        "valid": False,
                        "reason": "template_date_placeholder",
                    },
                    "source_completeness_status": "template_placeholder_dates",
                    "source_company_line": lines[company_index],
                    "source_role_line": lines[title_index],
                    "layout_pattern": "placeholder_date_anchored",
                    "confidence": 90,
                },
            })

        unique: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for record in records:
            metadata = record["metadata"]
            key = (
                normalize_keyword(metadata.get("source_company_line") or ""),
                normalize_keyword(metadata.get("source_role_line") or ""),
                normalize_keyword(metadata.get("raw_date_text") or ""),
            )
            if key not in seen:
                seen.add(key)
                unique.append(record)
        return unique

    def _split_company_first_entries(
        self,
        text: str,
    ) -> list[dict]:
        """
        Parse employer-first layouts with any of these structures:

            Company, City, ST
            2007 - 12/2011
            SENIOR ACCOUNT EXECUTIVE

            Company, City, ST
            TITLE, February 2009 - Present

            Company
            TITLE (1995 - 1998), City, ST

        Repeated page markers and duplicate ``continued`` role headers are
        ignored while their following responsibility text remains attached to
        the original role.
        """
        lines = [
            line.strip()
            for line in str(
                text or ""
            ).splitlines()
            if line.strip()
        ]

        lines = [
            line
            for line in lines
            if not self._is_page_marker_line(
                line
            )
        ]

        groups: list[dict] = []
        index = 0
        group_number = 0

        while index < len(lines):
            employer = self._parse_employer_header(
                lines[index]
            )

            if not employer:
                index += 1
                continue

            group_number += 1
            group_id = (
                f"employer_group_"
                f"{group_number}"
            )
            source_company_line = lines[index]
            cursor = index + 1
            employer_date = None

            if (
                cursor < len(lines)
                and self._is_date_range_only_line(
                    lines[cursor]
                )
            ):
                employer_date = lines[cursor]
                cursor += 1

            group_end = cursor

            while group_end < len(lines):
                normalized = self._normalize_heading(
                    lines[group_end]
                )

                if (
                    normalized in self.STOP_HEADINGS
                    or normalized
                    in self.VOLUNTEER_HEADINGS
                ):
                    break

                if self._is_experience_subsection_heading(
                    lines[group_end]
                ):
                    break

                if self._parse_undated_role_company_line(
                    lines[group_end]
                ):
                    break

                if (
                    group_end > cursor
                    and self._parse_employer_header(
                        lines[group_end]
                    )
                ):
                    break

                group_end += 1

            role_records: list[dict] = []
            role_positions: list[int] = []
            current_role_index: int | None = None

            for relative_index, line in enumerate(
                lines[cursor:group_end]
            ):
                role = self._parse_flexible_role_header(
                    line,
                    fallback_date=employer_date,
                )

                if role:
                    duplicate_index = None

                    if role.get("continued"):
                        for candidate_index in range(
                            len(role_records) - 1,
                            -1,
                            -1,
                        ):
                            candidate = (
                                role_records[
                                    candidate_index
                                ]
                            )

                            if (
                                normalize_keyword(
                                    candidate[
                                        "job_title"
                                    ]
                                )
                                == normalize_keyword(
                                    role["job_title"]
                                )
                                and normalize_keyword(
                                    candidate.get(
                                        "date_text"
                                    )
                                    or ""
                                )
                                == normalize_keyword(
                                    role.get(
                                        "date_text"
                                    )
                                    or ""
                                )
                            ):
                                duplicate_index = (
                                    candidate_index
                                )
                                break

                    if duplicate_index is not None:
                        current_role_index = (
                            duplicate_index
                        )
                        continue

                    role["body_lines"] = []
                    role_records.append(role)
                    role_positions.append(
                        relative_index
                    )
                    current_role_index = (
                        len(role_records) - 1
                    )
                    continue

                if current_role_index is not None:
                    role_records[
                        current_role_index
                    ]["body_lines"].append(
                        line
                    )

            if not role_records:
                index += 1
                continue

            stacked_roles = (
                role_positions
                == list(
                    range(len(role_positions))
                )
            )

            shared_body: list[str] = []

            if (
                stacked_roles
                and role_records
            ):
                for role in reversed(
                    role_records
                ):
                    if role["body_lines"]:
                        shared_body = list(
                            role["body_lines"]
                        )
                        break

                if shared_body:
                    for role in role_records:
                        if not role[
                            "body_lines"
                        ]:
                            role[
                                "body_lines"
                            ] = list(
                                shared_body
                            )

            for role in role_records:
                normalized_lines = [
                    f"Title: "
                    f"{role['job_title']}",
                    f"Company: "
                    f"{employer['company']}",
                ]

                location = (
                    role.get("location")
                    or employer.get("location")
                )

                if location:
                    normalized_lines.append(
                        f"Location: {location}"
                    )

                if role.get("date_text"):
                    normalized_lines.append(
                        role["date_text"]
                    )

                normalized_lines.extend(
                    role["body_lines"]
                )

                groups.append({
                    "raw_text": "\n".join(
                        normalized_lines
                    ),
                    "metadata": {
                        "employer_group_id":
                            group_id,
                        "responsibilities_scope":
                            (
                                "employer_group_shared"
                                if (
                                    len(role_records) > 1
                                    and stacked_roles
                                )
                                else "role_specific"
                            ),
                        "shared_role_responsibilities": bool(
                            len(role_records) > 1
                            and stacked_roles
                        ),
                        "responsibility_scope": (
                            "employer_group"
                            if (
                                len(role_records) > 1
                                and stacked_roles
                            )
                            else "role_specific"
                        ),
                        "shared_responsibility_group_id": (
                            group_id
                            if (
                                len(role_records) > 1
                                and stacked_roles
                            )
                            else None
                        ),
                        "source_company_line":
                            source_company_line,
                        "source_role_line":
                            role["source_line"],
                    },
                })

            index = group_end

        groups.extend(
            self._split_undated_role_company_entries(
                lines,
                start_group_number=group_number,
            )
        )

        return groups

    def _is_experience_subsection_heading(
        self,
        line: str,
    ) -> bool:
        """
        Detect a structural subheading that starts a new experience group.

        This is intentionally generic. It does not depend on candidate,
        employer, filename, or resume-specific text.

        Examples:
            PREVIOUS SALES EXPERIENCE
            Prior Professional Experience
            Additional Work Experience

        A valid job-title line such as "Customer Experience Manager" is
        rejected before the heading rule is evaluated.
        """
        clean = self._strip_bullet(
            str(line or "")
        ).strip()

        if (
            not clean
            or len(clean) > 80
            or self._is_page_marker_line(clean)
            or self._is_date_only_line(clean)
            or self._parse_flexible_role_header(clean)
            or self._parse_undated_role_company_line(clean)
        ):
            return False

        normalized = self._normalize_heading(clean)
        tokens = normalized.split()

        if (
            "experience" not in tokens
            or not 2 <= len(tokens) <= 7
        ):
            return False

        qualifiers = {
            "previous",
            "prior",
            "earlier",
            "additional",
            "other",
            "selected",
            "relevant",
            "related",
            "professional",
            "work",
            "career",
            "employment",
            "sales",
            "industry",
        }

        if not qualifiers.intersection(tokens):
            return False

        # Headings are short labels, not prose sentences.
        if re.search(r"[.!?;]$", clean):
            return False

        return True

    def _parse_employer_header(
        self,
        line: str,
    ) -> dict | None:
        clean = self._strip_bullet(
            str(line or "")
        ).strip()

        if (
            not clean
            or self._is_date_only_line(
                clean
            )
            or self._is_page_marker_line(
                clean
            )
        ):
            return None

        if self._parse_flexible_role_header(
            clean
        ):
            return None

        if self._starts_with_action_verb(
            clean
        ):
            return None

        match = re.match(
            r"^(?P<company>.+?),\s*"
            r"(?P<city>[A-Z][A-Za-z.'\-]*"
            r"(?:\s+[A-Z][A-Za-z.'\-]*){0,3}),\s*"
            r"(?P<region>[A-Z]{1,3})$",
            clean,
        )

        if match:
            company = match.group(
                "company"
            ).strip(" ,")
            location = (
                f"{match.group('city')}, "
                f"{match.group('region')}"
            )

            if self._is_valid_company(
                company
            ):
                return {
                    "company": company,
                    "location": location,
                }

        lower_words = normalize_keyword(
            clean
        ).split()

        has_company_suffix = any(
            word.strip(".,")
            in self.COMPANY_SUFFIXES
            for word in lower_words
        )

        if (
            has_company_suffix
            and self._is_valid_company(clean)
        ):
            return {
                "company":
                    self._clean_company(clean),
                "location": None,
            }

        return None

    def _is_page_marker_line(
        self,
        line: str,
    ) -> bool:
        return bool(
            re.fullmatch(
                r"\s*(?:"
                r"page\s+\d+\s+(?:of|/)\s+\d+"
                r"|resume\s*,?\s*p\.?\s*\d+"
                r")\s*",
                str(line or ""),
                re.IGNORECASE,
            )
        )

    def _is_date_range_only_line(
        self,
        line: str,
    ) -> bool:
        value = str(line or "").strip()

        if not value:
            return False

        date_result = self._extract_dates(
            value
        )

        if not (
            date_result.get("start_date")
            and date_result.get("end_date")
        ):
            return False

        stripped = re.sub(
            r"[\s,;()]+",
            " ",
            value,
        ).strip()

        evidence = re.sub(
            r"[\s,;()]+",
            " ",
            str(
                date_result.get(
                    "date_evidence"
                )
                or ""
            ),
        ).strip()

        return (
            bool(evidence)
            and normalize_keyword(
                stripped
            )
            == normalize_keyword(
                evidence
            )
        )

    def _parse_flexible_role_header(
        self,
        line: str,
        *,
        fallback_date: str | None = None,
    ) -> dict | None:
        source = self._strip_bullet(
            str(line or "")
        ).strip()

        if (
            not source
            or self._is_page_marker_line(
                source
            )
        ):
            return None

        continued = bool(
            re.search(
                r"\bcontinued\b",
                source,
                re.IGNORECASE,
            )
        )

        clean = re.sub(
            r"\s+continued\s*(?:…|\.\.\.)?\s*$",
            "",
            source,
            flags=re.IGNORECASE,
        ).strip()

        standard = self._parse_role_date_line(
            clean
        )

        if standard:
            standard.update({
                "location": None,
                "continued": continued,
            })
            return standard

        date_pattern = (
            rf"(?:{self.MONTH_PATTERN})\.?\s+"
            rf"(?:19|20)\d{{2}}"
            rf"|(?:19|20)\d{{2}}"
        )

        match = re.match(
            rf"^(?P<title>.+?)\s*"
            rf"\((?P<dates>{date_pattern}\s*"
            rf"(?:-|–|—|to)\s*"
            rf"(?:{date_pattern}|present|current|now|ongoing))\)"
            rf"\s*,?\s*"
            rf"(?P<location>"
            rf"[A-Z][A-Za-z.'\-]*(?:\s+[A-Z][A-Za-z.'\-]*){{0,3}},\s*"
            rf"[A-Z]{{1,3}}"
            rf")?\s*$",
            clean,
            re.IGNORECASE,
        )

        if match:
            title = self._clean_job_title(
                match.group("title")
            )

            if self._is_valid_job_title(
                title
            ):
                return {
                    "job_title":
                        self._normalize_job_title(
                            title
                        ),
                    "date_text":
                        match.group(
                            "dates"
                        ).strip(),
                    "location":
                        (
                            match.group(
                                "location"
                            ).strip()
                            if match.group(
                                "location"
                            )
                            else None
                        ),
                    "source_line": source,
                    "continued": continued,
                }

        title_candidate = self._clean_job_title(
            clean
        )

        title_like = bool(
            clean.isupper()
            or self._is_valid_job_title(
                title_candidate
            )
        )

        if (
            title_like
            and self._is_valid_job_title(
                title_candidate
            )
        ):
            return {
                "job_title":
                    self._normalize_job_title(
                        title_candidate
                    ),
                "date_text": fallback_date,
                "location": None,
                "source_line": source,
                "continued": continued,
            }

        return None

    def _parse_undated_role_company_line(
        self,
        line: str,
    ) -> dict | None:
        clean = self._strip_bullet(
            str(line or "")
        ).strip()

        if (
            not clean
            or self._contains_experience_date(
                clean
            )
            or "," not in clean
        ):
            return None

        title_part, company_part = (
            clean.split(",", 1)
        )

        title = self._clean_job_title(
            title_part
        )
        company = self._clean_company(
            company_part
        )

        if not (
            self._is_valid_job_title(
                title
            )
            and self._is_valid_company(
                company
            )
        ):
            return None

        return {
            "job_title":
                self._normalize_job_title(
                    title
                ),
            "company": company,
            "source_line": clean,
        }

    def _split_undated_role_company_entries(
        self,
        lines: list[str],
        *,
        start_group_number: int,
    ) -> list[dict]:
        parsed: list[
            tuple[int, dict]
        ] = []

        for index, line in enumerate(lines):
            item = (
                self
                ._parse_undated_role_company_line(
                    line
                )
            )

            if item:
                parsed.append(
                    (index, item)
                )

        if not parsed:
            return []

        first_index = parsed[0][0]
        intro_lines = []

        for candidate in reversed(
            lines[
                max(0, first_index - 3):
                first_index
            ]
        ):
            if (
                self._looks_like_responsibility(
                    candidate
                )
                or self._starts_with_action_verb(
                    candidate
                )
            ):
                intro_lines.insert(
                    0,
                    candidate,
                )

        records = []
        prior_shared_group_id = (
            "previous_roles_group_"
            f"{start_group_number + 1}"
        )

        for offset, (_, item) in enumerate(
            parsed,
            start=1,
        ):
            normalized_lines = [
                f"Title: "
                f"{item['job_title']}",
                f"Company: "
                f"{item['company']}",
            ]
            normalized_lines.extend(
                intro_lines
            )

            records.append({
                "raw_text": "\n".join(
                    normalized_lines
                ),
                "metadata": {
                    "employer_group_id":
                        (
                            "undated_prior_group_"
                            f"{start_group_number + offset}"
                        ),
                    "responsibilities_scope":
                        "prior_roles_shared",
                    "shared_role_responsibilities": True,
                    "responsibility_scope":
                        "previous_roles_group",
                    "shared_responsibility_group_id":
                        prior_shared_group_id,
                    "undated_prior_role": True,
                    "date_status":
                        "not_provided_in_source",
                    "location_status":
                        "not_provided_in_source",
                    "source_completeness_status":
                        "partial_source",
                    "confidence": 82,
                    "source_company_line":
                        item["source_line"],
                    "source_role_line":
                        item["source_line"],
                },
            })

        return records

    def _parse_role_date_line(self, line: str) -> dict | None:
        clean = self._strip_bullet(str(line or "")).strip()
        pattern = re.compile(
            rf"^(?P<title>.+?),\s*"
            rf"(?P<dates>(?:{self.MONTH_PATTERN})\.?\s+(?:19|20)\d{{2}}\s*"
            rf"(?:-|–|—|to)\s*(?:(?:{self.MONTH_PATTERN})\.?\s+(?:19|20)\d{{2}}|"
            rf"present|current|now|ongoing))$",
            re.IGNORECASE,
        )
        match = pattern.match(clean)
        if not match:
            return None

        title = self._clean_job_title(match.group("title"))
        if not self._is_valid_job_title(title):
            return None

        return {
            "job_title": self._normalize_job_title(title),
            "date_text": match.group("dates").strip(),
            "source_line": clean,
        }

    def _split_experience_entries(self, text: str, from_experience_section: bool) -> list[str]:
        text = self._normalize_text(text)

        if not text:
            return []

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

            if len(entry) < 8:
                continue

            if self._has_experience_signal(entry, from_experience_section):
                cleaned.append(entry)

        return cleaned

    def _split_block_lines(self, block: str) -> list[str]:
        """
        Split on a new role header, not on a date line.

        Resume entries commonly use:
            Job title
            Date range
            Company
            Bullets

        Treating the date as a new record is what produced company="Apr".
        """
        lines = [line.strip() for line in block.splitlines() if line.strip()]

        if not lines:
            return []

        entries = []
        current = []

        for line in lines:
            clean = self._strip_bullet(line)

            if not current:
                current = [line]
                continue

            # Bullets, action sentences, dates, and company lines belong to
            # the current record.
            if self.BULLET_PATTERN.match(line):
                current.append(line)
                continue

            if self._starts_with_action_verb(clean):
                current.append(line)
                continue

            if self._is_date_only_line(clean):
                current.append(line)
                continue

            starts_new = (
                self._looks_like_new_experience_start(clean)
                and self._entry_has_boundary_signal(current)
            )

            if starts_new:
                entries.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            entries.append("\n".join(current))

        return entries

    def _entry_has_boundary_signal(self, lines: list[str]) -> bool:
        """Whether the accumulated record is complete enough to close."""
        if not lines:
            return False

        current_text = "\n".join(lines)
        dates = self._extract_dates(current_text)

        has_date = bool(
            dates.get("start_date")
            or dates.get("end_date")
            or any(self._is_date_only_line(line) for line in lines)
        )
        has_responsibility = any(
            self.BULLET_PATTERN.match(line)
            or self._looks_like_responsibility(self._strip_bullet(line))
            for line in lines
        )
        has_identity = bool(
            self._extract_job_title(current_text)
            or self._extract_company(current_text)
        )

        return has_date or has_responsibility or (
            has_identity and len(lines) >= 3
        )

    def _is_date_only_line(self, line: str) -> bool:
        """Reject month/date fragments as titles, companies, or new records."""
        if not line:
            return False

        value = self._strip_bullet(line).strip()
        lower = value.lower()

        if not re.search(r"\b(?:19|20)\d{2}\b", lower):
            return False

        allowed = lower
        allowed = re.sub(r"\b(?:19|20)\d{2}\b", " ", allowed)
        allowed = re.sub(
            rf"\b(?:{self.MONTH_PATTERN}|present|current|now|ongoing|"
            r"seasonal|spring|summer|fall|autumn|winter|to|and)\b",
            " ",
            allowed,
            flags=re.IGNORECASE,
        )
        allowed = re.sub(r"[\s\-–—/&(),.]+", "", allowed)

        return not allowed
    def _looks_like_new_experience_start(self, line: str) -> bool:
        clean = self._strip_bullet(line)

        if not clean:
            return False

        if self._is_label_line(clean):
            return False

        if self._starts_with_action_verb(clean):
            return False

        if self._is_date_only_line(clean):
            return False

        if self._is_achievement_sentence(clean):
            return False

        if clean.endswith(".") and len(clean.split()) > 4:
            return False

        title = self._extract_job_title(clean)
        company = self._extract_company(clean)
        dates = self._extract_dates(clean)
        has_date = bool(dates.get("start_date") or dates.get("end_date"))

        normalized_words = normalize_keyword(clean).split()
        has_company_suffix = any(
            word in self.COMPANY_SUFFIXES
            for word in normalized_words
        )

        # A company-only line follows the title/date and belongs to the
        # current record. It must not start another experience.
        if company and not has_date and has_company_suffix:
            return False

        # Inline header: Title | Company | Dates
        if sum(bool(value) for value in [title, company, has_date]) >= 2:
            return True

        # Standalone short job-title line.
        if (
            title
            and len(clean.split()) <= 8
            and not has_company_suffix
        ):
            return True

        return False

    def _scan_full_text_windows(self, text: str) -> list[str]:
        text = self._normalize_text(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        windows = []

        for idx, line in enumerate(lines):
            if self._has_experience_signal(line, from_experience_section=False):
                start = max(0, idx - 1)
                end = min(len(lines), idx + 8)
                windows.append("\n".join(lines[start:end]))

        return windows

    # ================================================================
    # Parse
    # ================================================================

    def _parse_experience(
        self,
        raw_text: str,
        *,
        employment_type_hint: str | None = None,
    ) -> dict:
        raw_text = self._normalize_text(raw_text)

        header_info = self._extract_title_company_from_date_header(raw_text)

        job_title = header_info.get("job_title") or self._extract_job_title(raw_text)
        company = header_info.get("company") or self._extract_company(raw_text)
        location = self._extract_location(raw_text, company=company)
        dates = self._extract_dates(raw_text)
        volunteer = self._is_volunteer_experience(raw_text)
        employment_type = (
            self._extract_employment_type(raw_text, volunteer=True)
            if volunteer
            else employment_type_hint or self._extract_employment_type(raw_text)
        )
        responsibilities = self._extract_responsibilities(raw_text, job_title, company)
        description = self._extract_description(raw_text, responsibilities, job_title, company)
        technologies = self._extract_technologies(raw_text)
        metrics = self._extract_metrics(raw_text)
        semantic_score = self._semantic_experience_score(raw_text)

        confidence = self._score_experience(
            job_title=job_title,
            company=company,
            location=location,
            dates=dates,
            employment_type=employment_type,
            responsibilities=responsibilities,
            description=description,
            technologies=technologies,
            metrics=metrics,
            volunteer=volunteer,
            raw_text=raw_text,
            semantic_score=semantic_score,
        )

        duration_months = self._calculate_dates_duration(
            dates
        )

        return {
            "job_title": job_title,
            "company": company,
            "location": location,
            "employment_type": employment_type,
            "volunteer": volunteer,
            "start_date": dates.get("start_date"),
            "end_date": dates.get("end_date"),
            "start_year": dates.get("start_year"),
            "end_year": dates.get("end_year"),
            "current": dates.get("current", False),
            "periods": dates.get("periods", []),
            "period_count": dates.get("period_count", 0),
            "date_mode": dates.get("date_mode"),
            "continuous": dates.get("continuous"),
            "date_evidence": dates.get("date_evidence"),
            "duration_months": duration_months,
            "description": description,
            "responsibilities": responsibilities,
            "technologies": technologies,
            "metrics": metrics,
            "semantic_score": semantic_score,
            "raw_text": raw_text,
            "confidence": confidence,
        }

    # ================================================================
    # Job title
    # ================================================================

    def _extract_job_title(self, text: str) -> str | None:
        labeled = self._extract_labeled_text(text, self.TITLE_LABELS)

        if labeled:
            candidate = re.split(r"\n|\||;|,", labeled)[0]
            candidate = self._clean_job_title(candidate)

            if self._is_valid_job_title(candidate):
                return self._normalize_job_title(candidate)

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for line in lines[:4]:
            clean = self._strip_bullet(line)

            parts = re.split(
                r"\s+\|\s+|\s+at\s+|\s+-\s+|\s+–\s+|\s+—\s+",
                clean,
                maxsplit=1,
                flags=re.IGNORECASE,
            )

            candidate = self._clean_job_title(parts[0])

            if self._is_valid_job_title(candidate):
                return self._normalize_job_title(candidate)

            direct = self._find_job_title_in_text(clean)

            if direct:
                return self._normalize_job_title(direct)

        direct = self._find_job_title_in_text(text)

        if direct:
            return self._normalize_job_title(direct)

        if self.use_spacy and self.nlp is not None:
            return self._extract_job_title_with_spacy(text)

        return None

    def _find_job_title_in_text(self, text: str) -> str | None:
        if not text:
            return None

        titles = sorted(self.job_titles, key=len, reverse=True)

        for title in titles:
            pattern = re.escape(title)
            pattern = pattern.replace(r"\ ", r"\s+")

            if re.search(rf"\b{pattern}\b", text, re.IGNORECASE):
                return title

        return None

    def _extract_job_title_with_spacy(self, text: str) -> str | None:
        if not self.use_spacy or self.nlp is None or not text:
            return None

        doc = self.nlp(text[:800])

        for chunk in doc.noun_chunks:
            candidate = self._clean_job_title(chunk.text)

            if self._is_valid_job_title(candidate):
                return self._normalize_job_title(candidate)

        return None

    def _clean_job_title(self, title: str) -> str:
        title = str(title or "").strip()

        title = re.sub(
            r"(?i)\s*\((?:co[\s-]?op|intern(?:ship)?|contract|"
            r"temporary|part[\s-]?time|full[\s-]?time)\)\s*$",
            "",
            title,
        )
        title = re.split(
            r"\.|,|;|\n|\||\s+at\s+|\s+with\s+|\s+for\s+|\s+in\s+|\s+using\s+",
            title,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        title = re.sub(r"^(a|an|the)\s+", "", title, flags=re.IGNORECASE)
        title = re.sub(r"^[\-:|]+", "", title)
        title = re.sub(r"[\-:|]+$", "", title)
        title = re.sub(r"\s+", " ", title)

        return title.strip()

    def _normalize_job_title(self, title: str) -> str:
        title = str(title).strip()
        title = re.sub(r"\s+", " ", title)

        special = {
            "hr": "HR", "ui": "UI", "ux": "UX", "qa": "QA",
            "seo": "SEO", "it": "IT", "cfo": "CFO",
            "ceo": "CEO", "cto": "CTO", "bi": "BI",
            "ai": "AI", "api": "API", "cio": "CIO",
            "cmo": "CMO", "coo": "COO", "cpa": "CPA",
            "crm": "CRM", "erp": "ERP", "sql": "SQL",
        }

        small_words = {"and", "of", "in", "for", "with", "as"}
        all_upper = title.isupper()

        def normalize_word(match: re.Match) -> str:
            word = match.group(0)
            lower = word.casefold()

            if lower in special:
                return special[lower]
            if lower in small_words:
                return lower
            if not all_upper and word.isupper() and 2 <= len(word) <= 8:
                return word
            return lower.capitalize()

        return re.sub(r"[A-Za-z]+", normalize_word, title)

    def _is_valid_job_title(self, title: str) -> bool:
        if not title:
            return False

        title = self._clean_job_title(title)
        lower = normalize_keyword(title)
        words = lower.split()

        if len(title) < 3 or len(title) > 80:
            return False

        if len(words) > 8:
            return False

        if "@" in lower or "http" in lower or "www." in lower:
            return False

        if re.search(r"\b(19|20)\d{2}\b", lower):
            return False

        if self._is_date_only_line(title):
            return False

        if words and words[0] in self.BAD_JOB_TITLE_STARTERS:
            return False

        if any(
            re.search(pattern, title)
            for pattern in self.BAD_JOB_TITLE_PATTERNS
        ):
            return False

        if self._is_achievement_sentence(title):
            return False

        bad_words = {
            "company", "employer", "university", "college", "school",
            "gpa", "project", "github", "demo", "technologies",
            "responsibilities", "description", "location",
        }

        if any(word in bad_words for word in words):
            return False

        if lower in self.job_titles:
            return True

        if words and words[-1] in self.JOB_SUFFIXES:
            return True

        # Semantic matching is a fallback only for short noun-like phrases.
        if (
            len(words) <= 5
            and not any(word in self.ACTION_VERBS for word in words)
            and self._semantic_job_role_score(title)
            >= self.role_semantic_threshold
        ):
            return True

        return False

    def _is_achievement_sentence(self, value: str) -> bool:
        if not value:
            return False

        clean = self._strip_bullet(value).strip()
        lower = normalize_keyword(clean)
        words = lower.split()

        if not words:
            return False

        if words[0] in self.BAD_JOB_TITLE_STARTERS:
            return True

        if re.search(
            r"(?i)\b(by manager|resulting in|responsible for|"
            r"initiative to|recognized for|awarded for)\b",
            clean,
        ):
            return True

        if len(words) >= 7 and re.search(r"[.;:]", clean):
            return True

        return False
    def _extract_company(self, text: str) -> str | None:
        labeled = self._extract_labeled_text(text, self.COMPANY_LABELS)

        if labeled:
            candidate = re.split(r"\n|\||;", labeled)[0]
            candidate = self._clean_company(candidate)

            if self._is_valid_company(candidate):
                return candidate

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for line in lines[:6]:
            clean = self._strip_bullet(line)

            if (
                self._is_date_only_line(clean)
                or self._starts_with_action_verb(clean)
                or self._is_achievement_sentence(clean)
            ):
                continue

            match = re.search(
                r"\b(?:at|@)\s+([A-Z][A-Za-z0-9&.,'\-\s]{2,70})",
                clean,
                re.IGNORECASE,
            )

            if match:
                candidate = self._clean_company(match.group(1))

                if self._is_valid_company(candidate):
                    return candidate

            # Inline separators: Title | Company | Location | Date
            parts = re.split(
                r"\s+\|\s+|\s+-\s+|\s+–\s+|\s+—\s+",
                clean,
            )

            if len(parts) >= 2:
                for part in parts[1:3]:
                    candidate = self._clean_company(part)

                    if self._is_valid_company(candidate):
                        return candidate

            # Comma-based company/location lines. Prefer the organization
            # immediately before the final location.
            comma_parts = [
                part.strip()
                for part in clean.split(",")
                if part.strip()
            ]

            if len(comma_parts) >= 2:
                ordered_parts = list(reversed(comma_parts[:-1]))

                for part in ordered_parts:
                    candidate = self._clean_company(part)

                    if self._is_valid_company(candidate):
                        return candidate

            # Whole-line organization with a strong organization suffix.
            lower_words = normalize_keyword(clean).split()

            if any(
                word in self.COMPANY_SUFFIXES
                for word in lower_words
            ):
                candidate = self._clean_company(clean)

                if self._is_valid_company(candidate):
                    return candidate

        if self.use_spacy and self.nlp is not None:
            company = self._extract_company_with_spacy(text)

            if company:
                return company

        return None

    def _extract_company_with_spacy(self, text: str) -> str | None:
        if not self.use_spacy or self.nlp is None or not text:
            return None

        header_text = "\n".join(text.splitlines()[:5])
        doc = self.nlp(header_text[:600])

        for ent in doc.ents:
            if ent.label_ == "ORG":
                candidate = self._clean_company(ent.text)

                if self._is_valid_company(candidate):
                    return candidate

        return None

    def _clean_company(self, value: str) -> str:
        value = str(value or "").strip()

        value = re.split(
            r"\n|\||;|\s{2,}|\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b|\b(?:19|20)\d{2}\b",
            value,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        value = re.sub(r"\b(remote|hybrid|onsite|present|current)\b", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^[\-:|@]+", "", value)
        value = re.sub(r"[\-:|]+$", "", value)
        value = re.sub(r"\s+", " ", value)

        return value.strip(" ,-|")

    def _is_valid_company(self, company: str) -> bool:
        if not company:
            return False

        company = self._clean_company(company)
        lower = normalize_keyword(company)
        words = lower.split()

        if len(company) < 2 or len(company) > 100:
            return False

        if not words:
            return False

        if self._is_date_only_line(company):
            return False

        if lower in self.MONTH_NAMES or lower in self.NON_COMPANY_TERMS:
            return False

        if "@" in lower or "http" in lower or "www." in lower:
            return False

        if re.search(r"\b(19|20)\d{2}\b", lower):
            return False

        if self._is_achievement_sentence(company):
            return False

        if words[0] in self.BAD_JOB_TITLE_STARTERS:
            return False

        if lower in self.job_titles:
            return False

        if any(
            word in {"remote", "hybrid", "onsite", "present", "current"}
            for word in words
        ):
            return False

        if lower in self.known_technologies:
            return False

        if any(
            normalize_keyword(tech) == lower
            for tech in self.known_technologies
        ):
            return False

        if self._is_valid_job_title(company):
            return False

        if words and words[-1] in self.JOB_SUFFIXES:
            return False

        # Long verb-heavy text is a responsibility, not an organization.
        if (
            len(words) > 7
            and any(word in self.ACTION_VERBS for word in words)
        ):
            return False

        if any(word in self.COMPANY_SUFFIXES for word in words):
            return True

        # Generic title-case fallback, kept conservative.
        if len(words) <= 6 and re.search(r"[A-Z][A-Za-z]+", company):
            return True

        return False
    def _extract_location(self, text: str, company: str | None = None) -> str | None:
        labeled = self._extract_labeled_text(text, self.LOCATION_LABELS)

        if labeled:
            candidate = re.split(r"\n|\||;", labeled)[0].strip()

            if self._is_valid_location(candidate, company=company):
                return self._clean_location(candidate)

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for line in lines[:4]:
            parts = re.split(r"\s+\|\s+|\s+-\s+|\s+–\s+|\s+—\s+", line)

            for part in parts[1:]:
                candidate = self._clean_location(part)

                if self._is_valid_location(candidate, company=company):
                    return candidate

        if self.use_spacy and self.nlp is not None:
            header_text = "\n".join(lines[:4])
            doc = self.nlp(header_text[:400])

            for ent in doc.ents:
                if ent.label_ in {"GPE", "LOC"}:
                    candidate = self._clean_location(ent.text)

                    if self._is_valid_location(candidate, company=company):
                        return candidate

        return None
    def _clean_location(self, value: str) -> str:
        value = str(value or "").strip()

        value = re.sub(r"\b(?:remote|hybrid|onsite)\b", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\b(?:19|20)\d{2}\b.*$", "", value)
        value = re.sub(r"\s+", " ", value)

        return value.strip(" ,.-|")

    def _is_valid_location(self, value: str, company: str | None = None) -> bool:
        if not value:
            return False

        value = self._clean_location(value)
        lower = normalize_keyword(value)
        words = lower.split()
        action_words = {
            "supporting", "working", "reviewing", "dealing", "offering",
            "preparing", "completing", "checking", "performing",
            "devising", "providing", "responsible", "helping",
            "assisting", "verifying", "maintaining",
        }

        if words and words[0] in action_words:
            return False
        month_names = {
            "jan", "january", "feb", "february", "mar", "march",
            "apr", "april", "may", "jun", "june", "jul", "july",
            "aug", "august", "sep", "sept", "september",
            "oct", "october", "nov", "november", "dec", "december",
        }

        if lower in month_names:
            return False

        if len(value) < 2 or len(value) > 70:
            return False

        if company and lower == normalize_keyword(company):
            return False

        if lower in self.job_titles:
            return False

        if lower in self.NON_LOCATION_TERMS:
            return False

        if any(word in self.NON_LOCATION_TERMS for word in words):
            return False

        if lower in self.known_technologies:
            return False

        if any(word in self.COMPANY_SUFFIXES for word in words):
            return False

        if any(word in {"present", "current", "remote", "hybrid", "onsite"} for word in words):
            return False

        if re.search(r"\b(19|20)\d{2}\b", lower):
            return False

        has_comma = "," in value
        has_title_case = bool(re.search(r"[A-Z][A-Za-z]+", value))

        return has_comma or has_title_case

    def _is_year_only_date(self, value: str | None) -> bool:
        if not value:
            return False

        value = str(value).strip()

        return bool(re.fullmatch(r"(?:19|20)\d{2}", value))

    def _extract_employment_type(self, text: str, volunteer: bool = False) -> str | None:
        if volunteer:
            return "Volunteer"

        if not text:
            return None

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        header_text = " ".join(lines[:2]).lower()

        if re.search(r"\bfreelance\b|\bfreelancer\b", header_text):
            return "Freelance"

        if re.search(r"\bself[-\s]?employed\b", header_text):
            return "Self-employed"

        if re.search(r"\bco[\s-]?op\b", header_text):
            return "Co-op"

        if re.search(r"\bpart[-\s]?time\b", header_text):
            return "Part-time"

        if re.search(r"\bfull[-\s]?time\b", header_text):
            return "Full-time"

        if re.search(r"\bcontract\b|\bcontractor\b", header_text):
            return "Contract"

        if re.search(r"\bintern\b|\binternship\b", header_text):
            return "Internship"

        if re.search(r"\bremote\b", header_text):
            return "Remote"

        return None

    def _is_volunteer_experience(
        self,
        text: str,
    ) -> bool:
        if not text:
            return False

        normalized = normalize_keyword(
            text
        )

        for indicator in (
            self.VOLUNTEER_INDICATORS
        ):
            phrase = normalize_keyword(
                indicator
            )

            if not phrase:
                continue

            pattern = re.escape(
                phrase
            ).replace(
                r"\ ",
                r"\s+",
            )

            if re.search(
                rf"(?<![a-z0-9])"
                rf"{pattern}"
                rf"(?![a-z0-9])",
                normalized,
                re.IGNORECASE,
            ):
                return True

        return False

    # ================================================================
    # Dates / duration / overlap
    # ================================================================

    def _extract_dates(self, text: str) -> dict:
        """
        Extract continuous and repeated seasonal date ranges.

        Example:
            Feb - Apr 2015 & 2016

        becomes:
            Feb 2015 - Apr 2015
            Feb 2016 - Apr 2016
        """
        result = {
            "start_date": None,
            "end_date": None,
            "start_year": None,
            "end_year": None,
            "current": False,
            "periods": [],
            "period_count": 0,
            "date_mode": "unresolved",
            "continuous": None,
            "date_evidence": None,
        }

        if not text:
            return result

        seasonal = self._extract_repeated_seasonal_periods(
            text
        )

        if seasonal:
            return seasonal

        year = r"(?:19|20)\d{2}"
        placeholder_year = r"(?:19|20)[Xx]{2}"

        month_year = (
            rf"(?:{self.MONTH_PATTERN})\.?\s+"
            rf"(?:{year}|{placeholder_year})"
        )
        numeric_month_year = (
            rf"(?:0?[1-9]|1[0-2])/"
            rf"(?:{year}|{placeholder_year})"
        )
        date_unit = (
            rf"(?:{month_year}|{numeric_month_year}|"
            rf"{year}|{placeholder_year})"
        )

        range_pattern = re.compile(
            rf"({date_unit})\s*(?:-|–|—|to)\s*"
            rf"((?:{date_unit})|present|current|now|ongoing)",
            re.IGNORECASE,
        )

        match = range_pattern.search(text)

        if match:
            start_raw = match.group(1).strip()
            end_raw = match.group(2).strip()

            start_date = self._normalize_date(start_raw)
            start_year = self._extract_year(start_raw)

            result["start_date"] = start_date
            result["start_year"] = start_year
            result["date_mode"] = "continuous_range"
            result["continuous"] = True
            result["date_evidence"] = (
                match.group(0).strip()
            )

            if end_raw.lower() in {
                "present",
                "current",
                "now",
                "ongoing",
            }:
                end_date = "Present"
                end_year = datetime.now().year
                result["current"] = True
            else:
                end_date = self._normalize_date(end_raw)
                end_year = self._extract_year(end_raw)

            result["end_date"] = end_date
            result["end_year"] = end_year

            period = self._build_date_period(
                start_date=start_date,
                end_date=end_date,
                current=result["current"],
            )

            if period:
                result["periods"] = [period]
                result["period_count"] = 1

            return result

        single_pattern = re.compile(
            rf"({month_year}|{numeric_month_year}|"
            rf"{year}|{placeholder_year})",
            re.IGNORECASE,
        )

        single = single_pattern.search(text)

        if single:
            raw = single.group(1).strip()
            result["end_date"] = self._normalize_date(raw)
            result["end_year"] = self._extract_year(raw)
            result["date_mode"] = "single_date"
            result["date_evidence"] = (
                single.group(0).strip()
            )

        return result

    def _extract_repeated_seasonal_periods(
        self,
        text: str,
    ) -> dict | None:
        """
        Parse a same-month range repeated across multiple years.

        Supported:
        - Feb - Apr 2015 & 2016
        - February to April 2015 and 2016
        - Jun-Aug 2021, 2022
        - Mar–May 2019/2020

        Nov-Feb style ranges are intentionally not inferred because the
        year association is ambiguous.
        """
        year = r"(?:19|20)\d{2}"
        separator = r"(?:&|and|,|/)"

        pattern = re.compile(
            rf"\b(?P<start_month>{self.MONTH_PATTERN})\.?\s*"
            rf"(?:-|–|—|to)\s*"
            rf"(?P<end_month>{self.MONTH_PATTERN})\.?\s+"
            rf"(?P<years>{year}"
            rf"(?:\s*{separator}\s*{year})+)\b",
            re.IGNORECASE,
        )

        match = pattern.search(str(text))

        if not match:
            return None

        start_month_number = self._month_number_from_name(
            match.group("start_month")
        )
        end_month_number = self._month_number_from_name(
            match.group("end_month")
        )

        if not start_month_number or not end_month_number:
            return None

        if end_month_number < start_month_number:
            return None

        years = []

        for value in re.findall(
            r"(?:19|20)\d{2}",
            match.group("years"),
        ):
            year_value = int(value)

            if year_value not in years:
                years.append(year_value)

        if len(years) < 2:
            return None

        start_month_label = self._canonical_month_label(
            start_month_number
        )
        end_month_label = self._canonical_month_label(
            end_month_number
        )

        periods = []

        for year_value in years:
            period = self._build_date_period(
                start_date=(
                    f"{start_month_label} {year_value}"
                ),
                end_date=(
                    f"{end_month_label} {year_value}"
                ),
                current=False,
            )

            if period:
                periods.append(period)

        if len(periods) < 2:
            return None

        return {
            "start_date": periods[0]["start_date"],
            "end_date": periods[-1]["end_date"],
            "start_year": periods[0]["start_year"],
            "end_year": periods[-1]["end_year"],
            "current": False,
            "periods": periods,
            "period_count": len(periods),
            "date_mode": "repeated_seasonal_periods",
            "continuous": False,
            "date_evidence": match.group(0).strip(),
        }

    def _build_date_period(
        self,
        *,
        start_date: str,
        end_date: str,
        current: bool = False,
    ) -> dict | None:
        start = self._parse_date_to_month(
            start_date,
            is_start=True,
        )
        end = self._parse_date_to_month(
            end_date,
            current=current,
            is_start=False,
        )

        if not start or not end or end < start:
            return None

        return {
            "start_date": start_date,
            "end_date": end_date,
            "start_year": start[0],
            "end_year": end[0],
            "duration_months":
                self._months_between_months(
                    start,
                    end,
                ),
        }

    def _month_number_from_name(
        self,
        value: str,
    ) -> int | None:
        normalized = (
            str(value or "")
            .strip()
            .lower()
            .rstrip(".")
        )

        return (
            self.MONTH_TO_NUM.get(normalized)
            or self.MONTH_TO_NUM.get(normalized[:3])
        )

    def _canonical_month_label(
        self,
        month_number: int,
    ) -> str:
        labels = {
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        }

        return labels[month_number]

    def _normalize_date(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value).strip())

    def _extract_year(self, value: str) -> int | None:
        match = re.search(r"\b(19|20)\d{2}\b", str(value))

        if not match:
            return None

        return int(match.group(0))

    def _parse_date_to_month(self, value: str | None, current: bool = False, is_start: bool = True) -> tuple[int, int] | None:
        if current:
            now = datetime.now()
            return now.year, now.month

        if not value:
            return None

        raw = str(value).strip()
        lower = raw.lower()

        if lower in {"present", "current", "now", "ongoing"}:
            now = datetime.now()
            return now.year, now.month

        month_year_match = re.search(
            rf"\b({self.MONTH_PATTERN})\.?\s+((?:19|20)\d{{2}})\b",
            lower,
            re.IGNORECASE,
        )

        if month_year_match:
            month_raw = month_year_match.group(1).lower().rstrip(".")
            year = int(month_year_match.group(2))
            month = self.MONTH_TO_NUM.get(month_raw[:3], self.MONTH_TO_NUM.get(month_raw))

            if month:
                return year, month

        numeric_match = re.search(r"\b(0?[1-9]|1[0-2])/(19|20)\d{2}\b", raw)

        if numeric_match:
            month = int(numeric_match.group(1))
            year = int(re.search(r"(19|20)\d{2}", raw).group(0))
            return year, month

        year = self._extract_year(raw)

        if year:
            return year, 1 if is_start else 12

        return None

    def _calculate_dates_duration(
        self,
        dates: dict,
    ) -> int | None:
        """
        Sum real periods instead of treating a seasonal gap as continuous.
        """
        periods = dates.get("periods", []) or []

        if periods:
            total = 0

            for period in periods:
                duration = period.get("duration_months")

                if not isinstance(duration, int):
                    start = self._parse_date_to_month(
                        period.get("start_date"),
                        is_start=True,
                    )
                    end = self._parse_date_to_month(
                        period.get("end_date"),
                        is_start=False,
                    )

                    if not start or not end or end < start:
                        continue

                    duration = self._months_between_months(
                        start,
                        end,
                    )

                if duration > 0:
                    total += duration

            return total or None

        return self._calculate_duration_months(
            dates.get("start_date"),
            dates.get("end_date"),
            bool(dates.get("current")),
        )

    def _experience_periods(
        self,
        exp: dict,
    ) -> list[
        tuple[tuple[int, int], tuple[int, int]]
    ]:
        parsed_periods = []

        for period in exp.get("periods", []) or []:
            start = self._parse_date_to_month(
                period.get("start_date"),
                is_start=True,
            )
            end = self._parse_date_to_month(
                period.get("end_date"),
                is_start=False,
            )

            if start and end and end >= start:
                parsed_periods.append((start, end))

        if parsed_periods:
            return parsed_periods

        legacy_period = self._experience_period(exp)

        return [legacy_period] if legacy_period else []

    def _period_pair_overlaps(
        self,
        period1: tuple[
            tuple[int, int],
            tuple[int, int],
        ],
        period2: tuple[
            tuple[int, int],
            tuple[int, int],
        ],
    ) -> bool:
        start1, end1 = period1
        start2, end2 = period2

        return (
            start1 <= end2
            and start2 <= end1
        )

    def _calculate_duration_months(
        self,
        start_date: str | None,
        end_date: str | None,
        current: bool,
    ) -> int | None:
        start = self._parse_date_to_month(start_date, is_start=True)
        end = self._parse_date_to_month(end_date, current=current, is_start=False)

        if not start or not end:
            return None

        months = self._months_between_months(start, end)

        if months <= 0:
            return None

        return months

    def _months_between_months(self, start: tuple[int, int], end: tuple[int, int]) -> int:
        start_year, start_month = start
        end_year, end_month = end

        if (end_year, end_month) < (start_year, start_month):
            return 0

        return ((end_year - start_year) * 12) + (end_month - start_month) + 1

    def _experience_period(self, exp: dict) -> tuple[tuple[int, int], tuple[int, int]] | None:
        start = self._parse_date_to_month(exp.get("start_date"), is_start=True)
        end = self._parse_date_to_month(
            exp.get("end_date"),
            current=bool(exp.get("current")),
            is_start=False,
        )

        if not start or not end:
            return None

        if end < start:
            return None

        return start, end

    def _is_overlapping(
        self,
        exp1: dict,
        exp2: dict,
    ) -> bool:
        periods1 = self._experience_periods(exp1)
        periods2 = self._experience_periods(exp2)

        if not periods1 or not periods2:
            return False

        # Preserve protection for year-only job transitions:
        # 2016-2018 followed by 2018-2023 is not automatically
        # considered concurrent.
        exp1_end = exp1.get("end_date")
        exp2_start = exp2.get("start_date")
        exp2_end = exp2.get("end_date")
        exp1_start = exp1.get("start_date")

        same_boundary_1 = (
            self._is_year_only_date(exp1_end)
            and self._is_year_only_date(exp2_start)
            and exp1_end == exp2_start
        )
        same_boundary_2 = (
            self._is_year_only_date(exp2_end)
            and self._is_year_only_date(exp1_start)
            and exp2_end == exp1_start
        )

        same_month_boundary = (
            exp1_end and exp2_start and str(exp1_end).lower() == str(exp2_start).lower()
        ) or (
            exp2_end and exp1_start and str(exp2_end).lower() == str(exp1_start).lower()
        )

        if same_boundary_1 or same_boundary_2 or same_month_boundary:
            return False

        return any(
            self._period_pair_overlaps(
                period1,
                period2,
            )
            for period1 in periods1
            for period2 in periods2
        )

    def _detect_overlapping_experiences(self, experiences: list[dict]) -> list[dict]:
        overlaps = []

        for i, exp1 in enumerate(experiences):
            for exp2 in experiences[i + 1:]:
                if not self._is_overlapping(exp1, exp2):
                    continue

                overlap_type = "concurrent"

                type1 = normalize_keyword(exp1.get("employment_type") or "")
                type2 = normalize_keyword(exp2.get("employment_type") or "")

                if "freelance" in {type1, type2}:
                    overlap_type = "freelance"

                company1 = normalize_keyword(exp1.get("company") or "")
                company2 = normalize_keyword(exp2.get("company") or "")
                if company1 and company1 == company2:
                    overlap_type = "same_employer_role_overlap"

                if "volunteer" in {type1, type2} or exp1.get("volunteer") or exp2.get("volunteer"):
                    overlap_type = "volunteer"

                overlaps.append({
                    "experience1": self._experience_summary(exp1),
                    "experience2": self._experience_summary(exp2),
                    "type": overlap_type,
                })

        return overlaps

    def _experience_summary(self, exp: dict) -> str:
        title = exp.get("job_title") or "Unknown Role"
        company = exp.get("company") or "Unknown Company"
        periods = exp.get("periods", []) or []

        if len(periods) > 1:
            date_summary = "; ".join(
                (
                    f"{period.get('start_date', '?')} - "
                    f"{period.get('end_date', '?')}"
                )
                for period in periods
            )
        else:
            start = exp.get("start_date") or "?"
            end = exp.get("end_date") or "?"
            date_summary = f"{start} - {end}"

        return (
            f"{title} at {company} "
            f"({date_summary})"
        )

    def _merge_periods(
        self,
        periods: list[tuple[tuple[int, int], tuple[int, int]]],
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        if not periods:
            return []

        periods = sorted(periods, key=lambda item: item[0])
        merged = [periods[0]]

        for start, end in periods[1:]:
            last_start, last_end = merged[-1]

            adjacent_or_overlap = self._month_index(start) <= self._month_index(last_end) + 1

            if adjacent_or_overlap:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))

        return merged

    def _month_index(self, period: tuple[int, int]) -> int:
        year, month = period
        return year * 12 + month

    def _calculate_total_experience_months(
        self,
        experiences: list[dict],
    ) -> int:
        """
        Calculate the union of every real period.

        A value such as Feb-Apr 2015 & 2016 contributes six months,
        not the continuous span from Feb 2015 through Apr 2016.
        """
        if not experiences:
            return 0

        periods = []

        for exp in experiences:
            periods.extend(
                self._experience_periods(exp)
            )

        merged = self._merge_periods(periods)

        return sum(
            self._months_between_months(
                start,
                end,
            )
            for start, end in merged
        )

    def _extract_responsibilities(
        self,
        text: str,
        job_title: str | None = None,
        company: str | None = None,
    ) -> list[str]:
        responsibilities = []

        labeled = self._extract_labeled_text(text, self.DESCRIPTION_LABELS)

        if labeled:
            text_for_lines = labeled
        else:
            text_for_lines = text

        bullet_responsibilities = self._extract_responsibilities_from_bullets(text_for_lines)
        responsibilities.extend(bullet_responsibilities)

        for line in ([] if bullet_responsibilities else text_for_lines.splitlines()):
            raw = line.strip()

            if not raw:
                continue

            clean = self._strip_bullet(raw)

            if job_title and normalize_keyword(clean) == normalize_keyword(job_title):
                continue

            if company and normalize_keyword(clean) == normalize_keyword(company):
                continue

            if self._is_label_line(clean):
                continue

            if self._looks_like_title_company_line(clean):
                continue

            if self._looks_like_responsibility(clean):
                responsibilities.append(self._clean_sentence(clean))

            if not responsibilities:
                responsibilities = self._extract_responsibilities_from_lines_fallback(text)

        return self._unique(responsibilities)[:12]

    def _extract_responsibilities_from_bullets(self, text: str) -> list[str]:
        if not text:
            return []

        responsibilities = [
            self._clean_sentence(value)
            for value in self._reconstruct_bullet_lines(text)
            if len(value) > 10
        ]

        return self._unique(responsibilities)

    def _reconstruct_bullet_lines(self, text: str) -> list[str]:
        """Join visual wraps while retaining explicit or action-led boundaries."""

        output: list[str] = []
        current: str | None = None
        incomplete = re.compile(
            r"(?i)(?:[,;:]|\b(?:and|or|with|including|supporting|using|"
            r"through|across|for|to|by|via|while|which|that|و|أو|مع))\s*$"
        )
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            has_bullet = bool(self.BULLET_PATTERN.match(line))
            clean = self._strip_bullet(line)
            protected = (
                self._is_label_line(clean)
                or self._looks_like_title_company_line(clean)
            )
            words = normalize_keyword(clean).split()
            action_start = bool(
                words
                and words[0] in self.ACTION_VERBS
                and self._looks_like_responsibility(clean)
            )

            if has_bullet or (current is None and action_start):
                if current:
                    output.append(current)
                current = clean
                continue
            if current is None:
                continue
            # A lowercase wrapped continuation can legitimately contain a
            # year ("the summer of 2017"). It is prose, not a new date header.
            lowercase_continuation = bool(clean and clean[0].islower())
            if lowercase_continuation and not protected:
                current = f"{current.rstrip()} {clean.lstrip()}"
                continue
            protected = protected or self._is_date_boundary(clean)
            if protected:
                output.append(current)
                current = None
                continue
            if action_start:
                output.append(current)
                current = clean
                continue
            begins_continuation = bool(
                clean
                and (
                    clean[0].islower()
                    or clean.startswith(("و", "،"))
                    or incomplete.search(current)
                    or not self._looks_like_responsibility(clean)
                )
            )
            if begins_continuation:
                current = f"{current.rstrip()} {clean.lstrip()}"
            else:
                output.append(current)
                current = None
        if current:
            output.append(current)
        return [re.sub(r"\s+([,.;:!?])", r"\1", value) for value in output]

    def _is_date_boundary(self, value: str) -> bool:
        if len(value.split()) > 7:
            return False
        dates = self._extract_dates(value)
        return bool(
            dates.get("start_date")
            or dates.get("end_date")
            or dates.get("periods")
        )

    def _extract_description(
        self,
        text: str,
        responsibilities: list[str],
        job_title: str | None = None,
        company: str | None = None,
    ) -> str:
        if responsibilities:
            return " ".join(responsibilities[:3])

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        desc_lines = []

        for line in lines:
            clean = self._strip_bullet(line)

            if job_title and normalize_keyword(clean) == normalize_keyword(job_title):
                continue

            if company and normalize_keyword(clean) == normalize_keyword(company):
                continue

            if self._is_label_line(clean):
                continue

            if self._looks_like_title_company_line(clean):
                continue

            if len(clean.split()) >= 5:
                desc_lines.append(clean)

        return self._clean_sentence(" ".join(desc_lines[:3]))

    def _looks_like_responsibility(self, line: str) -> bool:
        if not line:
            return False

        words = normalize_keyword(line).split()

        if len(words) < 4 or len(words) > 45:
            return False

        if words and words[0] in self.ACTION_VERBS:
            return True

        if any(verb in words for verb in self.ACTION_VERBS):
            return True

        if self.METRIC_PATTERN.search(line):
            return True

        if self.BULLET_PATTERN.match(line):
            return True

        return False

    def _extract_technologies(self, text: str) -> list[str]:
        scan_text = self._technology_scan_text(text)

        found, _ = find_keywords_in_text(scan_text, self.known_technologies)
        manual_found = self._find_known_technologies_manually(scan_text)
        forced_found = self._find_forced_technologies(scan_text)

        result = self._normalize_technology_output(
            found + manual_found + forced_found
        )

        has_real_automation_context = bool(
            re.search(
                r"\b(?:"
                r"robotic process automation|rpa|"
                r"test automation|workflow automation|"
                r"industrial automation|plc|selenium"
                r")\b",
                scan_text,
                re.IGNORECASE,
            )
        )

        if not has_real_automation_context:
            result = [
                item
                for item in result
                if item.lower() != "automation"
            ]

        return result

    def _find_known_technologies_manually(self, text: str) -> list[str]:
        if not text:
            return []

        found = []

        for tech in sorted(self.known_technologies, key=len, reverse=True):
            pattern = re.escape(tech)
            pattern = pattern.replace(r"\ ", r"\s+")

            if re.search(rf"(?<![a-z0-9+#.]){pattern}(?![a-z0-9+#.])", text, re.IGNORECASE):
                found.append(tech)

        return self._unique(found)

    def _find_forced_technologies(self, text: str) -> list[str]:
        if not text:
            return []

        found = []

        for canonical, pattern in self.FORCED_TECH_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                found.append(canonical)

        return self._unique(found)

    def _extract_metrics(
        self,
        text: str,
    ) -> list[str]:
        """
        Extract measurable evidence without crossing line boundaries.

        Currency suffixes such as M/K/B are preserved, while page markers,
        years followed by job titles, and similar layout artifacts are
        excluded.
        """
        if not text:
            return []

        cleaned_lines = [
            line
            for line in str(text).splitlines()
            if not self._is_page_marker_line(
                line
            )
        ]
        text = "\n".join(cleaned_lines)
        metrics: list[str] = []

        metric_nouns = (
            r"customers?|clients?|users?|employees?|students?|"
            r"patients?|orders?|transactions?|records?|reports?|"
            r"invoices?|accounts?|cases?|projects?|guests?|"
            r"famil(?:y|ies)|seniors?|members?|tickets?|"
            r"payments?|returns?|applications?|locations?|stores?|"
            r"branches?|sites?|campaigns?|contracts?|agencies?|vendors?|"
            r"products?|representatives?"
        )

        number_words = (
            r"one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
            r"seventeen|eighteen|nineteen|twenty|thirty|forty|"
            r"fifty|sixty|seventy|eighty|ninety|hundred|thousand"
        )

        currency_suffix = (
            r"(?:k|m|b|thousand|million|billion)?"
        )

        patterns = [
            r"\b\d+(?:\.\d+)?[ \t]*%",
            (
                r"\b(?:increased|reduced|improved|decreased|"
                r"optimized|boosted|saved|grew|rose|declined)"
                r"[ \t]+(?:by[ \t]+)?"
                r"\d+(?:\.\d+)?[ \t]*%"
            ),
            (
                r"(?:\b(?:up[ \t]+to|over|more[ \t]+than|"
                r"approximately|about)[ \t]+)?"
                r"(?:USD|CAD|EUR|GBP)?[ \t]*"
                r"[$€£][ \t]*"
                r"(?:\d{1,3}(?:,\d{3})+|\d+)"
                r"(?:\.\d+)?"
                + currency_suffix
                + r"\+?"
            ),
            (
                r"\b(?:USD|CAD|EUR|GBP)[ \t]*"
                r"(?:\d{1,3}(?:,\d{3})+|\d+)"
                r"(?:\.\d+)?"
                + currency_suffix
                + r"\+?"
            ),
            (
                rf"\b(?:over|more[ \t]+than|up[ \t]+to|"
                rf"approximately|about|nearly|around)?[ \t]*"
                rf"\d+(?:,\d{{3}})*(?:\.\d+)?\+?"
                rf"[ \t]+(?:{metric_nouns})\b"
            ),
            (
                rf"\b(?:over|more[ \t]+than|up[ \t]+to|"
                rf"approximately|about|nearly|around)?[ \t]*"
                rf"(?:{number_words})"
                rf"(?:[- \t]+(?:{number_words})){{0,3}}"
                rf"[ \t]+(?:major[ \t]+|active[ \t]+|new[ \t]+|"
                rf"retail[ \t]+|local[ \t]+|physical[ \t]+|"
                rf"online[ \t]+)?"
                rf"(?:{metric_nouns})\b"
            ),
            (
                r"\b\d+(?:\.\d+)?[ \t]*"
                r"(?:k|m|b|million|thousand|billion)\+?\b"
            ),
            (
                r"\bfrom[ \t]+\d+(?:\.\d+)?"
                r"[ \t]+to[ \t]+\d+(?:\.\d+)?\b"
            ),
            (
                r"\b(?:under|within|in)[ \t]+"
                r"\d+(?:\.\d+)?[ \t]*"
                r"(?:ms|s|sec|seconds|minutes|hours|days)\b"
            ),
        ]

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                text,
                re.IGNORECASE,
            ):
                value = re.sub(
                    r"[ \t]+",
                    " ",
                    match.group(0),
                ).strip(" ,.;:")

                if not value:
                    continue

                if re.fullmatch(
                    r"(?:19|20)\d{2}[ \t]+"
                    r"[A-Za-z]+",
                    value,
                ):
                    continue

                metrics.append(value)

        unique_metrics = self._unique(
            metrics
        )

        currency_values = {
            re.sub(
                r"^(?:USD|CAD|EUR|GBP)?"
                r"[ \t]*[$€£][ \t]*",
                "",
                value,
                flags=re.IGNORECASE,
            ).casefold()
            for value in unique_metrics
            if re.search(
                r"[$€£]|^(?:USD|CAD|EUR|GBP)",
                value,
                re.IGNORECASE,
            )
        }

        return [
            value
            for value in unique_metrics
            if not (
                not re.search(
                    r"[$€£]|^(?:USD|CAD|EUR|GBP)",
                    value,
                    re.IGNORECASE,
                )
                and value.casefold()
                in currency_values
            )
        ]


    # ================================================================
    # Validation / scoring
    # ================================================================

    def _has_experience_signal(self, text: str, from_experience_section: bool) -> bool:
        if not text:
            return False

        lower = normalize_keyword(text)
        dates = self._extract_dates(text)

        if from_experience_section:
            if self._extract_job_title(text) or self._extract_company(text) or dates.get("end_date"):
                return True

        if dates.get("start_date") and dates.get("end_date"):
            return True

        if self._extract_job_title(text) and (self._extract_company(text) or dates.get("end_date")):
            return True

        if any(verb in lower.split() for verb in self.ACTION_VERBS) and self._extract_company(text):
            return True

        if self._is_volunteer_experience(text) and (self._extract_job_title(text) or self._extract_company(text)):
            return True

        if self._sbert_ready() and self._semantic_experience_score(text) >= self.semantic_threshold:
            return True

        return False

    def _is_valid_experience(
        self,
        item: dict,
        from_experience_section: bool,
    ) -> bool:
        return not self._experience_validation_errors(
            item,
            from_experience_section,
        )

    def _experience_validation_errors(
        self,
        item: dict,
        from_experience_section: bool,
    ) -> list[str]:
        if not item:
            return ["empty_item"]

        errors = []
        raw_text = str(item.get("raw_text") or "").strip()
        normalized_raw = normalize_keyword(
            raw_text
        )
        normalized_title = normalize_keyword(
            item.get("job_title")
            or ""
        )
        normalized_company = normalize_keyword(
            item.get("company")
            or ""
        )

        template_identity = bool(
            normalized_title
            in {
                "job title",
                "position title",
                "role title",
            }
            or normalized_company
            in {
                "company name",
                "employer name",
                "organization name",
            }
        )
        template_body = bool(
            "key responsibility or achievement"
            in normalized_raw
            or (
                "job title" in normalized_raw
                and "company name" in normalized_raw
            )
        )
        if template_identity or template_body:
            errors.append(
                "template_experience_placeholder"
            )

        if any(
            re.search(pattern, raw_text)
            for pattern in self.BAD_EXPERIENCE_PATTERNS
        ):
            errors.append("non_experience_block")

        job_title = str(item.get("job_title") or "").strip()
        company = str(item.get("company") or "").strip()
        responsibilities = item.get("responsibilities", []) or []

        if job_title and not self._is_valid_job_title(job_title):
            errors.append("invalid_job_title")

        if company and not self._is_valid_company(company):
            errors.append("invalid_company")

        if company and (
            normalize_keyword(company) in self.MONTH_NAMES
            or self._is_date_only_line(company)
        ):
            errors.append("company_is_date_or_month")

        if job_title and self._is_achievement_sentence(job_title):
            errors.append("job_title_is_achievement_sentence")

        dates = bool(item.get("start_date") or item.get("end_date"))
        identity = bool(job_title or company)

        if item.get("confidence", 0) < self.min_confidence:
            errors.append("low_confidence")

        if not identity:
            errors.append("missing_title_and_company")

        if not dates and not responsibilities:
            errors.append("missing_dates_and_responsibilities")

        strong_signals = sum([
            bool(job_title),
            bool(company),
            dates,
            bool(responsibilities),
        ])

        if from_experience_section:
            if strong_signals < 3:
                errors.append("insufficient_structural_evidence")
        else:
            # Full-text fallback is intentionally stricter.
            if not job_title or strong_signals < 3:
                errors.append("insufficient_full_text_evidence")

        # Semantic similarity can support a record, but never validate it alone.
        return list(dict.fromkeys(errors))
    def _score_experience(
        self,
        job_title,
        company,
        location,
        dates,
        employment_type,
        responsibilities,
        description,
        technologies,
        metrics,
        volunteer,
        raw_text,
        semantic_score,
    ) -> int:
        """
        Confidence reflects structural correctness, not resume seniority or
        the number of years worked.
        """
        score = 0

        if job_title:
            score += 25

        if company:
            score += 25

        if dates.get("start_date") and dates.get("end_date"):
            score += 20
        elif dates.get("start_date") or dates.get("end_date"):
            score += 8

        if responsibilities:
            score += min(20, len(responsibilities) * 5)

        if metrics:
            score += min(5, len(metrics) * 3)

        if location:
            score += 3

        if employment_type or volunteer:
            score += 2

        if technologies:
            score += min(3, len(technologies))

        # Semantic evidence is deliberately weak.
        if semantic_score >= self.semantic_threshold:
            score += 2

        return min(score, 100)
    def _annotate_shared_responsibility_groups(
        self,
        experiences: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """
        Build additive group-level attribution without deleting legacy
        per-role responsibilities or metrics.

        Consumers that need strict attribution should read
        ``experience_groups``. Existing consumers can continue reading each
        role exactly as before.
        """
        grouped: dict[tuple[str, str], dict] = {}
        previous_fingerprint_ids: dict[str, str] = {}

        def unique_strings(values: list[Any]) -> list[str]:
            output: list[str] = []
            seen: set[str] = set()
            for value in values:
                clean = re.sub(
                    r"\s+",
                    " ",
                    str(value or "").strip(),
                )
                key = normalize_keyword(clean)
                if clean and key not in seen:
                    seen.add(key)
                    output.append(clean)
            return output

        for role_index, item in enumerate(experiences, start=1):
            legacy_scope = str(
                item.get("responsibilities_scope") or ""
            )
            public_scope = str(
                item.get("responsibility_scope") or ""
            )

            is_employer_shared = (
                legacy_scope == "employer_group_shared"
                or public_scope == "employer_group"
            )
            is_previous_shared = (
                legacy_scope == "prior_roles_shared"
                or public_scope == "previous_roles_group"
            )

            if not (is_employer_shared or is_previous_shared):
                item.setdefault(
                    "shared_role_responsibilities",
                    False,
                )
                item.setdefault(
                    "responsibility_scope",
                    "role_specific",
                )
                item.setdefault(
                    "responsibility_attribution",
                    "role_specific",
                )
                item.setdefault(
                    "metrics_attribution",
                    (
                        "role_specific"
                        if item.get("metrics")
                        else "none_provided"
                    ),
                )
                continue

            responsibilities = unique_strings(
                list(item.get("responsibilities", []) or [])
            )
            metrics = unique_strings(
                list(item.get("metrics", []) or [])
            )

            if is_employer_shared:
                scope = "employer_group"
                group_id = str(
                    item.get("shared_responsibility_group_id")
                    or item.get("employer_group_id")
                    or (
                        "employer_group_"
                        + re.sub(
                            r"[^a-z0-9]+",
                            "_",
                            normalize_keyword(
                                item.get("company") or "unknown"
                            ),
                        ).strip("_")
                    )
                )
                group_type = "employer"
            else:
                scope = "previous_roles_group"
                fingerprint = "|".join(
                    normalize_keyword(value)
                    for value in responsibilities
                ) or "no_shared_narrative"
                group_id = str(
                    item.get("shared_responsibility_group_id")
                    or previous_fingerprint_ids.setdefault(
                        fingerprint,
                        "previous_roles_group_"
                        f"{len(previous_fingerprint_ids) + 1}",
                    )
                )
                group_type = "previous_roles"

            item["shared_role_responsibilities"] = True
            item["responsibility_scope"] = scope
            item["shared_responsibility_group_id"] = group_id
            item["responsibility_attribution"] = (
                "shared_not_role_specific"
            )
            item["metrics_attribution"] = (
                "shared_group"
                if metrics
                else "none_provided"
            )
            item["role_specific_responsibilities"] = []
            item["role_specific_metrics"] = []

            group_key = (group_type, group_id)
            group = grouped.setdefault(
                group_key,
                {
                    "group_id": group_id,
                    "group_type": group_type,
                    "company": (
                        item.get("company")
                        if group_type == "employer"
                        else None
                    ),
                    "companies": [],
                    "role_indexes": [],
                    "role_titles": [],
                    "shared_role_responsibilities": True,
                    "responsibility_scope": scope,
                    "responsibilities": [],
                    "metrics": [],
                    "source_evidence": [],
                },
            )
            group["role_indexes"].append(role_index)
            if item.get("job_title"):
                group["role_titles"].append(item["job_title"])
            if item.get("company"):
                group["companies"].append(item["company"])
            group["responsibilities"].extend(responsibilities)
            group["metrics"].extend(metrics)
            for evidence_key in (
                "source_company_line",
                "source_role_line",
            ):
                if item.get(evidence_key):
                    group["source_evidence"].append(
                        item[evidence_key]
                    )

        groups: list[dict] = []
        for group in grouped.values():
            for key in (
                "companies",
                "role_titles",
                "responsibilities",
                "metrics",
                "source_evidence",
            ):
                group[key] = unique_strings(group[key])
            group["role_count"] = len(group["role_indexes"])
            groups.append(group)

        groups.sort(
            key=lambda group: min(
                group.get("role_indexes") or [10**9]
            )
        )
        groups = self._trim_cross_group_boundary_leakage(
            groups
        )
        return experiences, groups

    def _trim_cross_group_boundary_leakage(
        self,
        groups: list[dict],
    ) -> list[dict]:
        """
        Remove only trailing exact duplicates that leaked across an
        immediately adjacent structural group boundary.

        Per-role source payloads are left untouched for backward
        compatibility. The correction applies to the group-level source of
        truth and records an audit trail.
        """
        ordered = list(groups or [])

        for index in range(len(ordered) - 1):
            current = ordered[index]
            following = ordered[index + 1]

            if (
                current.get("group_type") != "employer"
                or following.get("group_type")
                != "previous_roles"
            ):
                continue

            current_indexes = list(
                current.get("role_indexes", [])
                or []
            )
            following_indexes = list(
                following.get("role_indexes", [])
                or []
            )

            if (
                not current_indexes
                or not following_indexes
                or min(following_indexes)
                != max(current_indexes) + 1
            ):
                continue

            next_values = {
                normalize_keyword(value)
                for value in (
                    following.get(
                        "responsibilities",
                        [],
                    )
                    or []
                )
                if value
            }
            responsibilities = list(
                current.get("responsibilities", [])
                or []
            )
            removed: list[str] = []

            while (
                responsibilities
                and normalize_keyword(
                    responsibilities[-1]
                ) in next_values
            ):
                removed.insert(
                    0,
                    responsibilities.pop(),
                )

            if not removed:
                continue

            current["responsibilities"] = (
                responsibilities
            )
            current[
                "excluded_cross_group_responsibilities"
            ] = [
                {
                    "value": value,
                    "reason":
                        "trailing_duplicate_after_group_boundary",
                    "target_group_id":
                        following.get("group_id"),
                }
                for value in removed
            ]
            current["boundary_status"] = "reconciled"

        return ordered

    def _is_source_explicit_undated_role(
        self,
        item: dict,
    ) -> bool:
        return bool(
            item.get("undated_prior_role")
            or item.get("date_status")
            == "not_provided_in_source"
            or item.get("responsibilities_scope")
            == "prior_roles_shared"
            or str(
                item.get("employer_group_id")
                or ""
            ).startswith("undated_prior_group_")
        )

    def _experience_entry_quality(
        self,
        item: dict,
        index: int | None = None,
    ) -> dict:
        prefix = (
            f"experience_{index}"
            if index is not None
            else "experience"
        )
        warnings: list[str] = []
        informational_warnings: list[str] = []
        score = 0

        source_explicit_undated = (
            self._is_source_explicit_undated_role(item)
        )

        if item.get("job_title"):
            score += 18
        else:
            warnings.append(
                f"{prefix}_job_title_unresolved"
            )

        if item.get("company"):
            score += 18
        else:
            warnings.append(
                f"{prefix}_company_unresolved"
            )

        if source_explicit_undated:
            item["date_status"] = (
                "not_provided_in_source"
            )
            item["location_status"] = (
                "not_provided_in_source"
                if not item.get("location")
                else "provided"
            )
            item["source_completeness_status"] = (
                "partial_source"
            )
            item["quality_status"] = "partial_source"
            score += 28
            informational_warnings.append(
                f"{prefix}_dates_not_provided_in_source"
            )
            if not item.get("location"):
                informational_warnings.append(
                    f"{prefix}_location_not_provided_in_source"
                )
        else:
            if item.get("start_date"):
                score += 10
            else:
                warnings.append(
                    f"{prefix}_start_date_unresolved"
                )

            if item.get("end_date") or item.get("current"):
                score += 10
            else:
                warnings.append(
                    f"{prefix}_end_date_unresolved"
                )

            if isinstance(item.get("duration_months"), int):
                score += 10
            else:
                warnings.append(
                    f"{prefix}_duration_unresolved"
                )

            if item.get("location"):
                score += 5
            else:
                warnings.append(
                    f"{prefix}_location_unresolved"
                )

        if item.get("responsibilities"):
            score += 16
        else:
            warnings.append(
                f"{prefix}_responsibilities_unresolved"
            )

        if item.get("metrics"):
            score += 5

        if item.get("technologies") or item.get("description"):
            score += 4

        if item.get("employment_type") or item.get("volunteer"):
            score += 4

        bounded_score = max(0, min(100, score))

        return {
            "status": "ok" if not warnings else "degraded",
            "quality_status": (
                "partial_source"
                if source_explicit_undated and not warnings
                else "complete_source"
                if not warnings
                else "unresolved"
            ),
            "score": bounded_score,
            "warnings": warnings,
            "informational_warnings": informational_warnings,
        }

    def _calculate_experience_score(
        self,
        experiences: list[dict],
        total_months: int,
        rejected_count: int = 0,
    ) -> int:
        if not experiences:
            return 0

        qualities = [
            self._experience_entry_quality(item)
            for item in experiences
        ]
        average_entry_score = sum(
            quality["score"] for quality in qualities
        ) / len(qualities)

        confidences = [
            max(
                0,
                min(
                    100,
                    max(
                        int(item.get("confidence", 0) or 0),
                        82
                        if self._is_source_explicit_undated_role(item)
                        else 0,
                    ),
                ),
            )
            for item in experiences
        ]
        average_confidence = sum(confidences) / len(confidences)

        total_candidates = len(experiences) + rejected_count
        acceptance_ratio = (
            len(experiences) / total_candidates
            if total_candidates
            else 0.0
        )

        score = round(
            average_entry_score * 0.70
            + average_confidence * 0.20
            + acceptance_ratio * 100 * 0.10
        )

        warnings = [
            warning
            for quality in qualities
            for warning in quality["warnings"]
        ]

        critical_suffixes = (
            "_job_title_unresolved",
            "_company_unresolved",
            "_start_date_unresolved",
            "_end_date_unresolved",
            "_duration_unresolved",
        )

        if any(
            warning.endswith(critical_suffixes)
            for warning in warnings
        ):
            score = min(score, 86)

        if warnings:
            score = min(score, 90)

        if acceptance_ratio < 0.60:
            score = min(score, 60)

        return max(0, min(92, score))

    def _build_experience_quality(
        self,
        experiences: list[dict],
        rejected_entries: list[dict],
        score: int,
    ) -> dict:
        warnings: list[str] = []
        informational_warnings: list[str] = []
        entry_quality: list[dict] = []

        for index, item in enumerate(experiences, start=1):
            quality = self._experience_entry_quality(
                item,
                index=index,
            )
            entry_quality.append(quality)
            warnings.extend(quality.get("warnings", []))
            informational_warnings.extend(
                quality.get("informational_warnings", [])
            )

        if rejected_entries:
            warnings.append(
                f"rejected_experience_candidates:{len(rejected_entries)}"
            )

        low_confidence = sum(
            1
            for item in experiences
            if (
                not self._is_source_explicit_undated_role(item)
                and int(item.get("confidence", 0) or 0) < 60
            )
        )
        if low_confidence:
            warnings.append(
                f"low_confidence_experiences:{low_confidence}"
            )

        critical_warning = any(
            warning.endswith((
                "_job_title_unresolved",
                "_company_unresolved",
                "_start_date_unresolved",
                "_end_date_unresolved",
                "_duration_unresolved",
            ))
            for warning in warnings
        )

        if score < 60:
            status = "needs_review"
        elif critical_warning or score < 75:
            status = "degraded"
        else:
            status = "ok"

        return {
            "status": status,
            "score": score,
            "valid_count": len(experiences),
            "rejected_count": len(rejected_entries),
            "warnings": list(dict.fromkeys(warnings)),
            "informational_warnings": list(dict.fromkeys(
                informational_warnings
            )),
            "entry_quality": entry_quality,
        }

    def _extract_labeled_text(self, text: str, labels: set[str]) -> str:
        labels_sorted = sorted(labels, key=len, reverse=True)
        labels_pattern = "|".join(re.escape(label) for label in labels_sorted)

        pattern = re.compile(rf"\b({labels_pattern})\s*[:\-]\s*(.+)", re.IGNORECASE)
        lines = text.splitlines()

        for index, line in enumerate(lines):
            match = pattern.search(line.strip())

            if not match:
                continue

            collected = [match.group(2).strip()]

            for next_line in lines[index + 1:]:
                stripped = next_line.strip()

                if not stripped:
                    break

                if self._is_any_label_line(stripped):
                    break

                if self._simple_new_entry_start(stripped):
                    break

                collected.append(stripped)

            return "\n".join(collected).strip()

        return ""

    def _simple_new_entry_start(self, line: str) -> bool:
        clean = self._strip_bullet(line)

        if not clean:
            return False

        if self._starts_with_action_verb(clean):
            return False

        dates = self._extract_dates(clean)

        if dates.get("start_date") or dates.get("end_date"):
            return True

        if self._find_job_title_in_text(clean) and len(clean.split()) <= 12:
            return True

        return False

    def _is_label_line(self, line: str, labels: set[str] | None = None) -> bool:
        labels = labels or (
            self.TITLE_LABELS
            | self.COMPANY_LABELS
            | self.LOCATION_LABELS
            | self.DESCRIPTION_LABELS
        )

        normalized = normalize_keyword(line.split(":", 1)[0].split("-", 1)[0])
        return normalized in labels

    def _is_any_label_line(self, line: str) -> bool:
        return self._is_label_line(line)

    # ================================================================
    # Output helpers
    # ================================================================

    def _deduplicate_experiences(self, experiences: list[dict]) -> list[dict]:
        seen = set()
        result = []

        for item in experiences:
            title_key = normalize_keyword(item.get("job_title") or "")
            company_key = normalize_keyword(item.get("company") or "")
            start_key = normalize_keyword(item.get("start_date") or "")
            end_key = normalize_keyword(item.get("end_date") or "")

            key = f"{title_key}|{company_key}|{start_key}|{end_key}"

            if not title_key and not company_key:
                continue

            if key not in seen:
                seen.add(key)
                result.append(item)

        return result

    def _get_current_position(self, experiences: list[dict]) -> str | None:
        current = [item for item in experiences if item.get("current")]

        if not current:
            return None

        item = sorted(current, key=lambda x: x.get("confidence", 0), reverse=True)[0]

        if item.get("job_title") and item.get("company"):
            return f"{item.get('job_title')} at {item.get('company')}"

        return item.get("job_title") or item.get("company")

    def _get_top_companies(self, experiences: list[dict]) -> list[str]:
        return self._unique([item.get("company") for item in experiences if item.get("company")])

    def _get_top_titles(self, experiences: list[dict]) -> list[str]:
        return self._unique([item.get("job_title") for item in experiences if item.get("job_title")])

    def _get_top_technologies(self, experiences: list[dict]) -> list[str]:
        counts = {}

        for item in experiences:
            for tech in item.get("technologies", []):
                key = tech.lower()

                if key not in counts:
                    counts[key] = {"name": tech, "count": 0}

                counts[key]["count"] += 1

        ordered = sorted(counts.values(), key=lambda item: item["count"], reverse=True)

        return [item["name"] for item in ordered]

    def _generate_recommendations(
        self,
        experiences: list[dict],
        overlaps: list[dict] | None = None,
    ) -> list[dict]:
        if not experiences:
            return [{
                "severity": "medium",
                "type": "missing",
                "message": "No clear work experience found.",
            }]

        recommendations = []

        for index, item in enumerate(experiences, start=1):
            missing = []
            if not item.get("job_title"):
                missing.append("job title")
            if not item.get("company"):
                missing.append("company")
            source_explicit_undated = (
                self._is_source_explicit_undated_role(item)
            )
            placeholder_dates = (
                item.get("date_status")
                == "placeholder_unresolved"
            )

            # Placeholder dates are present in the source and already
            # generate one document-level replacement recommendation.
            # Do not misreport them as extractor failures for every role.
            if not (
                source_explicit_undated
                or placeholder_dates
            ):
                if not item.get("start_date"):
                    missing.append("start date")
                if not (
                    item.get("end_date")
                    or item.get("current")
                ):
                    missing.append("end date")
                if not isinstance(
                    item.get("duration_months"),
                    int,
                ):
                    missing.append("duration")
            if not item.get("responsibilities"):
                missing.append("responsibilities/achievements")

            if missing:
                recommendations.append({
                    "severity": "medium",
                    "type": "incomplete_experience",
                    "message": (
                        f"Experience #{index} is missing: {', '.join(missing)}."
                    ),
                })

        with_metrics = [
            index
            for index, item in enumerate(experiences, start=1)
            if item.get("metrics")
        ]
        without_metrics = [
            index
            for index, item in enumerate(experiences, start=1)
            if (
                not item.get("metrics")
                and not item.get(
                    "shared_role_responsibilities"
                )
                and not self._is_source_explicit_undated_role(
                    item
                )
            )
        ]

        if with_metrics:
            recommendations.append({
                "severity": "good",
                "type": "metrics_detected",
                "message": (
                    "Measurable achievements were detected in experience "
                    f"entries: {with_metrics}."
                ),
                "evidence": [
                    metric
                    for item in experiences
                    for metric in item.get("metrics", [])
                ],
            })
            if without_metrics:
                recommendations.append({
                    "severity": "low",
                    "type": "metrics_partial",
                    "message": (
                        "Add quantified results only to experience entries "
                        f"that do not already contain them: {without_metrics}."
                    ),
                })
        else:
            recommendations.append({
                "severity": "medium",
                "type": "missing_metrics",
                "message": (
                    "Add measurable achievements if you have them, such as "
                    "percentages, savings, users, clients, or revenue impact."
                ),
            })

        shared_scopes = {
            str(item.get("responsibility_scope") or "")
            for item in experiences
            if item.get("shared_role_responsibilities")
        }
        if shared_scopes:
            recommendations.append({
                "severity": "info",
                "type": "shared_source_responsibilities",
                "message": (
                    "The source resume uses shared responsibilities for "
                    "multiple roles. They are preserved once at group level "
                    "and marked as not role-specific."
                ),
                "scopes": sorted(shared_scopes),
            })

        if overlaps:
            same_employer_only = all(
                item.get("type") == "same_employer_role_overlap"
                for item in overlaps
            )
            recommendations.append({
                "severity": "good",
                "type": (
                    "same_employer_roles_grouped"
                    if same_employer_only
                    else "overlap_detected"
                ),
                "message": (
                    "Multiple roles at the same employer were grouped and "
                    "total experience was calculated without double-counting."
                    if same_employer_only
                    else
                    "Concurrent experiences were detected and total "
                    "experience was calculated without double-counting."
                ),
            })

        return recommendations or [{
            "severity": "good",
            "type": "complete",
            "message": "Experience section looks strong.",
        }]


    def _empty_result(self) -> dict:
        return {
            "experiences": [],
            "experience_groups": [],
            "shared_responsibility_group_count": 0,
            "count": 0,
            "has_experience": False,
            "total_experience_months": 0,
            "total_experience_years": 0,
            "professional_experience_months": 0,
            "professional_experience_years": 0,
            "paid_experience_months": 0,
            "volunteer_experience_months": 0,
            "volunteer_experience_years": 0,
            "total_validated_experience_months": 0,
            "total_validated_experience_years": 0,
            "current_position": None,
            "top_companies": [],
            "top_titles": [],
            "top_technologies": [],
            "overlapping_experiences": [],
            "overlap_count": 0,
            "experience_score": 0,
            "experience_quality": {
                "status": "needs_review",
                "score": 0,
                "valid_count": 0,
                "rejected_count": 0,
                "warnings": ["no_valid_experience"],
            },
            "rejected_entries": [],
            "recommendations": [{
                "severity": "medium",
                "type": "empty",
                "message": "No clear work experience found.",
            }],
            "raw_experience_text": "",
            "mode": "empty",
            "extractor_mode": self._get_mode_name(),
            "spacy_available": SPACY_AVAILABLE,
            "sbert_available": SBERT_AVAILABLE,
        }
    def _load_job_titles_database(self) -> list[str]:
        titles = set(normalize_keyword(title) for title in self.JOB_TITLES)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(current_dir)

        possible_paths = [
            os.path.join(project_dir, "data", "roles.json"),
            os.path.join(project_dir, "data", "job_titles.json"),
        ]

        for path in possible_paths:
            if not os.path.exists(path):
                continue

            try:
                with open(path, encoding="utf-8") as file:
                    data = json.load(file)

                if isinstance(data, dict):
                    for items in data.values():
                        if isinstance(items, list):
                            for title in items:
                                titles.add(normalize_keyword(title))

                elif isinstance(data, list):
                    for title in data:
                        titles.add(normalize_keyword(title))

            except Exception:
                pass

        return normalize_keyword_list(list(titles))

    def _build_technology_database(self) -> list[str]:
        skills = []

        for sector_data in ALL_KEYWORDS_DATABASE.values():
            for key in (
                    "technologies",
                    "tools",
                    "software_tools",
                    "platforms",
            ):
                skills.extend(sector_data.get(key, []))

        skills.extend([
            "python", "java", "javascript", "typescript", "react",
            "node.js", "django", "flask", "fastapi", "laravel",
            "html", "css", "sql", "mysql", "postgresql", "mongodb",
            "redis", "aws", "azure", "gcp", "docker", "kubernetes",
            "ci/cd", "git", "github actions", "rest api", "api",
            "graphql", "machine learning", "deep learning", "nlp",
            "power bi", "tableau", "excel", "quickbooks", "sap",
            "oracle", "salesforce", "figma", "jira", "caseware",
            "taxprep", "netsuite", "simply accounting","act!",
            "great plains dynamics", "sunnet system", "focus report",
            "microsoft word","microsoft excel","microsoft powerpoint",
            "microsoft access","microsoft project","microsoft outlook",
            "powerpoint","windows",
        ])

        return normalize_keyword_list(skills)

    def _technology_scan_text(
            self,
            text: str,
    ) -> str:
        if not text:
            return ""

        accepted_lines = []

        for line in str(text).splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            # لا نستخرج technologies من metadata.
            if re.match(
                    r"^(?:title|company|location)\s*:",
                    stripped,
                    re.IGNORECASE,
            ):
                continue

            accepted_lines.append(stripped)

        return "\n".join(accepted_lines)

    def _normalize_technology_output(self, items: list[str]) -> list[str]:
        non_tech_terms = {
            "revenue", "customer", "customers", "sales", "business",
            "management", "project", "portfolio", "dashboard", "system",
            "platform", "application", "app", "company", "employee",
            "employees", "client", "clients","advertising","marketing",
            "accounting","finance","auditing","leadership",
        }

        result = []

        for item in items:
            key = normalize_keyword(item)

            if not key or key in non_tech_terms:
                continue

            result.append(canonical_technology(item).display)

        result = self._unique(result)

        specific_apis = {
            tech for tech in result
            if tech.lower().endswith(" api") and tech.lower() != "api"
        }

        if specific_apis and "API" in result:
            result = [tech for tech in result if tech != "API"]

        return result

    def _canonical_technology_name(self, key: str) -> str:
        return canonical_technology(key).display

    def _normalize_text(self, text: str) -> str:
        text = str(text or "")
        text = text.replace("–", "-").replace("—", "-")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # A discretionary hyphen marks a word-wrap opportunity rather than a
        # literal character. Join the two word fragments before rebuilding
        # visual line wraps (for example, "report­\ning" -> "reporting").
        text = re.sub(r"(?<=\w)\u00ad[ \t]*\n[ \t]*(?=\w)", "", text)
        text = text.replace("\u00ad", "")

        # Preserve a bullet and its sentence on the same line.
        text = re.sub(
            r"(?m)^\s*[•▪●○◦‣∙]\s*",
            "• ",
            text,
        )
        text = re.sub(
            r"(?<!\n)[•▪●○◦‣∙]\s*",
            "\n• ",
            text,
        )

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

    def _strip_bullet(self, text: str) -> str:
        return self.BULLET_PATTERN.sub("", str(text)).strip()

    def _starts_with_action_verb(self, line: str) -> bool:
        words = normalize_keyword(line).split()

        if not words:
            return False

        return words[0] in self.ACTION_VERBS

    def _looks_like_title_company_line(self, line: str) -> bool:
        if not line:
            return False

        if self._starts_with_action_verb(line):
            return False

        if len(line.split()) > 16:
            return False

        has_title = bool(self._extract_job_title(line))
        has_company = bool(self._extract_company(line))
        has_date = bool(self._extract_dates(line).get("end_date"))

        return sum([has_title, has_company, has_date]) >= 2

    def _clean_sentence(self, value: str) -> str:
        value = str(value or "").strip()
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"^[|,\-:]+", "", value)
        value = re.sub(r"[|,\-:]+$", "", value)

        return value.strip()

    def _unique(self, items: list[str]) -> list[str]:
        seen = set()
        result = []

        for item in items:
            if item is None:
                continue

            item = str(item).strip()

            if not item:
                continue

            key = re.sub(r"[.!?;:,]+$", "", re.sub(r"\s+", " ", item.casefold())).strip()

            if key not in seen:
                seen.add(key)
                result.append(item)

        return result

    def _get_mode_name(self) -> str:
        parts = ["rule", "regex", "dictionary"]

        if self.use_spacy and self.nlp is not None:
            parts.append("spacy")

        if self._sbert_ready():
            parts.append("sbert")

        return "+".join(parts)

    def _extract_title_company_from_date_header(self, text: str) -> dict:
        """
        Handles formats like:
        Oct 2014 - Present Accountant PwC
        Feb 2014 - Sept 2014 Assurance Graduate PwC
        """

        result = {
            "job_title": None,
            "company": None,
        }

        if not text:
            return result

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if not lines:
            return result

        first_line = lines[0]

        month_year = rf"(?:{self.MONTH_PATTERN})\.?\s+(?:19|20)\d{{2}}"
        year = r"(?:19|20)\d{2}"
        date_unit = rf"(?:{month_year}|{year})"

        pattern = re.compile(
            rf"^\s*({date_unit})\s*(?:-|–|—|to)\s*((?:{date_unit})|present|current|now|ongoing)\s+(.+)$",
            re.IGNORECASE,
        )

        match = pattern.search(first_line)

        if not match:
            return result

        rest = match.group(3).strip()

        title = self._find_job_title_in_text(rest)

        if not title:
            return result

        title_pattern = re.escape(title)
        title_pattern = title_pattern.replace(r"\ ", r"\s+")

        company_part = re.sub(
            rf"\b{title_pattern}\b",
            "",
            rest,
            count=1,
            flags=re.IGNORECASE,
        ).strip(" -|,.")

        normalized_title = self._normalize_job_title(title)
        company = self._clean_company(company_part)

        result["job_title"] = normalized_title

        if company and self._is_valid_company(company):
            result["company"] = company

        return result

    def _unique_keep_order(self, items: list) -> list:
        """
        Remove duplicates while preserving original order.
        Used by fallback extractors such as responsibilities extraction.
        """
        if not items:
            return []

        seen = set()
        result = []

        for item in items:
            if item is None:
                continue

            item = str(item).strip()

            if not item:
                continue

            # normalize spaces
            item = re.sub(r"\s+", " ", item).strip()

            key = re.sub(r"[.!?;:,]+$", "", re.sub(r"\s+", " ", item.casefold())).strip()

            if key not in seen:
                seen.add(key)
                result.append(item)

        return result
    def _extract_responsibilities_from_lines_fallback(self, text: str) -> list[str]:
        if not text:
            return []

        responsibilities = []

        action_starts = (
            "dealing", "offering", "reviewing", "preparing", "completing",
            "checking", "performing", "devising", "providing", "responsible",
            "helping", "assisting", "verifying", "maintaining", "working",
            "supporting", "managing", "leading", "developing", "created",
            "built", "analyzed", "analysed", "reduced", "improved"
        )

        skip_patterns = [
            r"^\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)",
            r"^\s*(19|20)\d{2}",
        ]

        for raw_line in text.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            # Handle: Main duties performed: e Dealing with...
            line = re.sub(
                r"(?i)^main duties performed\s*:\s*",
                "",
                line,
            ).strip()

            # Clean OCR bullet prefixes
            line = re.sub(
                r"^\s*(?:[•\-*]|e[¢@=]?|¢|v)\s+",
                "",
                line,
            ).strip()

            if not line:
                continue

            lower = line.lower()

            if any(re.search(pattern, lower) for pattern in skip_patterns):
                continue

            if len(line.split()) < 4:
                continue

            if lower.startswith(action_starts):
                responsibilities.append(line)

        return self._unique_keep_order(responsibilities)

# =====================================================================
# 🧪 Test
# =====================================================================

if __name__ == "__main__":
    extractor = ExperienceExtractor(
        use_spacy=True,
        use_sbert=True,
        allow_model_download=True,
    )

    test_cases = [
        {
            "name": "Software experience",
            "data": {
                "sections": {
                    "experience": {
                        "content": """
                        Software Engineer | ABC Tech Solutions | Amman, Jordan | Jan 2021 - Present
                        Developed REST APIs using Python, FastAPI, PostgreSQL, and Docker.
                        Improved system performance by 35%.
                        Led integration with AWS services and CI/CD pipelines.

                        Frontend Developer - Digital Agency - Remote - 2019 - 2020
                        Built responsive dashboards using React, JavaScript, and REST APIs.
                        Supported 20+ client websites and improved page speed by 40%.
                        """
                    }
                }
            },
        },
        {
            "name": "Accounting experience",
            "data": {
                "sections": {
                    "experience": {
                        "content": """
                        Senior Accountant | Al Noor Trading Company | Dubai, UAE | 2018 - 2023
                        Prepared monthly financial statements and reconciled bank accounts.
                        Managed accounts payable and receivable for 150+ clients.
                        Reduced reporting errors by 25% using Excel and QuickBooks.

                        Junior Accountant at Finance House LLC | 2016 - 2018
                        Processed invoices, reviewed expenses, and supported annual audits.
                        """
                    }
                }
            },
        },
        {
            "name": "Education / teaching experience",
            "data": {
                "sections": {
                    "experience": {
                        "content": """
                        English Teacher - Bright Future School | Cairo, Egypt | Sep 2020 - Present
                        Prepared lesson plans and taught English to 120+ students.
                        Improved student exam results by 18%.
                        Coordinated parent communication and classroom activities.
                        """
                    }
                }
            },
        },
        {
            "name": "Raw text fallback",
            "data": """
            John Doe
            Data Analyst

            Work Experience
            Data Analyst | Market Insights Group | 2022 - Present
            Analyzed sales data using SQL, Excel, and Power BI.
            Built dashboards that reduced reporting time by 30%.

            Education
            Bachelor of Business Administration
            """
        },
        {
            "name": "Overlapping + volunteer",
            "data": {
                "sections": {
                    "experience": {
                        "content": """
                        Data Analyst | Market Insights Group | 2022 - Present
                        Analyzed sales data using SQL, Excel, and Power BI.
                        Built dashboards that reduced reporting time by 30%.

                        Freelance Power BI Consultant | Remote | 2023 - 2024
                        Created Power BI dashboards for 5+ clients.
                        Improved reporting accuracy by 20%.
                        """
                    },
                    "volunteer": {
                        "content": """
                        Volunteer Coordinator | Local NGO | 2021 - 2022
                        Organized community service events and supported 200+ participants.
                        """
                    }
                }
            },
        },
    ]

    for case in test_cases:
        print("\n\n" + "#" * 70)
        print(case["name"])
        print("#" * 70)

        result = extractor.extract(case["data"])
        extractor.print_report(result)
