# =====================================================================
# 📊 بنك الكلمات المفتاحية الشامل - جميع القطاعات (نسخة نهائية - lowercase)
# =====================================================================
# يحتوي على: 21 قطاع رئيسي + 17 قطاع في ALL_CATEGORIES
# إجمالي الكلمات المفتاحية: 1500+ كلمة
# جميع الكلمات بحروف صغيرة لتسهيل المطابقة
# =====================================================================
import json
import re
from pathlib import Path

ALL_KEYWORDS_DATABASE = {

    # ================================================================
    # 1. تطوير البرمجيات - Software Development
    # ================================================================
    "software_development": {
        "label": "Software Development",
        "job_titles": [
            "software engineer", "software developer", "full stack developer",
            "backend developer", "frontend developer", "web developer",
            "programmer", "devops engineer", "application developer",
        ],
        "hard_skills": [
            # لغات برمجة
            "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
            "ruby", "php", "swift", "kotlin", "scala", "dart", "matlab", "r",
            "sql", "pl/sql", "t-sql", "nosql", "graphql", "html", "css",

            # frameworks & libraries
            "react", "angular", "vue.js", "next.js", "node.js", "express.js",
            "django", "flask", "fastapi", "spring boot", "laravel", "ruby on rails",
            "asp.net", ".net core", "entity framework", "hibernate", "jquery",
            "bootstrap", "tailwind css", "sass", "redux", "mobx", "nuxt.js",
            "svelte", "material ui", "vuex", "pinia", "context api",
            "webpack", "vite", "babel", "eslint",

            # قواعد بيانات
            "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
            "oracle database", "sql server", "dynamodb", "cassandra", "firebase",
            "sqlite", "hive", "realm",

            # devops & cloud
            "aws", "azure", "google cloud", "gcp", "docker", "kubernetes",
            "jenkins", "gitlab ci", "github actions", "terraform", "ansible",
            "linux", "unix", "bash", "shell scripting", "nginx", "apache",
            "rabbitmq", "kafka", "helm", "argocd", "prometheus", "grafana",
            "elk stack", "ci/cd", "infrastructure as code", "monitoring",

            # أدوات
            "git", "github", "gitlab", "bitbucket", "jira", "confluence",
            "vs code", "intellij", "eclipse", "postman", "swagger",
            "jest", "cypress", "testing library",

            # مفاهيم
            "rest api", "soap", "microservices", "mvc", "oop",
            "agile", "scrum", "kanban", "tdd", "ci/cd",
            "design patterns", "system design", "data structures", "algorithms",
            "responsive design", "mobile first", "cross-browser",
            "pwa", "seo", "web performance", "accessibility",

            # أمان
            "oauth", "jwt", "ssl/tls", "penetration testing", "owasp",
            "authentication", "sanctum", "firebase auth", "zero trust",
        ],
        "soft_skills": [
            "problem solving", "critical thinking", "analytical skills",
            "teamwork", "communication", "time management",
            "attention to detail", "adaptability", "creativity",
            "project management", "leadership", "mentoring",
            "debugging", "code review", "documentation",
            "self-learning", "team collaboration", "user empathy",
            "reliability", "continuous learning",
        ],
        "action_verbs": [
            "developed", "built", "designed", "implemented", "optimized",
            "deployed", "integrated", "maintained", "architected", "refactored",
            "automated", "configured", "monitored", "delivered", "enhanced",
            "created", "managed", "reduced", "improved",
        ],
        "other_keywords": [
            "full stack", "frontend", "backend", "api development",
            "web application", "mobile application", "responsive design",
            "cross-browser compatibility", "performance optimization",
            "scalability", "code quality", "best practices",
            "open source", "version control", "deployment",
            "end-to-end solution", "zero downtime", "crash-free",
            "software engineering", "web development", "app development",
        ],
        "achievements_keywords": [
            "reduced load time", "improved performance", "increased throughput",
            "optimized queries", "reduced errors", "scaled to", "handled requests",
            "improved ux", "reduced bounce rate", "increased conversion",
            "improved load time", "increased engagement", "reduced costs",
            "improved uptime", "zero downtime", "increased reliability",
            "reduced deployment time", "published on app store", "published on google play",
            "achieved rating", "downloads", "active users",
        ],
    },

    # ================================================================
    # 2. تطوير الواجهات الأمامية - Frontend Developer
    # ================================================================
    "frontend_developer": {
        "label": "Frontend Developer",
        "hard_skills": [
            "html", "css", "javascript", "typescript", "react", "vue.js",
            "angular", "next.js", "nuxt.js", "svelte", "jquery",
            "tailwind css", "bootstrap", "sass", "scss", "material ui",
            "redux", "vuex", "pinia", "context api",
            "webpack", "vite", "babel", "eslint",
            "jest", "cypress", "testing library",
            "responsive design", "mobile first", "cross-browser",
            "rest api", "graphql", "axios", "fetch api",
            "git", "github", "figma", "adobe xd",
            "seo", "web performance", "accessibility", "pwa",
        ],
        "soft_skills": [
            "creativity", "attention to detail", "communication",
            "user empathy", "problem solving", "team collaboration",
            "time management", "adaptability",
        ],
        "action_verbs": [
            "designed", "developed", "built", "implemented", "optimized",
            "delivered", "created", "enhanced", "maintained", "integrated",
        ],
        "achievements_keywords": [
            "improved ux", "reduced bounce rate", "increased conversion",
            "optimized performance", "improved load time", "increased engagement",
        ],
    },

    # ================================================================
    # 3. تطوير الواجهات الخلفية - Backend Developer
    # ================================================================
    "backend_developer": {
        "label": "Backend Developer",
        "hard_skills": [
            "python", "php", "java", "node.js", "c#", "ruby", "go", "rust",
            "laravel", "django", "flask", "fastapi", "spring boot", "express",
            "mysql", "postgresql", "mongodb", "redis", "sqlite", "oracle",
            "rest api", "graphql", "microservices", "docker", "kubernetes",
            "aws", "azure", "gcp", "linux", "git", "github", "ci/cd",
            "jenkins", "nginx", "apache", "rabbitmq", "kafka",
            "jwt", "oauth", "authentication", "sanctum", "firebase",
        ],
        "soft_skills": [
            "problem solving", "team collaboration", "communication",
            "analytical thinking", "attention to detail", "time management",
            "self-learning", "adaptability",
        ],
        "action_verbs": [
            "developed", "built", "designed", "implemented", "optimized",
            "deployed", "integrated", "maintained", "architected", "refactored",
        ],
        "achievements_keywords": [
            "reduced load time", "improved performance", "increased throughput",
            "optimized queries", "reduced errors", "scaled to", "handled requests",
        ],
    },

    # ================================================================
    # 4. تطوير تطبيقات الجوال - Mobile Developer
    # ================================================================
    "mobile_developer": {
        "label": "Mobile Developer",
        "hard_skills": [
            "flutter", "react native", "swift", "kotlin", "dart",
            "ios", "android", "xcode", "android studio",
            "firebase", "rest api", "graphql",
            "redux", "bloc", "getx", "provider",
            "sqlite", "hive", "realm",
            "push notifications", "google maps", "payment gateway",
            "app store", "google play", "testflight",
            "git", "github", "ci/cd",
        ],
        "soft_skills": [
            "problem solving", "attention to detail", "communication",
            "creativity", "team collaboration", "time management",
        ],
        "action_verbs": [
            "developed", "built", "published", "designed", "implemented",
            "optimized", "maintained", "delivered", "integrated",
        ],
        "achievements_keywords": [
            "published on app store", "published on google play",
            "achieved rating", "downloads", "active users", "crash-free",
        ],
    },

    # ================================================================
    # 5. DevOps
    # ================================================================
    "devops_engineer": {
        "label": "DevOps Engineer",
        "hard_skills": [
            "docker", "kubernetes", "jenkins", "gitlab ci", "github actions",
            "terraform", "ansible", "helm", "argocd",
            "aws", "azure", "gcp", "linux", "bash",
            "nginx", "apache", "prometheus", "grafana", "elk stack",
            "python", "go", "shell scripting",
            "git", "github", "bitbucket",
            "ci/cd", "infrastructure as code", "monitoring",
        ],
        "soft_skills": [
            "problem solving", "analytical thinking", "communication",
            "team collaboration", "attention to detail", "reliability",
        ],
        "action_verbs": [
            "automated", "deployed", "configured", "monitored", "maintained",
            "optimized", "implemented", "built", "managed", "reduced",
        ],
        "achievements_keywords": [
            "reduced deployment time", "improved uptime", "automated",
            "reduced costs", "zero downtime", "increased reliability",
        ],
    },

    # ================================================================
    # 6. علم البيانات - Data Science / AI
    # ================================================================
    "data_science": {
        "label": "Data Science & AI",
        "job_titles": [
            "data scientist", "data analyst", "machine learning engineer",
            "ai engineer", "data engineer", "business intelligence analyst",
            "nlp engineer", "computer vision engineer",
        ],
        "hard_skills": [
                "python", "r", "sql", "matlab", "julia",
            "pandas", "numpy", "scipy", "scikit-learn",
            "tensorflow", "pytorch", "keras", "hugging face",
            "machine learning", "deep learning", "nlp", "computer vision",
            "statistical analysis", "data visualization",
            "tableau", "power bi", "matplotlib", "seaborn", "plotly",
            "big data", "spark", "hadoop", "hive", "kafka",
            "aws sagemaker", "google ai", "azure ml",
            "a/b testing", "feature engineering", "model deployment",
            "jupyter", "git", "docker", "excel",
            "data mining", "predictive analytics", "statistics",
            "etl", "data pipeline", "data warehouse",
            "bert", "gpt", "transformer", "yolo", "opencv",
        ],
        "soft_skills": [
            "analytical thinking", "problem solving", "communication",
            "curiosity", "attention to detail", "critical thinking",
            "storytelling with data", "team collaboration",
            "research skills", "continuous learning",
        ],
        "action_verbs": [
            "analyzed", "developed", "built", "trained", "optimized",
            "predicted", "visualized", "implemented", "deployed", "researched",
            "modeled", "extracted", "transformed", "automated",
        ],
        "other_keywords": [
            "data analysis", "visualization", "statistics",
            "reporting", "dashboard", "insights", "big data",
            "data-driven decision making", "predictive modeling",
            "data mining", "business intelligence",
        ],
        "achievements_keywords": [
            "improved accuracy", "reduced error rate", "predicted",
            "increased revenue", "saved costs", "discovered insights",
            "improved model performance", "automated pipeline"
        ],
    },

    # ================================================================
    # 7. الأمن السيبراني - Cybersecurity
    # ================================================================
    "cybersecurity": {
        "label": "Cybersecurity",
        "job_titles": [
            "cybersecurity engineer", "security analyst", "penetration tester",
            "ethical hacker", "security architect", "information security officer",
            "soc analyst", "security consultant",
        ],
        "hard_skills": [
            "penetration testing", "ethical hacking", "vulnerability assessment",
            "siem", "soc", "incident response", "forensics",
            "firewalls", "ids/ips", "vpn", "zero trust",
            "kali linux", "metasploit", "burp suite", "wireshark", "nmap",
            "owasp", "cve", "cvss", "iso 27001", "nist",
            "python", "bash", "powershell",
            "cloud security", "aws security", "azure security",
            "compliance", "risk assessment", "gdpr", "hipaa",
            "network security", "encryption", "cybersecurity",
            "splunk", "crowdstrike", "palo alto", "fortinet",
        ],
        "soft_skills": [
            "analytical thinking", "attention to detail", "problem solving",
            "communication", "integrity", "continuous learning",
            "incident management", "threat hunting",
        ],
        "action_verbs": [
            "secured", "identified", "mitigated", "detected", "investigated",
            "implemented", "assessed", "monitored", "responded", "hardened",
            "patched", "audited", "encrypted", "analyzed",
        ],
        "other_keywords": [
            "security operations", "threat intelligence", "vulnerability management",
            "security assessment", "compliance audit", "risk management",
            "security framework", "incident management", "disaster recovery",
        ],
        "achievements_keywords": [
            "reduced vulnerabilities", "detected threats", "prevented breaches",
            "improved security posture", "zero incidents", "compliance achieved",
            "reduced response time", "passed audit",
        ],
    },
# ============================================================
    # 💼 الأعمال والإدارة - Business & Management
    # ============================================================
    "project_manager": {
        "label": "Project Manager",
        "hard_skills": [
            "Project Management", "Agile", "Scrum", "Kanban", "Waterfall",
            "PMP", "Prince2", "PMI", "Risk Management",
            "Microsoft Project", "Jira", "Asana", "Trello", "Monday.com",
            "Budget Management", "Resource Planning", "Stakeholder Management",
            "MS Office", "Excel", "PowerPoint", "Visio",
            "ERP", "SAP", "Business Analysis",
            "Change Management", "Quality Management", "KPIs",
        ],
        "soft_skills": [
            "Leadership", "Communication", "Team Management", "Problem Solving",
            "Decision Making", "Negotiation", "Organizational Skills",
            "Time Management", "Conflict Resolution", "Interpersonal Skills",
            "Adaptability", "Strategic Thinking", "Scheduling",
        ],
        "action_verbs": [
            "Led", "Managed", "Coordinated", "Delivered", "Planned",
            "Executed", "Monitored", "Facilitated", "Organized", "Oversaw",
        ],
        "achievements_keywords": [
            "delivered on time", "under budget", "increased efficiency",
            "reduced costs", "improved team performance", "completed successfully",
        ],
    },

    # ============================================================
    # 🎨 التصميم - Design
    # ============================================================
    "ui_ux_designer": {
        "label": "UI/UX Designer",
        "hard_skills": [
            "Figma", "Adobe XD", "Sketch", "InVision", "Zeplin",
            "Adobe Photoshop", "Adobe Illustrator", "After Effects",
            "Wireframing", "Prototyping", "User Research",
            "Usability Testing", "A/B Testing", "Design Systems",
            "HTML", "CSS", "Responsive Design", "Mobile Design",
            "Typography", "Color Theory", "Information Architecture",
            "User Journey Mapping", "Personas", "Design Thinking",
        ],
        "soft_skills": [
            "Creativity", "Empathy", "Communication", "Attention to Detail",
            "Problem Solving", "Collaboration", "User Empathy",
            "Presentation Skills", "Adaptability", "Critical Thinking",
        ],
        "action_verbs": [
            "Designed", "Created", "Developed", "Prototyped", "Researched",
            "Tested", "Delivered", "Improved", "Collaborated", "Presented",
        ],
        "achievements_keywords": [
            "improved user experience", "increased conversion",
            "reduced friction", "improved task completion",
            "increased satisfaction", "reduced bounce rate",
        ],
    },

    # ================================================================
    # 8. التسويق الرقمي - Digital Marketing
    # ================================================================
    "digital_marketing": {
        "label": "Digital Marketing",
        "hard_skills": [
            "seo", "sem", "sea", "smo", "google ads", "google analytics",
            "google search console", "google tag manager", "bing ads",
            "keyword research", "link building", "on-page seo", "off-page seo", "ppc",
            "facebook ads", "instagram ads", "linkedin ads", "tiktok ads",
            "twitter ads", "pinterest ads", "social media marketing",
            "community management", "influencer marketing",
            "content marketing", "content strategy", "copywriting",
            "blogging", "wordpress", "cms", "hubspot", "marketo",
            "email marketing", "marketing automation", "mailchimp",
            "sendgrid", "activecampaign", "klaviyo",
            "data analysis", "a/b testing", "conversion rate optimization",
            "cro", "kpi", "roi", "web analytics", "looker studio", "ctr", "cpa",
            "e-commerce", "shopify", "magento", "woocommerce",
            "prestashop", "amazon marketing", "ebay",
            "crm", "salesforce", "lead generation", "inbound marketing",
            "canva", "photoshop", "illustrator", "figma",
            "adobe creative suite", "hootsuite", "buffer",
            "campaign management", "brand management", "market research",
            "digital marketing", "branding", "advertising",
        ],
        "soft_skills": [
            "creativity", "communication", "analytical thinking",
            "project management", "team leadership", "strategic planning",
            "problem solving", "adaptability", "time management",
            "storytelling", "brand awareness", "customer focus",
            "team collaboration", "interpersonal skills", "organizational skills",
        ],
        "action_verbs": [
            "launched", "increased", "grew", "managed", "developed",
            "executed", "optimized", "created", "led", "improved",
        ],
        "other_keywords": [
            "b2b", "b2c", "lead generation", "brand strategy",
            "market research", "target audience", "customer journey",
            "digital transformation", "growth hacking", "viral marketing",
            "customer acquisition", "retention", "engagement",
            "campaign management", "budget management",
        ],
        "achievements_keywords": [
            "increased traffic", "improved conversion rate", "reduced bounce rate",
            "grew followers", "increased sales", "roi", "reduced cpa",
            "increased engagement", "improved ctr", "increased conversion",
        ],
    },

"marketing": {
    "label": "Marketing Manager",

    "hard_skills": [
        "Digital Marketing","SEO","SEM","PPC",
        "Google Ads","Social Media Marketing","Content Marketing",
        "Email Marketing","Google Analytics","Facebook Ads","Instagram Ads",
        "CMS","WordPress","HubSpot","Salesforce",
        "Mailchimp","E-commerce","Conversion Rate","A/B Testing",
        "Market Research","Brand Management",
        "Campaign Management","CRM","Lead Generation","Inbound Marketing",
        "Adobe Creative Suite","Canva","Figma",

        # أضفهم هون
        "Marketing Strategy","Marketing Plan Development","Advertising",
        "Sales Management","Promotions","Direct Mail","Website Content",
        "Strategic Partnership Building","Channel Development",
        "Relationship Building","Vendor Relations","ACT!",
    ],

    "soft_skills": [
        "Creativity","Communication","Analytical Thinking","Strategic Thinking",
        "Team Collaboration","Problem Solving","Adaptability","Leadership",
        "Organizational Skills","Interpersonal Skills",
    ],

    "action_verbs": [
        "Launched","Increased","Grew","Managed",
        "Developed","Executed","Optimized","Created",
        "Led","Improved",
    ],

    "achievements_keywords": [
        "increased traffic","improved conversion rate","reduced bounce rate","grew followers",
        "increased sales","ROI","reduced CPA","increased engagement","improved CTR",
    ],
},

    # ================================================================
    # 9. المالية والمحاسبة - Finance & Accounting
    # ================================================================
    "finance_accounting": {
        "label": "Finance & Accounting",
        "hard_skills": [
            "sap", "oracle financials", "quickbooks", "xero", "sage",
            "microsoft dynamics", "netsuite", "freshbooks", "wave", "erp", "oracle",
            "gaap", "ifrs", "account reconciliation", "general ledger",
            "accounts payable", "accounts receivable", "payroll",
            "tax preparation", "tax planning", "auditing",
            "financial statements", "balance sheet", "p&l", "tax compliance",
            "financial analysis", "financial modeling", "forecasting",
            "budgeting", "variance analysis", "cost accounting",
            "excel", "vba", "pivot tables", "vlookup",
            "cost analysis", "financial planning",
            "financial reporting", "sec reporting", "management reporting",
            "cash flow", "internal controls", "sox compliance",
            "risk management", "portfolio management", "investment analysis",
            "mergers & acquisitions", "due diligence", "risk assessment",
            "power bi", "tableau", "cpa", "cma", "cfa",
            "accounting", "bookkeeping", "financial analysis",
        ],
        "soft_skills": [
            "attention to detail", "analytical skills", "integrity",
            "problem solving", "time management", "organization",
            "communication", "confidentiality", "critical thinking",
            "teamwork", "leadership", "ethics", "reliability",
            "organizational skills",
        ],
        "action_verbs": [
            "managed", "analyzed", "prepared", "reconciled", "audited",
            "reviewed", "processed", "reported", "monitored", "improved",
        ],
        "other_keywords": [
            "compliance", "regulatory", "reconciliation", "audit trail",
            "financial planning", "strategic planning", "cost reduction",
            "revenue growth", "profitability", "cash management",
            "treasury", "tax compliance", "year-end close",
        ],
        "achievements_keywords": [
            "reduced costs", "saved", "improved accuracy", "streamlined",
            "increased efficiency", "reduced errors", "saved hours",
        ],
    },

    # ================================================================
    # 10. الموارد البشرية - Human Resources
    # ================================================================
    "human_resources": {
        "label": "Human Resources",
        "hard_skills": [
            "hris", "workday", "sap successfactors", "bamboohr", "sap hr",
            "applicant tracking systems", "ats", "greenhouse", "lever",
            "payroll systems", "adp", "compensation planning",
            "benefits administration", "labor law", "employment law",
            "osha", "eeo", "fmla", "ada compliance",
            "performance management", "talent acquisition",
            "recruitment", "onboarding", "offboarding",
            "training & development", "learning & development",
            "succession planning", "workforce planning",
            "hr policies", "employee relations",
            "excel", "powerpoint", "ms office",
            "human resources", "employee engagement",
        ],
        "soft_skills": [
            "communication", "empathy", "conflict resolution",
            "negotiation", "leadership", "problem solving",
            "discretion", "confidentiality", "interpersonal skills",
            "organizational skills", "cultural awareness",
            "emotional intelligence", "coaching", "mentoring",
            "decision making", "time management", "adaptability",
        ],
        "action_verbs": [
            "recruited", "managed", "developed", "implemented", "trained",
            "coordinated", "evaluated", "resolved", "facilitated", "improved",
        ],
        "other_keywords": [
            "recruitment", "onboarding", "offboarding", "retention",
            "employee relations", "workforce planning", "succession planning",
            "training & development", "diversity & inclusion", "dei",
            "employee engagement", "organizational development",
            "change management", "hr strategy", "talent management",
        ],
        "achievements_keywords": [
            "reduced turnover", "improved retention", "hired",
            "reduced time-to-hire", "improved satisfaction", "trained",
        ],
    },

    # ================================================================
    # 11. الرعاية الصحية - Healthcare / Medical
    # ================================================================
    "healthcare": {
        "label": "Healthcare / Medical",
        "hard_skills": [
            "emr", "ehr", "epic", "cerner", "meditech",
            "patient care", "diagnosis", "treatment planning",
            "medical terminology", "icd-10", "cpt coding",
            "hipaa", "clinical research", "laboratory skills",
            "phlebotomy", "surgical procedures", "life support",
            "acls", "bls", "pals", "first aid",
            "medical imaging", "radiology", "ultrasound",
            "pharmacy", "medication administration",
            "clinical assessment", "surgery", "emergency medicine",
            "internal medicine", "evidence-based medicine",
            "pharmacology", "pathology", "telemedicine",
            "patient education", "electronic health records",
            "healthcare", "medical records", "clinical practice",
            "medicine", "medical research", "preventive care",
            "patient assessment", "hospital",
        ],
        "soft_skills": [
            "compassion", "communication", "patient advocacy",
            "teamwork", "critical thinking", "problem solving",
            "empathy", "attention to detail", "time management",
            "stress management", "active listening",
            "cultural competence", "bedside manner",
            "decision making", "team collaboration", "adaptability",
            "leadership",
        ],
        "action_verbs": [
            "treated", "diagnosed", "performed", "managed", "assessed",
            "conducted", "supervised", "implemented", "researched", "educated",
        ],
        "other_keywords": [
            "quality improvement", "patient safety", "evidence-based",
            "clinical outcomes", "healthcare management",
            "regulatory compliance", "accreditation", "jcaho",
            "infection control", "telemedicine", "home health",
            "long-term care", "acute care", "primary care",
        ],
        "achievements_keywords": [
            "improved patient outcomes", "reduced complications",
            "increased patient satisfaction", "performed procedures",
        ],
    },

    # ================================================================
    # 12. التمريض - Nursing
    # ================================================================
    "nursing": {
        "label": "Nursing",
        "hard_skills": [
            "nursing", "patient monitoring", "medication administration",
            "critical care", "emergency care", "clinical care",
            "health assessment", "patient safety", "care planning",
            "vital signs", "wound care", "iv therapy",
            "catheterization", "patient education",
            "ehr", "emr", "hipaa",
            "acls", "bls", "pals", "first aid",
        ],
        "soft_skills": [
            "compassion", "communication", "empathy",
            "attention to detail", "problem solving", "teamwork",
            "time management", "stress management", "adaptability",
            "patient advocacy", "active listening",
        ],
        "action_verbs": [
            "cared for", "administered", "monitored", "assessed",
            "managed", "educated", "coordinated", "implemented", "documented",
        ],
        "other_keywords": [
            "patient safety", "quality care", "infection control",
            "pain management", "fall prevention", "discharge planning",
        ],
        "achievements_keywords": [
            "improved patient outcomes", "reduced falls",
            "increased patient satisfaction", "reduced medication errors",
        ],
    },

    # ================================================================
    # 13. الصيدلة - Pharmacy
    # ================================================================
    "pharmacy": {
        "label": "Pharmacy",
        "hard_skills": [
            "pharmacy", "pharmacology", "drug dispensing",
            "medication therapy", "prescription review",
            "patient counseling", "clinical pharmacy",
            "pharmaceutical care", "drug interactions",
            "compounding", "inventory management",
            "medication reconciliation", "pharmacokinetics",
            "pharmacodynamics", "therapeutic drug monitoring",
            "hipaa", "fda regulations", "dea regulations",
        ],
        "soft_skills": [
            "attention to detail", "communication", "patient counseling",
            "problem solving", "accuracy", "time management",
            "empathy", "integrity", "teamwork",
        ],
        "action_verbs": [
            "dispensed", "counseled", "reviewed", "managed",
            "compounded", "verified", "monitored", "educated",
        ],
        "other_keywords": [
            "patient safety", "medication management",
            "quality assurance", "regulatory compliance",
            "inventory control", "clinical services",
        ],
        "achievements_keywords": [
            "reduced medication errors", "improved patient adherence",
            "increased efficiency", "reduced costs",
        ],
    },

    # ================================================================
    # 14. الهندسة - Engineering
    # ================================================================
    "engineering": {
        "label": "Engineering",
        "hard_skills": [
            "autocad", "solidworks", "matlab", "simulink",
            "ansys", "catia", "revit", "sketchup", "civil 3d",
            "sap2000", "etabs", "primavera p6",
            "plc programming", "scada", "labview",
            "circuit design", "pcb design", "fpga", "vhdl",
            "verilog", "signal processing", "power systems",
            "electrical systems", "control systems", "electronics",
            "renewable energy", "automation",
            "mechanical design", "thermodynamics", "fluid mechanics",
            "hvac", "finite element analysis", "cfd",
            "manufacturing", "maintenance", "cad", "cam",
            "structural analysis", "geotechnical", "surveying",
            "construction management", "bim", "building codes",
            "concrete design", "steel design", "cost estimation",
            "gis", "infrastructure", "site engineer",
            "lean manufacturing", "six sigma", "5s",
            "process improvement", "quality control", "kaizen",
            "process engineering", "chemical analysis",
            "distillation", "polymer science",
            "osha", "safety standards", "risk assessment",
            "ms project", "project planning",
            "engineering analysis", "quality assurance",
            "electrical maintenance", "instrumentation",
        ],
        "soft_skills": [
            "problem solving", "analytical skills", "critical thinking",
            "project management", "teamwork", "communication",
            "attention to detail", "creativity", "technical writing",
            "leadership", "decision making", "risk assessment",
            "team collaboration", "organizational skills", "time management",
        ],
        "action_verbs": [
            "designed", "managed", "analyzed", "supervised", "implemented",
            "coordinated", "developed", "evaluated", "built", "delivered",
        ],
        "other_keywords": [
            "quality assurance", "regulatory compliance", "safety standards",
            "iso", "technical specifications", "design review",
            "prototyping", "testing", "validation", "optimization",
            "cost reduction", "efficiency", "sustainability",
            "manufacturing", "r&d", "product development",
        ],
        "achievements_keywords": [
            "completed on time", "under budget", "improved structural",
            "reduced costs", "increased efficiency", "safety record",
        ],
    },

    # ================================================================
    # 15. العمارة - Architecture
    # ================================================================
    "architecture": {
        "label": "Architecture",
        "hard_skills": [
            "architecture", "architectural design", "urban planning",
            "autocad", "revit", "sketchup", "3d modeling",
            "building design", "construction drawings",
            "rhino", "grasshopper", "v-ray", "lumion",
            "bim", "building codes", "zoning regulations",
            "sustainable design", "leed", "interior design",
            "landscape architecture", "master planning",
            "site analysis", "space planning",
            "adobe photoshop", "adobe illustrator", "indesign",
        ],
        "soft_skills": [
            "creativity", "attention to detail", "communication",
            "problem solving", "visual communication", "presentation skills",
            "project management", "team collaboration", "client management",
            "time management", "critical thinking",
        ],
        "action_verbs": [
            "designed", "developed", "created", "planned", "coordinated",
            "presented", "managed", "oversaw", "delivered", "conceptualized",
        ],
        "other_keywords": [
            "schematic design", "design development", "construction documents",
            "feasibility studies", "permitting", "code compliance",
            "sustainability", "green building",
        ],
        "achievements_keywords": [
            "designed", "completed projects", "received awards",
            "under budget", "ahead of schedule", "client satisfaction",
        ],
    },

    # ================================================================
    # 16. المبيعات - Sales
    # ================================================================
    "sales": {
        "label": "Sales",
        "hard_skills": [
            "crm", "salesforce", "hubspot crm", "zoho crm",
            "pipeline management", "lead generation", "cold calling",
            "b2b sales", "b2c sales", "enterprise sales",
            "solution selling", "consultative selling", "spin selling",
            "negotiation", "closing", "account management",
            "sales forecasting", "revenue operations", "territory management",
            "proposal writing", "contract negotiation",
            "sales strategy", "business development",
            "customer acquisition", "client relationship",
            "revenue growth",
        ],
        "soft_skills": [
            "communication", "persuasion", "relationship building",
            "active listening", "empathy", "resilience",
            "self-motivation", "time management", "adaptability",
            "problem solving", "teamwork", "presentation skills",
            "emotional intelligence", "objection handling",
        ],
        "action_verbs": [
            "sold", "negotiated", "closed", "generated", "managed",
            "developed", "increased", "built", "achieved", "exceeded",
        ],
        "other_keywords": [
            "quota", "target", "commission", "revenue growth",
            "market share", "customer acquisition", "customer retention",
            "cross-selling", "up-selling", "prospecting",
            "networking", "business development", "strategic partnerships",
            "sales cycle", "roi", "value proposition",
        ],
        "achievements_keywords": [
            "exceeded quota", "increased sales", "grew revenue",
            "acquired clients", "retained customers", "increased market share",
        ],
    },

    # ================================================================
    # 17. إدارة المشاريع - Project Management
    # ================================================================
    "project_management": {
        "label": "Project Management",
        "hard_skills": [
            "ms project", "jira", "asana", "trello", "monday.com",
            "smartsheet", "wrike", "basecamp", "clickup",
            "agile", "scrum", "kanban", "waterfall", "hybrid",
            "prince2", "pmbok", "pmp", "pmi",
            "risk management", "budget management",
            "resource allocation", "scheduling", "gantt charts",
            "critical path", "earned value management",
            "stakeholder management", "change management",
            "quality management", "kpis",
            "ms office", "excel", "powerpoint", "visio",
            "erp", "sap", "business analysis",
        ],
        "soft_skills": [
            "leadership", "communication", "stakeholder management",
            "problem solving", "decision making", "negotiation",
            "conflict resolution", "team building", "motivation",
            "time management", "organization", "adaptability",
            "strategic thinking", "influencing", "delegation",
            "team management", "interpersonal skills", "scheduling",
        ],
        "action_verbs": [
            "led", "managed", "coordinated", "delivered", "planned",
            "executed", "monitored", "facilitated", "organized", "oversaw",
        ],
        "other_keywords": [
            "deliverables", "milestones", "scope", "timeline",
            "budget", "resources", "quality", "stakeholders",
            "risk", "procurement", "integration", "closure",
            "status reports", "change management", "governance",
            "pmo", "project charter", "sow", "lessons learned",
        ],
        "achievements_keywords": [
            "delivered on time", "under budget", "increased efficiency",
            "reduced costs", "improved team performance", "completed successfully",
        ],
    },

    # ================================================================
    # 18. خدمة العملاء - Customer Service
    # ================================================================
    "customer_service": {
        "label": "Customer Service",
        "hard_skills": [
            "zendesk", "freshdesk", "intercom", "salesforce service cloud",
            "livechat", "helpscout", "servicenow",
            "crm", "ticketing systems", "knowledge base",
            "call center", "ivr", "cti", "chat support",
            "email support", "phone support", "social media support",
        ],
        "soft_skills": [
            "communication", "empathy", "patience",
            "active listening", "problem solving", "conflict resolution",
            "positive attitude", "adaptability", "time management",
            "emotional intelligence", "de-escalation",
            "customer focus", "service orientation",
        ],
        "action_verbs": [
            "resolved", "assisted", "handled", "responded", "managed",
            "supported", "addressed", "followed up", "escalated", "improved",
        ],
        "other_keywords": [
            "first contact resolution", "customer satisfaction",
            "nps", "csat", "sla", "kpi",
            "ticket resolution", "escalation", "follow-up",
            "customer experience", "customer journey",
            "quality assurance", "feedback", "retention",
            "loyalty", "churn", "onboarding",
        ],
        "achievements_keywords": [
            "improved csat", "reduced response time", "increased nps",
            "reduced churn", "improved resolution rate", "increased retention",
        ],
    },

    # ================================================================
    # 19. التعليم - Education
    # ================================================================
    "education": {
        "label": "Education / Teacher / Educator",
        "hard_skills": [
            "lms", "moodle", "blackboard", "canvas", "google classroom",
            "curriculum development", "lesson planning", "assessment",
            "e-learning", "instructional design", "articulate",
            "educational technology", "smart board", "multimedia",
            "special education", "esl", "distance learning",
            "microsoft office", "google workspace", "zoom",
            "student evaluation", "iep", "differentiated instruction",
            "teaching", "classroom management",
            "learning outcomes",
        ],
        "soft_skills": [
            "communication", "patience", "classroom management",
            "creativity", "adaptability", "empathy",
            "leadership", "organization", "motivation",
            "active listening", "mentoring", "collaboration",
            "cultural awareness", "problem solving",
            "interpersonal skills",
        ],
        "action_verbs": [
            "taught", "developed", "designed", "implemented", "evaluated",
            "managed", "created", "facilitated", "mentored", "assessed",
        ],
        "other_keywords": [
            "student engagement", "learning outcomes", "pedagogy",
            "differentiated instruction", "inclusion", "accessibility",
            "professional development", "accreditation", "syllabus",
            "rubric", "formative assessment", "summative assessment",
            "blended learning", "flipped classroom",
        ],
        "achievements_keywords": [
            "improved student performance", "increased pass rate",
            "developed curriculum", "trained teachers", "improved engagement",
        ],
    },

    # ================================================================
    # 20. القانون - Law
    # ================================================================
    "legal": {
        "label": "Law / Legal",
        "hard_skills": [
            "lexisnexis", "westlaw", "pacer", "clio",
            "legal research", "document review", "due diligence",
            "contract drafting", "litigation", "ediscovery",
            "case management", "compliance", "regulatory",
            "corporate law", "ip law", "employment law",
            "legal writing", "brief writing", "depositions",
            "legal drafting", "regulatory affairs",
            "negotiation", "contract law",
        ],
        "soft_skills": [
            "analytical skills", "critical thinking", "communication",
            "attention to detail", "negotiation", "persuasion",
            "problem solving", "research skills", "time management",
            "discretion", "integrity", "ethics",
            "client relations", "presentation skills",
        ],
        "action_verbs": [
            "advised", "represented", "drafted", "negotiated", "researched",
            "litigated", "reviewed", "analyzed", "counseled", "defended",
        ],
        "other_keywords": [
            "precedent", "statute", "regulation", "jurisdiction",
            "arbitration", "mediation", "settlement", "litigation",
            "pro bono", "bar association", "continuing education",
            "confidentiality", "attorney-client privilege",
        ],
        "achievements_keywords": [
            "won cases", "settled disputes", "reduced liability",
            "drafted contracts", "achieved compliance", "protected assets",
        ],
    },

    # ================================================================
    # 21. إدارة الأعمال - Business Administration
    # ================================================================
    "business_management": {
        "label": "Business Administration",
        "hard_skills": [
            "management", "operations", "business strategy",
            "project management", "planning", "coordination",
            "budget management", "strategic planning",
            "ms office", "excel", "powerpoint",
            "business analysis", "erp", "sap",
            "change management", "quality management",
            "kpis", "risk management",
            "leadership", "decision making",
            "stakeholder management",
            "organizational development",
        ],
        "soft_skills": [
            "leadership", "communication", "decision making",
            "problem solving", "strategic thinking", "team management",
            "organizational skills", "time management", "negotiation",
            "interpersonal skills", "adaptability", "conflict resolution",
        ],
        "action_verbs": [
            "led", "managed", "directed", "oversaw", "implemented",
            "developed", "executed", "coordinated", "optimized", "transformed",
        ],
        "other_keywords": [
            "management", "leadership", "operations",
            "business strategy", "project management",
            "planning", "coordination", "budget management",
            "stakeholders", "governance", "compliance",
        ],
        "achievements_keywords": [
            "increased revenue", "reduced costs", "improved efficiency",
            "grew market share", "streamlined operations", "achieved targets",
        ],
    },
    # ============================================================
    # ⚙️ 22. الهندسة المدنية  - Civil Engineering
    # ============================================================
    "civil_engineering": {
        "label": "Civil Engineering",
        "hard_skills": [
            "autocad", "autocad civil 3d", "revit", "sap2000", "etabs",
            "safe", "staad.pro", "tekla", "primavera p6", "ms project",
            "arcgis", "gis", "surveying", "total station", "gps",
            "structural analysis", "structural design", "seismic design",
            "geotechnical engineering", "soil testing", "foundation design",
            "construction management", "site supervision", "quality control",
            "project planning", "cost estimation", "bill of quantities", "boq",
            "building codes", "aci", "asce", "ibc", "astm",
            "osha", "safety standards", "safety plans", "hse",
            "transportation engineering", "highway design", "traffic engineering",
            "water resources", "hydrology", "hydraulics", "storm water",
            "concrete design", "steel design", "timber design",
            "bridge design", "road design", "drainage design",
            "bim", "building information modeling",
            "pavement design", "asphalt",
        ],
        "soft_skills": [
            "problem solving", "analytical thinking", "communication",
            "team collaboration", "attention to detail", "leadership",
            "organizational skills", "time management", "decision making",
            "technical writing", "negotiation",
        ],
        "action_verbs": [
            "designed", "managed", "analyzed", "supervised", "implemented",
            "coordinated", "developed", "evaluated", "built", "delivered",
            "inspected", "approved", "estimated", "planned",
        ],
        "achievements_keywords": [
            "completed on time", "under budget", "improved structural",
            "reduced costs", "increased efficiency", "safety record",
            "zero incidents", "delivered ahead of schedule",
        ],
    },
    # ================================================================
    # 23. الهندسة الكهربائية والإلكترونية - Electrical & Electronic Engineering
    # ================================================================
    "electrical_engineering": {
        "label": "Electrical & Electronic Engineering",
        "hard_skills": [
            # برمجة وأنظمة مدمجة
            "arduino", "raspberry pi", "embedded systems", "microcontroller",
            "pic microcontroller", "arm", "stm32", "esp32", "atmega",
            "labview", "plc programming", "scada", "hmi", "dcs",
            "fpga", "vhdl", "verilog", "quartus",
            "matlab", "simulink", "labview", "pspice",

            # الكترونيات وتصميم الدوائر
            "circuit design", "pcb design", "altium designer", "eagle",
            "kicad", "multisim", "proteus", "ltspice",
            "analog electronics", "digital electronics", "mixed signal",
            "signal processing", "dsp", "image processing",
            "embedded c", "c programming", "assembly",

            # ذكاء اصطناعي وتعلم الآلة
            "tensorflow", "keras", "pytorch", "opencv",
            "deep learning", "machine learning", "computer vision",
            "artificial intelligence", "neural networks", "nlp",
            "python", "anaconda", "jupyter",
            "scikit-learn", "numpy", "pandas",
            "ros", "robotic operating system",

            # أنظمة الطاقة
            "power systems", "power distribution", "power electronics",
            "transformers", "switchgear", "motor drives", "vfd",
            "renewable energy", "solar pv", "wind energy", "battery storage",
            "plc", "automation", "control systems",
            "pid controller", "servo systems", "ac/dc drives",

            # اتصالات وشبكات
            "wireless communication", "rf design", "antenna design",
            "iot", "internet of things", "zigbee", "bluetooth", "wifi",
            "lora", "mqtt", "modbus", "can bus", "ethernet",
            "v2x", "vanet", "wsn", "wireless sensor networks",
            "slam", "computer vision", "vslam",

            # برامج تصميم وتحليل
            "autocad electrical", "eplan", "revit mep",
            "etap", "pscad", "digsilent", "psse",
            "dialux", "relux", "mat lab",

            # اختبار وقياس
            "oscilloscope", "multimeter", "spectrum analyzer",
            "signal generator", "data acquisition", "daq",
            "labview", "ni instruments", "matlab data acquisition",

            # مشاريع بحثية وأكاديمية
            "research publications", "ieee", "conference papers",
            "deep learning research", "loop closure detection",
            "path planning", "obstacle avoidance", "autonomous vehicles",
            "robotics", "robot arm", "gesture control", "kinect",
            "image recognition", "object detection", "slam",
            "traffic management", "smart systems", "ict",

            # معايير ومواصفات
            "iec", "ieee standards", "nema", "iso",
            "safety standards", "osha", "calibration",
            "testing", "commissioning", "maintenance",
        ],
        "soft_skills": [
            "problem solving", "analytical thinking", "attention to detail",
            "research skills", "communication", "teamwork",
            "technical writing", "leadership", "time management",
            "self-learning", "continuous learning", "creativity",
            "project management", "critical thinking", "innovation",
        ],
        "action_verbs": [
            "designed", "developed", "implemented", "tested", "commissioned",
            "maintained", "programmed", "analyzed", "optimized", "researched",
            "published", "presented", "supervised", "trained", "managed",
            "built", "created", "investigated", "simulated", "automated",
        ],
        "other_keywords": [
            "embedded system design", "ai/ml deep learning",
            "image processing", "web development", "android app development",
            "full stack developer", "system designing",
            "python programmer", "instrumentation engineer",
            "electronic engineering", "electronic engineer",
            "phd research", "funded research", "ict r&d",
            "suparco", "conference secretary", "publications",
            "h-index", "citations", "impact factor",
        ],
        "achievements_keywords": [
            "published papers", "research publications", "citations",
            "h-index", "impact factor", "funded projects",
            "conference presentations", "awards", "scholarships",
            "improved efficiency", "reduced costs", "patent",
            "3rd position", "1st division", "cgpa", "percentage",
            "secured position", "winner", "runner up",
        ],
    },

    # ================================================================
    # 25. الذكاء الاصطناعي والروبوتات - AI & Robotics
    # ================================================================
    "ai_robotics": {
        "label": "AI & Robotics",
        "hard_skills": [
            # ذكاء اصطناعي
            "artificial intelligence", "machine learning", "deep learning",
            "neural networks", "cnn", "rnn", "lstm", "gan", "transformer",
            "nlp", "natural language processing", "computer vision",
            "reinforcement learning", "transfer learning",

            # أطر عمل
            "tensorflow", "keras", "pytorch", "scikit-learn",
            "opencv", "hugging face", "bert", "gpt",
            "yolo", "faster rcnn", "resnet", "vgg",

            # روبوتيكا
            "ros", "robotic operating system", "ros2",
            "slam", "vslam", "path planning", "motion planning",
            "obstacle avoidance", "autonomous vehicles",
            "robot arm", "industrial robots", "drone",
            "sensor fusion", "lidar", "camera", "imu",

            # بيانات ومعالجة
            "python", "matlab", "c++", "julia",
            "pandas", "numpy", "scipy",
            "data collection", "data labeling", "model training",
            "model deployment", "edge ai", "embedded ml",

            # أدوات وبيئات
            "jupyter", "google colab", "anaconda",
            "docker", "git", "linux", "ubuntu",
            "gazebo", "rviz", "moveit",
            "raspberry pi", "arduino", "nvidia jetson",
            "cuda", "gpu computing",
        ],
        "soft_skills": [
            "research skills", "analytical thinking", "problem solving",
            "creativity", "continuous learning", "technical writing",
            "communication", "teamwork", "critical thinking",
            "attention to detail", "innovation",
        ],
        "action_verbs": [
            "trained", "developed", "researched", "implemented", "optimized",
            "published", "designed", "tested", "deployed", "analyzed",
            "automated", "simulated", "programmed",
        ],
        "other_keywords": [
            "deep learning research", "computer vision applications",
            "slam systems", "autonomous systems",
            "loop closure detection", "viewpoint invariant",
            "ieee transactions", "robotics",
        ],
        "achievements_keywords": [
            "improved accuracy", "published papers", "citations",
            "conference presentations", "funded projects",
            "h-index", "impact factor", "reduced error rate",
        ],
    },

    # ================================================================
    # 26. الهندسة الميكانيكية - Mechanical Engineering
    # ================================================================
    "mechanical_engineering": {
        "label": "Mechanical Engineering",
        "hard_skills": [
            "solidworks", "autocad", "catia", "inventor", "nx", "ptc creo",
            "ansys", "abaqus", "nastran", "hypermesh",
            "matlab", "simulink", "labview",
            "mechanical design", "product design", "machine design",
            "thermodynamics", "heat transfer", "fluid mechanics",
            "hvac design", "refrigeration", "air conditioning",
            "finite element analysis", "fea", "cfd", "fatigue analysis",
            "gd&t", "tolerance analysis", "dfm", "dfa", "dfmea",
            "manufacturing processes", "cnc machining", "sheet metal",
            "welding", "casting", "forging", "injection molding",
            "lean manufacturing", "six sigma", "5s", "kaizen", "poka-yoke",
            "quality control", "spc", "msa", "ppap", "apqp",
            "plm", "pdm",
            "material science", "metallurgy", "composites", "polymers",
            "hydraulics", "pneumatics", "piping design",
            "maintenance", "reliability engineering", "fmea", "rcm",
            "iso 9001", "iso 14001", "asme", "astm",
        ],
        "soft_skills": [
            "problem solving", "analytical thinking", "creativity",
            "attention to detail", "communication", "teamwork",
            "leadership", "time management", "technical writing",
        ],
        "action_verbs": [
            "designed", "developed", "analyzed", "optimized", "tested",
            "manufactured", "implemented", "managed", "improved", "reduced",
            "engineered", "simulated", "validated", "commissioned",
        ],
        "achievements_keywords": [
            "reduced weight", "improved performance", "increased efficiency",
            "reduced costs", "improved reliability", "reduced downtime",
            "improved design", "passed testing", "met specifications",
        ],
    },

}

# =====================================================================
# 📊 ALL_CATEGORIES - جميع الفئات العامة (موسعة - lowercase)
# =====================================================================
ALL_CATEGORIES = {
    "software": [
        "python", "java", "c++", "c#", "php", "laravel", "django", "flask",
        "spring", "javascript", "typescript", "react", "vue", "angular",
        "nodejs", "mysql", "postgresql", "mongodb", "redis",
        "docker", "kubernetes", "aws", "azure", "git", "github",
        "rest api", "graphql", "oop", "design patterns", "microservices"
    ],
    "data_science": [
        "python", "pandas", "numpy", "scikit-learn", "tensorflow",
        "pytorch", "machine learning", "deep learning",
        "data analysis", "statistics", "power bi", "tableau",
        "data visualization", "feature engineering",
        "data mining", "sql", "big data", "nlp",
        "computer vision", "predictive analytics"
    ],
    "cybersecurity": [
        "penetration testing", "ethical hacking", "network security",
        "siem", "soc", "firewall", "ids", "ips", "wireshark",
        "burp suite", "owasp", "incident response",
        "vulnerability assessment", "risk assessment",
        "encryption", "cybersecurity", "linux", "kali linux"
    ],
    "hr": [
        "recruitment", "talent acquisition", "employee relations",
        "onboarding", "training", "performance management",
        "payroll", "compensation", "benefits administration",
        "hr policies", "human resources", "workforce planning",
        "employee engagement", "labor law"
    ],
    "accounting": [
        "accounting", "financial reporting", "bookkeeping",
        "general ledger", "audit", "tax", "budgeting",
        "accounts payable", "accounts receivable",
        "financial statements", "cost accounting",
        "financial analysis", "quickbooks", "excel", "erp"
    ],
    "marketing": [
        "digital marketing", "seo", "sem", "content marketing",
        "social media marketing", "google analytics",
        "email marketing", "branding", "advertising",
        "influencer marketing", "campaign management",
        "market research", "conversion rate optimization"
    ],
    "sales": [
        "sales", "business development", "lead generation",
        "customer acquisition", "crm", "sales strategy",
        "negotiation", "account management",
        "client relationship", "pipeline management",
        "revenue growth", "sales forecasting"
    ],
    "business": [
        "management", "leadership", "operations",
        "business strategy", "strategic planning",
        "project management", "budget management",
        "decision making", "stakeholder management",
        "organizational development"
    ],
    "medical": [
        "patient care", "diagnosis", "treatment",
        "clinical practice", "medical records",
        "hospital", "healthcare", "medicine",
        "surgery", "medical research",
        "preventive care", "patient assessment"
    ],
    "nursing": [
        "nursing", "patient monitoring",
        "medication administration",
        "critical care", "emergency care",
        "health assessment", "patient safety",
        "clinical care", "care planning"
    ],
    "pharmacy": [
        "pharmacy", "pharmacology", "drug dispensing",
        "medication therapy", "prescription review",
        "patient counseling", "clinical pharmacy",
        "pharmaceutical care", "drug interactions"
    ],
    "mechanical": [
        "solidworks", "autocad", "catia",
        "mechanical design", "manufacturing",
        "maintenance", "thermodynamics",
        "fluid mechanics", "cad", "cam",
        "quality control","engineering analysis"
    ],
    "electrical": [
        "electrical systems", "power systems",
        "circuit design", "electronics",
        "plc", "automation", "control systems",
        "renewable energy", "electrical maintenance",
        "instrumentation"
    ],
    "architecture": [
        "architecture", "architectural design",
        "urban planning", "autocad", "revit",
        "sketchup", "3d modeling",
        "building design", "construction drawings"
    ],
    "education": [
        "teaching", "curriculum development",
        "classroom management", "lesson planning",
        "student assessment", "educational technology",
        "instructional design", "learning outcomes"
    ],
    "law": [
        "legal research", "litigation",
        "contract law", "corporate law",
        "legal drafting", "compliance",
        "regulatory affairs", "negotiation",
        "case management"
    ]
}

# =====================================================================
# 📊 Normalization / Aliases / Matching Config
# =====================================================================

KEYWORD_ALIASES = {
    # JavaScript / TypeScript
    "js": "javascript",
    "nodejs": "node.js",
    "node js": "node.js",
    "reactjs": "react",
    "react js": "react",
    "vuejs": "vue.js",
    "vue js": "vue.js",
    "ts": "typescript",

    # Databases
    "postgres": "postgresql",
    "postgre": "postgresql",
    "mongo": "mongodb",

    # DevOps / Cloud
    "k8s": "kubernetes",
    "gh actions": "github actions",
    "gcloud": "google cloud",
    "google cloud platform": "google cloud",
    "amazon web services": "aws",

    # Python / ML
    "py": "python",
    "sklearn": "scikit-learn",
    "tf": "tensorflow",
    "ml": "machine learning",
    "dl": "deep learning",
    "cv": "computer vision",

    # Common spelling variants
    "powerbi": "power bi",
    "ms excel": "excel",
    "ms project": "microsoft project",
    "ms office": "microsoft office",
    "a b testing": "a/b testing",
    "ab testing": "a/b testing",
}

MATCH_WEIGHTS = {
    "job_titles": 5.0,
    "hard_skills": 3.0,
    "achievements_keywords": 2.5,
    "other_keywords": 1.5,
    "action_verbs": 1.2,
    "soft_skills": 1.0,
}

MATCH_FIELDS = [
    "job_titles",
    "hard_skills",
    "soft_skills",
    "other_keywords",
    "action_verbs",
    "achievements_keywords",
]


# =====================================================================
# 🧹 Normalization helpers
# =====================================================================

def normalize_keyword(value: str) -> str:
    """
    توحيد شكل keyword:
    - lowercase
    - إزالة مسافات زائدة
    - توحيد بعض الرموز
    بدون حذف رموز مهمة مثل:
    c++, c#, .net, ci/cd, node.js
    """
    if value is None:
        return ""

    value = str(value).strip().lower()

    value = value.replace("’", "'").replace("“", '"').replace("”", '"')
    value = value.replace("&", " and ")

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_keyword_list(items: list) -> list[str]:
    """
    lowercase + deduplicate مع الحفاظ على الترتيب.
    """
    if not items:
        return []

    seen = set()
    result = []

    for item in items:
        keyword = normalize_keyword(item)

        if not keyword:
            continue

        if keyword not in seen:
            seen.add(keyword)
            result.append(keyword)

    return result


def normalize_keywords_database() -> None:
    """
    يطبع normalize على قاعدة البيانات نفسها:
    - يحول كل الكلمات إلى lowercase
    - يزيل التكرارات داخل كل list
    - ينظف ALL_CATEGORIES أيضاً
    """

    for sector_data in ALL_KEYWORDS_DATABASE.values():
        for field in MATCH_FIELDS:
            if field in sector_data:
                sector_data[field] = normalize_keyword_list(sector_data[field])

    for category_name, keywords in ALL_CATEGORIES.items():
        ALL_CATEGORIES[category_name] = normalize_keyword_list(keywords)


def _make_term_pattern(term: str) -> str:
    """
    Regex آمن للمطابقة.
    يمنع false positives مثل:
    go داخل ongoing
    r داخل reporting
    java داخل javascript

    ويدعم كلمات فيها رموز مثل:
    c++, c#, .net, ci/cd, node.js
    """

    term = normalize_keyword(term)

    if not term:
        return ""

    escaped = re.escape(term)

    # المسافات في keyword ممكن تكون مسافة أو أكثر في CV
    escaped = escaped.replace(r"\ ", r"\s+")

    return rf"(?<![a-z0-9+#.]){escaped}(?![a-z0-9+#.])"


def _contains_term(normalized_text: str, term: str) -> bool:
    pattern = _make_term_pattern(term)

    if not pattern:
        return False

    return re.search(pattern, normalized_text, flags=re.IGNORECASE) is not None


def normalize_cv_text(cv_text: str) -> str:
    """
    تجهيز نص CV للمطابقة:
    - lowercase
    - تنظيف مسافات
    - توسيع aliases

    مثال:
    js      => javascript
    ts      => typescript
    k8s     => kubernetes
    postgres=> postgresql
    """

    text = normalize_keyword(cv_text)

    if not text:
        return ""

    expanded_terms = []

    for alias, canonical in KEYWORD_ALIASES.items():
        alias = normalize_keyword(alias)
        canonical = normalize_keyword(canonical)

        if _contains_term(text, alias):
            expanded_terms.append(canonical)

    if expanded_terms:
        text = text + " " + " ".join(expanded_terms)

    return text


# نطبّع قاعدة البيانات فور تحميل الملف
normalize_keywords_database()


# =====================================================================
# 📊 وظائف مساعدة
# =====================================================================

def get_all_sectors() -> list[str]:
    """إرجاع أسماء جميع القطاعات في ALL_KEYWORDS_DATABASE"""
    return list(ALL_KEYWORDS_DATABASE.keys())


def get_all_categories() -> list[str]:
    """إرجاع أسماء جميع الفئات في ALL_CATEGORIES"""
    return list(ALL_CATEGORIES.keys())


def get_sector_data(sector_name: str) -> dict | None:
    """إرجاع بيانات قطاع معين من ALL_KEYWORDS_DATABASE"""
    return ALL_KEYWORDS_DATABASE.get(sector_name)


def get_category_keywords(category_name: str) -> list[str]:
    """إرجاع كلمات فئة معينة من ALL_CATEGORIES"""
    return ALL_CATEGORIES.get(category_name, [])


def get_all_hard_skills(sector_name: str | None = None) -> list[str]:
    """استخراج جميع المهارات التقنية"""
    if sector_name and sector_name in ALL_KEYWORDS_DATABASE:
        return ALL_KEYWORDS_DATABASE[sector_name].get("hard_skills", [])

    all_skills = []

    for sector_data in ALL_KEYWORDS_DATABASE.values():
        all_skills.extend(sector_data.get("hard_skills", []))

    return normalize_keyword_list(all_skills)


def get_all_soft_skills(sector_name: str | None = None) -> list[str]:
    """استخراج جميع المهارات الناعمة"""
    if sector_name and sector_name in ALL_KEYWORDS_DATABASE:
        return ALL_KEYWORDS_DATABASE[sector_name].get("soft_skills", [])

    all_skills = []

    for sector_data in ALL_KEYWORDS_DATABASE.values():
        all_skills.extend(sector_data.get("soft_skills", []))

    return normalize_keyword_list(all_skills)


def find_keywords_in_text(
    cv_text: str,
    keywords: list[str],
) -> tuple[list[str], list[str]]:
    """
    يرجع:
    - found
    - missing

    باستخدام word-boundary matching بدل substring matching.
    """

    normalized_text = normalize_cv_text(cv_text)

    found = []
    missing = []

    for keyword in normalize_keyword_list(keywords):
        if _contains_term(normalized_text, keyword):
            found.append(keyword)
        else:
            missing.append(keyword)

    return found, missing


def match_cv_with_sector(cv_text: str, sector_name: str) -> dict | None:
    """
    مقارنة السيرة الذاتية مع قطاع محدد.

    التحسينات:
    - safe regex matching بدل substring
    - aliases مثل js -> javascript
    - weights حسب أهمية الحقل
    - job_titles أعلى وزن
    - hard_skills أعلى من soft_skills
    """

    if sector_name not in ALL_KEYWORDS_DATABASE:
        return None

    sector = ALL_KEYWORDS_DATABASE[sector_name]
    normalized_text = normalize_cv_text(cv_text)

    results = {
        "sector": sector_name,
        "label": sector.get("label", sector_name),

        "job_titles_found": [],
        "job_titles_missing": [],

        "hard_skills_found": [],
        "hard_skills_missing": [],

        "soft_skills_found": [],
        "soft_skills_missing": [],

        "other_keywords_found": [],
        "other_keywords_missing": [],

        "action_verbs_found": [],
        "action_verbs_missing": [],

        "achievements_keywords_found": [],
        "achievements_keywords_missing": [],

        "weighted_score": 0,
        "max_score": 0,
        "match_rate": 0,
    }

    weighted_score = 0.0
    max_score = 0.0

    for field in MATCH_FIELDS:
        keywords = sector.get(field, [])
        weight = MATCH_WEIGHTS.get(field, 1.0)

        found_key = f"{field}_found"
        missing_key = f"{field}_missing"

        for keyword in keywords:
            max_score += weight

            if _contains_term(normalized_text, keyword):
                results[found_key].append(keyword)
                weighted_score += weight
            else:
                results[missing_key].append(keyword)

    results["weighted_score"] = round(weighted_score, 2)
    results["max_score"] = round(max_score, 2)
    results["match_rate"] = round((weighted_score / max_score) * 100, 1) if max_score else 0

    return results


def auto_detect_sector(
    cv_text: str,
    top_n: int = 5,
    min_score: float = 5.0,
) -> list[tuple[str, float]]:
    """
    اكتشاف القطاع المناسب تلقائياً.

    التحسين:
    - لا نعتمد على action verbs أو achievements وحدها
    - لازم القطاع يكون عنده hard skill أو job title match
    """

    normalized_text = normalize_cv_text(cv_text)

    if not normalized_text:
        return []

    scores = []

    for sector_name, sector_data in ALL_KEYWORDS_DATABASE.items():
        score = 0.0
        strong_signal_found = False

        for field in MATCH_FIELDS:
            weight = MATCH_WEIGHTS.get(field, 1.0)

            for keyword in sector_data.get(field, []):
                if _contains_term(normalized_text, keyword):
                    score += weight

                    if field in {"job_titles", "hard_skills"}:
                        strong_signal_found = True

        if strong_signal_found and score >= min_score:
            scores.append((sector_name, round(score, 2)))

    if not scores:
        return []

    scores.sort(key=lambda item: item[1], reverse=True)

    return scores[:top_n]


def auto_detect_category(
    cv_text: str,
    top_n: int = 5,
    min_score: int = 1,
) -> list[tuple[str, int]]:
    """
    اكتشاف الفئة المناسبة من ALL_CATEGORIES.

    يرجع [] إذا كل النتائج صفر.
    """

    normalized_text = normalize_cv_text(cv_text)

    if not normalized_text:
        return []

    scores = []

    for category_name, keywords in ALL_CATEGORIES.items():
        score = 0

        for keyword in keywords:
            if _contains_term(normalized_text, keyword):
                score += 1

        if score >= min_score:
            scores.append((category_name, score))

    if not scores:
        return []

    scores.sort(key=lambda item: item[1], reverse=True)

    return scores[:top_n]


def get_total_keywords_count() -> int:
    """إجمالي عدد الكلمات المفتاحية بعد normalization"""
    total = 0

    for sector_data in ALL_KEYWORDS_DATABASE.values():
        for field in MATCH_FIELDS:
            total += len(sector_data.get(field, []))

    return total


def get_sector_keywords_flat(sector_name: str) -> list[str]:
    """كل كلمات قطاع معين في list واحدة"""
    if sector_name not in ALL_KEYWORDS_DATABASE:
        return []

    sector = ALL_KEYWORDS_DATABASE[sector_name]

    all_keywords = []

    for field in MATCH_FIELDS:
        all_keywords.extend(sector.get(field, []))

    return normalize_keyword_list(all_keywords)


def get_all_keywords_flat() -> list[str]:
    """كل كلمات جميع القطاعات في list واحدة"""
    all_keywords = []

    for sector_name in ALL_KEYWORDS_DATABASE:
        all_keywords.extend(get_sector_keywords_flat(sector_name))

    return normalize_keyword_list(all_keywords)


# =====================================================================
# 💾 JSON Export / Load
# =====================================================================

def export_keywords_to_json(file_path: str = "keywords_database.json") -> str:
    """
    تصدير قاعدة الكلمات إلى JSON.
    مفيد لو بدك لاحقاً تفصل البيانات عن الكود.
    """

    path = Path(file_path)

    payload = {
        "all_keywords_database": ALL_KEYWORDS_DATABASE,
        "all_categories": ALL_CATEGORIES,
        "keyword_aliases": KEYWORD_ALIASES,
        "match_weights": MATCH_WEIGHTS,
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(path)


def load_keywords_from_json(file_path: str) -> dict:
    """
    تحميل قاعدة الكلمات من JSON.
    حالياً لا يغير المتغيرات global تلقائياً.
    فقط يرجع البيانات.
    """

    path = Path(file_path)

    return json.loads(path.read_text(encoding="utf-8"))


# =====================================================================
# 🧪 Tests
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("📊 بنك الكلمات المفتاحية الشامل - CV Analyzer Pro")
    print("=" * 70)

    print(f"\n✅ عدد القطاعات في ALL_KEYWORDS_DATABASE: {len(ALL_KEYWORDS_DATABASE)}")
    print(f"✅ عدد الفئات في ALL_CATEGORIES: {len(ALL_CATEGORIES)}")
    print(f"✅ إجمالي الكلمات المفتاحية بعد التنظيف: {get_total_keywords_count():,}")

    print("\n📂 القطاعات في ALL_KEYWORDS_DATABASE:")
    for name, data in ALL_KEYWORDS_DATABASE.items():
        label = data.get("label", name)
        h = len(data.get("hard_skills", []))
        s = len(data.get("soft_skills", []))
        o = len(data.get("other_keywords", []))
        j = len(data.get("job_titles", []))
        a = len(data.get("action_verbs", []))
        ach = len(data.get("achievements_keywords", []))

        print(
            f"  ✅ {label:<35} | "
            f"Titles: {j:>2} | "
            f"Hard: {h:>3} | "
            f"Soft: {s:>3} | "
            f"Other: {o:>3} | "
            f"Verbs: {a:>3} | "
            f"Ach: {ach:>3} | "
            f"Total: {j + h + s + o + a + ach:>4}"
        )

    print("\n🧪 Matching test:")

    sample_cv = """
    Senior Software Engineer with experience in JS, TS, React, NodeJS,
    Postgres, K8s, Docker, AWS, CI/CD and microservices.
    Improved performance and reduced deployment time.
    This sentence contains ongoing work, but it should not match Go.
    """

    sector_result = match_cv_with_sector(sample_cv, "software_development")

    print("\nSoftware match rate:", sector_result["match_rate"])
    print("Hard skills found:", sector_result["hard_skills_found"][:20])
    print("Job titles found:", sector_result["job_titles_found"])
    print("Detected sectors:", auto_detect_sector(sample_cv))

    empty_cv = "This text has no meaningful resume keywords."
    print("Empty detection:", auto_detect_sector(empty_cv))

    print("\n" + "=" * 70)