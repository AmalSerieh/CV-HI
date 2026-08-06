class BaseExtractor:
    """دوال مشتركة بين كل extractors"""

    @staticmethod
    def ensure_text(text) -> str:
        if text is None:
            return ""

        if isinstance(text, dict):
            raise TypeError(
                "Expected string, got dict. "
                "Use extracted['text'] instead of passing the whole extraction result."
            )

        if not isinstance(text, str):
            raise TypeError(f"Expected str, got {type(text).__name__}")

        return text

    @staticmethod
    def unique_keep_order(items: list) -> list:
        """
        إزالة التكرار مع الحفاظ على الترتيب.
        مناسبة للقوائم النصية مثل emails, phones, links.
        """
        if not items:
            return []

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