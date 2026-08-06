# =====================================================================
# 🚀 projects_extractor.py
# =====================================================================
# Hybrid Projects Extractor:
# - Regex / Rule-Based for exact data: links, dates, technologies, metrics
# - spaCy for NLP support
# - SBERT for semantic project detection and project type classification
# - Supports local model OR model download
# =====================================================================

import json
import os
import re
from typing import Any

from resume_analyzer.ai.model_registry import ModelRegistry
from resume_analyzer.terminology import canonical_technology

try:
    _DEFAULT_NLP = ModelRegistry.get_spacy("en_core_web_sm")
    SPACY_AVAILABLE = True
except (OSError, ImportError, RuntimeError):
    _DEFAULT_NLP = None
    SPACY_AVAILABLE = False

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


class ProjectsExtractor:
    """Professional Hybrid Projects Extractor."""

    PROJECT_HEADINGS = {
        "projects", "project", "personal projects", "academic projects",
        "professional projects", "selected projects", "key projects",
        "technical projects", "software projects", "portfolio",
        "project portfolio", "open source", "open-source projects",
        "side projects", "capstone project", "graduation project",
        "final year project", "research projects",
    }

    STOP_HEADINGS = {
        "summary", "profile", "objective", "experience", "work experience",
        "professional experience", "employment history", "education",
        "academic background", "skills", "technical skills", "certifications",
        "languages", "awards", "achievements", "publications", "references",
        "volunteer", "interests", "contact", "personal information",
    }

    PROJECT_KEYWORDS = {
        "project", "application", "app", "website", "web app",
        "system", "platform", "dashboard", "tool", "api", "model",
        "classifier", "predictor", "analyzer", "management system",
        "e-commerce", "portfolio", "capstone", "graduation project",
        "final year project", "open source", "automation", "bot",
        "chatbot", "mobile app", "web platform", "research project",
    }

    ACTION_VERBS = {
        "built", "developed", "designed", "implemented", "created",
        "deployed", "integrated", "automated", "optimized", "trained",
        "analyzed", "tested", "launched", "published", "engineered",
        "architected", "refactored", "improved", "delivered",
        "building", "developing", "designing", "implementing", "creating",
        "deploying", "integrating", "automating", "optimizing", "working",
        "preparing", "supporting", "collaborating", "contributing",
        "طورت", "تطوير", "عملت", "إعداد", "بناء", "نفذت",
    }

    TITLE_LABELS = {
        "project", "project name", "title", "name", "app",
        "application", "system", "platform",
    }

    DESCRIPTION_LABELS = {
        "description", "overview", "summary", "about", "details",
        "project description",
    }

    TECH_LABELS = {
        "technologies", "technology", "tech stack", "stack",
        "tools", "tools used", "environment", "built with", "using",
    }

    ROLE_LABELS = {
        "role",
        "position",
        "job title",
        "my role",
        "project role",
        "responsibility",
        "responsibilities",
    }

    ROLE_TITLES = {
        # Software / IT
        "software engineer", "software developer", "frontend developer",
        "backend developer", "full stack developer", "mobile developer",
        "web developer", "data analyst", "data scientist", "machine learning engineer",
        "devops engineer", "cloud engineer", "qa engineer", "test engineer",
        "ui ux designer", "product designer", "system administrator",
        "database administrator", "business analyst", "technical lead",
        "team lead", "project manager", "product manager",

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

        # Healthcare / Medical
        "doctor", "physician", "nurse", "registered nurse",
        "pharmacist", "dentist", "medical assistant",
        "lab technician", "laboratory technician",
        "radiology technician", "physiotherapist",
        "clinical researcher", "healthcare assistant",

        # Engineering
        "civil engineer", "mechanical engineer", "electrical engineer",
        "electronic engineer", "industrial engineer",
        "chemical engineer", "site engineer", "project engineer",
        "quality engineer", "maintenance engineer",
        "planning engineer", "structural engineer",
        "architect", "interior designer",

        # Legal
        "lawyer", "attorney", "legal assistant", "legal advisor",
        "paralegal", "legal consultant", "compliance officer",
        "contract specialist",

        # HR / Administration
        "hr specialist", "human resources specialist",
        "recruiter", "talent acquisition specialist",
        "hr coordinator", "hr manager", "office administrator",
        "administrative assistant", "executive assistant",
        "operations coordinator", "operations manager",

        # Sales / Marketing / Customer Service
        "sales representative", "sales executive", "sales manager",
        "account manager", "business development representative",
        "business development manager", "marketing specialist",
        "digital marketing specialist", "marketing manager",
        "social media specialist", "content creator",
        "seo specialist", "customer service representative",
        "customer support agent", "call center agent",
        "client relations officer",

        # General
        "consultant", "coordinator", "specialist", "assistant",
        "manager", "supervisor", "lead", "analyst", "officer",
        "representative", "intern", "trainee", "volunteer",
        "مطور برمجيات", "مهندس برمجيات",
    }

    ROLE_SUFFIXES = {
        "engineer", "developer", "designer", "analyst", "manager",
        "specialist", "coordinator", "consultant", "assistant",
        "officer", "representative", "agent", "teacher", "instructor",
        "lecturer", "professor", "nurse", "doctor", "physician",
        "pharmacist", "dentist", "accountant", "auditor",
        "bookkeeper", "lawyer", "attorney", "paralegal",
        "architect", "technician", "administrator", "supervisor",
        "lead", "intern", "trainee", "volunteer",
    }

    LINK_LABELS = {
        "link", "links", "url", "demo", "live demo", "github",
        "repo", "repository", "source code",
    }

    BAD_PROJECT_CONTEXT = {
        "phone", "email", "linkedin", "gpa", "cgpa",
        "university", "college", "school",
    }

    PROJECT_TYPE_DESCRIPTIONS = {
        "web_application": "web application website frontend backend full stack dashboard api platform",
        "mobile_application": "mobile app android ios flutter react native app store google play",
        "data_ai_project": "machine learning data science artificial intelligence nlp computer vision model prediction",
        "automation_tool": "automation script bot workflow tool scraping integration productivity",
        "cloud_devops_project": "cloud devops docker kubernetes deployment ci cd infrastructure monitoring",
        "business_system": "management system crm erp inventory sales accounting business dashboard",
        "research_project": "research experiment paper publication thesis academic study analysis",
        "design_project": "ui ux design prototype figma wireframe user experience design system",
        "other": "general project software solution application implementation",
    }

    PROJECT_SEMANTIC_DESCRIPTIONS = [
        "software project built developed implemented using technologies with features and results",
        "academic or graduation project with title technologies description and implementation",
        "portfolio project with github demo link tech stack and development details",
        "machine learning or data science project with model training analysis and results",
        "web or mobile application project with frontend backend database and deployment",
    ]

    NON_PROJECT_SEMANTIC_DESCRIPTIONS = [
        "work experience job responsibilities company employment history",
        "education degree university school gpa graduation",
        "skills list technical skills programming languages tools",
        "contact information phone email linkedin location",
        "certifications courses training awards languages",
    ]

    ROLE_SEMANTIC_DESCRIPTIONS = [
        "professional job title or project role such as accountant teacher nurse engineer analyst manager specialist",
        "person role in a project such as team lead project manager coordinator researcher assistant consultant",
        "business finance accounting role such as accountant auditor financial analyst bookkeeper finance manager",
        "education role such as teacher instructor lecturer professor trainer teaching assistant",
        "healthcare medical role such as nurse doctor pharmacist dentist medical assistant lab technician",
        "legal administrative sales marketing role such as lawyer assistant officer representative specialist manager",
    ]

    NON_ROLE_SEMANTIC_DESCRIPTIONS = [
        "software project application platform dashboard website system tool",
        "technical skills programming languages frameworks tools technologies",
        "project description achievements metrics results improvements",
        "education university degree gpa graduation date",
        "contact information email phone linkedin github portfolio",
    ]

    ROLE_BAD_WORDS = {
        "using", "built", "developed", "created", "implemented",
        "designed", "improved", "reduced", "increased", "optimized",
        "python", "docker", "react", "aws", "sql", "javascript",
        "application", "website", "platform", "dashboard", "system",
        "tool", "api", "project", "gpa", "university", "college",
        "github", "demo", "link", "technologies", "technology",
    }

    NON_TECH_TERMS = {
        "revenue",
        "customer",
        "customers",
        "order",
        "orders",
        "sales",
        "business",
        "management",
        "project",
        "portfolio",
        "e-commerce",
        "ecommerce",
        "dashboard",
        "system",
        "platform",
        "application",
        "app",
        "operations",
        "planning",
        "account management",
    }
    BULLET_PATTERN = re.compile(r"^\s*[•\-\*►▪]\s*")

    URL_PATTERN = re.compile(
        r"\b(?:https?://|www\.)[^\s<>()]+|"
        r"\b(?:github|gitlab|bitbucket)\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+/?[^\s<>()]*",
        re.IGNORECASE,
    )

    METRIC_PATTERN = re.compile(
        r"\b("
        r"\d+(?:\.\d+)?\s*%|"
        r"\d+(?:\.\d+)?\s*(?:k|m|million|thousand)\+?|"
        r"\d+\+?\s*(?:users|requests|downloads|stars|clients|records|transactions|items|pages|apis)"
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
        semantic_threshold: float = 0.43,
        type_threshold: float = 0.38,
        role_semantic_threshold: float = 0.36,
        max_projects: int = 20,
        min_confidence: int = 35,
        max_title_words: int = 14,
    ):
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.nlp = _DEFAULT_NLP if self.use_spacy else None

        self.use_sbert = use_sbert and SBERT_AVAILABLE
        self.allow_model_download = allow_model_download
        self.model_name = model_name
        self.semantic_threshold = semantic_threshold
        self.type_threshold = type_threshold
        self.role_semantic_threshold = role_semantic_threshold

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = (
            model_path
            if model_path
            else os.path.join(current_dir, "..", "models", "sbert_model")
        )

        self.sbert_model = None
        self.project_embeddings = None
        self.non_project_embeddings = None
        self.type_embeddings = None
        self.project_type_names = list(self.PROJECT_TYPE_DESCRIPTIONS.keys())
        self.role_embeddings = None
        self.non_role_embeddings = None

        self.max_projects = max_projects
        self.min_confidence = min_confidence
        self.max_title_words = max_title_words

        self.known_technologies = self._build_technology_database()
        self.role_titles = self._load_roles_database()

        if self.use_sbert:
            self._load_sbert_if_available()

    # ================================================================
    # Public API
    # ================================================================

    def extract(self, parsed_sections_or_text: Any) -> dict:
        full_text = self._get_full_text(parsed_sections_or_text)
        projects_text = self._get_projects_text(parsed_sections_or_text)

        if not projects_text and full_text:
            projects_text = self._extract_projects_section_from_text(full_text)

        candidate_text = self._normalize_text(projects_text)

        if not candidate_text and not full_text:
            return self._empty_result()

        # A generic resume can mention "projects", "systems", or several
        # technologies in its summary and work history without containing a
        # projects section. Treating the entire document as project content
        # turns headings such as EDUCATION or the resume title into fabricated
        # project names. Broad discovery is therefore limited to structurally
        # project-like windows below.
        raw_entries = (
            self._split_project_entries(candidate_text)
            if candidate_text
            else []
        )
        raw_entries.extend(self._extract_from_experience(parsed_sections_or_text))

        projects = []

        for raw_entry in raw_entries:
            project = self._parse_project(raw_entry)

            if self._is_valid_project(project):
                projects.append(project)

        if not projects and full_text:
            for window in self._scan_full_text_windows(full_text):
                if not self._has_standalone_project_evidence(window):
                    continue
                project = self._parse_project(window)

                if self._is_valid_project(project):
                    projects.append(project)

        projects = self._deduplicate_projects(projects)
        projects = sorted(projects, key=lambda item: item.get("confidence", 0), reverse=True)
        projects = projects[: self.max_projects]

        return {
            "projects": projects,
            "count": len(projects),
            "has_projects": bool(projects),
            "top_technologies": self._get_top_technologies(projects),
            "project_score": self._calculate_project_score(projects),
            "recommendations": self._generate_recommendations(projects),
            "raw_projects_text": projects_text or "",
            "mode": self._get_mode_name(),
            "spacy_available": SPACY_AVAILABLE,
            "sbert_available": SBERT_AVAILABLE,
        }

    def print_report(self, result: dict) -> None:
        print("\n" + "=" * 70)
        print("                    🚀 PROJECTS REPORT")
        print("=" * 70)

        print(f"\n📊 Projects Found: {result.get('count', 0)}")
        print(f"   Project Score:  {result.get('project_score', 0)}")
        print(f"   Mode:           {result.get('mode')}")

        top_tech = result.get("top_technologies", [])

        if top_tech:
            print(f"   Top Tech:       {', '.join(top_tech[:12])}")

        projects = result.get("projects", [])

        if projects:
            print("\n📁 Projects:")
            print("-" * 70)

            for idx, project in enumerate(projects, start=1):
                print(f"\n   #{idx} [{project.get('confidence', 0)}% confidence]")
                print(f"   Title:        {project.get('title')}")
                print(f"   Type:         {project.get('project_type')}")
                print(f"   Type Score:   {project.get('project_type_score')}")
                print(f"   Semantic:     {project.get('semantic_score')}")
                print(f"   Role:         {project.get('role')}")
                print(f"   Dates:        {project.get('start_date')} → {project.get('end_date')}")
                print(f"   Current:      {project.get('current')}")
                print(f"   Technologies: {', '.join(project.get('technologies', []))}")
                print(f"   GitHub:       {project.get('github')}")
                print(f"   Demo:         {project.get('demo')}")
                print(f"   Link:         {project.get('link')}")

                if project.get("description"):
                    print(f"   Description:  {project.get('description')[:180]}")

                if project.get("highlights"):
                    print("   Highlights:")
                    for item in project.get("highlights", [])[:4]:
                        print(f"      - {item}")

                if project.get("metrics"):
                    print(f"   Metrics:      {', '.join(project.get('metrics'))}")

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
        """
        تحميل SBERT المشترك من ModelRegistry،
        مع بناء embeddings الخاصة بالمشاريع مرة واحدة داخل هذا extractor.
        """

        if self._sbert_ready():
            return True

        if not SBERT_AVAILABLE or SentenceTransformer is None:
            return False

        try:
            self.sbert_model = ModelRegistry.get_sbert(
                model_path=self.model_path,
                fallback_model_name=getattr(
                    self,
                    "model_name",
                    "all-MiniLM-L6-v2",
                ),
                allow_download=self.allow_model_download,
            )

        except Exception as exc:
            print(f"⚠️ Projects SBERT unavailable: {exc}")
            self.sbert_model = None
            return False

        try:
            self.project_embeddings = self.sbert_model.encode(
                self.PROJECT_SEMANTIC_DESCRIPTIONS,
                convert_to_tensor=True,
            )

            self.non_project_embeddings = self.sbert_model.encode(
                self.NON_PROJECT_SEMANTIC_DESCRIPTIONS,
                convert_to_tensor=True,
            )

            type_descriptions = [
                f"{name.replace('_', ' ')}: {description}"
                for name, description
                in self.PROJECT_TYPE_DESCRIPTIONS.items()
            ]

            self.type_embeddings = self.sbert_model.encode(
                type_descriptions,
                convert_to_tensor=True,
            )

            self.role_embeddings = self.sbert_model.encode(
                self.ROLE_SEMANTIC_DESCRIPTIONS,
                convert_to_tensor=True,
            )

            self.non_role_embeddings = self.sbert_model.encode(
                self.NON_ROLE_SEMANTIC_DESCRIPTIONS,
                convert_to_tensor=True,
            )

            return True

        except Exception as exc:
            print(f"⚠️ Failed to build project embeddings: {exc}")

            self.project_embeddings = None
            self.non_project_embeddings = None
            self.type_embeddings = None
            self.role_embeddings = None
            self.non_role_embeddings = None

            return False

    def _sbert_ready(self) -> bool:
        return (
                self.sbert_model is not None
                and self.project_embeddings is not None
                and self.non_project_embeddings is not None
                and self.type_embeddings is not None
                and self.role_embeddings is not None
                and self.non_role_embeddings is not None
                and util is not None
        )

    def _load_roles_database(self) -> list[str]:
        """
        Dictionary layer:
        - يستخدم ROLE_TITLES الافتراضي
        - وإذا وجدت data/roles.json يدمجها معها
        """

        roles = set(normalize_keyword(role) for role in self.ROLE_TITLES)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(current_dir)
        roles_path = os.path.join(project_dir, "data", "roles.json")

        if os.path.exists(roles_path):
            try:
                with open(roles_path, encoding="utf-8") as file:
                    data = json.load(file)

                if isinstance(data, dict):
                    for items in data.values():
                        if isinstance(items, list):
                            for role in items:
                                roles.add(normalize_keyword(role))

                elif isinstance(data, list):
                    for role in data:
                        roles.add(normalize_keyword(role))

            except Exception:
                pass

        return normalize_keyword_list(list(roles))

    def _semantic_project_score(self, text: str) -> float:
        if not text:
            return 0.0

        base_score = 0.0

        if self._sbert_ready():
            embedding = self.sbert_model.encode([text[:1200]], convert_to_tensor=True)

            project_score = util.cos_sim(
                embedding,
                self.project_embeddings,
            ).max().item()

            non_project_score = util.cos_sim(
                embedding,
                self.non_project_embeddings,
            ).max().item()

            base_score = max(0.0, project_score - (non_project_score * 0.35))

        # Rule boost: link واضح
        if self.URL_PATTERN.search(text):
            base_score = max(base_score, 0.30)

        # Rule boost: technologies واضحة
        scan_text = self._technology_scan_text(text)
        techs, _ = find_keywords_in_text(scan_text, self.known_technologies)

        if len(techs) >= 3:
            base_score = max(base_score, 0.25)

        # Rule boost: project keywords
        lower = text.lower()

        if any(keyword in lower for keyword in self.PROJECT_KEYWORDS):
            base_score = max(base_score, 0.28)

        return round(base_score, 3)

    def _semantic_role_score(self, role: str) -> float:
        """
        Model layer:
        يعطي score إذا candidate يشبه job/project role.
        يستخدم SBERT إذا جاهز.
        """

        if not role or not self._sbert_ready():
            return 0.0

        if self.role_embeddings is None or self.non_role_embeddings is None:
            return 0.0

        embedding = self.sbert_model.encode([role[:200]], convert_to_tensor=True)

        role_score = util.cos_sim(
            embedding,
            self.role_embeddings,
        ).max().item()

        non_role_score = util.cos_sim(
            embedding,
            self.non_role_embeddings,
        ).max().item()

        final = role_score - (non_role_score * 0.35)

        return round(max(0.0, final), 3)

    def _classify_project_type(self, text: str) -> tuple[str | None, float]:
        if not text or not self._sbert_ready():
            return None, 0.0

        embedding = self.sbert_model.encode([text[:1200]], convert_to_tensor=True)
        scores = util.cos_sim(embedding, self.type_embeddings)[0]

        best_idx = scores.argmax().item()
        best_score = scores[best_idx].item()

        if best_score < self.type_threshold:
            return "other", round(best_score, 3)

        return self.project_type_names[best_idx], round(best_score, 3)

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

    def _get_projects_text(self, data: Any) -> str:
        if not isinstance(data, dict):
            return ""

        sections = data.get("sections", data)

        if not isinstance(sections, dict):
            return ""

        for key in ["projects", "project", "portfolio"]:
            value = sections.get(key)

            if isinstance(value, dict) and value.get("content"):
                return value.get("content")

            if isinstance(value, str) and value.strip():
                return value

        for key, value in sections.items():
            normalized_key = self._normalize_heading(str(key))

            if normalized_key in self.PROJECT_HEADINGS:
                if isinstance(value, dict):
                    return value.get("content", "") or ""

                if isinstance(value, str):
                    return value

        return ""

    def _extract_projects_section_from_text(self, text: str) -> str:
        lines = text.splitlines()
        start_index = None

        for index, line in enumerate(lines):
            if self._normalize_heading(line) in self.PROJECT_HEADINGS:
                start_index = index + 1
                break

        if start_index is None:
            return ""

        collected = []

        for line in lines[start_index:]:
            if self._normalize_heading(line) in self.STOP_HEADINGS:
                break

            collected.append(line)

        return "\n".join(collected).strip()

    # ================================================================
    # Splitting
    # ================================================================

    def _split_project_entries(self, text: str) -> list[str]:
        text = self._normalize_text(text)
        structured = self._split_structured_project_entries(text)
        if structured:
            return [entry for entry in structured if self._has_project_signal(entry)]
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

            if len(entry) < 5:
                continue

            if self._has_project_signal(entry):
                cleaned.append(entry)

        return cleaned

    def _split_structured_project_entries(self, text: str) -> list[str]:
        """Segment title/date layouts before any sentence-level heuristics run."""

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        starts: list[int] = []
        for index, line in enumerate(lines):
            clean = self._strip_bullet(line)
            if self._starts_with_action_verb(clean) or self._is_date_only_line(clean):
                continue
            pipe_title = clean.split("|", 1)[0].strip() if "|" in clean else ""
            has_title_role = bool(
                pipe_title
                and self._looks_like_title_line(pipe_title)
                and clean.split("|", 1)[1].strip()
            )
            followed_by_date = bool(
                index + 1 < len(lines)
                and self._looks_like_title_line(clean)
                and self._is_date_only_line(lines[index + 1])
            )
            if has_title_role or followed_by_date:
                starts.append(index)
        if not starts:
            return []
        entries = []
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            entry = "\n".join(lines[start:end]).strip()
            if entry:
                entries.append(entry)
        return entries

    def _is_date_only_line(self, line: str) -> bool:
        clean = self._strip_bullet(line).strip()
        month = rf"(?:{self.MONTH_PATTERN})\.?\s+(?:19|20)\d{{2}}"
        unit = rf"(?:{month}|(?:19|20)\d{{2}})"
        return bool(
            re.fullmatch(
                rf"{unit}(?:\s*(?:-|â€“|â€”|to)\s*(?:{unit}|present|current|ongoing|now))?",
                clean,
                re.IGNORECASE,
            )
        )

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
                and self._looks_like_new_project_start(line)
                and self._has_project_signal("\n".join(current))
            )

            if starts_new:
                entries.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            entries.append("\n".join(current))

        return entries

    def _looks_like_new_project_start(self, line: str) -> bool:
        clean = self._strip_bullet(line)
        lower = clean.lower()

        if not clean:
            return False

        if self._is_label_line(clean):
            return False

        # لا تبدأ مشروع جديد من جملة إنجاز أو metric
        if self._starts_with_action_verb(clean):
            return False

        if self._looks_like_result_or_metric_line(clean):
            return False

        # الجمل المنتهية بنقطة غالباً description وليست title
        if clean.endswith(".") and len(clean.split()) > 3:
            return False

        if self._extract_title_from_label(clean):
            return True

        if any(keyword in lower for keyword in self.PROJECT_KEYWORDS) and len(clean.split()) <= 14:
            return True

        if self._looks_like_title_line(clean):
            return True

        return False

    def _scan_full_text_windows(self, text: str) -> list[str]:
        text = self._normalize_text(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        windows = []

        for idx, line in enumerate(lines):
            if self._has_project_signal(line):
                start = max(0, idx - 1)
                end = min(len(lines), idx + 7)
                windows.append("\n".join(lines[start:end]))

        return windows

    def _has_standalone_project_evidence(self, text: str) -> bool:
        """Require project structure before accepting a full-resume fallback.

        Keyword presence alone is deliberately insufficient. Resume summaries
        commonly mention projects, systems, tools, and technologies; those
        mentions must not turn nearby section headings into project titles.
        """

        lines = [
            self._strip_bullet(line.strip())
            for line in self._normalize_text(text).splitlines()
            if line.strip()
        ]
        if not lines:
            return False

        explicit_label = re.compile(
            r"(?i)^(?:project\s+name|project)\s*[:\-]\s*\S"
        )
        if any(explicit_label.search(line) for line in lines):
            return True

        title_index = None
        for index, line in enumerate(lines[:3]):
            title_part = line.split("|", 1)[0].strip()
            normalized_title = f" {normalize_keyword(title_part)} "
            title_words = normalize_keyword(title_part).split()
            if (
                normalize_keyword(title_part) in self.role_titles
                or (
                    title_words
                    and title_words[-1] in self.ROLE_SUFFIXES
                )
            ):
                continue
            has_project_term = any(
                f" {normalize_keyword(keyword)} " in normalized_title
                for keyword in self.PROJECT_KEYWORDS
            )
            pipe_structure = "|" in line and bool(line.split("|", 1)[1].strip())
            if (
                self._looks_like_title_line(title_part)
                and (has_project_term or pipe_structure)
            ):
                title_index = index
                break

        if title_index is None:
            return False

        body_lines = []
        for line in lines[title_index + 1:]:
            if normalize_keyword(line) in self.STOP_HEADINGS:
                break
            body_lines.append(line)
        has_action = any(
            self._starts_with_action_verb(line)
            for line in body_lines
        )
        if not has_action:
            return False

        has_date = any(self._is_date_only_line(line) for line in body_lines)
        has_link = bool(self.URL_PATTERN.search("\n".join(body_lines)))
        has_technology = bool(self._extract_technologies("\n".join(body_lines)))
        return has_date or has_link or has_technology

    def _extract_from_experience(self, data: Any) -> list[str]:
        """
        يستخرج المشاريع التي تكون داخل قسم experience:
        Key Projects:
        Notable Projects:
        Major Projects:
        """

        if not isinstance(data, dict):
            return []

        sections = data.get("sections", data)

        if not isinstance(sections, dict):
            return []

        experience = sections.get("experience")

        if isinstance(experience, dict):
            text = experience.get("content", "") or ""
        elif isinstance(experience, str):
            text = experience
        else:
            return []

        if not text:
            return []

        patterns = [
            r"(?:key|notable|selected|major|main)\s+projects?\s*[:\-]\s*(.*?)(?=\n\s*\n|\n[A-Z][A-Za-z\s]{2,30}\s*[:\-]|$)",
            r"(?:projects?|portfolio)\s*[:\-]\s*(.*?)(?=\n\s*\n|\n[A-Z][A-Za-z\s]{2,30}\s*[:\-]|$)",
        ]

        entries = []

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                project_text = match.group(1).strip()

                if project_text:
                    entries.extend(self._split_project_entries(project_text))

        return entries

    # ================================================================
    # Parse
    # ================================================================

    def _parse_project(self, raw_text: str) -> dict:
        raw_text = self._normalize_text(raw_text)

        title = self._extract_title(raw_text)
        description = self._extract_description(raw_text, title)
        technologies = self._extract_technologies(raw_text)
        links = self._extract_links(raw_text)
        dates = self._extract_dates(raw_text)
        role = self._extract_role(raw_text)
        highlights = self._extract_highlights(raw_text, title)
        metrics = self._extract_metrics(raw_text)

        semantic_score = self._semantic_project_score(raw_text)
        project_type, project_type_score = self._classify_project_type(raw_text)

        confidence = self._score_project(
            title=title,
            description=description,
            technologies=technologies,
            links=links,
            dates=dates,
            highlights=highlights,
            metrics=metrics,
            role=role,
            raw_text=raw_text,
            semantic_score=semantic_score,
        )

        return {
            "title": title,
            "description": description,
            "technologies": technologies,
            "role": role,
            "start_date": dates.get("start_date"),
            "end_date": dates.get("end_date"),
            "current": dates.get("current", False),
            "link": links.get("link"),
            "github": links.get("github"),
            "demo": links.get("demo"),
            "all_links": links.get("all_links", []),
            "highlights": highlights,
            "metrics": metrics,
            "project_type": project_type,
            "project_type_score": project_type_score,
            "semantic_score": semantic_score,
            "raw_text": raw_text,
            "confidence": confidence,
        }

    # ================================================================
    # Title
    # ================================================================

    def _extract_title(self, text: str) -> str | None:
        labeled = self._extract_title_from_label(text)

        if labeled:
            return labeled

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for line in lines:
            clean = self._strip_bullet(line)

            if self._is_label_line(clean):
                continue

            # صيغة ممتازة:
            # Resume Analyzer Platform | Python, NLP, Docker | 2024
            if "|" in clean:
                first_part = clean.split("|", 1)[0].strip()
                first_part = self._clean_title(first_part)

                if self._looks_like_title_line(first_part):
                    return first_part

            if self._looks_like_title_line(clean):
                return self._clean_title(clean)

        links = self._extract_links(text)
        github = links.get("github")

        if github:
            return self._title_from_url(github)

        return None

    def _extract_title_from_label(self, text: str) -> str | None:
        pattern = re.compile(
            r"\b(?:project\s*name|project|title|name|application|app|system|platform)\s*[:\-]\s*(.+)",
            re.IGNORECASE,
        )

        for line in text.splitlines():
            match = pattern.search(line.strip())

            if not match:
                continue

            value = match.group(1).strip()
            value = re.split(r"\s+\|\s+|;|\s+-\s+", value)[0]
            value = self._clean_title(value)

            if self._looks_like_title_line(value):
                return value

        return None

    def _looks_like_title_line(self, line: str) -> bool:
        line = self._clean_title(line)

        if not line:
            return False

        lower = line.lower()
        words = line.split()

        if len(words) > self.max_title_words:
            return False

        if len(line) > 100:
            return False

        if "@" in lower or "http" in lower or "www." in lower:
            return False

        if lower in self.STOP_HEADINGS or lower in self.PROJECT_HEADINGS:
            return False

        if self._is_label_line(line):
            return False

        # مهم جداً: لا تعتبر جمل الإنجاز عنوان
        if self._starts_with_action_verb(line):
            return False

        if self._looks_like_result_or_metric_line(line):
            return False

        if line.endswith(".") and len(words) > 3:
            return False

        signals = [
            any(keyword in lower for keyword in self.PROJECT_KEYWORDS),
            bool(re.search(r"\b(api|crm|erp|cms|dashboard|analyzer|classifier|predictor|bot|app|website|platform)\b",
                           lower)),
            len(words) <= 7,
            bool(re.search(r"[A-Z][A-Za-z0-9]+", line)),
            bool(re.search(r"[\u0600-\u06ff]", line)) and len(words) <= 7,
        ]

        return sum(signals) >= 2

    def _clean_title(self, value: str) -> str:
        value = self._strip_bullet(value)
        value = re.sub(r"\b(?:19|20)\d{2}\b.*$", "", value)
        value = re.sub(r"\b(?:present|current|ongoing)\b.*$", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\b(?:github|demo|link|technologies|tech stack)\s*[:\-].*$", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^[|,\-:]+", "", value)
        value = re.sub(r"[|,\-:]+$", "", value)
        value = re.sub(r"\s+", " ", value)

        return value.strip()

    # ================================================================
    # Description / highlights
    # ================================================================

    def _extract_description(self, text: str, title: str | None = None) -> str:
        labeled = self._extract_labeled_text(text, self.DESCRIPTION_LABELS)

        if labeled:
            return self._clean_description(labeled)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        desc_lines = []

        for line in lines:
            clean = self._strip_bullet(line)

            if title and normalize_keyword(clean) == normalize_keyword(title):
                continue

            if self._is_label_line(clean, labels=self.TECH_LABELS | self.LINK_LABELS | self.ROLE_LABELS):
                continue

            if self.URL_PATTERN.search(clean):
                continue

            if self._is_date_only_line(clean):
                continue

            if self._looks_like_title_line(clean) and not desc_lines:
                continue

            if len(clean.split()) >= 4:
                desc_lines.append(clean)
            elif desc_lines:
                # PDF line wrapping can leave a meaningful final continuation
                # such as "operations." on its own physical line.
                desc_lines[-1] = f"{desc_lines[-1].rstrip()} {clean.lstrip()}"

        return self._clean_description(" ".join(desc_lines))

    def _extract_highlights(self, text: str, title: str | None = None) -> list[str]:
        highlights = []

        for line in text.splitlines():
            raw = line.strip()

            if not raw:
                continue

            clean = self._strip_bullet(raw)

            if title and normalize_keyword(clean) == normalize_keyword(title):
                continue

            if self._is_label_line(clean):
                continue

            if self.URL_PATTERN.search(clean):
                continue

            if self._looks_like_highlight(clean):
                highlights.append(self._clean_description(clean))

        return self._unique(highlights)[:8]

    def _looks_like_highlight(self, line: str) -> bool:
        lower = line.lower()
        words = lower.split()

        if len(words) < 4 or len(words) > 35:
            return False

        if any(verb in words for verb in self.ACTION_VERBS):
            return True

        if self.METRIC_PATTERN.search(line):
            return True

        if self.BULLET_PATTERN.match(line):
            return True

        return False

    def _clean_description(self, value: str) -> str:
        value = str(value).strip()
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"^[|,\-:]+", "", value)
        value = re.sub(r"[|,\-:]+$", "", value)

        return value.strip()

    # ================================================================
    # Technologies
    # ================================================================

    def _extract_technologies(self, text: str) -> list[str]:
        technologies = []

        scan_text = self._technology_scan_text(text)

        labeled = self._extract_labeled_text(scan_text, self.TECH_LABELS)

        if labeled:
            technologies.extend(self._split_technologies(labeled))

        found, _ = find_keywords_in_text(scan_text, self.known_technologies)
        technologies.extend(found)

        return self._normalize_technology_output(technologies, source_text=scan_text)

    def _split_technologies(self, text: str) -> list[str]:
        text = re.split(
            r"\n(?:description|overview|github|demo|link|role|responsibilities)\s*[:\-]",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        parts = re.split(r"[,;|/•]+|\s+\+\s+", text)
        result = []

        for part in parts:
            item = part.strip()
            item = re.sub(r"^[\[\(]+|[\]\)]+$", "", item)
            item = re.sub(r"\s+", " ", item)

            if self._is_valid_technology_item(item):
                result.append(item)

        return result

    def _is_valid_technology_item(self, value: str) -> bool:
        if not value:
            return False

        lower = value.lower()
        words = value.split()

        if len(value) < 2 or len(value) > 45:
            return False

        if len(words) > 5:
            return False

        if "@" in lower or "http" in lower or "www." in lower:
            return False

        if re.search(r"\b(19|20)\d{2}\b", value):
            return False

        return True

    def _normalize_technology_output(self, items: list[str], source_text: str = "") -> list[str]:
        normalized = []

        for item in items:
            key = normalize_keyword(item)

            if not key:
                continue

            canonical = canonical_technology(item).display

            if self._should_keep_technology(canonical, source_text):
                normalized.append(canonical)

        normalized = self._unique(normalized)

        # إذا في API محدد، لا تعرض API العام
        specific_apis = {
            tech for tech in normalized
            if tech.lower().endswith(" api") and tech.lower() != "api"
        }

        if specific_apis and "API" in normalized:
            normalized = [tech for tech in normalized if tech != "API"]

        return normalized

    def _canonical_technology_name(self, key: str) -> str:
        return canonical_technology(key).display

    def _build_technology_database(self) -> list[str]:
        skills = []

        for sector_data in ALL_KEYWORDS_DATABASE.values():
            skills.extend(sector_data.get("hard_skills", []))

        skills.extend([
            "python", "java", "javascript", "typescript", "react",
            "node.js", "django", "flask", "fastapi", "laravel",
            "html", "css", "sql", "mysql", "postgresql", "mongodb",
            "redis", "aws", "azure", "gcp", "docker", "kubernetes",
            "ci/cd", "git", "github", "rest api", "api", "graphql",
            "machine learning", "deep learning", "nlp", "power bi",
            "tableau", "excel", "figma", "firebase", "flutter",
            "react native", "android", "ios", "openai api",
        ])

        return normalize_keyword_list(skills)

    # ================================================================
    # Links / dates / role / metrics
    # ================================================================

    def _extract_links(self, text: str) -> dict:
        links = []

        for match in self.URL_PATTERN.finditer(text):
            url = match.group(0).rstrip(".,;)")
            links.append(self._normalize_url(url))

        links = self._unique(links)

        github = None
        demo = None

        for url in links:
            lower = url.lower()

            if "github.com" in lower or "gitlab.com" in lower or "bitbucket.org" in lower:
                github = github or url
            else:
                demo = demo or url

        return {
            "github": github,
            "demo": demo,
            "link": links[0] if links else None,
            "all_links": links,
        }

    def _normalize_url(self, url: str) -> str:
        url = str(url).strip()

        if url.startswith("www."):
            url = "https://" + url

        if not re.match(r"^https?://", url, re.IGNORECASE):
            url = "https://" + url

        return url

    def _title_from_url(self, url: str) -> str | None:
        match = re.search(r"github\.com/[^/]+/([^/?#]+)", url, re.IGNORECASE)

        if not match:
            return None

        return match.group(1).replace("-", " ").replace("_", " ").title()

    def _extract_dates(self, text: str) -> dict:
        result = {"start_date": None, "end_date": None, "current": False}

        month_year = rf"(?:{self.MONTH_PATTERN})\.?\s+(?:19|20)\d{{2}}"
        numeric_month_year = r"(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}"
        year = r"(?:19|20)\d{2}"
        date_unit = rf"(?:{month_year}|{numeric_month_year}|{year})"

        range_pattern = re.compile(
            rf"\b({date_unit})\s*(?:-|–|—|to)\s*((?:{date_unit})|present|current|now|ongoing)\b",
            re.IGNORECASE,
        )

        match = range_pattern.search(text)

        if match:
            result["start_date"] = self._normalize_date(match.group(1))
            end_raw = match.group(2)

            if end_raw.lower() in {"present", "current", "now", "ongoing"}:
                result["end_date"] = "Present"
                result["current"] = True
            else:
                result["end_date"] = self._normalize_date(end_raw)

            return result

        single = re.search(rf"\b({month_year}|{numeric_month_year}|{year})\b", text, re.IGNORECASE)

        if single:
            result["end_date"] = self._normalize_date(single.group(1))

        return result

    def _normalize_date(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value).strip())

    def _find_role_title_in_text(self, text: str) -> str | None:
        """
        Dictionary layer:
        يبحث داخل role_titles، سواء من ROLE_TITLES أو roles.json.
        """

        if not text:
            return None

        roles = sorted(self.role_titles, key=len, reverse=True)

        for role in roles:
            pattern = re.escape(role)
            pattern = pattern.replace(r"\ ", r"\s+")

            if re.search(rf"\b{pattern}\b", text, re.IGNORECASE):
                return role

        return None

    def _extract_role_with_spacy(self, text: str) -> str | None:
        """
        NLP layer:
        يستخدم spaCy noun_chunks لاستخراج candidate role.
        لا يقرر وحده، يمر عبر validation.
        """

        if not self.use_spacy or self.nlp is None or not text:
            return None

        doc = self.nlp(text[:800])

        for chunk in doc.noun_chunks:
            candidate = self._clean_role_candidate(chunk.text)

            if self._is_valid_role(candidate):
                return candidate

        return None

    def _clean_role_candidate(self, role: str) -> str:
        role = str(role).strip()

        role = re.split(
            r"\.|,|;|\n|\||\s+using\s+|\s+with\s+|\s+for\s+|\s+on\s+|\s+in\s+",
            role,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        role = re.sub(r"^(a|an|the)\s+", "", role, flags=re.IGNORECASE)
        role = re.sub(r"^[\-:|]+", "", role)
        role = re.sub(r"[\-:|]+$", "", role)
        role = re.sub(r"\s+", " ", role)

        return role.strip()

    def _normalize_role(self, role: str) -> str:
        role = str(role).strip()
        role = re.sub(r"\s+", " ", role)

        special = {
            "hr": "HR",
            "ui": "UI",
            "ux": "UX",
            "qa": "QA",
            "seo": "SEO",
            "it": "IT",
            "cfo": "CFO",
            "ceo": "CEO",
            "cto": "CTO",
            "ai": "AI",
        }

        small_words = {"and", "of", "in", "for", "with", "as"}

        result = []

        for word in role.lower().split():
            if word in special:
                result.append(special[word])
            elif word in small_words:
                result.append(word)
            else:
                result.append(word.capitalize())

        return " ".join(result)

    def _is_valid_role(self, role: str) -> bool:
        """
        Hybrid validation:
        1. Rule-Based cleaning/rejection
        2. Dictionary exact match
        3. Suffix validation
        4. SBERT semantic validation
        """

        if not role:
            return False

        role = self._clean_role_candidate(role)
        lower = normalize_keyword(role)
        words = lower.split()

        if len(role) < 3 or len(role) > 80:
            return False

        if len(words) > 7:
            return False

        if "@" in lower or "http" in lower or "www." in lower:
            return False

        if re.search(r"\b(19|20)\d{2}\b", lower):
            return False

        if any(word in self.ROLE_BAD_WORDS for word in words):
            return False

        # Dictionary exact match
        if lower in self.role_titles:
            return True

        # Rule suffix:
        # Financial Analyst, Math Teacher, Legal Assistant, Sales Manager
        if words and words[-1] in self.ROLE_SUFFIXES:
            return True

        # Model fallback:
        # يلتقط roles غير موجودة بالقاموس
        if self._semantic_role_score(role) >= self.role_semantic_threshold:
            return True

        return False

    def _extract_role(self, text: str) -> str | None:
        """
        Final hybrid role extraction:
        Regex + Dictionary + spaCy + SBERT validation.
        """

        if not text:
            return None

        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if "|" in first_line:
            role = self._clean_role_candidate(first_line.split("|", 1)[1])
            if self._is_valid_role(role):
                return self._normalize_role(role)

        # 1. Regex/labeled:
        # Role: Accountant
        # Position: Teacher
        labeled = self._extract_labeled_text(text, self.ROLE_LABELS)

        if labeled:
            role = re.split(r"\n|\||;|,", labeled)[0].strip()
            role = self._clean_role_candidate(role)

            if self._is_valid_role(role):
                return self._normalize_role(role)

        # 2. Regex patterns
        patterns = [
            r"\b(?:role|position|job title|my role|project role|acting as)\s*[:\-]\s*([A-Za-z][A-Za-z\s/&\-]{2,80})",
            r"\b(?:worked|served|contributed|participated)\s+as\s+(?:a|an)?\s*([A-Za-z][A-Za-z\s/&\-]{2,80})",
            r"\bas\s+(?:a|an)?\s*([A-Za-z][A-Za-z\s/&\-]{2,80})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if not match:
                continue

            role = self._clean_role_candidate(match.group(1))

            if self._is_valid_role(role):
                return self._normalize_role(role)

        # 3. Dictionary direct match
        role = self._find_role_title_in_text(text)

        if role and self._is_valid_role(role):
            return self._normalize_role(role)

        # 4. spaCy noun chunks + validation
        role = self._extract_role_with_spacy(text)

        if role:
            return self._normalize_role(role)

        return None



    def _extract_metrics(self, text: str) -> list[str]:
        if not text:
            return []

        metrics = []

        patterns = [
            r"\b\d+(?:\.\d+)?\s*%",
            r"\b\d+\+?\s*(?:users|requests|downloads|stars|clients|records|transactions|items|pages|apis|customers|orders)\b",
            r"\b(?:increased|reduced|improved|decreased|optimized|boosted|saved)\s+by\s+\d+(?:\.\d+)?\s*%",
            r"\bfrom\s+\d+(?:\.\d+)?\s+to\s+\d+(?:\.\d+)?\b",
            r"\b\d+(?:\.\d+)?\s*(?:k|m|million|thousand)\+?\b",
            r"\b(?:under|within|in)\s+\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds|minutes|hours)\b",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                metrics.append(match.group(0).strip())

        return self._unique(metrics)
    # ================================================================
    # Generic labeled text
    # ================================================================

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

                if self._looks_like_new_project_start(stripped):
                    break

                collected.append(stripped)

            return "\n".join(collected).strip()

        return ""

    def _is_label_line(self, line: str, labels: set[str] | None = None) -> bool:
        labels = labels or (
            self.TITLE_LABELS
            | self.DESCRIPTION_LABELS
            | self.TECH_LABELS
            | self.ROLE_LABELS
            | self.LINK_LABELS
        )

        normalized = normalize_keyword(line.split(":", 1)[0].split("-", 1)[0])
        return normalized in labels

    def _is_any_label_line(self, line: str) -> bool:
        return self._is_label_line(line)

    def _starts_with_action_verb(self, line: str) -> bool:
        if not line:
            return False

        words = normalize_keyword(line).split()

        if not words:
            return False

        return words[0] in self.ACTION_VERBS

    def _looks_like_result_or_metric_line(self, line: str) -> bool:
        if not line:
            return False

        lower = line.lower().strip()

        if self.METRIC_PATTERN.search(line):
            return True

        result_starters = {
            "improved", "increased", "reduced", "optimized",
            "decreased", "achieved", "delivered", "handled",
            "processed", "saved",
        }

        words = lower.split()

        return bool(words and words[0] in result_starters)

    def _technology_scan_text(self, text: str) -> str:
        """
        تنظيف النص قبل scan التقنيات:
        - نحذف الروابط حتى ما يطلع GitHub كتقنية من URL
        - نحمي كلمة CV بمعنى resume من أنها تتحول Computer Vision
        """

        if not text:
            return ""

        text = self.URL_PATTERN.sub(" ", text)

        # CV هنا غالباً resume/CV وليس Computer Vision
        text = re.sub(r"\bCV\b", "resume", text)

        return text

    def _should_keep_technology(self, tech: str, source_text: str) -> bool:
        if not tech:
            return False

        key = normalize_keyword(tech)
        lower_source = source_text.lower()

        # كلمات ATS/business ليست technologies
        if key in self.NON_TECH_TERMS:
            return False

        # لا نريد github من الرابط كـ technology
        if key == "github":
            return False

        # Computer Vision لا تقبل إلا إذا مكتوبة صراحة
        if key == "computer vision" and "computer vision" not in lower_source:
            return False

        return True
    # ================================================================
    # Validation / scoring
    # ================================================================

    def _has_project_signal(self, text: str) -> bool:
        lower = text.lower()

        if any(keyword in lower for keyword in self.PROJECT_KEYWORDS):
            return True

        if self.URL_PATTERN.search(text):
            return True

        technologies, _ = find_keywords_in_text(
            self._technology_scan_text(text),
            self.known_technologies,
        )
        if len(technologies) >= 2 and any(verb in lower.split() for verb in self.ACTION_VERBS):
            return True

        if self._extract_labeled_text(text, self.TECH_LABELS):
            return True

        if self._sbert_ready() and self._semantic_project_score(text) >= self.semantic_threshold:
            return True

        return False

    def _is_valid_project(self, project: dict) -> bool:
        if not project:
            return False

        if project.get("confidence", 0) < self.min_confidence:
            return False

        raw = (project.get("raw_text") or "").lower()

        if any(bad in raw for bad in self.BAD_PROJECT_CONTEXT):
            strong = sum(
                bool(project.get(key))
                for key in ["title", "description", "technologies", "github", "demo"]
            )

            if strong < 3 and project.get("semantic_score", 0) < self.semantic_threshold:
                return False

        title = project.get("title")
        description = project.get("description")
        technologies = project.get("technologies", [])
        links = project.get("all_links", [])
        highlights = project.get("highlights", [])
        semantic = project.get("semantic_score", 0)

        if title and (description or technologies or links or highlights):
            return True

        if technologies and links:
            return True

        if description and technologies and len(description.split()) >= 5:
            return True

        if semantic >= self.semantic_threshold and (title or description or technologies):
            return True

        return False

    def _score_project(
        self,
        title,
        description,
        technologies,
        links,
        dates,
        highlights,
        metrics,
        role,
        raw_text,
        semantic_score,
    ) -> int:
        score = 0

        if title:
            score += 22

        if description and len(description.split()) >= 5:
            score += 18

        if technologies:
            score += min(24, len(technologies) * 4)

        if links.get("github"):
            score += 10

        if links.get("demo"):
            score += 8

        if dates.get("start_date") or dates.get("end_date"):
            score += 6

        if highlights:
            score += min(12, len(highlights) * 4)

        if metrics:
            score += min(8, len(metrics) * 4)

        if role:
            score += 4

        if any(keyword in raw_text.lower() for keyword in self.PROJECT_KEYWORDS):
            score += 4

        if semantic_score:
            score += min(18, int(semantic_score * 35))

        return min(score, 100)

    def _calculate_project_score(self, projects: list[dict]) -> int:
        if not projects:
            return 0

        count_score = min(30, len(projects) * 10)
        best_confidence = max(project.get("confidence", 0) for project in projects)

        bonus = 0

        if any(project.get("github") or project.get("demo") for project in projects):
            bonus += 10

        if any(project.get("technologies") for project in projects):
            bonus += 10

        if any(project.get("metrics") for project in projects):
            bonus += 10

        return min(100, int((best_confidence * 0.6) + count_score + bonus))

    def _generate_recommendations(self, projects: list[dict]) -> list[dict]:
        if not projects:
            return [{
                "severity": "medium",
                "type": "missing",
                "message": "No clear projects found. Add 1-3 relevant projects with technologies and links.",
            }]

        recommendations = []

        if len(projects) < 2:
            recommendations.append({
                "severity": "medium",
                "type": "quantity",
                "message": "Only one project found. Add another strong project if relevant.",
            })

        for index, project in enumerate(projects, start=1):
            missing = []

            if not project.get("technologies"):
                missing.append("technologies")

            if not project.get("description"):
                missing.append("description")

            if not project.get("github") and not project.get("demo") and not project.get("link"):
                missing.append("project link/GitHub")

            if missing:
                recommendations.append({
                    "severity": "medium",
                    "type": "incomplete_project",
                    "message": f"Project #{index} is missing: {', '.join(missing)}.",
                })

        if not recommendations:
            recommendations.append({
                "severity": "good",
                "type": "complete",
                "message": "Projects section looks strong.",
            })

        return recommendations

    # ================================================================
    # Output helpers
    # ================================================================

    def _deduplicate_projects(self, projects: list[dict]) -> list[dict]:
        seen = set()
        result = []

        for project in projects:
            title_key = normalize_keyword(project.get("title") or "")
            github_key = normalize_keyword(project.get("github") or "")
            demo_key = normalize_keyword(project.get("demo") or "")
            key = github_key or demo_key or title_key

            if not key:
                continue

            if key not in seen:
                seen.add(key)
                result.append(project)

        return result

    def _get_top_technologies(self, projects: list[dict]) -> list[str]:
        counts = {}

        for project in projects:
            for tech in project.get("technologies", []):
                key = tech.lower()

                if key not in counts:
                    counts[key] = {"name": tech, "count": 0}

                counts[key]["count"] += 1

        ordered = sorted(counts.values(), key=lambda item: item["count"], reverse=True)

        return [item["name"] for item in ordered]

    def _empty_result(self) -> dict:
        return {
            "projects": [],
            "count": 0,
            "has_projects": False,
            "top_technologies": [],
            "project_score": 0,
            "recommendations": [{
                "severity": "medium",
                "type": "empty",
                "message": "No clear projects found.",
            }],
            "raw_projects_text": "",
            "mode": self._get_mode_name(),
            "spacy_available": SPACY_AVAILABLE,
            "sbert_available": SBERT_AVAILABLE,
        }

    # ================================================================
    # General helpers
    # ================================================================

    def _get_mode_name(self) -> str:
        parts = ["rule", "regex"]

        if self.use_spacy and self.nlp is not None:
            parts.append("spacy")

        if self._sbert_ready():
            parts.append("sbert")

        return "+".join(parts)

    def _normalize_text(self, text: str) -> str:
        text = str(text or "")
        text = text.replace("–", "-").replace("—", "-")
        text = text.replace("•", "\n• ")
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

    def _unique(self, items: list[str]) -> list[str]:
        seen = set()
        result = []

        for item in items:
            if item is None:
                continue

            item = str(item).strip()

            if not item:
                continue

            key = item.lower()

            if key not in seen:
                seen.add(key)
                result.append(item)

        return result


# =====================================================================
# 🧪 Test
# =====================================================================

if __name__ == "__main__":
    extractor = ProjectsExtractor(
        use_spacy=True,
        use_sbert=True,
        allow_model_download=True,
    )

    mock_sections = {
        "sections": {
            "projects": {
                "content": """
                Resume Analyzer Platform | Python, NLP, spaCy, Docker | 2024
                Developed a CV analysis system that extracts contact info, skills, education, and projects.
                Built modular extractors and improved parsing accuracy for PDF and DOCX resumes.
                GitHub: https://github.com/yuvraj/resume-analyzer

                E-Commerce Dashboard
                Tech Stack: React, Node.js, PostgreSQL, AWS
                Created an admin dashboard for tracking orders, revenue, and customers.
                Improved reporting speed by 35%.
                Demo: https://dashboard-demo.example.com

                Graduation Project: AI Chatbot
                Technologies: Python, FastAPI, OpenAI API, PostgreSQL
                Built a chatbot that answers student questions and stores conversation history.
                2023 - 2024
                """
            }
        }
    }

    result = extractor.extract(mock_sections)
    extractor.print_report(result)

    print(f"\n✅ spaCy Available: {SPACY_AVAILABLE}")
    print(f"✅ SBERT Available: {SBERT_AVAILABLE}")
    print(f"✅ Mode: {result.get('mode')}")
