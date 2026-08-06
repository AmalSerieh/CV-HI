"""Conservative anti-hallucination validation for proposed rewrites."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from resume_analyzer.schemas import PipelineReport, SkillGroup

_INJECTION = re.compile(
    r"(?i)\b(?:ignore (?:all |the )?(?:previous|prior) instructions?|system prompt|developer message|reveal (?:the )?prompt|call (?:a )?tool)\b"
)
_PERCENT = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?\s*%")
_MONEY = re.compile(
    r"(?i)(?:[$€£]\s*\d[\d,.]*|\d[\d,.]*\s*(?:usd|eur|gbp|dollars?|euros?|pounds?))"
)
_DATE = re.compile(
    r"(?i)\b(?:(?:19|20)\d{2}(?:\s*[-–—/]\s*(?:(?:19|20)\d{2}|present|current))?|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(?:19|20)\d{2})\b"
)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?!\w|[.,]\d)")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_COMPANY = re.compile(
    r"\b(?:at|for|with)\s+" r"([A-Z][\w&.+-]*(?:(?<![.!?])[\t ]+[A-Z][\w&.+-]*){0,4})"
)
_JOB_TITLE = re.compile(
    r"\b(?:as|as an?|role of)\s+" r"([A-Z][\w&.+/-]*(?:(?<![.!?])[\t ]+[A-Z][\w&.+/-]*){0,5})"
)
_VIA_RELATION = re.compile(
    r"\b(?:through|via)\s+([A-Z][A-Za-z0-9&.+/-]*(?:\s+[A-Z][A-Za-z0-9&.+/-]*){0,2})"
)
_CERTIFICATION = re.compile(
    r"(?i)\b((?:AWS|Azure|Google|Microsoft|Cisco|Oracle)?\s*"
    r"(?:certified|certification|certificate)\s+"
    r"(?!(?:and|with|using|experience)\b)"
    r"[A-Za-z][\w +#./-]{1,60}?"
    r"(?=[,.;:]|\s+(?:and|with|using|experience)\b|$))"
)
_DEGREE = re.compile(
    r"(?i)\b((?:bachelor(?:'s)?|master(?:'s)?|doctorate|ph\.?d\.?|bsc|msc|mba)"
    r"(?:\s+(?:degree\s+)?(?:in|of)\s+[A-Za-z][\w &+-]{1,60})?)"
)
_PROPER_NOUN_TOKEN = r"[A-Z][A-Za-z0-9&+#/-]*(?:\.[A-Za-z0-9&+#/-]+)*"
_PROPER_NOUN = re.compile(rf"\b{_PROPER_NOUN_TOKEN}(?:\s+{_PROPER_NOUN_TOKEN})*\b")

_TECH_ALIASES = {
    "python": {"python", "بايثون"},
    "javascript": {"javascript", "js", "جافاسكربت"},
    "typescript": {"typescript", "ts"},
    "react": {"react", "reactjs", "react.js", "رياكت"},
    "node.js": {"node", "nodejs", "node.js"},
    "sql": {"sql"},
    "postgresql": {"postgresql", "postgres"},
    "mysql": {"mysql"},
    "mongodb": {"mongodb", "mongo"},
    "aws": {"aws", "amazon web services"},
    "azure": {"azure"},
    "docker": {"docker", "دوكر"},
    "kubernetes": {"kubernetes", "k8s"},
    "git": {"git"},
    "java": {"java"},
    "c++": {"c++", "cpp"},
    "c#": {"c#", "c sharp"},
    "django": {"django"},
    "flask": {"flask"},
    "fastapi": {"fastapi", "fast api"},
    "pytorch": {"pytorch"},
    "tensorflow": {"tensorflow"},
    "power bi": {"power bi", "powerbi"},
    "rest api": {"rest api", "rest apis", "restful api", "restful apis"},
    "llm api": {"llm api", "llm apis", "large language model api", "large language model apis"},
    "rag": {"rag", "retrieval augmented generation", "retrieval-augmented generation"},
    "speech-to-text": {"speech-to-text", "speech to text"},
}
_SAFE_PROPER_NOUNS = {
    "A",
    "An",
    "The",
    "It",
    "Its",
    "This",
    "These",
    "They",
    "Their",
    "He",
    "His",
    "She",
    "Her",
    "Developed",
    "Built",
    "Created",
    "Implemented",
    "Maintained",
    "Supported",
    "Analyzed",
    "Prepared",
    "Coordinated",
    "Managed",
    "Used",
    "Worked",
    "Improved",
    "Contributed",
    "Handled",
    "Answered",
    "Responded",
    "Reconciled",
    "Processed",
    "Assisted",
    "Provided",
    "Generated",
    "Reviewed",
    "Resolved",
    "Streamlined",
    "Organized",
    "Recorded",
    "Updated",
    "Distributed",
}
_IRREGULAR_ACTION_OPENERS = {
    "built",
    "bought",
    "brought",
    "drove",
    "grew",
    "held",
    "led",
    "made",
    "oversaw",
    "ran",
    "sold",
    "taught",
    "wrote",
}
_ESCALATION_TERMS = re.compile(
    r"(?i)\b(?:architected|scalable|high[- ]performance|enterprise|optimized|"
    r"increased|reduced|boosted|drove|led|leadership|deployed|cloud-native|secured|"
    r"expert|proficient|advanced|specialist|senior|seasoned|extensive experience|"
    r"proven track record)\b"
)
_SUMMARY_ACRONYMS = {
    "AI",
    "API",
    "APIS",
    "BI",
    "ETL",
    "KPI",
    "KPIS",
    "LLM",
    "ML",
    "NLP",
    "OCR",
    "RAG",
    "REST",
    "SQL",
}
_CONTENT_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "including",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "using",
    "with",
    "through",
    "via",
    "while",
    "build",
    "building",
    "built",
    "create",
    "created",
    "deliver",
    "delivered",
    "develop",
    "developed",
    "developing",
    "help",
    "helped",
    "helping",
    "organize",
    "organized",
    "organizing",
    "support",
    "supported",
    "supporting",
    "use",
    "used",
    "utilize",
    "utilized",
    "utilizing",
    "work",
    "worked",
    "working",
    "ability",
    "degree",
    "experience",
    "experienced",
    "high",
    "highly",
    "knowledge",
    "nimble",
    "progress",
    "progresses",
    "prompt",
    "recognized",
    "reliable",
    "skill",
    "skills",
    "solid",
    "successfully",
    "sure",
    "various",
}
_CONTENT_ACTION_PREFIXES = (
    "alleviat",
    "answer",
    "conduct",
    "coordinat",
    "creat",
    "distribut",
    "ensur",
    "greet",
    "handl",
    "improv",
    "increas",
    "introduc",
    "maintain",
    "mak",
    "perform",
    "prepar",
    "reconcil",
    "recogniz",
    "repl",
    "respond",
    "sav",
    "synchroniz",
    "updat",
)
_ARABIC_CONTENT_STOPWORDS = {
    "او",
    "الى",
    "التي",
    "الذي",
    "الذين",
    "ثم",
    "عبر",
    "عن",
    "على",
    "في",
    "كما",
    "لدى",
    "ما",
    "مع",
    "من",
    "هذا",
    "هذه",
}
_ARABIC_ACTION_PREFIXES = (
    "اجاب",
    "اجرى",
    "ادار",
    "اعد",
    "اشرف",
    "استخدم",
    "انجز",
    "انشا",
    "بنى",
    "حافظ",
    "حقق",
    "حسن",
    "تحسين",
    "خفض",
    "طور",
    "تطوير",
    "عالج",
    "عزز",
    "قاد",
    "قدم",
    "راجع",
    "رفع",
    "ساهم",
    "سجل",
    "سهل",
    "صمم",
    "نفذ",
    "نسق",
    "نظم",
    "وزع",
)
_CONTENT_EQUIVALENTS = {
    "client": "customer",
    "clients": "customer",
    "customer": "customer",
    "customers": "customer",
    "email": "email",
    "emails": "email",
    "load": "workload",
    "loads": "workload",
    "workload": "workload",
    "workloads": "workload",
}
_DANGLING_TERMS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "including",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "using",
    "via",
    "while",
    "which",
    "with",
    "that",
    "ensuring",
    "maintaining",
    "making",
    "providing",
    "supporting",
}
_DANGLING_PHRASE = re.compile(
    r"(?i)\b(?:making\s+sure|a\s+high\s+degree\s+of|"
    r"(?:providing|delivering)\s+(?:excellent\s+)?(?:customer|client))\s*$"
)
_SUMMARY_BULLET = re.compile(r"^\s*[•●▪◦‣∙*-]\s*")


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ـ", "")
    value = re.sub(r"[\u064b-\u065f\u0670]", "", value)
    value = value.translate(str.maketrans("أإآى", "اااي"))
    return re.sub(r"\s+", " ", value).strip()


def _language(value: str) -> str:
    arabic = sum("\u0600" <= char <= "\u06ff" for char in value)
    latin = sum(char.isascii() and char.isalpha() for char in value)
    if arabic and latin:
        return "mixed"
    if arabic:
        return "ar"
    if latin:
        return "en"
    return "unknown"


def _technology_terms(value: str) -> set[str]:
    normalized = _normalize(value)
    found: set[str] = set()
    for canonical, aliases in _TECH_ALIASES.items():
        if any(
            re.search(rf"(?<!\w){re.escape(_normalize(alias))}(?!\w)", normalized)
            for alias in aliases
        ):
            found.add(canonical)
    return found


def _morphology_key(value: str) -> str:
    token = _normalize(value).strip("._-")
    for suffix, minimum in (("ing", 6), ("ed", 5)):
        if token.endswith(suffix) and len(token) >= minimum:
            token = token[: -len(suffix)]
            break
    if token.endswith("e") and len(token) > 4:
        token = token[:-1]
    return token


def _is_sentence_opening_action(text: str, start: int, token: str) -> bool:
    prefix = text[:start]
    if prefix.strip() and not re.search(r"[.!?\u061f]\s*$", prefix):
        return False
    normalized = _normalize(token)
    return normalized in _IRREGULAR_ACTION_OPENERS or (
        normalized.endswith(("ed", "ing")) and len(normalized) >= 6
    )


@dataclass(frozen=True)
class RewriteValidation:
    accepted: bool
    code: str | None = None
    message: str | None = None
    warnings: tuple[str, ...] = ()
    requires_review: bool = False


class RewriteValidator:
    @classmethod
    def incomplete_text_reason(cls, value: str) -> str | None:
        """Return a deterministic reason when text ends as an obvious fragment."""

        text = str(value or "").strip()
        if not text:
            return "text is empty"
        if "\u00ad" in text:
            return "text contains an unresolved soft-hyphen line break"
        if text[-1] in ",;:":
            return f"text ends with {text[-1]!r}"
        core = re.sub(r"[.!?؟]+$", "", text).strip()
        if not core:
            return "text contains no sentence content"
        if _DANGLING_PHRASE.search(core):
            return "text ends with an unfinished phrase"
        final_tokens = re.findall(r"(?u)[^\W_]+(?:[-'][^\W_]+)*", _normalize(core))
        if final_tokens and final_tokens[-1] in _DANGLING_TERMS:
            return f"text ends with the dangling term {final_tokens[-1]!r}"
        return None

    @staticmethod
    def comparison_key(value: str) -> str:
        value = unicodedata.normalize("NFKC", str(value or ""))
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"\s+([,.;:!?؟])", r"\1", value)
        value = re.sub(r"([,.;:!?؟])(?=\S)", r"\1 ", value)
        value = re.sub(r"[.!?؟]+$", "", value).strip()
        return value.casefold()

    def validate_text(
        self,
        report: PipelineReport,
        *,
        expected_original: str,
        response_original: str | None,
        improved: str,
        evidence_ids: list[str],
        output_language: str,
        allow_evidence_expansion: bool = True,
        preserve_summary_coverage: bool = False,
    ) -> RewriteValidation:
        evidence = {item.id: item for item in report.evidence}
        unknown = sorted(set(evidence_ids) - set(evidence))
        if unknown:
            return self._reject("UNKNOWN_EVIDENCE_ID", f"Unknown evidence IDs: {unknown}")
        if response_original is not None and response_original != expected_original:
            return self._reject("ORIGINAL_TEXT_MISMATCH", "Model original does not match input")
        if not improved.strip():
            return self._reject("EMPTY_IMPROVED_TEXT", "Improved text is empty")
        if _INJECTION.search(improved):
            return self._reject("PROMPT_INJECTION_OUTPUT", "Instruction-like output was rejected")
        incomplete_reason = self.incomplete_text_reason(improved)
        if incomplete_reason:
            return self._reject(
                "INVALID_MODEL_RESPONSE",
                f"Rewrite is incomplete: {incomplete_reason}.",
            )

        selected_text = (
            " ".join(str(evidence[item].value or "") for item in evidence_ids)
            if allow_evidence_expansion
            else ""
        )
        supported_text = f"{expected_original} {selected_text}"
        expected_language = (
            output_language if output_language != "unknown" else _language(expected_original)
        )
        improved_language = _language(improved)
        if (
            expected_language in {"en", "ar"}
            and improved_language in {"en", "ar"}
            and expected_language != improved_language
        ):
            return self._reject("LANGUAGE_CHANGED", "Rewrite changed the configured language")

        for pattern, invented, changed in (
            (_PERCENT, "INVENTED_PERCENTAGE", "CHANGED_PERCENTAGE"),
            (_MONEY, "INVENTED_MONEY_VALUE", "CHANGED_MONEY_VALUE"),
        ):
            result = self._compare_tokens(pattern, expected_original, improved, invented, changed)
            if result:
                return result
        date_result = self._compare_tokens(
            _DATE, expected_original, improved, "CHANGED_DATE", "CHANGED_DATE"
        )
        if date_result:
            return date_result
        number_result = self._compare_tokens(
            _NUMBER, expected_original, improved, "INVENTED_NUMBER", "CHANGED_NUMBER"
        )
        if number_result:
            return number_result

        original_urls = Counter(_normalize(item) for item in _URL.findall(expected_original))
        improved_urls = Counter(_normalize(item) for item in _URL.findall(improved))
        if improved_urls - original_urls:
            return self._reject("CHANGED_URL", "A URL was added or changed")
        if original_urls - improved_urls:
            return self._reject("CHANGED_URL", "A URL was removed")

        normalized_support = _normalize(supported_text)
        for match in _CERTIFICATION.finditer(improved):
            if _normalize(match.group(1)) not in normalized_support:
                return self._reject(
                    "INVENTED_CERTIFICATION",
                    f"Unsupported certification: {match.group(1)}",
                )
        for match in _DEGREE.finditer(improved):
            if _normalize(match.group(1)) not in normalized_support:
                return self._reject("INVENTED_DEGREE", f"Unsupported degree: {match.group(1)}")
        added_technologies = _technology_terms(improved) - _technology_terms(expected_original)
        supported_technologies = _technology_terms(selected_text)
        if added_technologies - supported_technologies:
            return self._reject(
                "INVENTED_TECHNOLOGY",
                f"Unsupported technologies: {sorted(added_technologies - supported_technologies)}",
            )
        for match in _COMPANY.finditer(improved):
            claim = _normalize(match.group(1).rstrip(".,;:"))
            if claim and claim not in normalized_support:
                return self._reject("INVENTED_COMPANY", f"Unsupported company: {match.group(1)}")
        for match in _JOB_TITLE.finditer(improved):
            claim = _normalize(match.group(1).rstrip(".,;:"))
            if claim and claim not in normalized_support:
                return self._reject("CHANGED_JOB_TITLE", f"Unsupported job title: {match.group(1)}")
        for match in _VIA_RELATION.finditer(expected_original):
            target = match.group(1).rstrip(".,;:")
            improved_relation = re.search(
                rf"(?i)\b(?:through|via)\s+{re.escape(target)}\b",
                improved,
            )
            if _normalize(target) in _normalize(improved) and not improved_relation:
                return self._reject(
                    "UNSUPPORTED_FACTUAL_CLAIM",
                    f"Rewrite changed the through/via relationship to {target}",
                )
        if _ESCALATION_TERMS.search(improved):
            support_morphology = {
                _morphology_key(token) for token in re.findall(r"(?u)\b[\w-]+\b", supported_text)
            }
            for match in _ESCALATION_TERMS.finditer(improved):
                claim = _normalize(match.group(0))
                supported = (
                    claim in normalized_support
                    if " " in claim or "-" in claim
                    else _morphology_key(claim) in support_morphology
                )
                if not supported:
                    return self._reject(
                        "UNSUPPORTED_FACTUAL_CLAIM",
                        f"Unsupported escalated claim: {match.group(0)}",
                    )

        for proper_match in _PROPER_NOUN.finditer(improved):
            proper_noun = proper_match.group(0)
            if proper_noun in _SAFE_PROPER_NOUNS:
                continue
            normalized = _normalize(proper_noun)
            tokens = proper_noun.split()
            if len(tokens) == 1 and _is_sentence_opening_action(
                improved,
                proper_match.start(),
                tokens[0],
            ):
                continue
            if tokens and tokens[0] in _SAFE_PROPER_NOUNS:
                tokens = tokens[1:]
            token_supported = all(
                _normalize(token) in normalized_support or bool(_technology_terms(token))
                for token in tokens
            )
            if (
                normalized not in normalized_support
                and not _technology_terms(proper_noun)
                and not token_supported
            ):
                return self._reject(
                    "UNSUPPORTED_PROPER_NOUN", f"Unsupported proper noun: {proper_noun}"
                )

        if preserve_summary_coverage:
            omitted_skills = self._omitted_explicit_skills(
                report,
                expected_original,
                improved,
            )
            original_acronyms = {
                item
                for item in re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b", expected_original)
                if item in _SUMMARY_ACRONYMS
            }
            improved_acronyms = {
                item
                for item in re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b", improved)
                if item in _SUMMARY_ACRONYMS
            }
            omitted_acronyms = sorted(original_acronyms - improved_acronyms)
            omitted_claims = self._omitted_summary_claims(expected_original, improved)
            if omitted_skills or omitted_acronyms or omitted_claims:
                omitted = list(dict.fromkeys([*omitted_skills, *omitted_acronyms]))[:8]
                if omitted_claims:
                    omitted.extend(f"claim: {claim[:80]}" for claim in omitted_claims[:2])
                return self._reject(
                    "UNSUPPORTED_FACTUAL_CLAIM",
                    f"Summary rewrite omitted supported content: {omitted}",
                )

        missing_content = self._missing_content_terms(expected_original, improved)
        if missing_content and not preserve_summary_coverage:
            return self._reject(
                "UNSUPPORTED_FACTUAL_CLAIM",
                "Rewrite omitted supported content terms: " + ", ".join(missing_content[:8]),
            )

        warnings: list[str] = []
        original_numbers = Counter(_NUMBER.findall(expected_original))
        improved_numbers = Counter(_NUMBER.findall(improved))
        if original_numbers - improved_numbers:
            warnings.append("The rewrite removed a number and requires human review.")
        if len(missing_content) >= 2:
            warnings.append(
                "The rewrite omitted descriptive terms that require review: "
                + ", ".join(missing_content[:6])
                + "."
            )
        return RewriteValidation(
            accepted=True,
            warnings=tuple(warnings),
            requires_review=bool(warnings),
        )

    def validate_skills(
        self,
        report: PipelineReport,
        *,
        expected_original: list[str],
        response_original: list[str] | None,
        improved_groups: list[SkillGroup],
        added_items: list[str],
        evidence_ids: list[str],
        removed_duplicates: list[str] | None = None,
    ) -> RewriteValidation:
        known = {item.id for item in report.evidence}
        if set(evidence_ids) - known:
            return self._reject("UNKNOWN_EVIDENCE_ID", "Skills rewrite cited unknown evidence")
        if response_original is not None and response_original != expected_original:
            return self._reject("ORIGINAL_TEXT_MISMATCH", "Skills originals do not match input")
        if added_items:
            invented = next((item for item in added_items if _technology_terms(item)), None)
            return self._reject(
                "INVENTED_TECHNOLOGY" if invented else "UNSUPPORTED_FACTUAL_CLAIM",
                "Skills rewrites may not add items",
            )
        if any(
            _INJECTION.search(value)
            for group in improved_groups
            for value in (group.group, *group.items)
        ):
            return self._reject("PROMPT_INJECTION_OUTPUT", "Instruction-like skill output")

        original_counts = Counter(self.skill_key(item) for item in expected_original)
        original_keys = set(original_counts)
        improved_items = [item for group in improved_groups for item in group.items]
        unsupported = [item for item in improved_items if self.skill_key(item) not in original_keys]
        if unsupported:
            code = (
                "INVENTED_TECHNOLOGY"
                if _technology_terms(" ".join(unsupported))
                else "UNSUPPORTED_FACTUAL_CLAIM"
            )
            return self._reject(code, f"Unsupported skills: {unsupported}")
        improved_counts = Counter(self.skill_key(item) for item in improved_items)
        improved_keys = set(improved_counts)
        missing = sorted(original_keys - improved_keys)
        if missing:
            return self._reject(
                "UNSUPPORTED_FACTUAL_CLAIM",
                f"Skills rewrite omitted supported items: {missing}",
            )
        removed_duplicates = removed_duplicates or []
        invalid_removed = [
            item
            for item in removed_duplicates
            if max(
                original_counts[self.skill_key(item)],
                improved_counts[self.skill_key(item)],
            )
            < 2
        ]
        if invalid_removed:
            return self._reject(
                "UNSUPPORTED_FACTUAL_CLAIM",
                f"Items reported as duplicates were not duplicates: {invalid_removed}",
            )
        return RewriteValidation(accepted=True)

    @staticmethod
    def skill_key(value: str) -> str:
        terms = _technology_terms(value)
        return next(iter(sorted(terms)), _normalize(value))

    @classmethod
    def _omitted_explicit_skills(
        cls,
        report: PipelineReport,
        original: str,
        improved: str,
    ) -> list[str]:
        omitted: list[str] = []
        for skill in report.entities.skills:
            if cls._phrase_present(original, skill.value) and not cls._phrase_present(
                improved,
                skill.value,
            ):
                omitted.append(skill.value)
        return list(dict.fromkeys(omitted))

    @staticmethod
    def _phrase_present(text: str, phrase: str) -> bool:
        technology = _technology_terms(phrase)
        if technology:
            return technology <= _technology_terms(text)
        normalized_text = re.sub(r"[^\w#+]+", " ", _normalize(text)).strip()
        normalized_phrase = re.sub(r"[^\w#+]+", " ", _normalize(phrase)).strip()
        return bool(
            normalized_phrase
            and re.search(
                rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)",
                normalized_text,
            )
        )

    @staticmethod
    def _missing_content_terms(original: str, improved: str) -> list[str]:
        def terms(value: str) -> list[tuple[str, str]]:
            values: list[tuple[str, str]] = []
            for token in re.findall(r"(?u)\b[\w+#-]{3,}\b", _normalize(value)):
                key = RewriteValidator._content_key(token)
                if key:
                    values.append((token, key))
            return values

        improved_terms = {key for _, key in terms(improved)}
        return list(
            dict.fromkeys(token for token, key in terms(original) if key not in improved_terms)
        )

    @staticmethod
    def _content_key(token: str) -> str | None:
        token = _normalize(token).strip("._-")
        if not token or token.isdigit() or token in _CONTENT_STOPWORDS:
            return None
        if re.search(r"[\u0600-\u06ff]", token):
            arabic_key = token
            if arabic_key[:1] in {"و", "ف"} and len(arabic_key) > 3:
                arabic_key = arabic_key[1:]
            if arabic_key in _ARABIC_CONTENT_STOPWORDS or any(
                arabic_key.startswith(prefix) for prefix in _ARABIC_ACTION_PREFIXES
            ):
                return None
            return arabic_key
        if token in _CONTENT_EQUIVALENTS:
            return _CONTENT_EQUIVALENTS[token]
        if token.endswith("ies") and len(token) > 4:
            key = f"{token[:-3]}y"
        elif token.endswith("ing") and len(token) > 5:
            key = token[:-3]
        elif token.endswith("ed") and len(token) > 4:
            key = token[:-2]
        elif token.endswith("es") and len(token) > 4:
            key = token[:-2]
        elif token.endswith("s") and len(token) > 3:
            key = token[:-1]
        else:
            key = token
        if any(
            token.startswith(prefix) or key.startswith(prefix)
            for prefix in _CONTENT_ACTION_PREFIXES
        ):
            return None
        return _CONTENT_EQUIVALENTS.get(key, key)

    @classmethod
    def _omitted_summary_claims(cls, original: str, improved: str) -> list[str]:
        improved_keys = {
            key
            for token in re.findall(r"(?u)\b[\w+#-]{3,}\b", _normalize(improved))
            if (key := cls._content_key(token))
        }
        omitted: list[str] = []
        for claim in cls._summary_claims(original):
            claim_keys = {
                key
                for token in re.findall(r"(?u)\b[\w+#-]{3,}\b", _normalize(claim))
                if (key := cls._content_key(token))
            }
            preserved_count = len(claim_keys.intersection(improved_keys))
            minimum_preserved = max(1, (len(claim_keys) + 1) // 2)
            if len(claim_keys) >= 2 and preserved_count < minimum_preserved:
                omitted.append(claim)
        return omitted

    @classmethod
    def restore_omitted_summary_claims(
        cls,
        report: PipelineReport,
        original: str,
        improved: str,
    ) -> str | None:
        """Append source claims containing coverage that a rewrite omitted."""

        missing_claims = cls._omitted_summary_claims(original, improved)
        missing_skills = cls._omitted_explicit_skills(report, original, improved)
        original_acronyms = {
            item
            for item in re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b", original)
            if item in _SUMMARY_ACRONYMS
        }
        improved_acronyms = {
            item
            for item in re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b", improved)
            if item in _SUMMARY_ACRONYMS
        }
        missing_acronyms = {
            acronym
            for acronym in original_acronyms - improved_acronyms
            if not any(
                re.search(rf"(?<!\w){re.escape(acronym)}(?!\w)", skill, re.IGNORECASE)
                for skill in missing_skills
            )
        }
        claims_to_restore: list[str] = []
        for claim in cls._summary_claims(original):
            if claim in missing_claims or any(
                re.search(rf"(?<!\w){re.escape(acronym)}(?!\w)", claim)
                for acronym in missing_acronyms
            ):
                claims_to_restore.append(claim)
        uncovered_skills = [
            skill
            for skill in missing_skills
            if not any(cls._phrase_present(claim, skill) for claim in claims_to_restore)
        ]
        if _language(original) != "en":
            for claim in cls._summary_claims(original):
                if any(cls._phrase_present(claim, skill) for skill in uncovered_skills):
                    claims_to_restore.append(claim)
            uncovered_skills = []
        if not claims_to_restore and not uncovered_skills:
            return None
        restored = " ".join(str(improved or "").split()).strip()
        additions: list[str] = []
        for claim in claims_to_restore:
            clean = " ".join(claim.split()).strip()
            if not clean:
                continue
            if clean[-1] not in ".!?\u061f":
                clean = f"{clean}."
            additions.append(clean)
        if uncovered_skills:
            if len(uncovered_skills) == 1:
                skill_list = uncovered_skills[0]
            else:
                skill_list = f"{', '.join(uncovered_skills[:-1])} and {uncovered_skills[-1]}"
            additions.append(f"Supported skills include {skill_list}.")
        if not additions:
            return None
        if restored and restored[-1] not in ".!?\u061f":
            restored = f"{restored}."
        return " ".join([restored, *additions]).strip()

    @staticmethod
    def _summary_claims(value: str) -> list[str]:
        lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
        has_bullets = any(_SUMMARY_BULLET.match(line) for line in lines)
        if has_bullets:
            claims: list[str] = []
            current = ""
            for line in lines:
                if _SUMMARY_BULLET.match(line):
                    if current:
                        claims.append(current)
                    current = _SUMMARY_BULLET.sub("", line).strip()
                elif current:
                    current = f"{current} {line}".strip()
            if current:
                claims.append(current)
            return claims
        combined = " ".join(lines)
        return [claim.strip() for claim in re.split(r"(?<=[.!?؟])\s+", combined) if claim.strip()]

    def _compare_tokens(
        self,
        pattern: re.Pattern,
        original: str,
        improved: str,
        invented_code: str,
        changed_code: str,
    ) -> RewriteValidation | None:
        original_values = Counter(_normalize(item) for item in pattern.findall(original))
        improved_values = Counter(_normalize(item) for item in pattern.findall(improved))
        added = improved_values - original_values
        if added:
            code = changed_code if original_values else invented_code
            return self._reject(code, f"Added or changed protected value: {next(iter(added))}")
        removed = original_values - improved_values
        if removed:
            return self._reject(
                changed_code,
                f"Removed protected value: {next(iter(removed))}",
            )
        return None

    @staticmethod
    def _reject(code: str, message: str) -> RewriteValidation:
        return RewriteValidation(False, code=code, message=message, requires_review=True)
