"""Internal web job and option models; canonical report models remain in schemas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnalysisOptions:
    enable_target_role: bool = True
    enable_recommendations: bool = True
    enable_ats: bool = True
    enable_job_match: bool = True
    enable_rewrites: bool = False
    enable_ocr: bool = True
    ai_provider: str = "none"
    ai_model: str | None = None
    output_language: str | None = None
    rewrite_sections: tuple[str, ...] = ("summary", "experience", "skills")
    bullet_rewrite_mode: str = "first"
    bullet_rewrite_count: int = 20
    bullet_rewrite_selection: tuple[int, ...] | None = None


@dataclass(frozen=True)
class PreparedUpload:
    directory: Path
    resume_path: Path
    original_name: str
    job_description: str | None = None
