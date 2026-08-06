import re

from .base import BaseExtractor


class NameExtractor(BaseExtractor):
    """استخراج الاسم باستخدام Header scoring + spaCy PERSON"""

    SECTION_WORDS = {
        "summary", "profile", "objective", "experience", "education",
        "skills", "projects", "certifications", "languages", "references",
        "contact", "resume", "cv", "curriculum", "vitae",
        "about", "overview",
    }

    JOB_TITLE_WORDS = {
        "engineer", "developer", "manager", "analyst", "designer",
        "consultant", "specialist", "architect", "lead", "senior",
        "director", "officer", "coordinator", "supervisor",
        "intern", "accountant", "auditor", "teacher", "professor",
        "nurse", "doctor", "assistant", "administrator", "software",
        "finance", "marketing", "sales", "hr", "data scientist",
        "full stack", "frontend", "backend", "devops",
        "student", "candidate", "graduate",
    }

    ORG_WORDS = {
        "university", "college", "school", "institute", "company",
        "corporation", "corp", "inc", "llc", "ltd", "firm", "llp",
        "bank", "hospital", "center", "department", "club", "program",
        "restaurant", "organization", "academy",
    }

    CONTACT_WORDS = {
        "email", "phone", "mobile", "linkedin", "github", "portfolio",
        "website", "address", "location",
    }

    def __init__(self, nlp=None):
        self.nlp = nlp

    def extract(self, text: str) -> str | None:
        text = self.ensure_text(text)

        if not text:
            return None

        candidates = []
        candidates.extend(self._from_header(text))

        if self.nlp is not None:
            candidates.extend(self._from_spacy(text))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[0]["name"]

    def _from_header(self, text: str) -> list:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidates = []

        for idx, line in enumerate(lines[:12]):
            name = self._clean_line(line)

            if not self._is_likely_name(name):
                continue

            score = self._score_header_name(name, idx)
            candidates.append({
                "name": name,
                "score": score,
                "source": "header",
            })

        return candidates

    def _from_spacy(self, text: str) -> list:
        candidates = []

        doc = self.nlp(text[:1200])

        for ent in doc.ents:
            if ent.label_ != "PERSON":
                continue

            name = self._clean_line(ent.text)

            if not self._is_likely_name(name):
                continue

            position_penalty = min(25, ent.start_char // 40)

            candidates.append({
                "name": name,
                "score": 55 - position_penalty,
                "source": "spacy",
            })

        return candidates

    def _clean_line(self, line: str) -> str:
        """تنظيف السطر قبل فحصه كاسم"""

        # إذا السطر يحتوي بيانات تواصل بعد |
        line = re.sub(r"\|.*$", "", line)

        # Name: Kelly DePaul -> Kelly DePaul
        line = re.sub(
            r"^\s*(name|full name|candidate)\s*[:\-]\s*",
            "",
            line,
            flags=re.IGNORECASE,
        )

        # إزالة الأقواس والرموز الزائدة من الطرف
        line = re.sub(r"^[^\w\u0600-\u06FF]+", "", line)
        line = re.sub(r"[^\w\u0600-\u06FF\.\-'\s]+$", "", line)

        line = re.sub(r"\s+", " ", line)
        return line.strip()

    def _is_likely_name(self, text: str) -> bool:
        if not text:
            return False

        lower = text.lower().strip()

        if "@" in text or "http" in lower or "www." in lower:
            return False

        if re.search(r"\d", text):
            return False

        if any(word in lower.split() for word in self.SECTION_WORDS):
            return False

        if any(word in lower for word in self.CONTACT_WORDS):
            return False

        if any(word in lower for word in self.ORG_WORDS):
            return False

        if any(word in lower for word in self.JOB_TITLE_WORDS):
            return False

        words = text.split()

        if not (2 <= len(words) <= 4):
            return False

        valid_words = 0

        for word in words:
            # يدعم English + Arabic letters + - . '
            cleaned = re.sub(r"[^A-Za-z\u0600-\u06FF\-\.']", "", word)

            if not cleaned:
                continue

            # Initial مثل A.
            if len(cleaned.replace(".", "")) == 1:
                valid_words += 1
                continue

            # عربي: لا يوجد uppercase/lowercase
            if re.search(r"[\u0600-\u06FF]", cleaned):
                valid_words += 1
                continue

            # إنجليزي
            if cleaned[0].isupper() or cleaned.isupper():
                valid_words += 1

        return valid_words == len(words)

    def _score_header_name(self, name: str, line_index: int) -> int:
        score = 0

        # أول سطر غالباً الاسم
        if line_index == 0:
            score += 45
        elif line_index <= 3:
            score += 25
        elif line_index <= 7:
            score += 10

        words = name.split()

        if 2 <= len(words) <= 3:
            score += 20
        elif len(words) == 4:
            score += 10

        # English title case أو Arabic
        if all(
            word[:1].isupper()
            or word.isupper()
            or re.search(r"[\u0600-\u06FF]", word)
            for word in words
        ):
            score += 15

        if "." in name:
            score += 3

        return score


if __name__ == "__main__":
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = None

    extractor = NameExtractor(nlp=nlp)

    samples = [
        """
        Jordan Example
        555.010.0500 | jordan@example.test | linkedin.com/in/jordan-example
        EDUCATION
        Example University, Example City
        """,
        """
        Jordan A. Example
        Senior Software Engineer
        jordan@example.test
        """,
        """
        الاسم: محمد أحمد الخالد
        البريد: test@example.com
        """,
    ]

    for sample in samples:
        print("Name:", extractor.extract(sample))
