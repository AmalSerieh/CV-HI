"""Server-rendered HTML pages."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from resume_analyzer.diagnostics.models import model_status

from ..services import AnalysisNotFound

router = APIRouter()


def _model_view() -> dict:
    """Keep the analysis form available when local-model discovery is unavailable."""

    try:
        return model_status(public=True)
    except (OSError, RuntimeError, ValueError):
        return {
            "configured_provider": "none",
            "configured_model": None,
            "fallback_available": True,
            "ollama": {
                "reachable": False,
                "available_models": [],
            },
            "transformers": {
                "installed": False,
            },
        }


def _evidence_label(field_path: str) -> str:
    """Turn canonical paths into short labels intended for resume owners."""

    normalized = field_path.casefold()
    if normalized.startswith("entities.contact."):
        field = field_path.rsplit(".", 1)[-1].replace("_", " ").title()
        return f"Contact information: {field}"
    if normalized.startswith("entities.skills"):
        return "Extracted skill"
    if normalized.startswith("entities.summary"):
        return "Professional summary"
    if normalized.startswith("entities.experience"):
        return "Experience entry"
    if normalized.startswith("entities.projects"):
        return "Project entry"
    if normalized.startswith("entities.education"):
        return "Education entry"
    if normalized.startswith("entities.languages"):
        return "Language entry"
    if ".heading" in normalized:
        return "Section heading"
    if normalized.startswith("extraction.layout_blocks"):
        return "Document text sample"
    if normalized.startswith("extraction.sections"):
        return "Extracted resume section"
    if "quality" in normalized:
        return "Extraction quality check"
    if "layout" in normalized or "reading_order" in normalized:
        return "Document layout check"
    return "Resume evidence"


def _evidence_view(report: dict) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for evidence in report.get("evidence", []):
        value = evidence.get("value")
        if value is None:
            value = (
                "Not present in the analyzed resume."
                if evidence.get("kind") == "missing"
                else "Recorded without a display value."
            )
        output[str(evidence["id"])] = {
            "label": _evidence_label(str(evidence.get("field_path", ""))),
            "value": value,
            "kind": evidence.get("kind", "present"),
        }
    return output


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"page_title": "Resume Intelligence Platform", "direction": "ltr"},
    )


@router.get("/analyze", response_class=HTMLResponse)
def analyze_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="analyze.html",
        context={
            "page_title": "Analyze a resume",
            "direction": "ltr",
            "settings": request.app.state.settings,
            "models": _model_view(),
        },
    )


@router.get("/results/{analysis_id}", response_class=HTMLResponse)
def result_page(request: Request, analysis_id: str):
    templates = request.app.state.templates
    try:
        identifier = UUID(analysis_id)
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "page_title": "Invalid analysis",
                "direction": "ltr",
                "message": "The analysis identifier is not valid.",
            },
            status_code=400,
        )
    try:
        record = request.app.state.job_store.get(identifier)
    except AnalysisNotFound:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "page_title": "Analysis not found",
                "direction": "ltr",
                "message": "This temporary analysis does not exist or has expired.",
            },
            status_code=404,
        )
    if record.status == "failed":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "page_title": "Analysis could not be completed",
                "direction": "ltr",
                "message": (record.error or {}).get("message", "Analysis failed."),
            },
            status_code=422,
        )
    if record.status != "completed" or record.result is None:
        return templates.TemplateResponse(
            request=request,
            name="progress.html",
            context={
                "page_title": "Analysis in progress",
                "direction": "ltr",
                "analysis_id": str(identifier),
            },
        )
    report = record.result
    language = (
        (report.get("target_role") or {}).get("language")
        or (report.get("ats") or {}).get("language")
        or "en"
    )
    direction = "rtl" if language == "ar" else "ltr"
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "page_title": "Analysis results",
            "direction": direction,
            "analysis_id": str(identifier),
            "report": report,
            "evidence_by_id": _evidence_view(report),
        },
    )
