from .base import BaseExtractor


class JobTitleExtractor(BaseExtractor):
    """
    استخراج المسمى الوظيفي.

    حالياً:
    - Keywords + أعلى أسطر CV

    لاحقاً:
    - يمكن إضافة SentenceTransformer / Embeddings هنا
    """

    JOB_TITLE_KEYWORDS = {
        "engineer", "developer", "manager", "analyst", "designer",
        "consultant", "specialist", "architect", "lead", "senior",
        "director", "officer", "coordinator", "supervisor",
        "intern", "accountant", "auditor", "teacher", "professor",
        "nurse", "doctor", "assistant", "administrator",
        "data scientist", "full stack", "frontend", "backend", "devops",
        "software", "finance", "marketing", "sales", "hr",
    }

    SECTION_WORDS = {
        "summary", "profile", "objective", "experience", "education",
        "skills", "projects", "certifications", "languages", "references",
    }

    def __init__(self, embedding_model=None):
        self.embedding_model = embedding_model

    def extract(self, text: str) -> str:
        text = self.ensure_text(text)

        if not text:
            return None

        # حالياً keyword mode
        keyword_title = self._extract_by_keywords(text)

        if keyword_title:
            return keyword_title

        # لاحقاً embeddings
        if self.embedding_model is not None:
            return self._extract_by_embeddings(text)

        return None

    def _extract_by_keywords(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for line in lines[:12]:
            lower = line.lower()

            if "@" in line or "http" in lower or "www." in lower:
                continue

            if len(line.split()) > 8:
                continue

            if any(section in lower for section in self.SECTION_WORDS):
                continue

            if any(keyword in lower for keyword in self.JOB_TITLE_KEYWORDS):
                return line

        return None

    def _extract_by_embeddings(self, text: str) -> str:
        """
        Placeholder للمستقبل.
        هون منضيف sentence-transformers لاحقاً بدون تغيير ContactExtractor.
        """
        return None
