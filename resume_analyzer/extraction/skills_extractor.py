# =====================================================================
# 🔧 skills_extractor.py
# =====================================================================
# المسؤولية:
# - استخراج المهارات من قسم skills
# - فحص summary/experience/projects لاكتشاف known skills
# - فصل hard skills و soft skills
# - تصنيف hard skills حسب المجال
# - sector match
#
# ملاحظات:
# - لا يوجد تحميل SBERT إجباري.
# - لا يوجد download تلقائي إلا إذا allow_model_download=True.
# - الوضع الافتراضي Rule-Based وسريع ومناسب offline.
# =====================================================================

import os
import re

from resume_analyzer.ai.model_registry import ModelRegistry

try:
    import spacy  # Availability check only; loading is delegated to ModelRegistry.
    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    SPACY_AVAILABLE = False

try:
    from sentence_transformers import util
    SBERT_AVAILABLE = True
except ImportError:
    util = None
    SBERT_AVAILABLE = False

try:
    from .keywords import (
        ALL_KEYWORDS_DATABASE,
        auto_detect_sector,
        find_keywords_in_text,
        normalize_keyword,
        normalize_keyword_list,
    )
    from .text_cleaner import TextCleaner
except ImportError:
    from keywords import (
        ALL_KEYWORDS_DATABASE,
        auto_detect_sector,
        find_keywords_in_text,
        normalize_keyword,
        normalize_keyword_list,
    )
    from text_cleaner import TextCleaner


class SkillsExtractor:
    """استخراج وتصنيف المهارات - Hybrid Rule-Based + Optional SBERT"""

    SKILL_SPLIT_PATTERN = re.compile(r"[,;|•]+")

    SKILL_SECTION_LABELS = [
        "languages",
        "programming languages",
        "frameworks",
        "libraries",
        "cloud",
        "cloud and devops",
        "cloud & devops",
        "devops",
        "data",
        "databases",
        "database",
        "tools",
        "soft skills",
        "hard skills",
        "technical skills",
    ]

    SKILL_LABEL_WORDS = {
        "programming",
        "frontend",
        "backend",
        "languages",
        "frameworks",
        "framework",
        "libraries",
        "library",
        "cloud",
        "devops",
        "data",
        "databases",
        "database",
        "tools",
        "soft",
        "skills",
        "technical",
    }
    BAD_SKILL_VERBS = {
        "developed", "develop", "built", "build", "created", "create",
        "managed", "manage", "led", "lead", "implemented", "implement",
        "improved", "improve", "reduced", "reduce", "increased", "increase",
        "designed", "design", "deployed", "deploy", "maintained", "maintain",
        "worked", "work", "handled", "handle", "responsible", "performed",
        "achieved", "delivered", "collaborated", "coordinated", "analyzed",
        "using", "used", "with", "for",
    }

    SOFT_SKILLS = {
        "communication",
        "teamwork",
        "leadership",
        "team leadership",
        "coaching",
        "presentations",
        "client presentations",
        "problem solving",
        "critical thinking",
        "time management",
        "adaptability",
        "creativity",
        "collaboration",
        "team collaboration",
        "analytical skills",
        "analytical thinking",
        "attention to detail",
        "interpersonal skills",
        "negotiation",
        "conflict resolution",
        "emotional intelligence",
        "mentoring",
        "presentation skills",
        "decision making",
        "organizational skills",
        "organization",
        "multitasking",
        "work ethic",
        "customer service",
        "flexibility",
        "self motivation",
        "self-motivation",
        "patience",
        "active listening",
        "reliability",
        "continuous learning",
        "self-learning",
        "strategic thinking",
    }

    SOFT_SKILL_CANONICAL = {
        "communication": "Communication",
        "communications": "Communication",
        "teamwork": "Teamwork",
        "team work": "Teamwork",
        "leadership": "Leadership",
        "team leadership": "Leadership",
        "problem solving": "Problem Solving",
        "critical thinking": "Critical Thinking",
        "time management": "Time Management",
        "adaptability": "Adaptability",
        "creativity": "Creativity",
        "collaboration": "Collaboration",
        "team collaboration": "Collaboration",
        "analytical skills": "Analytical Skills",
        "analytical thinking": "Analytical Thinking",
        "attention to detail": "Attention to Detail",
        "interpersonal skills": "Interpersonal Skills",
        "negotiation": "Negotiation",
        "conflict resolution": "Conflict Resolution",
        "mentoring": "Mentoring",
        "coaching": "Coaching",
        "presentation skills": "Presentation Skills",
        "presentation": "Presentation Skills",
        "presentations": "Presentation Skills",
        "decision making": "Decision Making",
        "organizational skills": "Organizational Skills",
        "organization": "Organization",
        "customer service": "Customer Service",
        "active listening": "Active Listening",
        "strategic thinking": "Strategic Thinking",
    }

    SOFT_PREFIX_MODIFIERS = {
        "effective", "proven", "professional", "strong",
        "excellent", "creative", "advanced", "solid",
        "exceptional", "demonstrated", "client", "team",
    }

    INVALID_STANDALONE_SKILLS = {
        "provider", "other internal systems",
        "/problem", "problem", "programming", "backend", "frontend",
    }

    GENERIC_CONTEXT_SKILLS = {
        "planning", "operations", "account management", "accounting",
        "management", "presentation", "presentations", "presentation skills",
    }

    EXPLICIT_CONTEXT_LABELS = {
        "business", "business skills", "domain", "domain knowledge",
        "business/domain knowledge",
        "methods", "methodologies", "finance", "finance and accounting",
        "soft skills", "interpersonal skills",
    }

    # Exact standalone industry/domain labels are context, not executable
    # skills. Compounds remain skills: for example, "Healthcare Analytics"
    # is not reclassified because only exact normalized matches are moved.
    DOMAIN_CONTEXT_ALIASES = {
        "healthcare": "Healthcare",
        "insurance": "Insurance",
        "retail": "Retail",
        "banking": "Banking",
        "manufacturing": "Manufacturing",
        "telecommunications": "Telecommunications",
        "hospitality": "Hospitality",
        "real estate": "Real Estate",
        "pharmaceutical": "Pharmaceuticals",
        "pharmaceuticals": "Pharmaceuticals",
        "nonprofit": "Nonprofit",
        "non profit": "Nonprofit",
        "government": "Government",
        "public sector": "Public Sector",
        "ecommerce": "E-commerce",
        "e commerce": "E-commerce",
    }

    LOCATION_ABBREVIATIONS = {
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
        "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
        "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
        "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
        "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
        "dc", "uk", "usa", "u s", "u s a",
    }

    VISUAL_TEMPLATE_SKILL_PATTERNS = (
        (re.compile(r"(?i)\bproject\s+management\b"), "Project Management", "hard"),
        (re.compile(r"(?i)\bstrong\s+decision\s+maker\b|\bdecision\s+making\b"), "Decision Making", "soft"),
        (re.compile(r"(?i)\bcomplex\s+problem\s+solver\b|\bcomplex\s+problem\s+solving\b"), "Complex Problem Solving", "soft"),
        (re.compile(r"(?i)\bcreative\s+design\b"), "Creative Design", "hard"),
    )

    HARD_SKILL_CATEGORIES = {
        "programming_languages": [
            "python", "java", "javascript", "typescript", "c++", "c#",
            "go", "rust", "php", "ruby", "swift", "kotlin", "dart",
            "scala", "r", "matlab", "julia", "sql", "pl/sql", "t-sql",
            "html", "css",
        ],

        "frameworks_libraries": [
            "react", "angular", "vue.js", "next.js", "nuxt.js", "node.js",
            "express.js", "django", "flask", "fastapi", "spring boot",
            "laravel", "ruby on rails", "asp.net", ".net core",
            "jquery", "bootstrap", "tailwind css", "sass", "scss",
            "redux", "material ui", "tensorflow", "pytorch", "keras",
            "scikit-learn", "pandas", "numpy", "opencv","microservices", "rest api", "api", "graphql",
        ],

        "databases": [
            "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
            "oracle database", "oracle", "sql server", "sqlite",
            "dynamodb", "cassandra", "firebase", "hive", "realm",
        ],

        "cloud_devops": [
            "aws", "azure", "gcp", "google cloud", "docker", "kubernetes",
            "jenkins", "gitlab ci", "github actions", "terraform",
            "ansible", "linux", "unix", "bash", "shell scripting",
            "nginx", "apache", "rabbitmq", "kafka", "helm", "argocd",
            "prometheus", "grafana", "elk stack", "ci/cd",
            "infrastructure as code", "monitoring",
        ],

        "data_ai": [
            "machine learning", "deep learning", "nlp",
            "natural language processing", "computer vision",
            "data analysis", "data science", "statistical analysis",
            "data visualization", "big data", "spark", "hadoop",
            "feature engineering", "model deployment", "predictive analytics",
            "statistics", "bert", "gpt", "transformer", "yolo",
            "speech-to-text",
        ],

        "bi_analytics_tools": [
            "excel", "power bi", "tableau", "looker studio",
            "matplotlib", "seaborn", "plotly", "jupyter",
            "google analytics", "google search console",
        ],

        "design_creative": [
            "figma", "adobe xd", "sketch", "invision", "zeplin",
            "photoshop", "adobe photoshop", "illustrator",
            "adobe illustrator", "after effects", "wireframing",
            "prototyping", "user research", "usability testing",
            "design systems", "typography", "color theory",
            "ui/ux design", "responsive design",
        ],

        "marketing_sales": [
            "seo", "sem", "ppc", "google ads", "facebook ads",
            "instagram ads", "social media marketing", "content marketing",
            "email marketing", "copywriting", "crm", "salesforce",
            "hubspot", "lead generation", "campaign management",
            "brand management", "market research","marketing",
            "marketing strategy","marketing plan development","market research","advertising",
            "sales","sales management","digital marketing","campaign management","brand management",
            "promotions","direct mail","website content","strategic partnership building",
            "channel development","relationship building","effective networking",
            "vendor relations","lead generation","crm","act!","seo",
        ],

        "finance_accounting": [
            "accounting", "bookkeeping", "financial reporting",
            "financial analysis", "budgeting", "forecasting",
            "auditing", "tax preparation", "tax planning",
            "payroll", "accounts payable", "accounts receivable",
            "general ledger", "quickbooks", "xero", "sap",
            "oracle financials", "gaap", "ifrs",
        ],

        "engineering": [
            "autocad", "solidworks", "matlab", "simulink", "ansys",
            "catia", "revit", "sketchup", "civil 3d", "sap2000",
            "etabs", "primavera p6", "plc programming", "scada",
            "circuit design", "pcb design", "fpga", "vhdl",
            "verilog", "structural analysis", "mechanical design",
            "hvac", "bim", "quality control",
        ],

        "medical_clinical": [
            "patient care", "diagnosis", "treatment planning",
            "medical terminology", "emr", "ehr", "hipaa",
            "clinical research", "laboratory skills", "phlebotomy",
            "surgery", "nursing", "patient assessment",
            "medication administration", "clinical care",
        ],

        "hr": [
            "recruitment", "talent acquisition", "onboarding",
            "offboarding", "payroll systems", "performance management",
            "employee relations", "hris", "workday", "bamboohr",
            "applicant tracking systems", "ats",
        ],

        "legal": [
            "legal research", "document review", "contract drafting",
            "litigation", "case management", "compliance",
            "regulatory", "legal writing", "legal drafting",
            "due diligence",
        ],

        "education_teaching": [
            "teaching", "curriculum development", "lesson planning",
            "assessment", "e-learning", "instructional design",
            "classroom management", "educational technology",
            "student evaluation",
        ],

        "productivity_tools": [
            "microsoft word", "microsoft excel", "microsoft powerpoint",
            "microsoft access", "microsoft outlook", "windows",
        ],

        "project_management": [
            "project management", "agile", "scrum", "kanban",
            "waterfall", "pmp", "prince2", "pmi", "risk management",
            "microsoft project", "jira", "asana", "trello",
            "budget management", "resource planning",
            "stakeholder management", "change management",
            "quality management", "kpis",
        ],

        "frontend": [
            "html", "css", "javascript", "typescript", "react", "angular",
            "vue.js", "next.js", "nuxt.js", "bootstrap", "tailwind css",
            "sass", "scss", "redux", "material ui", "responsive design",
        ],

        "backend": [
            "node.js", "express.js", "django", "flask", "fastapi",
            "spring boot", "laravel", "ruby on rails", "asp.net", ".net core",
            "microservices", "rest api", "api", "graphql",
        ],

        "tools": [
            "git", "github", "gitlab", "jira", "asana", "trello", "jupyter",
        ],

        "methods": [
            "agile", "scrum", "kanban", "waterfall", "prompt engineering",
        ],

        "business_domain": [
            "account management", "accounting", "operations", "planning",
        ],

    }

    CATEGORY_DESCRIPTIONS = {
        "programming_languages": "programming languages coding software development",
        "frameworks_libraries": "software frameworks libraries web backend frontend machine learning libraries",
        "databases": "databases sql nosql storage query data persistence",
        "cloud_devops": "cloud devops infrastructure deployment docker kubernetes ci cd",
        "data_ai": "data science machine learning artificial intelligence analytics statistics",
        "bi_analytics_tools": "business intelligence analytics dashboards reporting visualization tools",
        "design_creative": "ui ux design creative prototyping graphic design user experience",
        "marketing_sales": "marketing sales advertising seo campaigns crm lead generation",
        "finance_accounting": "finance accounting audit tax bookkeeping payroll financial reporting",
        "engineering": "engineering design manufacturing civil mechanical electrical construction",
        "medical_clinical": "medical clinical healthcare patient diagnosis treatment nursing",
        "hr": "human resources recruitment onboarding employee relations payroll",
        "legal": "legal law litigation compliance contracts regulatory",
        "education_teaching": "teaching education curriculum classroom training instruction",
        "productivity_tools": "office productivity software documents spreadsheets presentations email desktop operating systems",
        "project_management": "project management agile planning stakeholder budget risk",
        "frontend": "frontend browser user interface web application styling",
        "backend": "backend server api services web application frameworks",
        "tools": "software engineering development tools source control productivity",
        "methods": "engineering and delivery methods practices methodologies",
        "business_domain": "business domain operations accounting account management",
    }

    def __init__(
            self,
            use_spacy: bool = True,
            use_sbert: bool = False,
            model_path: str | None = None,
            allow_model_download: bool = False,
            sbert_threshold: float = 0.55,
            max_skill_words: int = 6,
            max_skill_chars: int = 55,
    ):
        self.cleaner = TextCleaner()
        self.keywords_db = ALL_KEYWORDS_DATABASE

        self.use_spacy_requested = bool(use_spacy)
        self.nlp = (
            self._load_shared_spacy_model()
            if self.use_spacy_requested and SPACY_AVAILABLE
            else None
        )
        self.use_spacy = self.nlp is not None

        self.use_sbert = use_sbert and SBERT_AVAILABLE
        self.allow_model_download = allow_model_download
        self.sbert_threshold = sbert_threshold

        self.max_skill_words = max_skill_words
        self.max_skill_chars = max_skill_chars

        self.sbert_model = None
        self.category_embeddings = None
        self.category_names = list(self.CATEGORY_DESCRIPTIONS.keys())

        current_dir = os.path.dirname(os.path.abspath(__file__))

        self.model_path = (
            model_path
            if model_path is not None
            else os.path.join(current_dir, "..", "models", "sbert_model")
        )

        self.skill_to_category = self._build_skill_category_map()
        self.all_known_hard_skills = self._build_all_known_hard_skills()
        self.all_known_soft_skills = normalize_keyword_list(list(self.SOFT_SKILLS))
        self.model_usage = self._new_model_usage()
        self.semantic_cache: dict[str, dict] = {}
        self._current_sections: dict = {}

    # ================================================================
    # 🤖 Shared models + per-request telemetry
    # ================================================================

    def _load_shared_spacy_model(self):
        """
        Load spaCy only through ModelRegistry.

        The project has used both get_spacy() and get_spacy_model()
        naming conventions, so this adapter supports either without
        creating a second model instance inside the extractor.
        """
        method = None

        for method_name in ("get_spacy", "get_spacy_model"):
            candidate = getattr(ModelRegistry, method_name, None)
            if callable(candidate):
                method = candidate
                break

        if method is None:
            print(
                "⚠️ Shared spaCy unavailable: ModelRegistry has no "
                "get_spacy/get_spacy_model method."
            )
            return None

        attempts = [
            ((), {}),
            ((), {"model_name": "en_core_web_sm"}),
            (("en_core_web_sm",), {}),
        ]
        last_type_error = None

        for args, kwargs in attempts:
            try:
                return method(*args, **kwargs)
            except TypeError as exc:
                last_type_error = exc
                continue
            except Exception as exc:
                print(f"⚠️ Shared spaCy unavailable: {exc}")
                return None

        if last_type_error is not None:
            print(
                "⚠️ Shared spaCy unavailable: unsupported ModelRegistry "
                f"signature ({last_type_error})."
            )

        return None

    def _new_model_usage(self) -> dict:
        """Create telemetry for one resume analysis request."""
        return {
            "spacy": {
                "available": bool(self.use_spacy and self.nlp is not None),
                "documents_processed": 0,
                "candidates_generated": 0,
            },
            "sbert": {
                "available": bool(self._sbert_ready()),
                # Unknown-skill classification calls only.
                "encode_calls": 0,
                "items_encoded": 0,
                "classified_items": [],
                "unclassified_items": [],
                "cache_hits": 0,
                "cache_misses": 0,
                # Category embeddings are initialization work, tracked
                # separately so they do not pretend to classify a resume.
                "category_embedding_builds": 0,
                "category_items_encoded": 0,
            },
            "rules": {
                "dictionary_matches": 0,
                "dictionary_match_items": [],
                "raw_dictionary_matches": [],
                "accepted_dictionary_matches": [],
                "rejected_before_semantic_analysis": [],
                "expanded_compound_skills": [],
                "regex_sector_detected": False,
            },
        }

    def _reset_model_usage(self) -> None:
        self.model_usage = self._new_model_usage()
        # Cache lives for one resume request only. This prevents duplicate
        # encoding during post-reconciliation refresh without retaining
        # user phrases across requests.
        self.semantic_cache = {}
        self._current_sections = {}

    def _run_spacy(self, text: str):
        """Run shared spaCy and count actual documents processed."""
        if not self.use_spacy or self.nlp is None or not str(text).strip():
            return None

        self.model_usage["spacy"]["documents_processed"] += 1
        return self.nlp(str(text))

    def _record_sbert_classification(
            self,
            *,
            skill: str,
            category: str,
            similarity: float,
    ) -> None:
        record = {
            "skill": skill,
            "category": category,
            "similarity": round(float(similarity), 4),
        }

        existing = self.model_usage["sbert"]["classified_items"]
        key = (
            normalize_keyword(skill),
            category,
        )

        if not any(
            (
                normalize_keyword(item.get("skill", "")),
                item.get("category"),
            ) == key
            for item in existing
        ):
            existing.append(record)

    def _get_effective_mode_name(self) -> str:
        """
        Report models that actually processed this resume.

        "available" means loaded and ready.
        "mode" means it was invoked on request data.
        """
        used = ["rules"]

        if self.model_usage["spacy"]["documents_processed"] > 0:
            used.append("spacy")

        if self.model_usage["sbert"]["encode_calls"] > 0:
            used.append("sbert")

        return "+".join(used)

    def _canonical_soft_skill(self, value: str) -> str | None:
        normalized = normalize_keyword(
            self._clean_skill(value)
        )

        if not normalized:
            return None

        direct = self.SOFT_SKILL_CANONICAL.get(normalized)
        if direct:
            return direct

        for known in sorted(
            self.all_known_soft_skills,
            key=len,
            reverse=True,
        ):
            known_normalized = normalize_keyword(known)

            if normalized == known_normalized:
                return self.SOFT_SKILL_CANONICAL.get(
                    known_normalized,
                    str(known).title(),
                )

            suffix = f" {known_normalized}"
            if not normalized.endswith(suffix):
                continue

            prefix = normalized[:-len(suffix)].strip()
            prefix_words = set(prefix.split())

            if prefix_words and prefix_words <= self.SOFT_PREFIX_MODIFIERS:
                return self.SOFT_SKILL_CANONICAL.get(
                    known_normalized,
                    str(known).title(),
                )

        return None

    def _partition_domain_context(
        self,
        values: list[str],
    ) -> tuple[list[str], list[str]]:
        """Separate exact standalone industry labels from real skills."""
        domains: list[str] = []
        skills: list[str] = []

        for value in values:
            cleaned = self._clean_skill(value)
            key = normalize_keyword(cleaned)
            canonical = self.DOMAIN_CONTEXT_ALIASES.get(key)

            if canonical:
                domains.append(canonical)
            else:
                skills.append(cleaned)

        return (
            self._unique_skills(domains),
            self._unique_skills(skills),
        )

    def _partition_skills(
        self,
        values: list[str],
    ) -> tuple[list[str], list[str]]:
        soft: list[str] = []
        hard: list[str] = []

        for value in values:
            cleaned = self._clean_skill(value)
            normalized = normalize_keyword(cleaned)

            if (
                not normalized
                or normalized in self.INVALID_STANDALONE_SKILLS
            ):
                continue

            canonical_soft = self._canonical_soft_skill(cleaned)
            if canonical_soft:
                soft.append(canonical_soft)
            else:
                hard.append(cleaned)

        return (
            self._unique_skills(soft),
            self._semantic_dedupe_skills(
                self._unique_skills(hard)
            ),
        )

    def _semantic_dedupe_skills(
        self,
        values: list[str],
    ) -> list[str]:
        """Prefer a specific compound skill over its generic subset."""
        unique = []
        seen = set()

        for value in values:
            key = normalize_keyword(value)
            if key and key not in seen:
                seen.add(key)
                unique.append(value)

        def tokens(value: str) -> set[str]:
            normalized = normalize_keyword(value)
            normalized = re.sub(r"[&/\-]+", " ", normalized)
            return {
                token
                for token in normalized.split()
                if token not in {"and", "of", "the"}
            }

        token_sets = [tokens(value) for value in unique]
        remove: set[int] = set()

        for index, _current in enumerate(unique):
            current_tokens = token_sets[index]
            if not current_tokens:
                continue

            for other_index, other in enumerate(unique):
                if index == other_index:
                    continue

                other_tokens = token_sets[other_index]
                if not current_tokens < other_tokens:
                    continue

                if (
                    len(other_tokens) >= len(current_tokens) + 1
                    and (
                        len(current_tokens) <= 2
                        or any(char in other for char in "&/")
                    )
                ):
                    remove.add(index)
                    break

        return [
            value
            for index, value in enumerate(unique)
            if index not in remove
        ]

    def _extract_explicit_named_tools(
        self,
        sections: dict,
    ) -> list[str]:
        """Extract named tools directly from evidence text.

        This is dictionary/regex based and does not require the tool to have
        already appeared in the general hard-skill ontology.
        """
        text = self._sections_text(sections)
        patterns = [
            (r"(?i)\bcaseware\b", "Caseware"),
            (r"(?i)\btaxprep\b", "Taxprep"),
            (r"(?i)\b(?:microsoft|ms)\s+access\b", "Microsoft Access"),
            (
                r"(?i)\b(?:experience\s+using|proficient\s+in|skilled\s+in|"
                r"(?:tools?|software|databases?)\s*[:\-])"
                r"[^.\n;]{0,80}\baccess\b",
                "Microsoft Access",
            ),
            (r"(?i)\bquickbooks\b", "QuickBooks"),
            (r"(?i)\b(?:microsoft\s+|ms\s+)?excel\b", "Microsoft Excel"),
            (r"(?i)\b(?:microsoft\s+|ms\s+)?powerpoint\b", "Microsoft PowerPoint"),
            (r"(?i)\bkeynote(?:\s+for\s+mac)?\b", "Apple Keynote"),
        ]
        return self._unique_skills([
            canonical
            for pattern, canonical in patterns
            if re.search(pattern, text)
        ])

    def _extract_tool_skills(self, hard_skills: list[str]) -> list[str]:
        """
        Return real software/platform tools for the pipeline summary.
        Domain skills such as Advertising are intentionally excluded.
        """
        canonical_tools = {
            "microsoft word": "Microsoft Word",
            "word": "Microsoft Word",
            "microsoft excel": "Microsoft Excel",
            "excel": "Microsoft Excel",
            "microsoft powerpoint": "Microsoft PowerPoint",
            "powerpoint": "Microsoft PowerPoint",
            "microsoft access": "Microsoft Access",
            "access": "Microsoft Access",
            "microsoft project": "Microsoft Project",
            "microsoft outlook": "Microsoft Outlook",
            "outlook": "Microsoft Outlook",
            "act!": "ACT!",
            "windows": "Windows",
            "power bi": "Power BI",
            "tableau": "Tableau",
            "google analytics": "Google Analytics",
            "google ads": "Google Ads",
            "facebook ads": "Facebook Ads",
            "instagram ads": "Instagram Ads",
            "hubspot": "HubSpot",
            "salesforce": "Salesforce",
            "mailchimp": "Mailchimp",
            "wordpress": "WordPress",
            "canva": "Canva",
            "figma": "Figma",
            "quickbooks": "QuickBooks",
            "caseware": "Caseware",
            "taxprep": "Taxprep",
            "keynote": "Apple Keynote",
            "keynote for mac": "Apple Keynote",
            "apple keynote": "Apple Keynote",
            "xero": "Xero",
            "sap": "SAP",
            "oracle": "Oracle",
            "jira": "Jira",
            "asana": "Asana",
            "trello": "Trello",
        }

        result = []
        seen = set()

        for skill in hard_skills:
            canonical = canonical_tools.get(normalize_keyword(skill))
            if canonical and canonical.lower() not in seen:
                seen.add(canonical.lower())
                result.append(canonical)

        return result


    def _sections_text(self, sections: dict) -> str:
        values = []
        for section in (sections or {}).values():
            if isinstance(section, dict):
                content = section.get("content", "")
            else:
                content = section
            if content:
                values.append(str(content))
        return "\n".join(values)

    def _expand_compound_skill(
        self,
        skill: str,
    ) -> list[str]:
        """
        Canonicalize common software aliases and expand compact compound
        skill phrases before semantic classification.
        """
        value = str(skill or "").strip()

        if not value:
            return []

        normalized = normalize_keyword(
            value
        )

        if normalized == "aipowered automation":
            dedicated = self._get_section_content(
                self._current_sections,
                "skills",
            )
            if re.search(
                r"(?i)(?<!\w)AIpowered[ \t]+automation(?!\w)",
                dedicated,
            ):
                return ["AI-powered automation"]

        exact_aliases = {
            "ms word": "Microsoft Word",
            "microsoft word": "Microsoft Word",
            "excel": "Microsoft Excel",
            "ms excel": "Microsoft Excel",
            "microsoft excel": "Microsoft Excel",
            "powerpoint": "Microsoft PowerPoint",
            "ms powerpoint": "Microsoft PowerPoint",
            "microsoft powerpoint":
                "Microsoft PowerPoint",
            "salesforce.com": "Salesforce",
            "salesforce": "Salesforce",
            "team leadership": "Leadership",
            "presentations": "Presentation Skills",
            "client presentations":
                "Presentation Skills",
            "postgres": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "speech to text": "Speech-to-Text",
            "speech-to-text": "Speech-to-Text",
            "prompt engineering": "Prompt Engineering",
            "kpis": "KPIs",
        }

        if normalized in exact_aliases:
            return [
                exact_aliases[
                    normalized
                ]
            ]

        compound_aliases = {
            "conflict resolution/problem solving": [
                "Conflict Resolution",
                "Problem Solving",
            ],
            "conflict resolution and problem solving": [
                "Conflict Resolution",
                "Problem Solving",
            ],
        }

        if normalized in compound_aliases:
            return list(
                compound_aliases[
                    normalized
                ]
            )

        if (
            "/" not in value
            or not normalized.startswith(
                "microsoft "
            )
        ):
            return [value]

        prefix_removed = re.sub(
            r"^\s*microsoft\s+",
            "",
            value,
            flags=re.IGNORECASE,
        )

        parts = [
            part.strip()
            for part in prefix_removed.split("/")
            if part.strip()
        ]

        canonical = {
            "word": "Microsoft Word",
            "excel": "Microsoft Excel",
            "powerpoint":
                "Microsoft PowerPoint",
            "access": "Microsoft Access",
            "project": "Microsoft Project",
            "outlook": "Microsoft Outlook",
        }

        expanded = [
            canonical.get(
                normalize_keyword(part),
                f"Microsoft {part}",
            )
            for part in parts
        ]

        return expanded or [value]

    def _filter_before_semantic_analysis(
            self,
            skills: list[str],
            sections: dict | None = None,
    ) -> tuple[list[str], list[dict]]:
        """
        Remove known ambiguous/label artifacts before SBERT sees them.
        This is intentionally conservative and evidence-aware.
        """
        context = self._sections_text(sections or self._current_sections)
        context_lower = context.lower()
        explicit_context = self._explicit_context_skills(sections or self._current_sections)

        go_is_explicit = bool(re.search(
            r"(?:programming\s+languages?|languages?)\s*[:\-][^\n]*\bgo\b"
            r"|\bgolang\b|\bgo\s+(?:programming|developer|engineer)\b"
            r"|\bwritten\s+in\s+go\b",
            context_lower,
            flags=re.IGNORECASE,
        ))
        r_is_explicit = bool(re.search(
            r"\b(?:r\s+programming|programming\s+in\s+r|using\s+r|"
            r"r\s+language|rstudio|tidyverse|ggplot2)\b",
            context_lower,
            flags=re.IGNORECASE,
        ))
        automation_is_explicit = bool(re.search(
            r"\b(?:workflow|test|testing|industrial|process|marketing|"
            r"robotic\s+process|rpa|selenium|plc)\s+automation\b"
            r"|\bautomation\s+(?:engineer|engineering|testing|tool|tools|"
            r"platform|framework)\b",
            context_lower,
            flags=re.IGNORECASE,
        ))

        accepted: list[str] = []
        rejected: list[dict] = []
        expanded_records: list[dict] = []

        for raw_skill in skills:
            expanded = self._expand_compound_skill(raw_skill)

            if len(expanded) > 1 or (
                expanded and normalize_keyword(expanded[0])
                != normalize_keyword(raw_skill)
            ):
                expanded_records.append({
                    "source": raw_skill,
                    "expanded": expanded,
                })

            for skill in expanded:
                key = normalize_keyword(skill)
                reason = None

                if key == "technology":
                    reason = "section_label_not_skill"
                elif key == "go" and not go_is_explicit:
                    reason = "ambiguous_token_without_programming_context"
                elif key == "r" and not r_is_explicit:
                    reason = "ambiguous_R_token_without_programming_context"
                elif key == "automation" and not automation_is_explicit:
                    reason = "ambiguous_or_company_name_without_skill_context"
                elif key in {"provider", "kpi", "kpis"} and key not in explicit_context:
                    reason = "metric_or_context_token_not_standalone_skill"
                elif key in self.GENERIC_CONTEXT_SKILLS and key not in explicit_context:
                    reason = "generic_term_without_explicit_skill_category"
                elif re.search(r"(?i)\b(?:aipowered|machinelearning|deeplearning)\b", skill):
                    reason = "malformed_concatenated_skill"
                elif skill.rstrip().endswith("&"):
                    reason = "incomplete_skill_fragment"
                elif key in {
                    "other internal systems",
                    "internal systems",
                }:
                    reason = "vague_tool_family_without_named_technology"

                if reason:
                    rejected.append({
                        "skill": skill,
                        "reason": reason,
                    })
                    continue

                accepted.append(skill)

        self.model_usage["rules"]["expanded_compound_skills"] = (
            expanded_records
        )
        return self._unique_skills(accepted), rejected

    def _explicit_context_skills(self, sections: dict) -> set[str]:
        content = self._get_section_content(sections, "skills")
        supported: set[str] = set()
        for raw_line in content.splitlines():
            if ":" not in raw_line:
                continue
            label, values = raw_line.split(":", 1)
            label_key = normalize_keyword(label.replace("&", "and"))
            if label_key not in self.EXPLICIT_CONTEXT_LABELS:
                continue
            for value in self._split_skill_items(values):
                supported.add(normalize_keyword(value))
        return supported

    def _extract_visual_template_skill_phrases(self, text: str) -> list[str]:
        output = []
        for pattern, canonical, _kind in self.VISUAL_TEMPLATE_SKILL_PATTERNS:
            if pattern.search(str(text or "")):
                output.append(canonical)
        return output

    def _is_location_or_education_fragment(self, skill: str, sections: dict) -> bool:
        key = normalize_keyword(skill)
        if key in self.LOCATION_ABBREVIATIONS:
            return True
        if re.fullmatch(r"[a-z]{2}", key) and key not in {"go", "r"}:
            return True

        education = self._get_section_content(sections, "education")
        skills_text = self._get_section_content(sections, "skills")
        in_education = bool(re.search(rf"(?i)(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", education))
        in_skills = bool(re.search(rf"(?i)(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", skills_text))
        if in_education and not in_skills:
            if re.search(r"(?i)\b(?:university|college|school|bachelor|master|degree)\b", education):
                return True
        return False

    def _polish_skill_result(self, result: dict, sections: dict) -> dict:
        if not isinstance(result, dict):
            return result

        skill_section = self._get_section_content(sections, "skills")
        explicit = self._extract_visual_template_skill_phrases(skill_section)
        all_skills = self._unique_skills(list(result.get("all_skills", []) or []) + explicit)
        all_skills = [
            skill for skill in all_skills
            if not self._is_location_or_education_fragment(skill, sections)
        ]

        soft_keys = {
            normalize_keyword(canonical)
            for _pattern, canonical, kind in self.VISUAL_TEMPLATE_SKILL_PATTERNS
            if kind == "soft"
        }
        soft = self._unique_skills(
            list(result.get("soft_skills", []) or [])
            + [skill for skill in all_skills if normalize_keyword(skill) in soft_keys]
        )
        soft_norm = {normalize_keyword(skill) for skill in soft}
        hard = self._unique_skills(
            [skill for skill in all_skills if normalize_keyword(skill) not in soft_norm]
        )

        result["all_skills"] = self._unique_skills(hard + soft)
        result["hard_skills"] = hard
        result["soft_skills"] = soft
        result["total_count"] = len(result["all_skills"])
        result["hard_count"] = len(hard)
        result["soft_count"] = len(soft)
        result["categorized_skills"] = self._categorize_hard_skills(hard, semantic=False)
        result["top_technologies"] = self._extract_tool_skills(hard)

        preserved = [
            item for item in result.get("recommendations", []) or []
            if item.get("type") not in {"quantity", "hard_skills", "soft_skills"}
        ]
        regenerated = self._generate_recommendations(
            result["all_skills"], hard, soft,
            result["categorized_skills"],
            result.get("sector_match"),
        )
        result["recommendations"] = self._unique_recommendation_dicts(preserved + regenerated)
        return result

    # ================================================================
    # 📂 MAIN
    # ================================================================

    def extract(
            self,
            parsed_sections: dict,
            detected_sector: str | None = None,
            job_description: str | None = None,
    ) -> dict:
        # Telemetry is per resume/request, not cumulative across users.
        self._reset_model_usage()
        sections = self._get_sections(parsed_sections)
        self._current_sections = sections

        all_skills = []

        skills_content = self._get_section_content(sections, "skills")

        if skills_content:
            text = self._prepare_skills_block(skills_content)

            all_skills.extend(self._extract_skills_from_text(text))
            all_skills.extend(
                self._extract_visual_template_skill_phrases(text)
            )

            if self.use_spacy and self.nlp is not None:
                all_skills.extend(self._extract_skill_phrases_with_spacy(text))

        for section_name in ["summary", "experience", "projects"]:
            content = self._get_section_content(sections, section_name)

            if not content:
                continue

            text = self.cleaner.clean(content)
            all_skills.extend(
                self._scan_text_for_known_skills(
                    text,
                    include_soft=(
                        section_name
                        in {"summary", "experience"}
                    ),
                )
            )

        raw_unique_skills = self._unique_skills(all_skills)

        raw_rule_matches = [
            skill
            for skill in raw_unique_skills
            if (
                normalize_keyword(skill) in self.all_known_hard_skills
                or normalize_keyword(skill) in self.all_known_soft_skills
            )
        ]
        self.model_usage["rules"]["raw_dictionary_matches"] = (
            list(raw_rule_matches)
        )

        unique_skills, rejected_before_semantic = (
            self._filter_before_semantic_analysis(
                raw_unique_skills,
                sections,
            )
        )

        known_rule_matches = [
            skill
            for skill in unique_skills
            if (
                normalize_keyword(skill) in self.all_known_hard_skills
                or normalize_keyword(skill) in self.all_known_soft_skills
            )
        ]
        self.model_usage["rules"]["dictionary_matches"] = len(
            known_rule_matches
        )
        self.model_usage["rules"]["dictionary_match_items"] = (
            list(known_rule_matches)
        )
        self.model_usage["rules"]["accepted_dictionary_matches"] = (
            list(known_rule_matches)
        )
        self.model_usage["rules"][
            "rejected_before_semantic_analysis"
        ] = rejected_before_semantic

        if not unique_skills:
            return self._empty_result()

        domain_context, skill_candidates = (
            self._partition_domain_context(
                unique_skills
            )
        )
        soft_skills, hard_skills = self._partition_skills(
            skill_candidates
        )
        explicit_tools = self._extract_explicit_named_tools(sections)
        hard_skills = self._unique_skills(
            hard_skills + explicit_tools
        )
        unique_skills = self._unique_skills(
            hard_skills + soft_skills
        )

        # Initial extraction is rule-only. SBERT runs once after
        # EvidenceReconciler removes false positives and adds evidence.
        categorized = self._categorize_hard_skills(
            hard_skills,
            semantic=False,
        )

        sector_evidence = []

        if not detected_sector:
            detected_sector, sector_evidence = (
                self._detect_sector_from_sections(
                    sections,
                    unique_skills + domain_context,
                )
            )
        else:
            sector_evidence = [
                "sector_provided_by_pipeline"
            ]

        sector_match = self._build_sector_match(
            hard_skills=hard_skills,
            categorized=categorized,
            sector_name=detected_sector,
            job_description=job_description,
        )

        recommendations = self._generate_recommendations(
            unique_skills,
            hard_skills,
            soft_skills,
            categorized,
            sector_match,
        )

        result = {
            "all_skills": unique_skills,
            "hard_skills": hard_skills,
            "soft_skills": soft_skills,
            "domain_context": domain_context,
            "categorized_skills": categorized,
            "total_count": len(unique_skills),
            "hard_count": len(hard_skills),
            "soft_count": len(soft_skills),
            "domain_count": len(domain_context),
            "detected_sector": detected_sector,
            "sector_evidence": sector_evidence,
            "sector_match": sector_match,
            "recommendations": recommendations,
            "top_technologies": self._extract_tool_skills(hard_skills),
            "mode": self._get_effective_mode_name(),
            "model_usage": self.model_usage,
        }
        return self._polish_skill_result(result, sections)

    def _detect_sector_from_sections(
            self,
            sections: dict,
            unique_skills: list[str],
    ) -> tuple[str | None, list[str]]:
        def section_content(name: str) -> str:
            section = sections.get(name, {})

            if isinstance(section, dict):
                return str(
                    section.get("content", "") or ""
                )

            return str(section or "")

        experience_text = section_content("experience")
        education_text = section_content("education")
        skills_text = section_content("skills")
        summary_text = section_content("summary")

        high_priority_text = (
                experience_text
                + "\n"
                + education_text
        )

        accounting_patterns = [
            r"\baccounting\b",
            r"\bbookkeep(?:er|ing)\b",
            r"\bgeneral ledger\b",
            r"\baccounts? payable\b",
            r"\baccounts? receivable\b",
            r"\bA/P\b",
            r"\bA/R\b",
            r"\btax(?:ation|prep| return)\b",
            r"\bquickbooks\b",
            r"\bcaseware\b",
        ]
        accounting_evidence = []
        for pattern in accounting_patterns:
            match = re.search(pattern, high_priority_text, re.IGNORECASE)
            if match:
                accounting_evidence.append(match.group(0))
        accounting_key = next(
            (candidate for candidate in (
                "finance_accounting", "accounting", "finance"
            ) if candidate in self.keywords_db),
            None,
        )
        if accounting_key and len(accounting_evidence) >= 4:
            self.model_usage["rules"]["regex_sector_detected"] = True
            return accounting_key, list(dict.fromkeys(accounting_evidence))

        marketing_patterns = [
            r"\bmarketing\b",
            r"\badvertis(?:ing|ement|e)\b",
            r"\bmarket research\b",
            r"\bmarketing plan\b",
            r"\bmarketing strategist\b",
            r"\bpromotions?\b",
            r"\bcampaigns?\b",
        ]

        marketing_evidence = []

        for pattern in marketing_patterns:
            match = re.search(
                pattern,
                high_priority_text,
                re.IGNORECASE,
            )

            if match:
                marketing_evidence.append(
                    match.group(0)
                )

        marketing_key = None

        for candidate in (
                "marketing_sales",
                "marketing",
                "sales_marketing",
        ):
            if candidate in self.keywords_db:
                marketing_key = candidate
                break

        # أكثر من دليل Marketing ضمن التعليم/الخبرة
        # أقوى من كلمات عامة مثل management وplanning.
        if (
                marketing_key
                and len(marketing_evidence) >= 2
        ):
            self.model_usage["rules"]["regex_sector_detected"] = True
            return (
                marketing_key,
                list(dict.fromkeys(
                    marketing_evidence
                )),
            )

        # fallback عام، مع وزن أكبر للتعليم والخبرة.
        weighted_context = "\n".join([
            experience_text,
            experience_text,
            experience_text,
            education_text,
            education_text,
            skills_text,
            summary_text,
            " ".join(unique_skills),
        ])

        sectors = auto_detect_sector(
            weighted_context
        )

        if not sectors:
            return None, []

        return sectors[0][0], [
            "weighted_section_detection"
        ]

    # ================================================================
    # 🔍 Extraction
    # ================================================================
    def _prepare_skills_block(self, text: str) -> str:
        """
        تنظيف قسم المهارات مع الحفاظ على فواصل العناوين الداخلية.

        يحل مشكلة:
        SQL Frameworks: React
        Django Cloud & DevOps: AWS
        """

        if not text:
            return ""

        text = re.sub(r"(?<=\w)-[ \t]*\n[ \t]*(?=\w)", "-", str(text))
        text = re.sub(
            r"(?i)(?<!\w)AIpowered(?=[ \t]+automation\b)",
            "AI-powered",
            text,
        )
        text = self.cleaner.clean(text)

        labels = sorted(self.SKILL_SECTION_LABELS, key=len, reverse=True)
        labels_pattern = "|".join(re.escape(label) for label in labels)

        # أضف line break قبل labels إذا كانت ملتصقة بعد skill
        text = re.sub(
            rf"\s+({labels_pattern})\s*:",
            r"\n\1:",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(r"\n+", "\n", text)

        return text.strip()

    def _looks_like_label_artifact(self, value: str) -> bool:
        """
        يمنع artifacts من spaCy مثل:
        SQL Frameworks
        Django Cloud
        CI/CD Data
        Excel Soft Skills
        """

        if not value:
            return False

        normalized = normalize_keyword(value)

        if normalized in self.all_known_hard_skills:
            return False

        if normalized in self.all_known_soft_skills:
            return False

        words = set(normalized.split())

        return bool(words & self.SKILL_LABEL_WORDS)

    def _extract_skills_from_text(self, text: str) -> list[str]:
        """
        استخراج المهارات من قسم Skills.

        يقبل:
        Languages: Python, JavaScript, C++
        - Docker
        React, Node.js, AWS

        ويرفض الجمل الطويلة مثل:
        Developed microservices using Python and Docker.
        """

        if not text:
            return []

        skills = []

        for raw_line in text.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            line = re.sub(r"^[•\-\*►▪]\s*", "", line).strip()

            if not line:
                continue

            if ":" in line:
                label, value = line.split(":", 1)

                if len(label.split()) <= 4 and value.strip():
                    skills.extend(self._split_skill_items(value))
                    continue

            if any(separator in line for separator in [",", ";", "|", "•"]):
                skills.extend(self._split_skill_items(line))
                continue

            if self._is_likely_skill_phrase(line):
                skills.append(self._clean_skill(line))

        return [
            skill for skill in skills
            if self._is_likely_skill_phrase(skill)
        ]

    def _split_skill_items(self, text: str) -> list[str]:
        items = self.SKILL_SPLIT_PATTERN.split(text)

        result = []

        for item in items:
            skill = self._clean_skill(item)

            if self._is_likely_skill_phrase(skill):
                result.append(skill)

        return result

    def _scan_text_for_known_skills(
        self,
        text: str,
        include_soft: bool = False,
    ) -> list[str]:
        """
        Scan narrative sections for known domain skills and, when requested,
        evidence-backed soft skills including common verb inflections.
        """
        if not text:
            return []

        found_hard, _ = find_keywords_in_text(
            text,
            self.all_known_hard_skills,
        )

        if not include_soft:
            return found_hard

        found_soft, _ = find_keywords_in_text(
            text,
            self.all_known_soft_skills,
        )

        evidence_patterns = {
            "Teamwork": (
                r"\bteam\s*work\b"
                r"|\bcollaborat(?:e|es|ed|ing|ion)\b"
            ),
            "Communication": (
                r"\bcommunications?\b"
                r"|\bcommunicat(?:e|es|ed|ing)\b"
            ),
            "Negotiation": (
                r"\bnegotiat(?:e|es|ed|ing|ion|ions)\b"
            ),
            "Mentoring": (
                r"\bmentor(?:s|ed|ing)?\b"
            ),
            "Coaching": (
                r"\bcoach(?:es|ed|ing)?\b"
            ),
            "Presentation Skills": (
                r"\bpresentation skills?\b|\bclient presentations?\b"
            ),
            "Leadership": (
                r"\bleadership\b"
                r"|\bled\b"
            ),
            "Problem Solving": (
                r"\bproblem[ -]solv(?:e|es|ed|ing)\b"
                r"|\bproblem solving\b"
            ),
            "Conflict Resolution": (
                r"\bconflict resolution\b"
                r"|\bresolved conflicts?\b"
            ),
            "Customer Service": (
                r"\bcustomer service\b"
                r"|\bclient satisfaction\b"
            ),
        }

        for canonical, pattern in (
            evidence_patterns.items()
        ):
            if re.search(
                pattern,
                text,
                re.IGNORECASE,
            ):
                found_soft.append(
                    canonical
                )

        return (
            found_hard
            + found_soft
        )

    def _extract_skill_phrases_with_spacy(self, text: str) -> list[str]:
        """
        spaCy مساعد فقط.
        نستخدمه بحذر على كل سطر لوحده حتى لا يدمج skill مع label السطر التالي.
        """

        if not self.use_spacy or self.nlp is None or not text:
            return []

        candidates = []

        for raw_line in text.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            line = re.sub(r"^[•\-\*►▪]\s*", "", line).strip()

            if not line:
                continue

            # لو السطر label: values، نحلل values فقط
            if ":" in line:
                label, value = line.split(":", 1)

                if len(label.split()) <= 4:
                    line = value.strip()

            # لو السطر قائمة مفصولة بفواصل، rule-based كافي
            if any(separator in line for separator in [",", ";", "|", "•"]):
                continue

            doc = self._run_spacy(line[:300])
            if doc is None:
                continue

            for chunk in doc.noun_chunks:
                phrase = self._clean_skill(chunk.text)

                if not self._is_likely_skill_phrase(phrase):
                    continue

                normalized = normalize_keyword(phrase)

                if (
                        normalized in self.all_known_hard_skills
                        or normalized in self.all_known_soft_skills
                        or self._contains_known_skill(normalized)
                ):
                    candidates.append(phrase)
                    self.model_usage["spacy"]["candidates_generated"] += 1

        return candidates

    def _contains_known_skill(self, phrase: str) -> bool:
        """
        يفيد spaCy:
        لو noun chunk مثل 'cloud deployment with docker'
        نعرف أنه فيه docker.
        """

        words = phrase.split()

        if len(words) > self.max_skill_words:
            return False

        for skill in self.all_known_hard_skills:
            if skill in phrase:
                return True

        for skill in self.all_known_soft_skills:
            if skill in phrase:
                return True

        return False

    def _passes_spacy_filter(self, value: str) -> bool:
        """
        فلتر spaCy لمنع الجمل الفعلية من التحول إلى skill.
        مثال مرفوض:
        Developed microservices using Python
        """

        if not self.use_spacy or self.nlp is None:
            return True

        normalized = normalize_keyword(value)

        if normalized in self.all_known_hard_skills:
            return True

        if normalized in self.all_known_soft_skills:
            return True

        doc = self._run_spacy(value)
        if doc is None:
            return True

        # لو فيه فعل واضح، غالباً جملة وليس skill
        if any(token.pos_ in {"VERB", "AUX"} for token in doc):
            return False

        # لو كل الكلمات stopwords أو punctuation، مرفوض
        meaningful_tokens = [
            token for token in doc
            if not token.is_stop and not token.is_punct and token.text.strip()
        ]

        if not meaningful_tokens:
            return False

        return True

    # ================================================================
    # 🧠 Validation
    # ================================================================

    def _clean_skill(self, value: str) -> str:
        value = str(value).strip()

        value = re.sub(r"^[•\-\*►▪/\\]+", "", value)
        value = re.sub(r"[\.\,\;\:\(\)\[\]\{\}]+$", "", value)
        value = re.sub(r"\s+", " ", value)

        return value.strip()

    def _is_likely_skill_phrase(self, value: str) -> bool:
        if not value:
            return False

        value = self._clean_skill(value)

        if not value:
            return False

        lower = normalize_keyword(value)
        words = lower.split()

        if lower in self.INVALID_STANDALONE_SKILLS:
            return False

        if value.rstrip().endswith("&"):
            return False

        if re.search(r"(?i)\b(?:aipowered|machinelearning|deeplearning)\b", value):
            return False

        if len(value) > self.max_skill_chars:
            return False

        if len(words) > self.max_skill_words:
            return False

        if "@" in lower or "http" in lower or "www." in lower:
            return False

        if re.search(r"\b(19|20)\d{2}\b", lower):
            return False

        if re.search(r"\d{3,}", lower) and lower not in {"iso 9001", "iso 27001"}:
            return False

        # Do not accept ordinary achievement sentences merely because
        # they contain a skill-like noun. Explicit compound skill
        # patterns remain valid even when one token can also be a verb,
        # for example "Creative Design".
        explicit_compound_skills = {
            normalize_keyword(canonical)
            for _, canonical, _ in self.VISUAL_TEMPLATE_SKILL_PATTERNS
        }
        if any(verb in words for verb in self.BAD_SKILL_VERBS):
            if (
                lower not in self.all_known_hard_skills
                and lower not in self.all_known_soft_skills
                and lower not in explicit_compound_skills
            ):
                return False

        # جملة عادية تنتهي بنقطة غالباً ليست skill
        if value.endswith(".") and len(words) > 2:
            return False

        # لازم تحتوي حرف
        if not re.search(r"[a-zA-Z+#.]", lower):
            return False

        if self._looks_like_label_artifact(value):
            return False

        if not self._passes_spacy_filter(value):
            return False
        return True

    def _unique_skills(self, skills: list[str]) -> list[str]:
        seen = set()
        result = []

        for skill in skills:
            skill = self._clean_skill(skill)

            if not self._is_likely_skill_phrase(skill):
                continue

            key = normalize_keyword(skill)

            if key not in seen:
                seen.add(key)
                result.append(skill)

        return result

    # ================================================================
    # 🗂️ Categorization
    # ================================================================

    def _categorize_hard_skills(
            self,
            hard_skills: list[str],
            *,
            semantic: bool = True,
    ) -> dict:
        if (
            semantic
            and self.use_sbert
            and SBERT_AVAILABLE
            and self._load_sbert_if_available()
        ):
            return self._categorize_sbert(hard_skills)

        return self._categorize_rule_based(hard_skills)

    def _categorize_rule_based(self, skills: list[str]) -> dict:
        categorized = {category: [] for category in self.CATEGORY_DESCRIPTIONS}
        categorized["other"] = []

        for skill in skills:

            key = normalize_keyword(skill)
            category = self.skill_to_category.get(key)

            if category:
                categorized[category].append(skill)
            else:
                categorized["other"].append(skill)

        return {
            category: sorted(set(values), key=lambda x: x.lower())
            for category, values in categorized.items()
            if values
        }

    def _categorize_sbert(self, skills: list[str]) -> dict:
        categorized = {
            category: []
            for category in self.CATEGORY_DESCRIPTIONS
        }
        categorized["other"] = []

        pending: list[str] = []

        for skill in skills:
            key = normalize_keyword(skill)
            category = self.skill_to_category.get(key)

            if category:
                categorized[category].append(skill)
                continue

            cached = self.semantic_cache.get(key)
            if cached is not None:
                self.model_usage["sbert"]["cache_hits"] += 1

                if cached.get("accepted"):
                    cached_category = cached["category"]
                    categorized[cached_category].append(skill)
                    self._record_sbert_classification(
                        skill=skill,
                        category=cached_category,
                        similarity=float(cached["similarity"]),
                    )
                else:
                    categorized["other"].append(skill)
                continue

            self.model_usage["sbert"]["cache_misses"] += 1
            pending.append(skill)

        if pending and self._sbert_ready() and util is not None:
            self.model_usage["sbert"]["encode_calls"] += 1
            self.model_usage["sbert"]["items_encoded"] += len(pending)

            skill_embeddings = self.sbert_model.encode(
                pending,
                convert_to_tensor=True,
            )

            cosine_scores = util.cos_sim(
                skill_embeddings,
                self.category_embeddings,
            )

            for index, skill in enumerate(pending):
                best_idx = cosine_scores[index].argmax().item()
                best_score = float(
                    cosine_scores[index][best_idx].item()
                )
                best_category = self.category_names[best_idx]
                key = normalize_keyword(skill)
                accepted = best_score >= self.sbert_threshold

                self.semantic_cache[key] = {
                    "accepted": accepted,
                    "category": best_category,
                    "similarity": round(best_score, 4),
                }

                if accepted:
                    categorized[best_category].append(skill)
                    self._record_sbert_classification(
                        skill=skill,
                        category=best_category,
                        similarity=best_score,
                    )
                else:
                    categorized["other"].append(skill)
                    record = {
                        "skill": skill,
                        "best_category": best_category,
                        "similarity": round(best_score, 4),
                    }
                    existing = self.model_usage["sbert"][
                        "unclassified_items"
                    ]
                    if not any(
                        normalize_keyword(item.get("skill", "")) == key
                        for item in existing
                    ):
                        existing.append(record)
        else:
            categorized["other"].extend(pending)

        return {
            category: sorted(
                set(values),
                key=lambda x: x.lower(),
            )
            for category, values in categorized.items()
            if values
        }

    def _build_skill_category_map(self) -> dict:
        mapping = {}

        for category, skills in self.HARD_SKILL_CATEGORIES.items():
            for skill in skills:
                key = normalize_keyword(skill)
                mapping[key] = category

        return mapping

    def _build_all_known_hard_skills(self) -> list[str]:
        skills = []

        for sector_data in self.keywords_db.values():
            skills.extend(sector_data.get("hard_skills", []))

        for category_skills in self.HARD_SKILL_CATEGORIES.values():
            skills.extend(category_skills)

        return normalize_keyword_list(skills)

    # ================================================================
    # 🤖 Optional SBERT
    # ================================================================

    def _sbert_ready(self) -> bool:
        return (
                self.sbert_model is not None
                and self.category_embeddings is not None
                and bool(self.category_names)
                and util is not None
        )

    def _load_sbert_if_available(self) -> bool:
        """
        Lazy loading باستخدام ModelRegistry:
        - SBERT يتحمل مرة واحدة على مستوى الـprocess
        - كل extractor يبني embeddings الخاصة فيه فقط
        - لا يعمل download إلا إذا allow_model_download=True
        """

        if self._sbert_ready():
            return True

        if not SBERT_AVAILABLE or util is None:
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
            self.model_usage["sbert"]["available"] = (
                self.sbert_model is not None
            )

        except Exception as exc:
            print(f"⚠️ Skills SBERT unavailable: {exc}")
            self.sbert_model = None
            return False

        try:
            category_descriptions = [
                f"{category.replace('_', ' ')}: {description}"
                for category, description
                in self.CATEGORY_DESCRIPTIONS.items()
            ]

            self.category_names = list(
                self.CATEGORY_DESCRIPTIONS.keys()
            )

            self.model_usage["sbert"]["category_embedding_builds"] += 1
            self.model_usage["sbert"]["category_items_encoded"] += len(
                category_descriptions
            )
            self.category_embeddings = self.sbert_model.encode(
                category_descriptions,
                convert_to_tensor=True,
            )
            self.model_usage["sbert"]["available"] = True

            return True

        except Exception as exc:
            print(f"⚠️ Failed to build skill embeddings: {exc}")

            self.category_embeddings = None
            self.category_names = []

            return False

    # ================================================================
    # 🎯 Sector Match
    # ================================================================

    def _sector_category_key(self, sector_name: str | None) -> str | None:
        """Map keyword-database sector keys to HARD_SKILL_CATEGORIES keys."""
        if not sector_name:
            return None

        category_map = {
            "marketing": "marketing_sales",
            "marketing_sales": "marketing_sales",
            "sales_marketing": "marketing_sales",
            "finance": "finance_accounting",
            "accounting": "finance_accounting",
            "finance_accounting": "finance_accounting",
            "project_manager": "project_management",
            "project_management": "project_management",
        }

        mapped = category_map.get(sector_name, sector_name)
        return mapped if mapped in self.CATEGORY_DESCRIPTIONS else None

    def _sector_label(self, sector_name: str | None) -> str:
        sector_data = (
            self.keywords_db.get(sector_name, {})
            if sector_name
            else {}
        )
        return (
            sector_data.get("label")
            or sector_name
            or "Unknown"
        )

    def _sector_evidence_from_categories(
            self,
            categorized: dict,
            sector_name: str | None,
    ) -> list[str]:
        category_key = self._sector_category_key(sector_name)
        if not category_key:
            return []

        values = categorized.get(category_key, []) or []
        return self._unique_skills(list(values))

    def _build_sector_match(
            self,
            *,
            hard_skills: list[str],
            categorized: dict,
            sector_name: str | None,
            job_description: str | None = None,
    ) -> dict | None:
        """
        Without a job description, report sector evidence only.
        A missing-skill percentage is meaningful only against a real job description.
        """
        if not sector_name:
            return None

        evidence_skills = self._sector_evidence_from_categories(
            categorized,
            sector_name,
        )

        if not str(job_description or "").strip():
            return {
                "sector": self._sector_label(sector_name),
                "sector_key": sector_name,
                "status": "sector_detected_job_description_required",
                "evidence_skills": evidence_skills,
                "evidence_count": len(evidence_skills),
                "matching": evidence_skills,
                "missing": [],
                "coverage": None,
                "relevance": None,
                "density": None,
                "match_rate": None,
            }

        return self._match_with_job_description(
            hard_skills=hard_skills,
            sector_name=sector_name,
            job_description=str(job_description),
            sector_evidence=evidence_skills,
        )

    def _match_with_job_description(
            self,
            *,
            hard_skills: list[str],
            sector_name: str,
            job_description: str,
            sector_evidence: list[str] | None = None,
    ) -> dict:
        """Compare resume skills only with skills explicitly evidenced in the JD."""
        required, _ = find_keywords_in_text(
            job_description,
            self.all_known_hard_skills,
        )
        required = self._unique_skills(required)

        resume_by_key = {
            normalize_keyword(skill): skill
            for skill in self._unique_skills(hard_skills)
        }

        matching = []
        missing = []

        for required_skill in required:
            key = normalize_keyword(required_skill)
            if key in resume_by_key:
                matching.append(resume_by_key[key])
            else:
                missing.append(required_skill)

        if not required:
            return {
                "sector": self._sector_label(sector_name),
                "sector_key": sector_name,
                "status": "job_description_no_recognized_skills",
                "evidence_skills": sector_evidence or [],
                "evidence_count": len(sector_evidence or []),
                "job_required_skills": [],
                "matching": [],
                "missing": [],
                "coverage": None,
                "relevance": None,
                "density": None,
                "match_rate": None,
            }

        required_count = len(required)
        matching_count = len(matching)
        resume_count = len(resume_by_key)

        coverage = matching_count / required_count
        relevance = matching_count / resume_count if resume_count else 0.0
        density = min(1.0, matching_count / 10)

        match_rate = round(
            (
                0.70 * coverage
                + 0.20 * relevance
                + 0.10 * density
            ) * 100,
            1,
        )

        return {
            "sector": self._sector_label(sector_name),
            "sector_key": sector_name,
            "status": "job_description_compared",
            "evidence_skills": sector_evidence or [],
            "evidence_count": len(sector_evidence or []),
            "job_required_skills": required,
            "matching": matching,
            "missing": missing,
            "coverage": round(coverage * 100, 1),
            "relevance": round(relevance * 100, 1),
            "density": round(density * 100, 1),
            "match_rate": match_rate,
        }

    def _match_with_sector(self, hard_skills: list[str], sector_name: str) -> dict:
        if not sector_name or sector_name not in self.keywords_db:
            return {
                "match_rate": 0,
                "sector": sector_name,
                "matching": [],
                "missing": [],
            }

        sector_data = self.keywords_db[sector_name]
        sector_label = sector_data.get("label", sector_name)

        required_hard = normalize_keyword_list(
            sector_data.get("hard_skills", [])
        )

        top_required = required_hard[:30]
        skills_text = " ".join(hard_skills)

        matching, missing = find_keywords_in_text(skills_text, top_required)

        current_count = len(hard_skills)
        required_count = len(top_required)
        matching_count = len(matching)

        coverage = matching_count / required_count if required_count else 0
        relevance = matching_count / current_count if current_count else 0
        density = min(1.0, matching_count / 10)

        match_rate = round(
            (
                0.50 * coverage
                + 0.35 * relevance
                + 0.15 * density
            ) * 100,
            1,
        )

        return {
            "sector": sector_label,
            "sector_key": sector_name,
            "matching": matching[:15],
            "missing": missing[:10],
            "coverage": round(coverage * 100, 1),
            "relevance": round(relevance * 100, 1),
            "density": round(density * 100, 1),
            "match_rate": match_rate,
        }

    # ================================================================
    # 💡 Recommendations
    # ================================================================

    def _generate_recommendations(
        self,
        all_skills: list[str],
        hard_skills: list[str],
        soft_skills: list[str],
        categorized: dict,
        sector_match: dict | None,
    ) -> list[dict]:
        recommendations = []

        total = len(all_skills)
        hard_count = len(hard_skills)
        soft_count = len(soft_skills)

        if total < 5:
            recommendations.append({
                "severity": "high",
                "type": "quantity",
                "message": f"عدد المهارات قليل ({total}). أضف 8-15 مهارة.",
            })
        elif total < 10:
            recommendations.append({
                "severity": "medium",
                "type": "quantity",
                "message": f"عدد المهارات مقبول ({total}). الأفضل 10-15 مهارة.",
            })
        else:
            recommendations.append({
                "severity": "good",
                "type": "quantity",
                "message": f"عدد المهارات ممتاز ({total}).",
            })

        if hard_count < 5:
            recommendations.append({
                "severity": "medium",
                "type": "hard_skills",
                "message": "أضف مهارات تقنية/عملية أكثر مرتبطة بالوظيفة.",
            })

        if soft_count < 2:
            recommendations.append({
                "severity": "medium",
                "type": "soft_skills",
                "message": "أضف 2-4 مهارات شخصية مثل Communication, Teamwork, Leadership.",
            })

        if sector_match:
            status = sector_match.get("status")
            sector_label = sector_match.get("sector", "Unknown")
            evidence = sector_match.get("evidence_skills", []) or []

            if status == "sector_detected_job_description_required":
                if evidence:
                    recommendations.append({
                        "severity": "good",
                        "type": "sector_detected",
                        "message": (
                            f"تم اكتشاف قطاع {sector_label} "
                            "مع أدلة مهارية واضحة."
                        ),
                        "evidence": evidence,
                    })

            elif status == "job_description_no_recognized_skills":
                recommendations.append({
                    "severity": "info",
                    "type": "job_description_skills_unresolved",
                    "message": (
                        "تم توفير وصف وظيفي، لكن لم يتم التعرف على "
                        "متطلبات مهارية واضحة داخله."
                    ),
                })

            elif status == "job_description_compared":
                rate = float(sector_match.get("match_rate", 0) or 0)
                missing = sector_match.get("missing", []) or []

                if rate < 30:
                    recommendations.append({
                        "severity": "high",
                        "type": "job_skill_match",
                        "message": (
                            f"تطابق مهارات الوصف الوظيفي منخفض ({rate}%). "
                            + (
                                f"المهارات غير المثبتة: {', '.join(missing[:5])}."
                                if missing
                                else ""
                            )
                        ).strip(),
                    })
                elif rate < 60:
                    recommendations.append({
                        "severity": "medium",
                        "type": "job_skill_match",
                        "message": (
                            f"تطابق مهارات الوصف الوظيفي متوسط ({rate}%)."
                        ),
                    })
                else:
                    recommendations.append({
                        "severity": "good",
                        "type": "job_skill_match",
                        "message": (
                            f"تطابق مهارات الوصف الوظيفي جيد ({rate}%)."
                        ),
                    })

        if "other" in categorized and len(categorized["other"]) >= 5:
            recommendations.append({
                "severity": "info",
                "type": "uncategorized_skills",
                "message": "بعض المهارات عامة أو لم يتم ربطها بتصنيف متخصص.",
                "skills": categorized["other"],
            })

        return recommendations

    def refresh_after_reconciliation(
            self,
            result: dict,
            job_description: str | None = None,
    ) -> dict:
        """
        Rebuild counts, categories, sector evidence, recommendations,
        and score after EvidenceReconciler adds/removes skills.
        """
        if not isinstance(result, dict):
            return result

        all_skills = self._unique_skills(
            list(result.get("all_skills", []) or [])
        )
        soft_skills = self._unique_skills(
            list(result.get("soft_skills", []) or [])
        )

        soft_keys = {
            normalize_keyword(skill)
            for skill in soft_skills
        }

        hard_candidates = list(result.get("hard_skills", []) or [])
        hard_candidates.extend(
            skill
            for skill in all_skills
            if normalize_keyword(skill) not in soft_keys
        )
        hard_skills = self._unique_skills(hard_candidates)

        # Filter after reconciliation and before the single semantic pass.
        hard_skills, rejected_before_semantic = (
            self._filter_before_semantic_analysis(
                hard_skills,
                self._current_sections,
            )
        )
        existing_rejected = self.model_usage["rules"].get(
            "rejected_before_semantic_analysis",
            [],
        )
        rejected_by_key = {
            (
                normalize_keyword(item.get("skill", "")),
                item.get("reason"),
            ): item
            for item in existing_rejected + rejected_before_semantic
        }
        self.model_usage["rules"][
            "rejected_before_semantic_analysis"
        ] = list(rejected_by_key.values())

        # Final union must not reintroduce filtered false positives.
        all_skills = self._unique_skills(
            hard_skills + soft_skills
        )

        result["all_skills"] = all_skills
        result["hard_skills"] = hard_skills
        result["soft_skills"] = soft_skills
        result["total_count"] = len(all_skills)
        result["hard_count"] = len(hard_skills)
        result["soft_count"] = len(soft_skills)

        categorized = self._categorize_hard_skills(
            hard_skills,
            semantic=True,
        )
        result["categorized_skills"] = categorized

        sector_key = result.get("detected_sector")
        sector_evidence = self._sector_evidence_from_categories(
            categorized,
            sector_key,
        )
        result["sector_evidence"] = sector_evidence

        result["sector_match"] = self._build_sector_match(
            hard_skills=hard_skills,
            categorized=categorized,
            sector_name=sector_key,
            job_description=job_description,
        )

        # Preserve reconciliation-specific recommendations, then regenerate
        # quantity/sector/categorization recommendations from current data.
        preserved = [
            item
            for item in result.get("recommendations", []) or []
            if item.get("type") not in {
                "quantity",
                "sector",
                "sector_detected",
                "job_skill_match",
                "job_description_skills_unresolved",
                "categorization",
                "uncategorized_skills",
                "hard_skills",
                "soft_skills",
            }
        ]

        refreshed = self._generate_recommendations(
            all_skills=all_skills,
            hard_skills=hard_skills,
            soft_skills=soft_skills,
            categorized=categorized,
            sector_match=result["sector_match"],
        )
        result["recommendations"] = self._unique_recommendation_dicts(
            preserved + refreshed
        )

        result["skills_score"] = self._calculate_refreshed_skills_score(
            result,
            sector_evidence,
        )
        result["skills_quality"] = {
            "status": "ok" if result["skills_score"] >= 65 else "degraded",
            "score": result["skills_score"],
            "warnings": [],
        }
        result["top_technologies"] = self._extract_tool_skills(hard_skills)
        result["mode"] = self._get_effective_mode_name()
        result["model_usage"] = self.model_usage

        return self._polish_skill_result(
            result,
            self._current_sections,
        )

    def _unique_recommendation_dicts(self, values: list[dict]) -> list[dict]:
        seen = set()
        result = []

        for item in values:
            if not isinstance(item, dict):
                continue

            key = (
                str(item.get("type", "")),
                str(item.get("message", "")),
            )
            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    def _calculate_refreshed_skills_score(
            self,
            result: dict,
            sector_evidence: list[str],
    ) -> int:
        total_count = int(
            result.get("total_count", 0) or 0
        )
        hard_count = int(
            result.get("hard_count", 0) or 0
        )
        soft_count = int(
            result.get("soft_count", 0) or 0
        )

        categorized = result.get(
            "categorized_skills",
            {},
        )

        specialized_count = sum(
            len(values)
            for key, values in categorized.items()
            if key != "other"
            and isinstance(values, list)
        )

        # 30 نقطة لكمية المهارات.
        quantity_score = min(
            30,
            round(total_count / 15 * 30),
        )

        # 25 نقطة لوجود hard skills.
        hard_score = min(
            25,
            round(hard_count / 10 * 25),
        )

        # 15 نقطة للمهارات الشخصية.
        soft_score = min(
            15,
            round(soft_count / 4 * 15),
        )

        # 20 نقطة للمهارات المصنفة.
        categorization_score = min(
            20,
            round(specialized_count / 8 * 20),
        )

        # 10 نقاط لأدلة القطاع.
        sector_score = min(
            10,
            round(len(sector_evidence) / 4 * 10),
        )

        score = (
                quantity_score
                + hard_score
                + soft_score
                + categorization_score
                + sector_score
        )

        uncategorized_count = len(
            categorized.get("other", []) or []
        )
        categorized_count = max(
            0,
            hard_count - uncategorized_count,
        )

        result["score_breakdown"] = {
            "quantity": quantity_score,
            "hard_skill_presence": hard_score,
            "soft_skill_evidence": soft_score,
            "categorization": categorization_score,
            "sector_evidence": sector_score,
            "raw_total": score,
            "score_cap": 95,
        }
        result["categorized_count"] = categorized_count
        result["uncategorized_count"] = uncategorized_count
        result["categorized_ratio"] = round(
            categorized_count / hard_count,
            4,
        ) if hard_count else 0.0

        return max(
            0,
            min(95, score),
        )

    # ================================================================
    # 🖨️ Report
    # ================================================================

    def print_report(self, result: dict) -> None:
        print("\n" + "=" * 70)
        print("                    🔧 SKILLS ANALYSIS REPORT")
        print("=" * 70)

        print(
            f"\n📊 Total: {result.get('total_count', 0)} | "
            f"Hard: {result.get('hard_count', 0)} | "
            f"Soft: {result.get('soft_count', 0)}"
        )

        mode = result.get("mode", "rule")

        mode_label = {
            "rules": "📋 Rules",
            "rules+spacy": "📋 Rules + spaCy",
            "rules+sbert": "🤖 Rules + SBERT",
            "rules+spacy+sbert": "🤖 Rules + spaCy + SBERT",
            # Backward compatibility with older exported results.
            "rule": "📋 Rule-Based",
            "rule+spacy": "📋 Rule-Based + spaCy",
            "sbert": "🤖 SBERT",
            "sbert+spacy": "🤖 SBERT + spaCy",
        }.get(mode, mode)

        print(f"   Mode: {mode_label}")

        usage = result.get("model_usage", {})
        if usage:
            spacy_usage = usage.get("spacy", {})
            sbert_usage = usage.get("sbert", {})
            rule_usage = usage.get("rules", {})

            print(
                "   Model usage: "
                f"spaCy docs={spacy_usage.get('documents_processed', 0)}, "
                f"SBERT calls={sbert_usage.get('encode_calls', 0)}, "
                f"SBERT items={sbert_usage.get('items_encoded', 0)}, "
                f"dictionary matches={rule_usage.get('dictionary_matches', 0)}"
            )

        if result.get("detected_sector"):
            print(f"   Sector: {result['detected_sector']}")

        categorized = result.get("categorized_skills", {})

        if categorized:
            print("\n📂 Hard Skills:")
            for category, skills in categorized.items():
                print(f"   [{category}] ({len(skills)}): {', '.join(skills)}")

        soft = result.get("soft_skills", [])

        if soft:
            print(f"\n🤝 Soft Skills ({len(soft)}): {', '.join(soft)}")

        sector_match = result.get("sector_match")

        if sector_match:
            status = sector_match.get("status")
            rate = sector_match.get("match_rate")

            if rate is None:
                print(f"\n🎯 Sector: {sector_match.get('sector', 'Unknown')}")
                print(f"   Status: {status}")
            else:
                print(f"\n🎯 Job Skill Match: {rate}%")
                print(
                    f"   Coverage: {sector_match.get('coverage', 0)}% | "
                    f"Relevance: {sector_match.get('relevance', 0)}% | "
                    f"Density: {sector_match.get('density', 0)}%"
                )

            if sector_match.get("matching"):
                print(f"   Matching: {', '.join(sector_match['matching'][:10])}")

            if sector_match.get("missing"):
                print(f"   Missing: {', '.join(sector_match['missing'][:10])}")

        recommendations = result.get("recommendations", [])

        if recommendations:
            print("\n💡 Recommendations:")

            icons = {
                "high": "❌",
                "medium": "⚠️",
                "good": "✅",
            }

            for recommendation in recommendations:
                icon = icons.get(recommendation.get("severity"), "•")
                print(f"   {icon} {recommendation.get('message')}")

        print("=" * 70)

    # ================================================================
    # 🧱 Helpers
    # ================================================================

    def _get_sections(self, parsed_sections: dict) -> dict:
        if not parsed_sections:
            return {}

        if "sections" in parsed_sections and isinstance(parsed_sections["sections"], dict):
            return parsed_sections["sections"]

        return parsed_sections

    def _get_section_content(self, sections: dict, section_name: str) -> str:
        if section_name not in sections:
            return ""

        section = sections[section_name]

        if isinstance(section, dict):
            return section.get("content", "") or ""

        if isinstance(section, str):
            return section

        return ""

    def _empty_result(self) -> dict:
        return {
            "all_skills": [],
            "hard_skills": [],
            "soft_skills": [],
            "domain_context": [],
            "categorized_skills": {},
            "total_count": 0,
            "hard_count": 0,
            "soft_count": 0,
            "domain_count": 0,
            "detected_sector": None,
            "sector_evidence": [],
            "sector_match": None,
            "recommendations": [
                {
                    "severity": "high",
                    "type": "empty",
                    "message": "لم يتم العثور على مهارات واضحة.",
                }
            ],
            "top_technologies": [],
            "mode": self._get_effective_mode_name(),
            "model_usage": self.model_usage,
        }

    def _get_mode_name(self) -> str:
        """Backward-compatible alias for effective, actually-used mode."""
        return self._get_effective_mode_name()



# =====================================================================
# 🧪 اختبار
# =====================================================================

if __name__ == "__main__":
    extractor = SkillsExtractor(
        use_spacy=True,
        use_sbert=False,
        allow_model_download=False,
    )

    mock_sections = {
        "sections": {
            "skills": {
                "content": """
                Languages: Python, JavaScript, TypeScript, SQL
                Frameworks: React, Node.js, Django
                Cloud & DevOps: AWS, Docker, Kubernetes, CI/CD
                Data: Power BI, Tableau, Excel
                Soft Skills: Leadership, Communication, Problem Solving
                """
            },
            "summary": {
                "content": "Senior Software Engineer with experience in microservices and REST API."
            },
            "experience": {
                "content": """
                Developed microservices using Python and Docker on AWS.
                Improved deployment reliability with CI/CD pipelines.
                """
            },
            "projects": {
                "content": "Built analytics dashboard using Power BI and PostgreSQL."
            },
        }
    }

    result = extractor.extract(mock_sections)
    extractor.print_report(result)

    print(f"\n✅ spaCy Available: {SPACY_AVAILABLE}")
    print(f"✅ SBERT Available: {SBERT_AVAILABLE}")
    print(f"✅ Mode: {result.get('mode')}")
