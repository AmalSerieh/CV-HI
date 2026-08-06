"""Bounded background execution of the one canonical pipeline."""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Lock
from typing import Any

from pydantic import ValidationError

from resume_analyzer import PipelineConfig, ResumePipeline
from resume_analyzer.schemas import PipelineReport

from ..config import WebSettings
from ..models import AnalysisOptions, PreparedUpload
from .job_store import JobRecord, JobStore, TooManyAnalyses
from .upload_service import UploadService

PipelineFactory = Callable[[PipelineConfig], Any]


class AnalysisService:
    def __init__(
        self,
        settings: WebSettings,
        store: JobStore,
        uploads: UploadService,
        pipeline_factory: PipelineFactory | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.uploads = uploads
        self.pipeline_factory = pipeline_factory or (lambda config: ResumePipeline(config=config))
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_analyses,
            thread_name_prefix="resume-analysis",
        )
        self._active = 0
        self._active_lock = Lock()

    def submit(self, upload: PreparedUpload, options: AnalysisOptions) -> JobRecord:
        with self._active_lock:
            if self._active >= self.settings.max_concurrent_analyses:
                raise TooManyAnalyses("The local analysis capacity is currently full")
            self._active += 1
        try:
            record = self.store.create(upload.directory, upload.original_name)
            self._executor.submit(self._run, record.id, upload, options)
            return record
        except Exception:
            with self._active_lock:
                self._active -= 1
            self.uploads.cleanup(upload.directory)
            raise

    def _run(self, analysis_id, upload: PreparedUpload, options: AnalysisOptions) -> None:
        try:
            self.store.update_stage(analysis_id, "running_pipeline")
            config = self._pipeline_config(options)
            pipeline = self.pipeline_factory(config)
            job_description = upload.job_description if options.enable_job_match else None
            result = pipeline.analyze(
                str(upload.resume_path),
                job_description=job_description,
            )
            self.store.update_stage(
                analysis_id,
                "validating_final_report",
                completed="running_pipeline",
            )
            canonical = PipelineReport.model_validate(result).to_json_dict()
            canonical["document"]["name"] = upload.original_name
            canonical["document"]["path"] = None
            if canonical["document"]["pages"] > self.settings.max_pages:
                raise ValueError("page_limit_exceeded")
            if canonical["extraction"]["character_count"] > self.settings.max_extracted_chars:
                raise ValueError("extracted_text_limit_exceeded")
            safe_result = self._remove_absolute_paths(canonical)
            safe_result = PipelineReport.model_validate(safe_result).to_json_dict()
            # A terminal "completed" state guarantees the private upload is already gone.
            self.uploads.cleanup(upload.directory)
            self.store.complete(analysis_id, safe_result)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            code, message = self._safe_failure(exc)
            self.store.fail(analysis_id, code, message)
        finally:
            self.uploads.cleanup(upload.directory)
            with self._active_lock:
                self._active = max(0, self._active - 1)

    def _pipeline_config(self, options: AnalysisOptions) -> PipelineConfig:
        base = PipelineConfig.from_env()
        provider = options.ai_provider.strip().casefold()
        if provider not in {"none", "ollama", "transformers"}:
            raise ValueError("invalid_ai_provider")
        model = (options.ai_model or "").strip() or None
        if model and (len(model) > 160 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model)):
            raise ValueError("invalid_ai_model")
        return replace(
            base,
            enable_ocr=options.enable_ocr,
            integrate_target_role=options.enable_target_role,
            enable_recommendations=options.enable_recommendations,
            enable_ats=options.enable_ats,
            enable_rewrites=options.enable_rewrites,
            rewrite_sections=options.rewrite_sections,
            rewrite_language=options.output_language,
            rewrite_max_bullets=options.bullet_rewrite_count,
            rewrite_bullet_selection=options.bullet_rewrite_selection,
            rewrite_all_bullets=options.bullet_rewrite_mode == "all",
            max_document_bytes=self.settings.max_upload_bytes,
            max_document_characters=self.settings.max_extracted_chars,
            max_job_description_characters=self.settings.max_job_description_chars,
            include_document_path=False,
            ai_provider=provider,
            ai_model=model if provider != "none" else None,
        )

    def _remove_absolute_paths(self, value: Any, key: str = "") -> Any:
        if key.casefold() in {"path", "file_path", "source_path", "temp_dir"} and (
            value is None or (isinstance(value, str) and self._is_absolute_path(value))
        ):
            return None
        if isinstance(value, dict):
            return {name: self._remove_absolute_paths(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return [self._remove_absolute_paths(item) for item in value]
        if isinstance(value, str) and self._is_absolute_path(value):
            return "[local path hidden]"
        return value

    @staticmethod
    def _is_absolute_path(value: str) -> bool:
        return bool(re.search(r"(?i)\b[A-Z]:[\\/]", value)) or value.startswith(
            ("/home/", "/Users/", "/tmp/")
        )

    @staticmethod
    def _safe_failure(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, ValidationError):
            return "invalid_pipeline_report", "The analysis produced an invalid report."
        if str(exc) == "page_limit_exceeded":
            return "too_many_pages", "The document exceeds the configured page limit."
        if str(exc) == "extracted_text_limit_exceeded":
            return "extracted_text_too_large", "The extracted text exceeds the safety limit."
        if str(exc) in {"invalid_ai_provider", "invalid_ai_model"}:
            return str(exc), "The selected local AI configuration is not valid."
        return (
            "analysis_failed",
            "The resume could not be analyzed. Check the document and settings.",
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.store.clear()
