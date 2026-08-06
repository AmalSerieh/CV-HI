# =====================================================================
# 🧹 text_cleaner.py - تنظيف ومعالجة نصوص السير الذاتية
# =====================================================================
# يدعم:
# - تنظيف نص CV مع الحفاظ على بنية الأسطر
# - تجهيز نسخة NLP للمطابقة والتحليل
# - حماية الاختصارات الأكاديمية مثل B.Sc. / Ph.D.
# - حماية المهارات التقنية مثل C++ / C# / .NET / Node.js / CI/CD
# - إصلاح أخطاء OCR بسيطة
# - إزالة artifacts مثل page 1 و 1 / 3
#
# ملاحظة مهمة:
# لا تستخدم clean() قبل ContactExtractor إذا كنت تريد استخراج الإيميل والروابط.
# الترتيب الصحيح:
#   raw_text = extracted["text"]
#   contact_info = contact_extractor.extract_all(raw_text)
#   cleaned_text = cleaner.clean(raw_text)
# =====================================================================

import re

try:
    import nltk
    from nltk.corpus import stopwords
except ImportError:  # Optional; basic cleaning remains fully functional.
    nltk = None
    stopwords = None

try:
    from cleantext import clean as clean_text
except ImportError:  # Optional; use the conservative local fallback below.
    clean_text = None


class TextCleaner:
    """تنظيف ومعالجة النص المستخرج من السيرة الذاتية"""

    # ================================================================
    # 🔒 عناصر محمية من التخريب أثناء التنظيف
    # ================================================================

    PROTECTED_SYMBOLS = {
        "°C": " DEGCELSIUS ",
        "°F": " DEGFAHRENHEIT ",
        "°": " DEGREE ",
        "±": " PLUSMINUS ",
        "²": " SQUARED ",
        "³": " CUBED ",
    }

    PROTECTED_ACRONYMS = {
        "B.Sc.": " BACHELORSCI ",
        "M.Sc.": " MASTERSCI ",
        "B.A.": " BACHELORARTS ",
        "M.A.": " MASTERARTS ",
        "B.Eng.": " BACHELORENG ",
        "M.Eng.": " MASTERENG ",
        "B.Tech.": " BACHELORTECH ",
        "M.Tech.": " MASTERTECH ",
        "Ph.D.": " PHDDEGREE ",
        "MBA": " MBADEGREE ",
        "BBA": " BBADEGREE ",
        "GPA": " GPASCORE ",
    }

    # مهم: سيتم تطبيق الحماية من الأطول للأقصر داخل _protect
    PROTECTED_TECH_SKILLS = {
        "Ruby on Rails": " RUBYONRAILSSKILL ",
        "React Native": " REACTNATIVESKILL ",
        "Tailwind CSS": " TAILWINDCSSSKILL ",
        "Material UI": " MATERIALUISKILL ",
        "Spring Boot": " SPRINGBOOTSKILL ",
        ".NET Core": " DOTNETCORESKILL ",

        "ASP.NET": " ASPNETSKILL ",
        "Express.js": " EXPRESSJSSKILL ",
        "React.js": " REACTJSSKILL ",
        "Node.js": " NODEJSSKILL ",
        "Next.js": " NEXTJSSKILL ",
        "Nuxt.js": " NUXTJSSKILL ",
        "Vue.js": " VUEJSSKILL ",

        "REST APIs": " RESTAPISSKILL ",
        "REST API": " RESTAPISKILL ",
        "GraphQL": " GRAPHQLSKILL ",
        "CI/CD": " CICDSKILL ",
        "PL/SQL": " PLSQLSKILL ",
        "T-SQL": " TSQLSKILL ",

        "SQL Server": " SQLSERVERSKILL ",
        "Power BI": " POWERBISKILL ",

        ".NET": " DOTNETSKILL ",
        "C++": " CPPSKILL ",
        "C#": " CSHARPSKILL ",
        "F#": " FSHARPSKILL ",
    }

    MONTHS = {
        "jan": "01",
        "feb": "02",
        "mar": "03",
        "apr": "04",
        "may": "05",
        "jun": "06",
        "jul": "07",
        "aug": "08",
        "sep": "09",
        "oct": "10",
        "nov": "11",
        "dec": "12",
    }

    OCR_MAP = {
        "Pyth0n": "Python",
        "Deve1oper": "Developer",
        "Experlence": "Experience",
        "experlence": "experience",
        "Sk1lls": "Skills",
        "Educatlon": "Education",
        "Certlfication": "Certification",
        "Certlfications": "Certifications",
    }

    _punkt_loaded = False
    _stopwords_loaded = False
    _cached_stopwords = set()

    # ================================================================
    # 🧱 Type Safety
    # ================================================================

    def _ensure_text(self, text) -> str:
        """
        التأكد أن المدخل نص وليس dict أو نوع آخر.

        مهم لأن TextExtractor.extract() يرجع dict.
        الصحيح:
            cleaner.clean(extracted["text"])

        الخطأ:
            cleaner.clean(extracted)
        """
        if text is None:
            return ""

        if isinstance(text, dict):
            raise TypeError(
                "TextCleaner expected a string, but got a dict. "
                "Use extracted['text'] instead of passing the whole extraction result."
            )

        if not isinstance(text, str):
            raise TypeError(
                f"TextCleaner expected str, got {type(text).__name__}"
            )

        return text

    # ================================================================
    # 🧹 Public Cleaning Methods
    # ================================================================

    def clean(self, text: str) -> str:
        """
        تنظيف محافظ للنص مع الحفاظ على بنية السيرة.

        هذه النسخة لا تستخدم clean-text لأنها مخصصة لنسخة العرض
        واكتشاف الأقسام، ويجب ألا تغيّر الكلمات أو تستبدل الإيميلات
        والروابط أو تُدخل placeholders داخل كلمات أخرى.

        مناسبة لـ:
        - SectionExtractor
        - Education / Experience extractors
        - حفظ analysis_text
        """
        text = self._ensure_text(text)

        if not text:
            return ""

        text = self.fix_ocr_errors(text)
        text = self.normalize_unicode_quotes(text)
        text = self.remove_page_artifacts(text)

        # تنظيف محافظ: نحافظ على bullets والأسطر والكلمات كما هي.
        text = self._cv_clean(
            text,
            preserve_bullets=True,
        )

        return text.strip()

    def clean_for_nlp(self, text: str) -> str:
        """
        تجهيز النص للـ NLP والـ matching.
        """
        text = self._ensure_text(text)

        if not text:
            return ""

        text = self.fix_ocr_errors(text)

        # مهم جداً قبل إزالة punctuation
        text = self.remove_page_artifacts(text)

        text = re.sub(
            r"(?im)^\s*(contact|email|e-mail|phone|mobile|website|linkedin|github)\s*:\s*.*$",
            " ",
            text,
        )

        # إزالة الإيميلات والروابط صراحة قبل no_punct
        text = re.sub(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            " ",
            text,
        )

        text = re.sub(
            r"\b(?:https?://|www\.)\S+|\b[a-zA-Z0-9-]+\.(?:com|net|org|edu|io|ai|co)\S*",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        text = self._protect(text)
        text = self._cv_clean(text)

        if clean_text is not None:
            text = clean_text(
                text,
                fix_unicode=True,
                to_ascii=False,
                lower=True,
                no_emoji=True,
                no_numbers=False,
                no_punct=True,
                replace_with_punct="",
                replace_with_url=" ",
                replace_with_email=" ",
            )
        else:
            text = re.sub(r"[^\w\s+#./-]", " ", text.casefold())

        text = self._restore_nlp(text)
        text = self.normalize_unicode_quotes(text)

        return re.sub(r"\s+", " ", text).strip()


    def clean_for_matching(self, text: str) -> str:
        """
        نسخة مخصصة للمطابقة أو حساب مدة الخبرة.

        هنا نستخدم normalize_dates لأن هذا مفيد للـ matching،
        لكن لا نستخدمه داخل clean() حتى لا نخسر معلومات التواريخ الأصلية.
        """
        text = self.clean_for_nlp(text)

        if not text:
            return ""

        text = self.normalize_dates(text)
        return re.sub(r"\s+", " ", text).strip()

    # ================================================================
    # 🔒 Protect / Restore
    # ================================================================

    def _safe_token_pattern(self, token: str) -> str:
        """
        يبني pattern يمنع مطابقة الاختصار داخل كلمة أخرى.

        مثال:
            MBA يجب أن يطابق "MBA candidate"
            ولا يجب أن يطابق "Ambassador"
        """
        escaped = re.escape(token)

        starts_word = bool(token and (token[0].isalnum() or token[0] == "_"))
        ends_word = bool(token and (token[-1].isalnum() or token[-1] == "_"))

        left = r"(?<!\w)" if starts_word else r"(?<![A-Za-z0-9])"
        right = r"(?!\w)" if ends_word else r"(?![A-Za-z0-9])"

        return f"{left}{escaped}{right}"

    def _protect(self, text: str) -> str:
        """استبدال العناصر الحساسة بـ placeholders آمنة."""

        # حماية المهارات التقنية من الأطول للأقصر
        # حتى لا يتم استبدال .NET قبل .NET Core مثلاً.
        for tech, placeholder in sorted(
            self.PROTECTED_TECH_SKILLS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            text = re.sub(
                self._safe_token_pattern(tech),
                placeholder,
                text,
                flags=re.IGNORECASE,
            )

        # حماية الاختصارات الأكاديمية من الأطول للأقصر.
        # نستخدم حدوداً آمنة حتى لا يتحول Ambassador إلى A MBA ssador.
        for acronym, placeholder in sorted(
            self.PROTECTED_ACRONYMS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            text = re.sub(
                self._safe_token_pattern(acronym),
                placeholder,
                text,
                flags=re.IGNORECASE,
            )

        # حماية الرموز العلمية
        for symbol, placeholder in sorted(
            self.PROTECTED_SYMBOLS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            text = text.replace(symbol, placeholder)

        return text

    def _restore(self, text: str) -> str:
        """استعادة العناصر المحمية بعد التنظيف العام."""

        for acronym, placeholder in self.PROTECTED_ACRONYMS.items():
            text = re.sub(
                re.escape(placeholder.strip()),
                acronym,
                text,
                flags=re.IGNORECASE,
            )

        for tech, placeholder in self.PROTECTED_TECH_SKILLS.items():
            text = re.sub(
                re.escape(placeholder.strip()),
                tech,
                text,
                flags=re.IGNORECASE,
            )

        for symbol, placeholder in self.PROTECTED_SYMBOLS.items():
            text = re.sub(
                re.escape(placeholder.strip()),
                symbol,
                text,
                flags=re.IGNORECASE,
            )

        return text

    def _restore_nlp(self, text: str) -> str:
        """
        استعادة العناصر المهمة للـ NLP.

        في NLP:
        - نعيد الاختصارات بدون نقطة نهائية غالباً
        - نعيد المهارات التقنية بصيغة lowercase
        - لا نعيد الرموز العلمية الأصلية، بل نتركها ككلمات مفهومة
        """

        for acronym, placeholder in self.PROTECTED_ACRONYMS.items():
            normalized_acronym = acronym.lower().rstrip(".")
            text = re.sub(
                re.escape(placeholder.strip().lower()),
                normalized_acronym,
                text,
                flags=re.IGNORECASE,
            )

        for tech, placeholder in self.PROTECTED_TECH_SKILLS.items():
            text = re.sub(
                re.escape(placeholder.strip().lower()),
                tech.lower(),
                text,
                flags=re.IGNORECASE,
            )

        # الرموز العلمية ككلمات للـ NLP
        symbol_words = {
            "DEGCELSIUS": "degcelsius",
            "DEGFAHRENHEIT": "degfahrenheit",
            "DEGREE": "degree",
            "PLUSMINUS": "plusminus",
            "SQUARED": "squared",
            "CUBED": "cubed",
        }

        for placeholder, word in symbol_words.items():
            text = re.sub(
                re.escape(placeholder.lower()),
                word,
                text,
                flags=re.IGNORECASE,
            )

        return text

    # ================================================================
    # 🧹 CV Cleaning Helpers
    # ================================================================

    def _cv_clean(self, text: str, preserve_bullets: bool = False) -> str:
        """
        تنظيف خاص بنصوص CV:
        - إصلاح الكلمات المقطوعة بسطر جديد
        - إزالة bullets
        - تقليل الرموز المزعجة
        - توحيد المسافات والأسطر
        """

        if not text:
            return ""

        # إصلاح الكلمات المقطوعة:
        # expe-
        # rience  => experience
        # لا نستخدم \s لأنه يشمل newline.
        text = re.sub(
            r"[ \t]+:",
            ":",
            text,
        )
        text = re.sub(
            r":[ \t]+",
            ": ",
            text,
        )
        # U+00AD is a discretionary PDF word-wrap marker, not a printable
        # hyphen. Join fragments before the general line-break repair.
        text = re.sub(
            r"(?<=\w)\u00ad[ \t]*\n[ \t]*(?=\w)",
            "",
            text,
        )
        text = text.replace("\u00ad", "")
        text = re.sub(
            r"(\w+(?:-\w+)*)-[ \t]*\n[ \t]*(\w+)",
            self._join_line_broken_word,
            text,
        )
        # فاصل بيانات الاتصال.
        text = re.sub(
            r"[ \t]*[ \t]*",
            " | ",
            text,
        )

        if preserve_bullets:
            # يحول checkmark إلى bullet حتى لو جاءت بعد نص أو colon.
            text = re.sub(
                r"[ \t]*[✓✔☑][ \t]*",
                "\n• ",
                text,
            )

        # نسخة العرض والتحليل البنيوي تحافظ على bullets.
        # نسخة NLP يمكنها إزالتها.
        if preserve_bullets:
            text = re.sub(
                r"(?m)^\s*[▪◆►■□○●◦‣⁃➢➤✓✔☐☑·]\s*",
                "• ",
                text,
            )
            text = re.sub(r"(?m)^\s*•\s*", "• ", text)
        else:
            text = re.sub(
                r"[•▪◆►■□○●◦‣⁃➢➤✓✔☐☑·]",
                " ",
                text,
            )

        # إزالة رموز مزعجة متكررة فقط، بدون إزالة رمز واحد مهم
        text = re.sub(
            r"([#$%^&*_=\[\]{}\\|;:'\"<>?`~])\1{1,}",
            r"\1",
            text,
        )

        # توحيد المسافات الأفقية
        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        # تقليل الأسطر الفارغة الكثيرة
        text = re.sub(
            r"\n\s*\n\s*\n+",
                "\n\n",
            text,
        )

        lines = [
            line.strip()
            for line in text.split("\n")
            if line.strip()
        ]

        return "\n".join(lines)

    @staticmethod
    def _join_line_broken_word(match: re.Match) -> str:
        """Repair PDF wraps without destroying supported compound words."""

        left, right = match.group(1), match.group(2)
        compound_prefixes = {
            "ai", "ml", "full", "front", "back", "speech-to",
            "text-to", "end-to", "real", "client", "role", "data",
            "cross", "e", "co",
        }
        preserve_hyphen = (
            left.casefold() in compound_prefixes
            or "-" in left
            or (left.isupper() and len(left) <= 5)
        )
        return f"{left}{'-' if preserve_hyphen else ''}{right}"

    def remove_page_artifacts(self, text: str) -> str:
        """إزالة أسطر مثل page 1 أو 1 / 3."""
        if not text:
            return ""

        cleaned_lines = []

        for line in text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()

            if re.match(r"^page\s+\d+$", lower):
                continue

            if re.match(r"^page\s+\d+\s+of\s+\d+$", lower):
                continue

            if re.match(r"^\d+\s*/\s*\d+$", lower):
                continue

            if re.match(r"^-+\s*\d+\s*-+$", lower):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def normalize_unicode_quotes(self, text: str) -> str:
        """توحيد علامات الاقتباس والفواصل الطويلة."""
        if not text:
            return ""

        replacements = {
            "\u201c": '"',
            "\u201d": '"',
            "\u2018": "'",
            "\u2019": "'",
            "\u00ab": '"',
            "\u00bb": '"',
            "\u201e": '"',
            "\u201a": "'",
            "–": "-",
            "—": "-",
            "−": "-",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def fix_ocr_errors(self, text: str) -> str:
        """إصلاح أخطاء OCR بسيطة ومحددة."""
        text = self._ensure_text(text)

        if not text:
            return ""

        for wrong, correct in self.OCR_MAP.items():
            text = re.sub(
                rf"\b{re.escape(wrong)}\b",
                correct,
                text,
                flags=re.IGNORECASE,
            )

        return text

    # ================================================================
    # 📅 Dates
    # ================================================================

    def normalize_dates(self, text: str) -> str:
        """
        تبسيط التواريخ لأغراض matching فقط.

        لا تستخدم هذه الدالة داخل clean() حتى لا تخسر تفاصيل مثل:
            March 2018 - May 2018
        """
        text = self._ensure_text(text)

        if not text:
            return ""

        # January 2020 -> 2020
        text = re.sub(
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\b",
            r"\2",
            text,
            flags=re.IGNORECASE,
        )

        # 01/2020 -> 2020
        text = re.sub(
            r"\b\d{1,2}/(\d{4})\b",
            r"\1",
            text,
        )

        # Present / Current / Now -> present
        text = re.sub(
            r"\b(present|current|now)\b",
            "present",
            text,
            flags=re.IGNORECASE,
        )

        return text

    # ================================================================
    # 🤖 NLP Helpers
    # ================================================================

    @classmethod
    def get_stopwords(cls) -> set:
        """
        تحميل stopwords من الجهاز فقط.
        بدون أي محاولة تحميل من الإنترنت.
        """
        if cls._stopwords_loaded:
            return cls._cached_stopwords

        if nltk is None or stopwords is None:
            return set()

        try:
            nltk.data.find("corpora/stopwords")
            cls._cached_stopwords = set(stopwords.words("english"))
        except LookupError:
            cls._cached_stopwords = set()
        cls._stopwords_loaded = True

        return cls._cached_stopwords

    def extract_words(self, text: str) -> list:
        """استخراج كلمات مناسبة للتحليل."""
        text = self._ensure_text(text)

        if not text:
            return []

        text = self._cv_clean(text)
        return re.findall(r"[a-zA-Z0-9\+\#\.\-/]+", text.lower())

    def extract_sentences(self, text: str) -> list:
        """
        تقسيم النص إلى جمل باستخدام NLTK Punkt فقط.
        بدون download وبدون regex fallback.
        """
        text = self._ensure_text(text)

        if not text:
            return []

        if nltk is None:
            return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]

        required_resources = [
            "tokenizers/punkt",
            "tokenizers/punkt_tab",
        ]

        try:
            for resource in required_resources:
                nltk.data.find(resource)
        except LookupError:
            return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]

        return nltk.sent_tokenize(text)


    def get_stats(self, text: str) -> dict:
        """إحصائيات عامة عن النص بعد التنظيف."""
        cleaned = self.clean(text)
        words = self.extract_words(cleaned)
        sentences = self.extract_sentences(cleaned)

        return {
            "chars": len(cleaned),
            "words": len(words),
            "unique": len(set(words)),
            "sentences": len(sentences),
        }


# =====================================================================
# 🧪 اختبار سريع
# =====================================================================

if __name__ == "__main__":
    cleaner = TextCleaner()

    sample_text = """
    • Python Developer with 5+ years of experience
    ◆ Skills: Python, C++, C#, F#, .NET Core, .NET, Node.js, Vue.js, React Native, CI/CD, REST API, PL/SQL
    ▪ Education: B.Sc. Computer Science
    expe-
    rience in web development
    Contact: test@example.test
    Website: https://example.com
    Temperature: 25°C ± 2°
    GPA: 3.8/4.0
    M.Sc. in Artificial Intelligence
    Ph.D. candidate
    page 1
    1 / 3
    """

    print("=" * 70)
    print("🧹 TEXT CLEANER TEST")
    print("=" * 70)

    print("\n📄 CLEANED TEXT:")
    cleaned = cleaner.clean(sample_text)
    print(cleaned)

    print("\n🤖 NLP READY:")
    nlp = cleaner.clean_for_nlp(sample_text)
    print(nlp)

    print("\n🧪 REGRESSION CHECK:")
    regression = cleaner.clean(
        "Finance Ambassador\nMBA candidate\nBBA graduate"
    )
    print(regression)
    assert "Finance Ambassador" in regression
    assert "A MBA ssador" not in regression

    print("\n📊 STATS:")
    print(cleaner.get_stats(sample_text))

    print("\n🔍 CHECK:")
    checks = [
        "c++",
        "c#",
        "f#",
        ".net core",
        ".net",
        "node.js",
        "vue.js",
        "react native",
        "ci/cd",
        "rest api",
        "pl/sql",
        "b.sc",
        "m.sc",
        "ph.d",
        "gpa",
        "experience",
    ]

    ok = True

    for item in checks:
        found = item in nlp.lower()
        print(f"   {'✅' if found else '❌'} {item}")

        if not found:
            ok = False

    print(f"\n{'🎉 All checks passed!' if ok else '⚠️ Some checks failed'}")
    regression_text = """
    Selected Contributions:
     Created new means of tracking purchased components
    Managed promotional materials, direct-mail pieces (coupon books), website content
    """.strip()

    regression_cleaned = cleaner.clean(regression_text)

    assert (
            "Selected Contributions:\n• Created new means"
            in regression_cleaned
    ), regression_cleaned

    assert (
            "direct-mail pieces (coupon books), website content"
            in regression_cleaned
    ), regression_cleaned

    assert "Selected Contributions: " not in regression_cleaned

    print("TextCleaner punctuation regression: PASSED")
