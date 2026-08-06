# =====================================================================
# 📂 cv_sections.py
# =====================================================================
# المسؤولية:
# - بنك أسماء أقسام السيرة الذاتية
# - كلمات مفتاحية لكل قسم
# - الأقسام المطلوبة والاختيارية
# - نصائح تحسين الأقسام
#
# ملاحظة:
# هذا الملف لا يستخرج الأقسام.
# الاستخراج يتم فقط من خلال section_extractor.py
# =====================================================================


# =====================================================================
# أسماء الأقسام المعتمدة
# =====================================================================

CV_SECTION_NAMES = [
    "contact_header",
    "summary",
    "experience",
    "education",
    "skills",
    "certifications",
    "projects",
    "languages",
    "volunteer",
    "awards",
    "publications",
    "interests",
    "references",
    "courses",
    "bootcamps",
    "internships",
    "freelance",
    "leadership",
    "organizations",
    "military",
    "additional_info",
    "fields",
    "programs",
    "contact",
    "other",
]


CV_SECTIONS = {
    section_name: ""
    for section_name in CV_SECTION_NAMES
}


# =====================================================================
# الكلمات المفتاحية لكل قسم
# =====================================================================
# قواعد التنظيف:
# - لا يوجد تكرار داخل نفس القسم.
# - تجنبنا الكلمات العامة جداً مثل: university, school, degree.
# - الكلمات المتداخلة تم وضعها في القسم الأقرب:
#   strengths             => skills
#   graduation project    => projects
#   social work           => volunteer
#   language computer     => skills
# =====================================================================

SECTION_KEYWORDS = {
    # ================================================================
    # 1. Summary / Profile
    # ================================================================
    "summary": [
        "summary",
        "profile",
        "objective",
        "about me",
        "about",
        "professional summary",
        "career objective",
        "personal statement",
        "executive summary",
        "professional profile",
        "career profile",
        "personal profile",
        "introduction",
        "overview",
        "qualifications summary",
        "career highlights",
    ],

    # ================================================================
    # 2. Work Experience
    # ================================================================
    "experience": [
        "experience",
        "experiences",
        "employment",
        "employment history",
        "work history",
        "work experience",
        "work experiences",
        "professional experience",
        "professional experiences",
        "professional background",
        "work background",
        "career history",
        "career experience",
        "job history",
        "relevant experience",
        "work summary",
        "professional history",
        "workexperience",
        "field related experience",
        "professional exp",
        "work exp",
        "prof exp",
    ],

    # ================================================================
    # 3. Education
    # ================================================================
    "education": [
        "education",
        "academic background",
        "educational background",
        "education background",
        "qualifications",
        "academic qualifications",
        "educational qualifications",
        "higher education",
        "academic history",
        "diplomas",
        "bachelor thesis",
        "master thesis",
        "phd thesis",
        "formation",
    ],

    # ================================================================
    # 4. Skills
    # ================================================================
    "skills": [
        "skills",
        "technical skills",
        "technical skill",
        "professional skills",
        "competencies",
        "core competencies",
        "key skills",
        "areas of expertise",
        "expertise",
        "technical proficiencies",
        "technologies",
        "skill set",
        "skill highlights",
        "professional competencies",
        "technical expertise",
        "tools and technologies",
        "tools & technologies",
        "programming skills",
        "computer skills",
        "it skills",
        "digital skills",
        "digital skill",
        "capabilities",
        "soft skills",
        "power skills",
        "core skills",
        "core proficiency",
        "core proficiencies",
        "tech skills",
        "additional skills",
        "interpersonal skills",
        "language and computer skills",
        "tools and frameworks",
        "tools & frameworks",
        "tools and ides",
        "tools & ides",
        "software tools",
        "other programming languages",
        "programming machines",
        "strengths",
        "key strengths",
        "professional strengths",
    ],

    # ================================================================
    # 5. Certifications
    # ================================================================
    "certifications": [
        "certifications",
        "certification",
        "certificates",
        "licenses",
        "licences",
        "licenses and certifications",
        "licenses & certifications",
        "certifications and licenses",
        "certifications & licenses",
        "credentials",
        "professional certifications",
        "technical certifications",
        "industry certifications",
        "accreditations",
        "online certificates",
    ],

    # ================================================================
    # 6. Projects
    # ================================================================
    "projects": [
        "projects",
        "project experience",
        "key projects",
        "personal projects",
        "academic projects",
        "portfolio",
        "project highlights",
        "selected projects",
        "recent projects",
        "side projects",
        "open source projects",
        "github projects",
        "professional projects",
        "major projects",
        "some of my projects",
        "main university projects",
        "projects in university",
        "graduation project",
        "capstone project",
    ],

    # ================================================================
    # 7. Languages
    # ================================================================
    "languages": [
        "languages",
        "language",
        "language skills",
        "language proficiency",
        "foreign languages",
        "spoken languages",
        "written languages",
        "language abilities",
        "multilingual",
        "bilingual",
    ],

    # ================================================================
    # 8. Volunteer
    # ================================================================
    "volunteer": [
        "volunteer",
        "volunteering",
        "volunteer experience",
        "volunteer work",
        "community service",
        "community involvement",
        "community engagement",
        "civic engagement",
        "charity work",
        "pro bono",
        "non profit",
        "non-profit",
        "ngo",
        "social work",
        "social service",
        "community work",
    ],

    # ================================================================
    # 9. Awards / Achievements
    # ================================================================
    "awards": [
        "awards",
        "honors",
        "honours",
        "achievements",
        "accomplishments",
        "recognition",
        "recognitions",
        "accolades",
        "awards and honors",
        "awards & honors",
        "honors and awards",
        "honors & awards",
        "distinctions",
        "prizes",
        "key achievements",
        "notable achievements",
        "professional achievements",
        "academic achievements",
        "academic achievement",
        "research achievements",
        "major achievements",
        "competitions",
        "bootcamps and achievements",
    ],

    # ================================================================
    # 10. Publications / Research
    # ================================================================
    "publications": [
        "publications",
        "published work",
        "papers",
        "articles",
        "journals",
        "publications and research",
        "academic publications",
        "research publications",
        "conference papers",
        "books",
        "chapters",
        "thesis",
        "dissertation",
        "patents",
        "white papers",
        "technical papers",
        "peer reviewed journal publications",
        "peer-reviewed journal publications",
    ],

    # ================================================================
    # 11. Interests
    # ================================================================
    "interests": [
        "interests",
        "hobbies",
        "activities",
        "personal interests",
        "extracurricular",
        "extracurricular activities",
        "extra curriculum activities",
        "extra-curricular activities",
        "hobbies and interests",
        "leisure activities",
        "personal activities",
        "outside interests",
        "passions",
        "pastimes",
    ],

    # ================================================================
    # 12. References
    # ================================================================
    "references": [
        "references",
        "referees",
        "recommendations",
        "professional references",
        "personal references",
        "letters of recommendation",
        "testimonials",
    ],

    # ================================================================
    # 13. Courses / Training
    # ================================================================
    "courses": [
        "courses",
        "coursework",
        "relevant coursework",
        "academic courses",
        "professional courses",
        "online courses",
        "mooc",
        "training",
        "training courses",
        "workshops",
        "seminars",
        "webinars",
        "my training courses",
        "extra courses",
        "extracurricular courses",
        "udemy course",
        "courses and books",
        "courses & books",
        "training and scholarships",
        "professional development",
    ],

    # ================================================================
    # 14. Bootcamps
    # ================================================================
    "bootcamps": [
        "bootcamps",
        "bootcamp",
        "coding bootcamp",
        "tech bootcamp",
        "intensive training",
        "immersive program",
        "bootcamps and courses",
    ],

    # ================================================================
    # 15. Internships
    # ================================================================
    "internships": [
        "internships",
        "internship",
        "internship experience",
        "summer internship",
        "co-op",
        "co op",
        "trainee",
        "traineeship",
        "apprenticeship",
    ],

    # ================================================================
    # 16. Freelance
    # ================================================================
    "freelance": [
        "freelance",
        "freelancing",
        "freelance work",
        "freelance experience",
        "freelancing experience",
        "self employed",
        "self-employed",
        "independent contractor",
        "contract work",
        "consulting",
    ],

    # ================================================================
    # 17. Leadership
    # ================================================================
    "leadership": [
        "leadership",
        "leadership experience",
        "leadership roles",
        "management experience",
        "team lead",
        "supervisor",
        "mentor",
        "coaching",
        "guidance",
    ],

    # ================================================================
    # 18. Organizations / Memberships
    # ================================================================
    "organizations": [
        "organizations",
        "memberships",
        "professional memberships",
        "affiliations",
        "associations",
        "societies",
        "professional associations",
        "industry memberships",
        "clubs",
    ],

    # ================================================================
    # 19. Military
    # ================================================================
    "military": [
        "military status",
        "military service",
        "army",
        "navy",
        "air force",
        "conscription",
        "national service",
    ],

    # ================================================================
    # 20. Additional Information
    # ================================================================
    "additional_info": [
        "additional information",
        "additional info",
        "further information",
        "other information",
        "miscellaneous",
        "additional",
    ],

    # ================================================================
    # 21. Research Fields
    # ================================================================
    "fields": [
        "fields",
        "research fields",
        "research interests",
        "areas of research",
        "research areas",
        "specialization",
        "specializations",
    ],

    # ================================================================
    # 22. Programs / Software Programs
    # ================================================================
    "programs": [
        "programs",
        "software programs",
        "computer programs",
        "applications",
    ],

    # ================================================================
    # 23. Contact
    # ================================================================
    "contact": [
        "contact",
        "contact information",
        "contact details",
        "personal details",
        "get in touch",
        "reach me",
        "how to reach me",
    ],
}


# =====================================================================
# Priority للألفاظ المتداخلة
# =====================================================================
# هذا للتوثيق ولاحقاً ممكن SectionExtractor يستخدمه لو قررنا نسمح
# بتكرار keyword بين أكثر من قسم.
# حالياً SECTION_KEYWORDS منظف بحيث لا توجد duplicates مقصودة.
# =====================================================================

AMBIGUOUS_KEYWORD_PRIORITY = {
    "strengths": "skills",
    "key strengths": "skills",
    "professional strengths": "skills",
    "graduation project": "projects",
    "capstone project": "projects",
    "social work": "volunteer",
    "social service": "volunteer",
    "community work": "volunteer",
    "training": "courses",
    "professional development": "courses",
    "language and computer skills": "skills",
}


# =====================================================================
# الأقسام المطلوبة
# =====================================================================

REQUIRED_SECTIONS = [
    "summary",
    "experience",
    "education",
    "skills",
]


# =====================================================================
# الأقسام الاختيارية
# =====================================================================

OPTIONAL_SECTIONS = [
    "certifications",
    "projects",
    "languages",
    "volunteer",
    "awards",
    "publications",
    "courses",
    "internships",
    "bootcamps",
    "freelance",
    "leadership",
    "organizations",
    "military",
    "interests",
    "references",
    "additional_info",
    "fields",
    "programs",
    "contact",
]


# =====================================================================
# ترتيب الأقسام المثالي
# =====================================================================

IDEAL_SECTION_ORDER = [
    "contact_header",
    "summary",
    "experience",
    "education",
    "skills",
    "certifications",
    "projects",
    "internships",
    "freelance",
    "bootcamps",
    "courses",
    "languages",
    "awards",
    "publications",
    "leadership",
    "volunteer",
    "organizations",
    "military",
    "interests",
    "references",
    "additional_info",
    "fields",
    "programs",
    "contact",
]


# =====================================================================
# نصائح تحسين لكل قسم
# =====================================================================

SECTION_TIPS = {
    "summary": [
        "Keep it 3-5 sentences.",
        "Focus on achievements, not responsibilities.",
        "Mention key skills relevant to the target job.",
        "Mention years of experience when available.",
        "Customize it for the target role.",
    ],

    "experience": [
        "Use bullet points.",
        "Start each bullet with a strong action verb.",
        "Add numbers, percentages, and measurable results.",
        "Mention start and end dates.",
        "Focus on outcomes and achievements.",
        "Use the format: action + result + metric.",
    ],

    "education": [
        "Mention the full degree name.",
        "Add university or institution name.",
        "Add graduation year when useful.",
        "Mention GPA only if it is strong.",
        "Include major or specialization.",
    ],

    "skills": [
        "Group skills by category.",
        "Use keywords from the job description.",
        "Prioritize the most relevant skills.",
        "Avoid very basic skills unless required.",
    ],

    "certifications": [
        "Mention the full certification name.",
        "Add the issuing organization.",
        "Add issue date or expiration date when relevant.",
    ],

    "projects": [
        "Mention the project name.",
        "Describe your role.",
        "Mention technologies used.",
        "Add project link when available.",
        "Mention impact or results.",
    ],

    "languages": [
        "Mention proficiency level.",
        "Add language certificates when available.",
    ],

    "courses": [
        "Mention course name.",
        "Add platform or institution.",
        "Add completion date when relevant.",
        "Focus on job-relevant courses.",
    ],

    "internships": [
        "Mention company name and role.",
        "Add start and end dates.",
        "Describe achievements during the internship.",
        "Mention skills gained.",
    ],

    "awards": [
        "Mention award name.",
        "Add issuing organization.",
        "Add year received.",
        "Briefly explain why it matters.",
    ],

    "volunteer": [
        "Mention organization name.",
        "Describe your contribution.",
        "Mention impact when possible.",
    ],

    "publications": [
        "Mention title.",
        "Add publisher, journal, or conference.",
        "Add date.",
        "Include link or DOI if available.",
    ],
}