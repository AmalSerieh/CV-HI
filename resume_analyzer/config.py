"""Configuration with safe offline defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_int(value: int, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class PipelineConfig:
    enable_ocr: bool = True
    ocr_language: str = "eng"
    tesseract_cmd: str | None = None
    use_spacy: bool = False
    use_sbert: bool = False
    allow_model_download: bool = False
    integrate_target_role: bool = True
    enable_recommendations: bool = True
    enable_ats: bool = True
    enable_rewrites: bool = False
    rewrite_sections: tuple[str, ...] = ("summary", "experience", "skills")
    rewrite_language: str | None = None
    max_document_bytes: int = 20_000_000
    max_document_characters: int = 250_000
    max_job_description_characters: int = 50_000
    max_prompt_characters: int = 50_000
    max_model_output_characters: int = 50_000
    max_summary_characters: int = 800
    max_bullet_characters: int = 500
    include_document_path: bool = False
    ai_provider: str = "none"
    ai_model: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ai_timeout_seconds: float = 20.0
    ai_retries: int = 1
    ai_retry_timeouts: bool = False
    ai_connect_timeout_seconds: float = 5.0
    ai_warmup: bool = False
    ai_warmup_timeout_seconds: float = 120.0
    ai_recommendation_timeout_seconds: float = 120.0
    ai_rewrite_timeout_seconds: float = 90.0
    ai_temperature: float = 0.0
    ai_seed: int = 42
    ai_max_tokens: int = 2048
    recommendation_max_output_tokens: int = 224
    rewrite_max_output_tokens: int = 1024
    summary_rewrite_max_output_tokens: int = 1024
    bullet_rewrite_max_output_tokens: int = 1024
    skills_rewrite_max_output_tokens: int = 1024
    skills_rewrite_ai_max_items: int = 24
    ollama_num_ctx: int = 4096
    ollama_keep_alive: str = "10m"
    ollama_cancel_cooldown_seconds: float = 2.0
    recommendation_max_skills: int = 16
    recommendation_max_experience_entries: int = 4
    recommendation_max_bullets_per_experience: int = 2
    recommendation_max_projects: int = 3
    recommendation_max_field_characters: int = 400
    recommendation_max_prompt_characters: int = 8_000
    recommendation_max_evidence_records: int = 10
    rewrite_max_bullets: int = 20
    rewrite_absolute_max_bullets: int = 20
    rewrite_bullet_selection: tuple[int, ...] | None = None
    rewrite_all_bullets: bool = False
    rewrite_max_input_characters: int = 12_000

    def __post_init__(self) -> None:
        if self.ai_timeout_seconds <= 0:
            raise ValueError("ai_timeout_seconds must be positive")
        if self.ai_retries < 0:
            raise ValueError("ai_retries cannot be negative")
        for value, name in (
            (self.ai_connect_timeout_seconds, "ai_connect_timeout_seconds"),
            (self.ai_warmup_timeout_seconds, "ai_warmup_timeout_seconds"),
            (self.ai_recommendation_timeout_seconds, "ai_recommendation_timeout_seconds"),
            (self.ai_rewrite_timeout_seconds, "ai_rewrite_timeout_seconds"),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.ollama_cancel_cooldown_seconds < 0:
            raise ValueError("ollama_cancel_cooldown_seconds cannot be negative")
        if not 0 <= self.ai_temperature <= 2:
            raise ValueError("ai_temperature must be between 0 and 2")
        _positive_int(self.ai_max_tokens, "ai_max_tokens")
        for value, name in (
            (self.recommendation_max_output_tokens, "recommendation_max_output_tokens"),
            (self.rewrite_max_output_tokens, "rewrite_max_output_tokens"),
            (self.summary_rewrite_max_output_tokens, "summary_rewrite_max_output_tokens"),
            (self.bullet_rewrite_max_output_tokens, "bullet_rewrite_max_output_tokens"),
            (self.skills_rewrite_max_output_tokens, "skills_rewrite_max_output_tokens"),
            (self.skills_rewrite_ai_max_items, "skills_rewrite_ai_max_items"),
            (self.ollama_num_ctx, "ollama_num_ctx"),
            (self.recommendation_max_skills, "recommendation_max_skills"),
            (
                self.recommendation_max_experience_entries,
                "recommendation_max_experience_entries",
            ),
            (
                self.recommendation_max_bullets_per_experience,
                "recommendation_max_bullets_per_experience",
            ),
            (self.recommendation_max_projects, "recommendation_max_projects"),
            (self.recommendation_max_field_characters, "recommendation_max_field_characters"),
            (self.recommendation_max_prompt_characters, "recommendation_max_prompt_characters"),
            (self.recommendation_max_evidence_records, "recommendation_max_evidence_records"),
            (self.rewrite_max_bullets, "rewrite_max_bullets"),
            (self.rewrite_absolute_max_bullets, "rewrite_absolute_max_bullets"),
            (self.rewrite_max_input_characters, "rewrite_max_input_characters"),
        ):
            _positive_int(value, name)
        for value, name in (
            (self.max_document_bytes, "max_document_bytes"),
            (self.max_document_characters, "max_document_characters"),
            (self.max_job_description_characters, "max_job_description_characters"),
            (self.max_prompt_characters, "max_prompt_characters"),
            (self.max_model_output_characters, "max_model_output_characters"),
            (self.max_summary_characters, "max_summary_characters"),
            (self.max_bullet_characters, "max_bullet_characters"),
        ):
            _positive_int(value, name)
        allowed_sections = {"summary", "experience", "skills"}
        if not self.rewrite_sections or set(self.rewrite_sections) - allowed_sections:
            raise ValueError("rewrite_sections must contain summary, experience, and/or skills")
        if self.rewrite_language not in {None, "en", "ar", "mixed"}:
            raise ValueError("rewrite_language must be en, ar, mixed, or unset")
        if self.rewrite_bullet_selection is not None:
            if any(value < 0 for value in self.rewrite_bullet_selection):
                raise ValueError("rewrite_bullet_selection indices cannot be negative")
            if len(self.rewrite_bullet_selection) != len(set(self.rewrite_bullet_selection)):
                raise ValueError("rewrite_bullet_selection indices must be unique")
        if self.allow_model_download and not (
            self.use_sbert
            or self.use_spacy
            or self.ai_provider.casefold() in {"transformers", "huggingface", "hf"}
        ):
            raise ValueError("allow_model_download requires an enabled model feature")

    @classmethod
    def from_env(cls) -> PipelineConfig:
        def flag(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            normalized = raw.strip().casefold()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise ValueError(f"{name} must be a boolean value")

        legacy_timeout = float(os.getenv("RESUME_AI_TIMEOUT_SECONDS", "60"))
        legacy_max_tokens = int(os.getenv("RESUME_AI_MAX_TOKENS", "2048"))
        legacy_rewrite_tokens = int(os.getenv("RESUME_REWRITE_MAX_OUTPUT_TOKENS", "256"))
        raw_bullet_selection = os.getenv("RESUME_REWRITE_BULLET_SELECTION", "").strip()
        bullet_selection = (
            tuple(
                int(value.strip()) - 1 for value in raw_bullet_selection.split(",") if value.strip()
            )
            if raw_bullet_selection
            else None
        )
        return cls(
            enable_ocr=flag("RESUME_ENABLE_OCR", True),
            ocr_language=os.getenv("TESSERACT_LANGUAGES", os.getenv("RESUME_OCR_LANGUAGE", "eng")),
            tesseract_cmd=os.getenv("TESSERACT_CMD", os.getenv("RESUME_TESSERACT_CMD", "")) or None,
            use_spacy=flag("RESUME_USE_SPACY", False),
            use_sbert=flag("RESUME_USE_SBERT", False),
            allow_model_download=flag("RESUME_ALLOW_MODEL_DOWNLOAD", False),
            integrate_target_role=flag("RESUME_ENABLE_TARGET_ROLE", True),
            enable_recommendations=flag("RESUME_ENABLE_RECOMMENDATIONS", True),
            enable_ats=flag("RESUME_ENABLE_ATS", True),
            enable_rewrites=flag("RESUME_ENABLE_REWRITES", False),
            rewrite_sections=tuple(
                item.strip().casefold()
                for item in os.getenv("RESUME_REWRITE_SECTIONS", "summary,experience,skills").split(
                    ","
                )
                if item.strip()
            ),
            rewrite_language=os.getenv("RESUME_REWRITE_LANGUAGE") or None,
            max_document_bytes=int(
                os.getenv(
                    "RESUME_MAX_DOCUMENT_BYTES",
                    str(int(os.getenv("RESUME_MAX_UPLOAD_MB", "10")) * 1_000_000),
                )
            ),
            max_document_characters=int(
                os.getenv(
                    "RESUME_MAX_DOCUMENT_CHARACTERS",
                    os.getenv("RESUME_MAX_EXTRACTED_CHARS", "200000"),
                )
            ),
            max_job_description_characters=int(
                os.getenv(
                    "RESUME_MAX_JOB_DESCRIPTION_CHARACTERS",
                    os.getenv("RESUME_MAX_JOB_DESCRIPTION_CHARS", "30000"),
                )
            ),
            max_prompt_characters=int(os.getenv("RESUME_MAX_PROMPT_CHARACTERS", "50000")),
            max_model_output_characters=int(
                os.getenv("RESUME_MAX_MODEL_OUTPUT_CHARACTERS", "50000")
            ),
            max_summary_characters=int(os.getenv("RESUME_MAX_SUMMARY_CHARACTERS", "800")),
            max_bullet_characters=int(os.getenv("RESUME_MAX_BULLET_CHARACTERS", "500")),
            include_document_path=flag(
                "RESUME_PUBLIC_ABSOLUTE_PATHS",
                flag("RESUME_INCLUDE_DOCUMENT_PATH", False),
            ),
            ai_provider=os.getenv("RESUME_AI_PROVIDER", "none"),
            ai_model=os.getenv("RESUME_AI_MODEL") or None,
            ollama_base_url=os.getenv("RESUME_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            ai_timeout_seconds=float(os.getenv("RESUME_AI_TIMEOUT_SECONDS", "60")),
            ai_retries=int(os.getenv("RESUME_AI_MAX_RETRIES", os.getenv("RESUME_AI_RETRIES", "1"))),
            ai_retry_timeouts=flag("RESUME_AI_RETRY_TIMEOUTS", False),
            ai_connect_timeout_seconds=float(os.getenv("RESUME_AI_CONNECT_TIMEOUT_SECONDS", "5")),
            ai_warmup=flag("RESUME_AI_WARMUP", False),
            ai_warmup_timeout_seconds=float(
                os.getenv("RESUME_AI_WARMUP_TIMEOUT_SECONDS", str(legacy_timeout))
            ),
            ai_recommendation_timeout_seconds=float(
                os.getenv("RESUME_AI_RECOMMENDATION_TIMEOUT_SECONDS", str(legacy_timeout))
            ),
            ai_rewrite_timeout_seconds=float(
                os.getenv("RESUME_AI_REWRITE_TIMEOUT_SECONDS", str(legacy_timeout))
            ),
            ai_temperature=float(os.getenv("RESUME_AI_TEMPERATURE", "0")),
            ai_seed=int(os.getenv("RESUME_AI_SEED", "42")),
            ai_max_tokens=legacy_max_tokens,
            recommendation_max_output_tokens=int(
                os.getenv("RESUME_RECOMMENDATION_MAX_OUTPUT_TOKENS", "224")
            ),
            rewrite_max_output_tokens=legacy_rewrite_tokens,
            summary_rewrite_max_output_tokens=int(
                os.getenv("RESUME_SUMMARY_REWRITE_MAX_OUTPUT_TOKENS", "384")
            ),
            bullet_rewrite_max_output_tokens=int(
                os.getenv("RESUME_BULLET_REWRITE_MAX_OUTPUT_TOKENS", "256")
            ),
            skills_rewrite_max_output_tokens=int(
                os.getenv("RESUME_SKILLS_REWRITE_MAX_OUTPUT_TOKENS", "768")
            ),
            skills_rewrite_ai_max_items=int(os.getenv("RESUME_SKILLS_REWRITE_AI_MAX_ITEMS", "24")),
            ollama_num_ctx=int(os.getenv("RESUME_OLLAMA_NUM_CTX", "4096")),
            ollama_keep_alive=os.getenv("RESUME_OLLAMA_KEEP_ALIVE", "10m"),
            ollama_cancel_cooldown_seconds=float(
                os.getenv("RESUME_OLLAMA_CANCEL_COOLDOWN_SECONDS", "2")
            ),
            recommendation_max_skills=int(os.getenv("RESUME_RECOMMENDATION_MAX_SKILLS", "16")),
            recommendation_max_experience_entries=int(
                os.getenv("RESUME_RECOMMENDATION_MAX_EXPERIENCE_ENTRIES", "4")
            ),
            recommendation_max_bullets_per_experience=int(
                os.getenv("RESUME_RECOMMENDATION_MAX_BULLETS_PER_EXPERIENCE", "2")
            ),
            recommendation_max_projects=int(os.getenv("RESUME_RECOMMENDATION_MAX_PROJECTS", "3")),
            recommendation_max_field_characters=int(
                os.getenv("RESUME_RECOMMENDATION_MAX_FIELD_CHARACTERS", "400")
            ),
            recommendation_max_prompt_characters=int(
                os.getenv("RESUME_RECOMMENDATION_MAX_PROMPT_CHARACTERS", "8000")
            ),
            recommendation_max_evidence_records=int(
                os.getenv("RESUME_RECOMMENDATION_MAX_EVIDENCE_RECORDS", "10")
            ),
            rewrite_max_bullets=int(os.getenv("RESUME_REWRITE_MAX_BULLETS", "20")),
            rewrite_absolute_max_bullets=int(
                os.getenv("RESUME_REWRITE_ABSOLUTE_MAX_BULLETS", "20")
            ),
            rewrite_bullet_selection=bullet_selection,
            rewrite_all_bullets=flag("RESUME_REWRITE_ALL_BULLETS", False),
            rewrite_max_input_characters=int(os.getenv("RESUME_REWRITE_MAX_INPUT_CHARS", "12000")),
        )
