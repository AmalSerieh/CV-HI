import re

from .base import BaseExtractor


class LocationExtractor(BaseExtractor):
    """
    استخراج الموقع باستخدام:
    1. spaCy NER إذا nlp موجود
    2. Regex fallback
    3. City list fallback

    الأفضل استخدامه على raw_text قبل التنظيف الكامل.
    """

    COMMON_CITIES = [
        "san francisco", "new york", "los angeles", "abu dhabi",
        "chicago", "seattle", "london", "paris", "berlin",
        "madrid", "rome", "toronto", "sydney", "dubai",
        "singapore", "tokyo", "seoul", "damascus", "beirut",
        "amman", "cairo", "riyadh", "istanbul", "doha",
        "jeddah", "aleppo",
    ]

    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }

    BLOCKED_WORDS = {
        "linkedin", "github", "email", "phone", "mobile", "website",
        "resume", "cv", "curriculum", "vitae", "portfolio",
    }

    ORG_WORDS = {
        "university", "college", "school", "institute", "company",
        "corporation", "corp", "inc", "llc", "ltd", "firm", "llp",
        "bank", "hospital", "center", "department", "club", "program",
        "restaurant", "organization",
    }

    def __init__(self, nlp=None):
        self.nlp = nlp

    def extract(self, text: str) -> str | None:
        text = self.ensure_text(text)

        if not text:
            return None

        header_text = self._get_header_text(text)

        # 1. Regex أولاً لأنه يلتقط Chicago, IL بشكل كامل
        location = self._from_regex(header_text)
        if location:
            return location

        # 2. spaCy بعده
        if self.nlp is not None:
            location = self._from_spacy(header_text)
            if location:
                return location

        # 3. city list
        location = self._from_city_list(header_text)
        if location:
            return location

        # fallback على أول 1500 حرف من النص الكامل
        location = self._from_regex(text[:1500])
        if location:
            return location

        if self.nlp is not None:
            location = self._from_spacy(text[:1500])
            if location:
                return location

        return self._from_city_list(text[:1500])

    def _get_header_text(self, text: str, max_lines: int = 12) -> str:
        """
        أخذ أول أسطر السيرة فقط.
        غالباً الاسم، الهاتف، الإيميل، الموقع، الروابط موجودين هنا.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines[:max_lines])

    def _from_spacy(self, text: str) -> str | None:
        """
        استخراج الموقع من spaCy.
        spaCy يعطي GPE/LOC، ونحن نفلتر النتائج.
        """
        if not self.nlp or not text:
            return None

        doc = self.nlp(text)

        candidates = []

        for ent in doc.ents:
            if ent.label_ not in {"GPE", "LOC"}:
                continue

            loc = ent.text.strip()

            if not self._is_valid_location(loc):
                continue

            score = self._score_location(loc, text, ent.start_char)

            candidates.append({
                "location": loc,
                "score": score,
            })

        if not candidates:
            return None

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[0]["location"]

    def _from_regex(self, text: str) -> str | None:
        """
        Regex fallback لمواقع مثل:
        Chicago, IL
        San Francisco, CA
        Dubai, UAE
        Damascus, Syria
        """

        if not text:
            return None

        patterns = [
            # City, US_STATE
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}),\s*([A-Z]{2})\b",

            # City, Country
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b",
        ]

        candidates = []

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                city = match.group(1).strip()
                region = match.group(2).strip()

                full_location = f"{city}, {region}"

                if not self._is_valid_location(full_location):
                    continue

                # لو الجزء الثاني حرفين، يفضل يكون State حقيقي
                if len(region) == 2 and region.upper() not in self.US_STATES:
                    continue

                score = self._score_location(full_location, text, match.start())

                candidates.append({
                    "location": full_location,
                    "score": score,
                })

        if not candidates:
            return None

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[0]["location"]

    def _from_city_list(self, text: str) -> str | None:
        """
        fallback أخير من قائمة مدن.
        القائمة مرتبة كـ list وليس set حتى تكون النتيجة ثابتة.
        """
        if not text:
            return None

        lower = text.lower()

        for city in self.COMMON_CITIES:
            if re.search(rf"\b{re.escape(city)}\b", lower):
                return city.title()

        return None

    def _is_valid_location(self, loc: str) -> bool:
        """
        فلترة المواقع غير المفيدة أو التي غالباً ليست location للشخص.
        """
        if not loc:
            return False

        lower = loc.lower().strip()

        if any(word in lower for word in self.BLOCKED_WORDS):
            return False

        if "@" in loc or "http" in lower or "www." in lower:
            return False

        if re.search(r"\d{4,}", loc):
            return False

        # تجنب أسماء دول عامة فقط
        if lower in {"united states", "usa", "world", "earth"}:
            return False

        # تجنب التقاط organization كموقع
        if any(org_word in lower for org_word in self.ORG_WORDS):
            return False

        # لا تقبل نص طويل جداً
        if len(loc.split()) > 5:
            return False

        return True

    def _score_location(self, loc: str, text: str, position: int) -> int:
        """
        إعطاء score للموقع.
        الأعلى إذا كان قريب من أعلى السيرة أو قرب كلمات contact.
        """
        score = 0

        # الأقرب للبداية أفضل
        if position <= 150:
            score += 40
        elif position <= 400:
            score += 25
        elif position <= 800:
            score += 10

        lower_loc = loc.lower()

        # إذا كان في نفس السطر مع contact info غالباً أقوى
        for line in text.splitlines():
            if lower_loc in line.lower():
                line_lower = line.lower()

                if any(marker in line_lower for marker in ["email", "phone", "mobile", "linkedin", "|"]):
                    score += 20

                if any(org in line_lower for org in self.ORG_WORDS):
                    score -= 25

        # City, ST أقوى من city فقط
        if "," in loc:
            score += 15

        return score


if __name__ == "__main__":
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = None

    extractor = LocationExtractor(nlp=nlp)

    sample = """
    Jordan Example
    555.010.0500 | jordan@example.test | linkedin.com/in/jordan-example
    Example City, EX

    EDUCATION
    Example University, Example City, EX

    EXPERIENCE
    Example Company, Example City, EX
    """

    print("Location:", extractor.extract(sample))
