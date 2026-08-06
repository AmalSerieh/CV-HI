"""Privacy-safe analysis and capability API."""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from resume_analyzer.diagnostics.health import application_health, system_capabilities
from resume_analyzer.diagnostics.models import model_status

from ..build_info import build_state
from ..models import AnalysisOptions
from ..services import AnalysisNotFound, TooManyAnalyses, UploadValidationError

router = APIRouter(prefix="/api")


def _boolean(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise HTTPException(status_code=422, detail="A feature toggle has an invalid value.")


def _identifier(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid analysis identifier.") from exc


def _record(request: Request, analysis_id: str):
    try:
        return request.app.state.job_store.get(_identifier(analysis_id))
    except AnalysisNotFound as exc:
        raise HTTPException(status_code=404, detail="Analysis not found or expired.") from exc


@router.post("/analyses", status_code=202)
async def create_analysis(
    request: Request,
    resume: Annotated[UploadFile, File()],
    job_description_text: str | None = Form(default=None),
    job_description_file: Annotated[UploadFile | None, File()] = None,
    enable_target_role: str | None = Form(default=None),
    enable_recommendations: str | None = Form(default=None),
    enable_ats: str | None = Form(default=None),
    enable_job_match: str | None = Form(default=None),
    enable_rewrites: str | None = Form(default=None),
    enable_ocr: str | None = Form(default=None),
    ai_provider: str = Form(default="none"),
    ai_model: str | None = Form(default=None),
    output_language: str = Form(default="auto"),
    rewrite_summary: str | None = Form(default=None),
    rewrite_experience: str | None = Form(default=None),
    rewrite_skills: str | None = Form(default=None),
    bullet_rewrite_mode: str = Form(default="first"),
    bullet_rewrite_count: int = Form(default=20),
    bullet_rewrite_selection: str = Form(default=""),
):
    source = build_state(
        request.app.state.startup_source_fingerprint,
        request.app.state.source_fingerprint_provider,
    )
    if source["restart_required"]:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "backend_restart_required",
                    "message": (
                        "The backend source changed after this server started. "
                        "Restart the local web application before analyzing another resume."
                    ),
                },
                "build": source,
            },
            headers={"Retry-After": "1"},
        )
    uploads = request.app.state.upload_service
    try:
        prepared = await uploads.prepare(
            resume,
            job_description_text=job_description_text,
            job_description_file=job_description_file,
        )
    except UploadValidationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
    language = None if output_language == "auto" else output_language
    if language not in {None, "en", "ar"}:
        uploads.cleanup(prepared.directory)
        raise HTTPException(status_code=422, detail="Invalid output language.")
    sections = tuple(
        name
        for name, enabled in (
            ("summary", _boolean(rewrite_summary, True)),
            ("experience", _boolean(rewrite_experience, True)),
            ("skills", _boolean(rewrite_skills, True)),
        )
        if enabled
    )
    if not sections:
        uploads.cleanup(prepared.directory)
        raise HTTPException(status_code=422, detail="Select at least one rewrite section.")
    bullet_rewrite_mode = bullet_rewrite_mode.strip().casefold()
    if bullet_rewrite_mode not in {"first", "specific", "all"}:
        uploads.cleanup(prepared.directory)
        raise HTTPException(status_code=422, detail="Invalid bullet rewrite mode.")
    if not 1 <= bullet_rewrite_count <= 20:
        uploads.cleanup(prepared.directory)
        raise HTTPException(
            status_code=422, detail="Bullet rewrite count must be between 1 and 20."
        )
    try:
        selected_bullets = tuple(
            dict.fromkeys(
                int(value.strip()) - 1
                for value in bullet_rewrite_selection.split(",")
                if value.strip()
            )
        )
    except ValueError as exc:
        uploads.cleanup(prepared.directory)
        raise HTTPException(
            status_code=422, detail="Specific bullet numbers must be comma-separated integers."
        ) from exc
    if bullet_rewrite_mode == "specific" and (
        not selected_bullets
        or any(value < 0 for value in selected_bullets)
        or len(selected_bullets) > 20
    ):
        uploads.cleanup(prepared.directory)
        raise HTTPException(
            status_code=422, detail="Select between 1 and 20 positive bullet numbers."
        )
    options = AnalysisOptions(
        enable_target_role=_boolean(enable_target_role, True),
        enable_recommendations=_boolean(enable_recommendations, True),
        enable_ats=_boolean(enable_ats, True),
        enable_job_match=_boolean(enable_job_match, True),
        enable_rewrites=_boolean(enable_rewrites, False),
        enable_ocr=_boolean(enable_ocr, True),
        ai_provider=ai_provider,
        ai_model=ai_model,
        output_language=language,
        rewrite_sections=sections,
        bullet_rewrite_mode=bullet_rewrite_mode,
        bullet_rewrite_count=bullet_rewrite_count,
        bullet_rewrite_selection=(selected_bullets if bullet_rewrite_mode == "specific" else None),
    )
    try:
        record = request.app.state.analysis_service.submit(prepared, options)
    except TooManyAnalyses:
        uploads.cleanup(prepared.directory)
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "analysis_capacity_reached",
                    "message": "The local analysis capacity is full. Try again shortly.",
                }
            },
            headers={"Retry-After": "5"},
        )
    return {
        "analysis_id": str(record.id),
        "status": record.status,
        "status_url": f"/api/analyses/{record.id}",
        "result_url": f"/api/analyses/{record.id}/result",
        "page_url": f"/results/{record.id}",
    }


@router.get("/analyses/{analysis_id}")
def analysis_status(request: Request, analysis_id: str):
    return _record(request, analysis_id).public_status()


@router.get("/analyses/{analysis_id}/result")
def analysis_result(request: Request, analysis_id: str):
    record = _record(request, analysis_id)
    if record.status != "completed" or record.result is None:
        raise HTTPException(status_code=409, detail="The result is not available yet.")
    return record.result


@router.get("/analyses/{analysis_id}/download")
def analysis_download(request: Request, analysis_id: str):
    record = _record(request, analysis_id)
    if record.status != "completed" or record.result is None:
        raise HTTPException(status_code=409, detail="The result is not available yet.")
    payload = json.dumps(record.result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    return Response(
        content=payload.encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="analysis-{record.id}.json"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(request: Request, analysis_id: str):
    try:
        request.app.state.job_store.delete(_identifier(analysis_id))
    except AnalysisNotFound as exc:
        raise HTTPException(status_code=404, detail="Analysis not found or expired.") from exc
    return Response(status_code=204)


@router.get("/health")
def health(request: Request):
    payload = application_health(request.app.state.settings)
    payload["build"] = build_state(
        request.app.state.startup_source_fingerprint,
        request.app.state.source_fingerprint_provider,
    )
    return payload


@router.get("/system")
def system(request: Request):
    return system_capabilities(request.app.state.settings, public=True)


@router.get("/models")
def models():
    return model_status(public=True)
