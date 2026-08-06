import re
from urllib.parse import urlparse

from .base import BaseExtractor
from .email import EmailExtractor


class LinkExtractor(BaseExtractor):
    """استخراج وتصنيف الروابط باستخدام Regex + URL parsing"""

    URL_PATTERN = re.compile(
        r"(?<!@)\b(?:https?://|www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+"
        r"(?:/[^\s,)\"'<>]*)?\b",
        re.IGNORECASE,
    )

    COMMON_EMAIL_DOMAINS = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com",
        "icloud.com", "aol.com", "proton.me", "protonmail.com", "mail.com",
        "example.com", "email.com", "test.com",
    }

    SOCIAL_DOMAINS = {
        "linkedin.com",
        "github.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "instagram.com",
    }

    PORTFOLIO_DOMAINS = {
        "behance.net", "dribbble.com", "medium.com",
        "kaggle.com", "leetcode.com", "hackerrank.com",
        "dev.to", "stackoverflow.com", "codepen.io",
        "gitlab.io", "netlify.app", "vercel.app",
        "herokuapp.com", "github.io", "notion.site",
    }

    PORTFOLIO_TLDS = {
        ".dev", ".me", ".io", ".app", ".site", ".tech",
    }
    NON_WEB_TECH_DOMAINS = {
        "node.js", "react.js", "vue.js", "next.js", "nuxt.js",
        "three.js", "d3.js",
    }

    def __init__(self, email_extractor: EmailExtractor = None):
        self.email_extractor = email_extractor or EmailExtractor()

    def clean_url(self, url: str) -> str:
        """تنظيف وتوحيد الرابط"""
        if not url:
            return ""

        url = str(url).strip()
        url = re.sub(r"\s+", "", url)
        url = re.sub(r"[.,;:!\?\)\]\}>]+$", "", url)

        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def domain(self, url: str) -> str:
        """استخراج الدومين بدون www"""
        try:
            parsed = urlparse(self.clean_url(url))
            domain = parsed.netloc.lower()

            if domain.startswith("www."):
                domain = domain[4:]

            return domain

        except Exception:
            return ""

    def canonical_key(self, url: str) -> str:
        """
        مفتاح موحد للرابط حتى نمنع التكرار:
        https://www.linkedin.com/in/x
        https://linkedin.com/in/x
        يعتبرهم نفس الرابط.
        """
        clean = self.clean_url(url)

        try:
            parsed = urlparse(clean)
            domain = parsed.netloc.lower()

            if domain.startswith("www."):
                domain = domain[4:]

            path = parsed.path.rstrip("/").lower()
            return domain + path

        except Exception:
            return (
                clean.lower()
                .replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .rstrip("/")
            )

    def is_valid_candidate(self, url: str) -> bool:
        """فلترة الروابط غير الصالحة"""
        if not url or "." not in url:
            return False

        lower = url.lower().strip()

        if lower.startswith(("mailto:", "tel:")):
            return False

        if "<" in lower or ">" in lower:
            return False

        # منع التقاط أشياء قصيرة وغريبة مثل a.b
        domain = self.domain(url)
        if domain and len(domain) < 4:
            return False
        if domain in self.NON_WEB_TECH_DOMAINS or domain.endswith(".js"):
            return False

        return True

    def categorize(self, url: str) -> str:
        """تصنيف الرابط"""
        clean = self.clean_url(url)
        lower_url = clean.lower()
        domain = self.domain(clean)

        if "linkedin.com" in lower_url:
            return "linkedin"

        if "github.com" in lower_url:
            return "github"

        if domain in self.PORTFOLIO_DOMAINS:
            return "portfolio"

        if any(domain.endswith(tld) for tld in self.PORTFOLIO_TLDS):
            return "portfolio"

        if any(keyword in lower_url for keyword in ["portfolio", "resume", "cv", "projects"]):
            return "portfolio"

        return "other"

    def extract_and_categorize(self, text: str, file_links: list = None) -> dict:
        """
        استخراج وتصنيف الروابط.

        file_links:
            روابط مستخرجة من PDF/DOCX كـ hyperlinks حقيقية.
        """
        text = self.ensure_text(text)
        file_links = file_links or []

        categorized = {
            "linkedin": [],
            "github": [],
            "portfolio": [],
            "other": [],
        }

        # مهم: طبّع الإيميلات أولاً حتى لا يلقط regex أجزاء منها كروابط
        normalized_text = (
            self.email_extractor.normalize_text(text)
            if hasattr(self.email_extractor, "normalize_text")
            else text
        )

        # حذف الإيميلات قبل استخراج الروابط
        text_without_emails = re.sub(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            " ",
            normalized_text,
            flags=re.IGNORECASE,
        )

        candidates = []
        candidates.extend(file_links)
        candidates.extend(self.URL_PATTERN.findall(text_without_emails))

        seen = set()

        for candidate in candidates:
            if not self.is_valid_candidate(candidate):
                continue

            clean = self.clean_url(candidate)
            key = self.canonical_key(clean)

            if key in seen:
                continue

            seen.add(key)

            category = self.categorize(clean)
            categorized[category].append(clean)

        return categorized

    def get_best(self, urls: list) -> str | None:
        return urls[0] if urls else None

    def extract_website(self, text: str, file_links: list = None) -> str | None:
        """
        استخراج موقع شخصي أو portfolio.

        يتجاهل:
        - LinkedIn
        - GitHub
        - دومينات الإيميل
        - دومينات البريد الشائعة
        """
        text = self.ensure_text(text)

        links = self.extract_and_categorize(text, file_links)
        if hasattr(self.email_extractor, "get_email_domains"):
            email_domains = self.email_extractor.get_email_domains(text)
        else:
            email_domains = {
                match.group(1).casefold()
                for match in re.finditer(
                    r"(?i)[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,24})",
                    text,
                )
            }

        candidates = []
        candidates.extend(links.get("portfolio", []))
        candidates.extend(links.get("other", []))

        for url in candidates:
            domain = self.domain(url)

            if not domain:
                continue

            if domain in self.COMMON_EMAIL_DOMAINS:
                continue

            if domain in email_domains:
                continue

            if domain in self.SOCIAL_DOMAINS:
                continue

            return url

        return None


if __name__ == "__main__":
    extractor = LinkExtractor()

    sample = """
    Jordan Example
    jordan @example.test
    linkedin.com/in/jordan-example
    github.com/jordan-example
    www.jordan-example.test
    kaggle.com/jordan-example
    """

    file_links = [
        "https://www.linkedin.com/in/jordan-example",
        "https://jordan-example.test/projects",
    ]

    links = extractor.extract_and_categorize(sample, file_links=file_links)

    print(links)
    print("Best LinkedIn:", extractor.get_best(links["linkedin"]))
    print("Website:", extractor.extract_website(sample, file_links=file_links))
