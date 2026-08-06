"""One source of truth for deterministic ATS policy constants and messages."""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_WEIGHTS = {
    "text_extractability": 15,
    "section_structure": 20,
    "layout_safety": 20,
    "formatting_consistency": 15,
    "content_clarity": 15,
    "contact_accessibility": 5,
    "consistency": 10,
}

CATEGORY_PENALTY_CAPS = dict(CATEGORY_WEIGHTS)

ISSUE_TO_SCORE_CATEGORY = {
    "extraction": "text_extractability",
    "structure": "section_structure",
    "layout": "layout_safety",
    "accessibility": "layout_safety",
    "formatting": "formatting_consistency",
    "content": "content_clarity",
    "contact": "contact_accessibility",
    "consistency": "consistency",
}

SCORE_LABELS = ((90, "excellent"), (75, "good"), (55, "fair"), (0, "poor"))
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
CATEGORY_ORDER = {
    "extraction": 0,
    "structure": 1,
    "layout": 2,
    "formatting": 3,
    "content": 4,
    "contact": 5,
    "consistency": 6,
    "accessibility": 7,
    "job_match": 8,
}


@dataclass(frozen=True)
class IssueDefinition:
    category: str
    severity: str
    penalty: int
    en: tuple[str, str, str]
    ar: tuple[str, str, str]


def _definition(category, severity, penalty, en, ar):
    return IssueDefinition(category, severity, penalty, en, ar)


ISSUE_DEFINITIONS = {
    "EMPTY_OR_UNREADABLE_TEXT": _definition(
        "extraction",
        "critical",
        15,
        (
            "Resume text is unreadable",
            "No reliable resume text is available for ATS parsing.",
            "Provide a text-based PDF or DOCX, or run verified OCR.",
        ),
        (
            "نص السيرة غير قابل للقراءة",
            "لا يتوفر نص موثوق يمكن لنظام التوظيف تحليله.",
            "استخدم ملف PDF نصياً أو DOCX، أو شغّل OCR موثوقاً.",
        ),
    ),
    "LOW_TEXT_VOLUME": _definition(
        "extraction",
        "high",
        10,
        (
            "Very little text was extracted",
            "The extracted text is too short for reliable parsing.",
            "Verify that the document contains selectable text and that all pages were extracted.",
        ),
        (
            "النص المستخرج قليل جداً",
            "النص المستخرج أقصر من أن يسمح بتحليل موثوق.",
            "تحقق من وجود نص قابل للتحديد ومن استخراج جميع الصفحات.",
        ),
    ),
    "LOW_EXTRACTION_QUALITY": _definition(
        "extraction",
        "high",
        8,
        (
            "Extraction quality needs review",
            "The extraction quality signal is below the reliable range.",
            "Review the exported text and correct the source document if content is missing or reordered.",
        ),
        (
            "جودة الاستخراج تحتاج مراجعة",
            "مؤشر جودة الاستخراج أقل من النطاق الموثوق.",
            "راجع النص الناتج وصحح الملف إذا كان المحتوى ناقصاً أو بترتيب خاطئ.",
        ),
    ),
    "OCR_REVIEW_REQUIRED": _definition(
        "extraction",
        "medium",
        3,
        (
            "OCR-derived text needs verification",
            "Some or all text was recovered with OCR and may contain recognition errors.",
            "Compare the extracted text with the visible document before submitting.",
        ),
        (
            "النص المستخرج عبر OCR يحتاج تحققاً",
            "تم استرداد بعض النص أو كله عبر OCR وقد يحتوي أخطاء تعرف.",
            "قارن النص المستخرج بالمستند المرئي قبل الإرسال.",
        ),
    ),
    "PAGE_OCR_REVIEW_REQUIRED": _definition(
        "extraction",
        "medium",
        3,
        (
            "OCR-derived page text needs verification",
            "One or more document pages were recovered with OCR and may contain recognition errors.",
            "Compare the OCR-derived pages with the visible document before submitting.",
        ),
        (
            "نص صفحة مستخرج عبر OCR يحتاج إلى تحقق",
            "تم استرداد صفحة واحدة أو أكثر عبر OCR وقد تحتوي على أخطاء تعرّف.",
            "قارن الصفحات المستخرجة عبر OCR بالمستند المرئي قبل الإرسال.",
        ),
    ),
    "CONTACT_OCR_REVIEW_REQUIRED": _definition(
        "contact",
        "medium",
        2,
        (
            "OCR-recovered contact details need verification",
            "At least one core contact field was recovered from an image rather than accessible text.",
            "Verify the recovered email and phone, then add them as selectable text when possible.",
        ),
        (
            "بيانات اتصال مستردة عبر OCR تحتاج إلى تحقق",
            "تم استرداد حقل اتصال أساسي واحد على الأقل من صورة بدلاً من نص قابل للوصول.",
            "تحقق من البريد والهاتف المستردين وأضفهما كنص قابل للتحديد عند الإمكان.",
        ),
    ),
    "CONTACT_MIXED_SOURCE_REVIEW_REQUIRED": _definition(
        "contact",
        "low",
        1,
        (
            "One core contact detail relies on OCR",
            "Email or phone is accessible text, but the other core field was recovered from an image.",
            "Verify the OCR-derived field and add it as selectable text when possible.",
        ),
        (
            "حقل اتصال أساسي واحد يعتمد على OCR",
            "البريد أو الهاتف نص قابل للوصول، لكن الحقل الأساسي الآخر مسترد من صورة.",
            "تحقق من الحقل المسترد وأضفه كنص قابل للتحديد عند الإمكان.",
        ),
    ),
    "CONTACT_PARTIAL_OCR_REVIEW_REQUIRED": _definition(
        "contact",
        "high",
        3,
        (
            "Contact OCR recovery is incomplete",
            "Core contact details were only partially recovered from an image.",
            "Verify every core contact field and add missing details as selectable text.",
        ),
        (
            "استرداد بيانات الاتصال عبر OCR غير مكتمل",
            "تم استرداد بيانات الاتصال الأساسية جزئياً فقط من صورة.",
            "تحقق من كل حقل اتصال أساسي وأضف البيانات الناقصة كنص قابل للتحديد.",
        ),
    ),
    "CONTACT_OCR_FAILED": _definition(
        "contact",
        "high",
        3,
        (
            "Contact OCR did not produce a reliable result",
            "Contact-region OCR was attempted, but its result was rejected or unavailable.",
            "Add core contact details as selectable text and verify them visually.",
        ),
        (
            "لم ينتج OCR لبيانات الاتصال نتيجة موثوقة",
            "تمت محاولة OCR لمنطقة الاتصال، لكن النتيجة رُفضت أو لم تتوفر.",
            "أضف بيانات الاتصال الأساسية كنص قابل للتحديد وتحقق منها بصرياً.",
        ),
    ),
    "BROKEN_CHARACTER_ENCODING": _definition(
        "extraction",
        "high",
        6,
        (
            "Broken characters were detected",
            "Replacement or mojibake characters reduce parser reliability.",
            "Re-export the resume with embedded Unicode fonts and verify the extracted text.",
        ),
        (
            "تم اكتشاف أحرف تالفة",
            "الأحرف البديلة أو المشوهة تقلل موثوقية التحليل.",
            "أعد تصدير السيرة بخطوط Unicode مضمنة وتحقق من النص.",
        ),
    ),
    "REPEATED_PAGE_FURNITURE": _definition(
        "extraction",
        "medium",
        3,
        (
            "Repeated headers or footers affect extraction",
            "Repeated page elements can be mixed into resume content.",
            "Keep repeating page furniture minimal and verify the reading order.",
        ),
        (
            "ترويسات أو تذييلات متكررة تؤثر في الاستخراج",
            "قد تختلط عناصر الصفحات المتكررة بمحتوى السيرة.",
            "قلل العناصر المتكررة وتحقق من ترتيب القراءة.",
        ),
    ),
    "MISSING_SUMMARY": _definition(
        "structure",
        "low",
        3,
        (
            "Professional summary is absent",
            "No clear summary or profile section was detected.",
            "Consider a concise evidence-based summary when it helps explain the target role.",
        ),
        (
            "الملخص المهني غير موجود",
            "لم يتم اكتشاف قسم ملخص أو نبذة واضح.",
            "فكّر في ملخص موجز مبني على الأدلة عندما يساعد في توضيح الدور المستهدف.",
        ),
    ),
    "MISSING_SKILLS_SECTION": _definition(
        "structure",
        "medium",
        6,
        (
            "Skills lack a dedicated section",
            "Skills exist in the resume but are not grouped under a clear skills heading.",
            "Add a clearly labeled skills section using only skills supported by the resume.",
        ),
        (
            "لا يوجد قسم واضح للمهارات",
            "توجد مهارات في السيرة لكنها غير مجمعة تحت عنوان واضح.",
            "أضف قسم مهارات واضحاً يتضمن المهارات المدعومة فقط.",
        ),
    ),
    "MISSING_EXPERIENCE": _definition(
        "structure",
        "high",
        10,
        (
            "Experience section is absent",
            "No professional, internship, or volunteer experience was detected.",
            "Add verified relevant experience when applicable; never create experience to fill the section.",
        ),
        (
            "قسم الخبرة غير موجود",
            "لم يتم اكتشاف خبرة مهنية أو تدريبية أو تطوعية.",
            "أضف خبرة حقيقية ذات صلة عند توفرها، ولا تنشئ خبرة لملء القسم.",
        ),
    ),
    "STUDENT_EXPERIENCE_OPTIONAL": _definition(
        "structure",
        "info",
        0,
        (
            "Experience was not detected",
            "The education/project profile may represent a student or early-career resume.",
            "Add internships, projects, or volunteer work only when they are genuine.",
        ),
        (
            "لم يتم اكتشاف خبرة",
            "قد تمثل بنية التعليم والمشاريع سيرة لطالب أو حديث التخرج.",
            "أضف التدريب أو المشاريع أو التطوع فقط عندما تكون حقيقية.",
        ),
    ),
    "DUPLICATE_SECTION_HEADING": _definition(
        "structure",
        "medium",
        4,
        (
            "A section heading is duplicated",
            "Repeated headings can fragment the parser's section map.",
            "Merge duplicate sections under one standard heading.",
        ),
        (
            "عنوان قسم مكرر",
            "العناوين المكررة قد تجزئ خريطة الأقسام لدى المحلل.",
            "ادمج الأقسام المكررة تحت عنوان قياسي واحد.",
        ),
    ),
    "AMBIGUOUS_SECTION_HEADING": _definition(
        "structure",
        "low",
        2,
        (
            "A section heading is ambiguous",
            "A non-standard heading may not clearly identify its content.",
            "Use a familiar Arabic or English section heading.",
        ),
        (
            "عنوان قسم غامض",
            "قد لا يوضح العنوان غير القياسي محتوى القسم.",
            "استخدم عنوان قسم عربي أو إنجليزي مألوفاً.",
        ),
    ),
    "FRAGMENTED_SECTION": _definition(
        "structure",
        "low",
        2,
        (
            "A section is unusually fragmented",
            "A detected section contains too little connected content.",
            "Combine related content and keep its heading attached to the section.",
        ),
        (
            "قسم مجزأ بشكل غير معتاد",
            "يحتوي قسم مكتشف على محتوى مترابط قليل جداً.",
            "اجمع المحتوى المرتبط وأبق العنوان متصلاً بالقسم.",
        ),
    ),
    "EXCESSIVE_SECTION_COUNT": _definition(
        "structure",
        "low",
        2,
        (
            "Too many sections were detected",
            "Excessive fragmentation can make parsing and scanning harder.",
            "Consolidate closely related sections.",
        ),
        (
            "تم اكتشاف عدد كبير من الأقسام",
            "التجزئة الزائدة قد تصعّب التحليل والقراءة.",
            "ادمج الأقسام المتقاربة في المعنى.",
        ),
    ),
    "EXPERIENCE_ENTRY_UNCLEAR": _definition(
        "content",
        "medium",
        4,
        (
            "An experience entry is unclear",
            "A role or company could not be separated reliably in an experience entry.",
            "Use a consistent role, company, location, and date structure.",
        ),
        (
            "إدخال خبرة غير واضح",
            "تعذر فصل المسمى أو الشركة بشكل موثوق في أحد إدخالات الخبرة.",
            "استخدم بنية ثابتة للمسمى والشركة والموقع والتاريخ.",
        ),
    ),
    "PROJECT_DESCRIPTION_MISSING": _definition(
        "content",
        "low",
        2,
        (
            "A project lacks a description",
            "A project name is present without enough descriptive context.",
            "Add a concise factual description of the work actually completed.",
        ),
        (
            "مشروع بلا وصف",
            "يوجد اسم مشروع دون سياق وصفي كافٍ.",
            "أضف وصفاً موجزاً وواقعياً للعمل المنجز فعلاً.",
        ),
    ),
    "EDUCATION_ENTRY_UNCLEAR": _definition(
        "content",
        "low",
        2,
        (
            "An education entry is unclear",
            "The degree or institution could not be identified clearly.",
            "Separate the degree, field, institution, and dates.",
        ),
        (
            "إدخال تعليمي غير واضح",
            "تعذر تحديد الدرجة أو المؤسسة بوضوح.",
            "افصل الدرجة والتخصص والمؤسسة والتواريخ.",
        ),
    ),
    "MULTI_COLUMN_READING_ORDER_RISK": _definition(
        "layout",
        "high",
        8,
        (
            "Possible multi-column reading-order risk",
            "Columns may be read in an incorrect order by parsers.",
            "Use a single-column layout or verify the exported reading order.",
        ),
        (
            "خطر محتمل في ترتيب قراءة الأعمدة",
            "قد تُقرأ الأعمدة بترتيب غير صحيح لدى بعض المحللات.",
            "استخدم تخطيط عمود واحد أو تحقق من ترتيب النص المصدر.",
        ),
    ),
    "TEXT_BOX_READING_ORDER_RISK": _definition(
        "layout",
        "high",
        8,
        (
            "Positioned text boxes may alter reading order",
            "Several text boxes or floating shapes carry document text.",
            "Move important text into the normal document flow.",
        ),
        (
            "مربعات النص قد تغيّر ترتيب القراءة",
            "تحمل عدة مربعات نص أو أشكال عائمة محتوى المستند.",
            "انقل النص المهم إلى التدفق العادي للمستند.",
        ),
    ),
    "CONTENT_CRITICAL_TABLE": _definition(
        "layout",
        "medium",
        5,
        (
            "A content table needs reading-order review",
            "A table contains substantial resume text and its reading order is not verified.",
            "Verify cell reading order or provide a text-first alternative.",
        ),
        (
            "جدول محتوى يحتاج مراجعة ترتيب القراءة",
            "يحتوي جدول على نص مهم ولم يتم التحقق من ترتيب قراءته.",
            "تحقق من ترتيب الخلايا أو وفر نسخة نصية بديلة.",
        ),
    ),
    "IMAGE_ONLY_CONTACT_INFORMATION": _definition(
        "contact",
        "high",
        5,
        (
            "Contact information may exist only as an image",
            "Important contact data is not represented as selectable text.",
            "Add visible text labels for every required contact field.",
        ),
        (
            "قد تكون معلومات الاتصال صورة فقط",
            "بيانات اتصال مهمة غير ممثلة كنص قابل للتحديد.",
            "أضف نصاً ظاهراً لكل حقل اتصال مطلوب.",
        ),
    ),
    "TEXT_OVERLAP_RISK": _definition(
        "layout",
        "high",
        8,
        (
            "Overlapping text was detected",
            "Overlapping text spans can be omitted or reordered during parsing.",
            "Fix overlapping objects and re-export the document.",
        ),
        (
            "تم اكتشاف نص متداخل",
            "قد تُحذف المقاطع المتداخلة أو يتغير ترتيبها أثناء التحليل.",
            "أصلح العناصر المتداخلة وأعد تصدير المستند.",
        ),
    ),
    "VERY_SMALL_FONT": _definition(
        "layout",
        "medium",
        4,
        (
            "Very small text was detected",
            "Some text uses a font size below a practical readability threshold.",
            "Use readable body text and verify that no important detail is compressed.",
        ),
        (
            "تم اكتشاف خط صغير جداً",
            "يستخدم بعض النص حجماً أقل من حد القراءة العملي.",
            "استخدم نصاً مقروءاً وتحقق من عدم ضغط التفاصيل المهمة.",
        ),
    ),
    "EXCESSIVE_FONT_VARIATION": _definition(
        "formatting",
        "low",
        2,
        (
            "Many font styles were detected",
            "Excessive font variation can make headings and body text inconsistent.",
            "Use a small, consistent font family set.",
        ),
        (
            "تم اكتشاف تنوع كبير في الخطوط",
            "تنوع الخطوط الزائد قد يجعل العناوين والنص غير متسقين.",
            "استخدم مجموعة صغيرة ومتسقة من الخطوط.",
        ),
    ),
    "LOW_CONTRAST_TEXT": _definition(
        "accessibility",
        "high",
        6,
        (
            "Low-contrast text may be unreadable",
            "Available metadata indicates poor text contrast.",
            "Use strong foreground/background contrast; color alone is not a problem.",
        ),
        (
            "قد يكون النص منخفض التباين غير مقروء",
            "تشير البيانات المتاحة إلى تباين ضعيف للنص.",
            "استخدم تبايناً واضحاً؛ وجود اللون وحده ليس مشكلة.",
        ),
    ),
    "UNRESOLVED_TEMPLATE_CONTENT": _definition(
        "content",
        "critical",
        12,
        (
            "Unresolved template content remains",
            "Placeholder instructions or values are still present in the resume.",
            "Replace every placeholder with verified candidate content or remove it.",
        ),
        (
            "ما زال محتوى القالب موجوداً",
            "تعليمات أو قيم افتراضية ما زالت ظاهرة في السيرة.",
            "استبدل كل عنصر افتراضي بمحتوى حقيقي موثوق أو احذفه.",
        ),
    ),
    "TEMPLATE_COPYRIGHT_REMAINS": _definition(
        "content",
        "medium",
        4,
        (
            "Template or sample attribution remains",
            "Sample-resume or template copyright text appears in the content.",
            "Remove template remnants that are not candidate information.",
        ),
        (
            "ما زال نص القالب أو حقوقه ظاهراً",
            "ظهر نص خاص بعينة سيرة أو حقوق قالب ضمن المحتوى.",
            "احذف بقايا القالب التي لا تمثل معلومات المرشح.",
        ),
    ),
    "INCONSISTENT_DATE_FORMATS": _definition(
        "consistency",
        "medium",
        4,
        (
            "Date formats are inconsistent",
            "Experience or education dates use multiple incompatible styles.",
            "Choose one clear date style and apply it consistently.",
        ),
        (
            "تنسيقات التواريخ غير متسقة",
            "تستخدم تواريخ الخبرة أو التعليم عدة أنماط غير متوافقة.",
            "اختر نمط تاريخ واضحاً وطبقه باستمرار.",
        ),
    ),
    "INCONSISTENT_BULLET_STYLES": _definition(
        "formatting",
        "low",
        2,
        (
            "Bullet styles are inconsistent",
            "Multiple bullet characters are used for comparable content.",
            "Use one standard bullet style throughout.",
        ),
        (
            "أنماط التعداد غير متسقة",
            "تُستخدم رموز تعداد مختلفة لمحتوى متشابه.",
            "استخدم نمط تعداد قياسياً واحداً.",
        ),
    ),
    "INCONSISTENT_HEADING_CASE": _definition(
        "formatting",
        "low",
        1,
        (
            "English heading capitalization is inconsistent",
            "Comparable English headings use mixed capitalization styles.",
            "Use one capitalization style for English section headings.",
        ),
        (
            "كتابة العناوين الإنجليزية غير متسقة",
            "تستخدم العناوين الإنجليزية أنماط أحرف مختلفة.",
            "استخدم نمطاً واحداً لكتابة عناوين الأقسام الإنجليزية.",
        ),
    ),
    "DUPLICATE_WHITESPACE": _definition(
        "formatting",
        "low",
        1,
        (
            "Repeated spacing was detected",
            "Some extracted lines contain unnecessary repeated spaces.",
            "Normalize spacing and re-export the document.",
        ),
        (
            "تم اكتشاف مسافات مكررة",
            "تحتوي بعض الأسطر على مسافات زائدة.",
            "وحّد المسافات وأعد تصدير المستند.",
        ),
    ),
    "BROKEN_BULLET_CHARACTERS": _definition(
        "formatting",
        "medium",
        3,
        (
            "Broken bullet characters were detected",
            "One or more bullet glyphs were not encoded cleanly.",
            "Replace them with a standard Unicode bullet or plain hyphen.",
        ),
        (
            "تم اكتشاف رموز تعداد تالفة",
            "لم تُرمّز بعض رموز التعداد بشكل صحيح.",
            "استبدلها برمز Unicode قياسي أو شرطة عادية.",
        ),
    ),
    "MALFORMED_LINK": _definition(
        "contact",
        "medium",
        3,
        (
            "A link appears malformed",
            "A URL-like value is incomplete or cannot be parsed reliably.",
            "Use a complete HTTPS URL with visible text.",
        ),
        (
            "رابط غير صالح",
            "قيمة شبيهة بالرابط ناقصة أو يتعذر تحليلها بثقة.",
            "استخدم رابط HTTPS كاملاً بنص ظاهر.",
        ),
    ),
    "INCONSISTENT_CURRENT_LABEL": _definition(
        "consistency",
        "low",
        2,
        (
            "Current-role labels are inconsistent",
            "Both “Present” and “Current” styles are used for active roles.",
            "Choose one label for ongoing date ranges.",
        ),
        (
            "تسميات الوظيفة الحالية غير متسقة",
            "تُستخدم تسميات إنجليزية مختلفة للأدوار المستمرة.",
            "اختر تسمية واحدة للنطاقات الزمنية المستمرة.",
        ),
    ),
    "VERY_LONG_PARAGRAPH": _definition(
        "content",
        "medium",
        3,
        (
            "A paragraph is difficult to scan",
            "A long block of text may hide important facts from recruiters and parsers.",
            "Split it into concise factual bullets without adding claims.",
        ),
        (
            "فقرة يصعب مسحها بصرياً",
            "قد تخفي كتلة نصية طويلة معلومات مهمة عن القارئ والمحلل.",
            "قسّمها إلى نقاط موجزة وواقعية دون إضافة ادعاءات.",
        ),
    ),
    "GENERIC_SHORT_BULLET": _definition(
        "content",
        "low",
        2,
        (
            "A bullet is too generic",
            "A very short experience bullet provides little actionable context.",
            "Clarify the existing action and object without inventing outcomes or metrics.",
        ),
        (
            "نقطة خبرة عامة جداً",
            "نقطة الخبرة القصيرة جداً لا تقدم سياقاً مفيداً.",
            "وضّح الفعل والموضوع الموجودين دون اختراع نتائج أو أرقام.",
        ),
    ),
    "DUPLICATE_CONTENT": _definition(
        "consistency",
        "medium",
        4,
        (
            "Duplicate content was detected",
            "Substantially identical content appears more than once.",
            "Keep one authoritative copy unless repetition is intentional and necessary.",
        ),
        (
            "تم اكتشاف محتوى مكرر",
            "يظهر محتوى متطابق إلى حد كبير أكثر من مرة.",
            "احتفظ بنسخة واحدة إلا إذا كان التكرار مقصوداً وضرورياً.",
        ),
    ),
    "MISSING_EMAIL": _definition(
        "contact",
        "medium",
        3,
        (
            "Email address is missing",
            "No email address was detected as selectable text.",
            "Add a valid email address if the candidate wants to be contacted by email.",
        ),
        (
            "البريد الإلكتروني غير موجود",
            "لم يتم اكتشاف بريد إلكتروني كنص قابل للتحديد.",
            "أضف بريداً صالحاً إذا أراد المرشح التواصل عبر البريد.",
        ),
    ),
    "MISSING_PHONE": _definition(
        "contact",
        "medium",
        2,
        (
            "Phone number is missing",
            "No phone number was detected as selectable text.",
            "Add a valid phone number when appropriate for the application.",
        ),
        (
            "رقم الهاتف غير موجود",
            "لم يتم اكتشاف رقم هاتف كنص قابل للتحديد.",
            "أضف رقماً صالحاً عندما يكون مناسباً للتقديم.",
        ),
    ),
    "MISSING_NAME": _definition(
        "contact",
        "low",
        1,
        (
            "Candidate name is missing",
            "No candidate name was detected in the contact information.",
            "Add the candidate's real name as visible text.",
        ),
        (
            "اسم المرشح غير موجود",
            "لم يتم اكتشاف اسم المرشح في معلومات الاتصال.",
            "أضف الاسم الحقيقي للمرشح كنص ظاهر.",
        ),
    ),
}

STRENGTH_TITLES = {
    "TEXT_EXTRACTION_HEALTHY": ("Text extraction is healthy", "استخراج النص جيد"),
    "CLEAR_SECTION_STRUCTURE": (
        "Core sections are clearly structured",
        "الأقسام الأساسية منظمة بوضوح",
    ),
    "SINGLE_COLUMN_LAYOUT": (
        "Single-column reading order is parser-friendly",
        "ترتيب العمود الواحد ملائم للتحليل",
    ),
    "VERIFIED_COLUMN_READING_ORDER": (
        "Column reading order was reconstructed",
        "تم التحقق من ترتيب قراءة الأعمدة",
    ),
    "CONTACT_TEXT_ACCESSIBLE": (
        "Required contact details are selectable text",
        "بيانات الاتصال الأساسية متاحة كنص",
    ),
    "DEDICATED_SKILLS_SECTION": ("A dedicated skills section is present", "يوجد قسم واضح للمهارات"),
    "COLOR_NOT_PENALIZED": (
        "Color is present without a verified readability failure",
        "الألوان موجودة دون مشكلة قراءة مثبتة",
    ),
    "TABLE_TEXT_EXTRACTED": ("Table content is available as text", "محتوى الجدول متاح كنص"),
}

STANDARD_SECTION_KEYS = {
    "summary",
    "profile",
    "objective",
    "skills",
    "experience",
    "education",
    "projects",
    "languages",
    "certifications",
    "contact",
    "volunteer",
    "awards",
    "achievements",
}

PLACEHOLDER_PATTERNS = (
    r"(?i)\b(?:your name|name here|student name|candidate name|applicant name|"
    r"insert (?:text|date)|lorem ipsum)\b",
    r"(?i)\b(?:describe in a few lines|sample (?:resume|résumé|cv)|"
    r"(?:resume|résumé|cv) (?:sample|template|example))\b",
    r"(?i)\b(?:(?:19|20)xx|yyyy)\b",
    r"(?:اكتب هنا|الاسم هنا|اسم الشركة|المسمى الوظيفي|أدخل النص|نموذج سيرة)",
)
COPYRIGHT_PATTERNS = (
    r"(?i)\b(?:copyright|all rights reserved|template by|designed by)\b",
    r"(?:حقوق النشر|جميع الحقوق محفوظة|تصميم القالب)",
)

JOB_KEYWORD_ALIASES = {
    "python": ("python", "بايثون"),
    "javascript": ("javascript", "java script", "js", "جافاسكربت"),
    "typescript": ("typescript", "ts", "تايب سكربت"),
    "react": ("react", "reactjs", "react.js", "رياكت"),
    "node.js": ("node", "nodejs", "node.js"),
    "sql": ("sql", "structured query language", "قواعد البيانات"),
    "postgresql": ("postgresql", "postgres"),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure", "microsoft azure"),
    "docker": ("docker", "دوكر"),
    "kubernetes": ("kubernetes", "k8s", "كوبرنيتس"),
    "machine learning": ("machine learning", "ml", "تعلم الآلة", "تعلم آلي"),
    "artificial intelligence": ("artificial intelligence", "ai", "ذكاء اصطناعي"),
    "data analysis": ("data analysis", "data analytics", "تحليل البيانات"),
    "project management": ("project management", "إدارة المشاريع"),
    "accounting": ("accounting", "محاسبة"),
    "financial analysis": ("financial analysis", "تحليل مالي"),
    "customer service": ("customer service", "customer support", "خدمة العملاء"),
    "communication": ("communication", "communications", "التواصل"),
    "leadership": ("leadership", "قيادة"),
    "agile": ("agile", "scrum", "أجايل"),
}

JOB_STOPWORDS = {
    "about",
    "after",
    "all",
    "also",
    "and",
    "are",
    "candidate",
    "company",
    "experience",
    "for",
    "from",
    "have",
    "ignore",
    "instructions",
    "job",
    "message",
    "must",
    "our",
    "please",
    "previous",
    "prompt",
    "required",
    "requirements",
    "resume",
    "role",
    "system",
    "that",
    "the",
    "this",
    "tool",
    "using",
    "with",
    "work",
    "years",
    "your",
    "على",
    "أن",
    "او",
    "أو",
    "إلى",
    "الى",
    "التي",
    "الذي",
    "خبرة",
    "سيرة",
    "شركة",
    "عمل",
    "في",
    "من",
    "هذا",
    "هذه",
    "يجب",
}
