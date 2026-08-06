"""Ensure the explicitly configured local Ollama service is ready."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from resume_analyzer import PipelineConfig
from resume_analyzer.environment import load_env_file

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _model_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in payload.get("models", []):
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def _service_state(base_url: str, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/api/tags"
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        OSError,
        TimeoutError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ):
        return {"reachable": False, "models": []}
    return {
        "reachable": isinstance(payload, dict),
        "models": _model_names(payload) if isinstance(payload, dict) else [],
    }


def _start_local_service() -> int:
    executable = shutil.which("ollama")
    if not executable:
        raise RuntimeError("Ollama is selected but the ollama executable was not found.")
    options: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        options["start_new_session"] = True
    process = subprocess.Popen([executable, "serve"], **options)
    return process.pid


def ensure_ollama(
    *,
    base_url: str,
    model: str | None,
    start: bool,
    wait_seconds: float = 20.0,
) -> dict[str, Any]:
    parsed = urlsplit(base_url)
    state = _service_state(base_url)
    started = False
    pid: int | None = None
    if not state["reachable"] and start:
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in _LOOPBACK_HOSTS:
            raise RuntimeError("Automatic Ollama startup is restricted to a loopback endpoint.")
        pid = _start_local_service()
        started = True
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            state = _service_state(base_url)
            if state["reachable"]:
                break
            time.sleep(0.2)

    available = bool(model and model in state["models"])
    return {
        "status": (
            "ready"
            if state["reachable"] and (not model or available)
            else ("model_missing" if state["reachable"] else "unavailable")
        ),
        "service_reachable": state["reachable"],
        "configured_model": model,
        "configured_model_available": available,
        "service_started": started,
        "service_pid": pid,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start a missing loopback Ollama service before checking readiness.",
    )
    parser.add_argument("--wait-seconds", type=float, default=20.0)
    args = parser.parse_args(argv)
    if args.wait_seconds <= 0:
        parser.error("--wait-seconds must be positive")

    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    config = PipelineConfig.from_env()
    if config.ai_provider.casefold() != "ollama":
        print(json.dumps({"status": "not_required"}, indent=2))
        return 0
    try:
        result = ensure_ollama(
            base_url=config.ollama_base_url,
            model=config.ai_model,
            start=args.start,
            wait_seconds=args.wait_seconds,
        )
    except RuntimeError as exc:
        print(json.dumps({"status": "unavailable", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
