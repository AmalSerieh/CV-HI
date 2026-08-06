"""Application factory and local Uvicorn entry point."""

from __future__ import annotations

import socket
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .build_info import SourceFingerprintMonitor, build_state, source_fingerprint
from .config import WebSettings
from .routes.api import router as api_router
from .routes.pages import router as page_router
from .services import AnalysisService, JobStore, UploadService


def create_app(
    settings: WebSettings | None = None,
    *,
    pipeline_factory: Callable[[Any], Any] | None = None,
) -> FastAPI:
    selected = settings or WebSettings.from_env()
    selected.prepare_runtime_directories()
    startup_fingerprint = source_fingerprint()
    fingerprint_monitor = SourceFingerprintMonitor(initial=startup_fingerprint)
    package_dir = Path(__file__).resolve().parent
    uploads = UploadService(selected)
    store = JobStore(selected.result_ttl_minutes, uploads.cleanup)
    analysis = AnalysisService(selected, store, uploads, pipeline_factory)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        analysis.shutdown()

    app = FastAPI(
        title="Resume Intelligence Platform",
        version="2.1.0",
        debug=selected.debug,
        lifespan=lifespan,
    )
    app.state.settings = selected
    app.state.upload_service = uploads
    app.state.job_store = store
    app.state.analysis_service = analysis
    app.state.startup_source_fingerprint = startup_fingerprint
    app.state.source_fingerprint_provider = fingerprint_monitor
    app.state.templates = Jinja2Templates(directory=package_dir / "templates")
    app.state.templates.env.globals["backend_build_state"] = lambda: build_state(
        app.state.startup_source_fingerprint,
        app.state.source_fingerprint_provider,
    )
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=package_dir / "static", html=True), name="static")
    app.include_router(page_router)
    app.include_router(api_router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        source = build_state(
            request.app.state.startup_source_fingerprint,
            request.app.state.source_fingerprint_provider,
        )
        # فقط أضف nosniff للملفات غير الثابتة
        if not request.url.path.startswith("/static/"):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        response.headers.setdefault("X-Resume-Build", source["build_id"])
        response.headers.setdefault(
            "X-Resume-Source-Stale",
            "true" if source["restart_required"] else "false",
        )
        return response

    @app.exception_handler(Exception)
    async def safe_error(_request: Request, _exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed.",
                }
            },
        )

    return app


app = create_app()


def _port_is_in_use(host: str, port: int) -> bool:
    probe_host = {
        "0.0.0.0": "127.0.0.1",
        "::": "::1",
    }.get(host, host)
    family = socket.AF_INET6 if ":" in probe_host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.25)
            return connection.connect_ex((probe_host, port)) == 0
    except OSError:
        return False


def main() -> None:
    settings = WebSettings.from_env()
    if _port_is_in_use(settings.host, settings.port):
        raise SystemExit(
            f"Port {settings.port} already has a local server. Stop the existing "
            "process with Ctrl+C, then launch again so updated backend code is loaded."
        )
    print(f"Resume Intelligence Platform: http://{settings.host}:{settings.port}")
    uvicorn.run(
        "resume_analyzer.web.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        reload_dirs=[str(Path(__file__).resolve().parents[1])] if settings.reload else None,
    )


if __name__ == "__main__":
    main()
