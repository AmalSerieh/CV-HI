"""Validate the complete application workflow over a real loopback HTTP server."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx

from resume_analyzer import PipelineConfig
from resume_analyzer.environment import load_env_file
from resume_analyzer.web.build_info import source_fingerprint


def _url(base_url: str, path: str) -> str:
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _require(response: httpx.Response, status: int) -> httpx.Response:
    if response.status_code != status:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path} returned "
            f"{response.status_code}, expected {status}"
        )
    return response


def _require_runtime_build(health: dict, expected_fingerprint: str) -> None:
    build = health.get("build")
    if not isinstance(build, dict):
        raise RuntimeError(
            "The server does not expose a backend build identity. "
            "It is likely a stale pre-fix process; stop it and launch a new server."
        )
    if build.get("restart_required"):
        raise RuntimeError("The server reports changed source and requires a restart.")
    expected_id = expected_fingerprint[:12]
    if build.get("build_id") != expected_id:
        raise RuntimeError(
            f"Server build {build.get('build_id')!r} does not match current source "
            f"{expected_id!r}; stop the stale listener and relaunch."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--resume",
        type=Path,
        default=Path("runtime/live-validation/synthetic_resume.pdf"),
    )
    parser.add_argument("--poll-timeout", type=float, default=420)
    parser.add_argument(
        "--live-ai",
        action="store_true",
        help="Use the configured local provider and enable bounded summary rewriting.",
    )
    args = parser.parse_args()
    if not args.resume.is_file():
        raise FileNotFoundError(f"Synthetic resume does not exist: {args.resume}")

    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    configured = PipelineConfig.from_env()
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        health = _require(client.get(_url(args.base_url, "/api/health")), 200).json()
        system_response = _require(client.get(_url(args.base_url, "/api/system")), 200)
        models_response = _require(client.get(_url(args.base_url, "/api/models")), 200)
        landing = _require(client.get(_url(args.base_url, "/")), 200)
        if health["status"] != "ok" or "Resume Intelligence Platform" not in landing.text:
            raise RuntimeError("Health or landing-page identity validation failed")
        _require_runtime_build(health, source_fingerprint())
        if "C:\\Users\\" in system_response.text or "C:\\Users\\" in models_response.text:
            raise RuntimeError("A diagnostic endpoint exposed an absolute user path")
        if '"endpoint"' in models_response.text:
            raise RuntimeError("The public models endpoint exposed its private Ollama endpoint")

        with args.resume.open("rb") as resume_file:
            submission = _require(
                client.post(
                    _url(args.base_url, "/api/analyses"),
                    files={"resume": (args.resume.name, resume_file, "application/pdf")},
                    data={
                        "job_description_text": (
                            "Software engineer role requiring Python, FastAPI, SQL, and Docker."
                        ),
                        "ai_provider": configured.ai_provider if args.live_ai else "none",
                        "ai_model": configured.ai_model if args.live_ai else "",
                        "enable_rewrites": str(args.live_ai).lower(),
                        "rewrite_summary": "true",
                        "rewrite_experience": "false",
                        "rewrite_skills": "false",
                    },
                ),
                202,
            ).json()

        deadline = time.monotonic() + args.poll_timeout
        status_payload = None
        while time.monotonic() < deadline:
            status_payload = _require(
                client.get(_url(args.base_url, submission["status_url"])), 200
            ).json()
            if status_payload["status"] in {"completed", "failed"}:
                break
            time.sleep(0.1)
        if not status_payload or status_payload["status"] != "completed":
            raise RuntimeError(f"Analysis did not complete: {status_payload}")

        result_response = _require(client.get(_url(args.base_url, submission["result_url"])), 200)
        result = result_response.json()
        _require(client.get(_url(args.base_url, submission["page_url"])), 200)
        download_path = submission["result_url"].replace("/result", "/download")
        downloaded = _require(client.get(_url(args.base_url, download_path)), 200).json()
        if result != downloaded:
            raise RuntimeError("Runtime and downloaded JSON reports differ")
        serialized = json.dumps(result, ensure_ascii=False)
        if "C:\\Users\\" in serialized or str(Path.cwd().resolve()) in serialized:
            raise RuntimeError("The public report exposed an absolute machine path")
        if result["schema_version"] != "2.1.0" or result["errors"]:
            raise RuntimeError("The completed report failed its canonical contract")
        migration_warnings = [
            warning for warning in result["warnings"] if warning["stage"] == "migration"
        ]
        if migration_warnings:
            raise RuntimeError("The canonical web flow emitted a migration warning")
        if args.live_ai:
            if result["module_status"]["recommendations"]["status"] != "complete":
                raise RuntimeError("Live web recommendations did not complete")
            if result["rewrites"]["provider"] != "ollama" or result["rewrites"]["status"] not in {
                "complete",
                "partial",
            }:
                raise RuntimeError("Live web summary rewriting did not return a validated result")

        _require(client.delete(_url(args.base_url, submission["status_url"])), 204)
        _require(client.get(_url(args.base_url, submission["status_url"])), 404)

    print(
        json.dumps(
            {
                "health": 200,
                "system": 200,
                "models": 200,
                "landing": 200,
                "upload": 202,
                "status": "completed",
                "result": 200,
                "page": 200,
                "download": 200,
                "download_equivalent": True,
                "absolute_path_exposed": False,
                "migration_warnings": 0,
                "recommendations": result["module_status"]["recommendations"]["status"],
                "rewrites": result["rewrites"]["status"],
                "rewrite_provider": result["rewrites"]["provider"],
                "delete": 204,
                "after_delete": 404,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
