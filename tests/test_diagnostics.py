from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

from resume_analyzer.diagnostics.environment import run_diagnostics
from resume_analyzer.diagnostics.health import application_health, system_capabilities
from resume_analyzer.diagnostics.models import model_status
from resume_analyzer.diagnostics.ocr import tesseract_status
from resume_analyzer.web.build_info import (
    SourceFingerprintMonitor,
    build_state,
    source_fingerprint,
)
from resume_analyzer.web.config import WebSettings
from scripts.ensure_ollama import ensure_ollama
from scripts.validate_web_workflow import _require_runtime_build


def test_web_settings_safe_defaults():
    settings = WebSettings()
    assert settings.host == "127.0.0.1"
    assert settings.public_absolute_paths is False
    assert settings.max_concurrent_analyses == 2


def test_web_settings_reload_defaults_and_override(monkeypatch):
    monkeypatch.delenv("APP_RELOAD", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert WebSettings.from_env().reload is True
    monkeypatch.setenv("APP_ENV", "production")
    assert WebSettings.from_env().reload is False
    monkeypatch.setenv("APP_RELOAD", "true")
    assert WebSettings.from_env().reload is True


def test_source_fingerprint_and_runtime_identity(tmp_path):
    package = tmp_path / "resume_analyzer"
    package.mkdir()
    source = package / "module.py"
    template = package / "results.html"
    script = package / "results.js"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    template.write_text("<main>First</main>\n", encoding="utf-8")
    script.write_text("const version = 1;\n", encoding="utf-8")
    first = source_fingerprint(tmp_path)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    second = source_fingerprint(tmp_path)
    assert first != second
    template.write_text("<main>Second</main>\n", encoding="utf-8")
    third = source_fingerprint(tmp_path)
    assert second != third
    script.write_text("const version = 2;\n", encoding="utf-8")
    fourth = source_fingerprint(tmp_path)
    assert third != fourth
    assert build_state(first, lambda: fourth)["restart_required"] is True
    _require_runtime_build(
        {"build": {"build_id": fourth[:12], "restart_required": False}},
        fourth,
    )
    with pytest.raises(RuntimeError, match="pre-fix"):
        _require_runtime_build({}, fourth)


def test_source_fingerprint_monitor_throttles_repeated_reads(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "resume_analyzer.web.build_info.source_fingerprint",
        lambda: calls.append(True) or "b" * 64,
    )
    monitor = SourceFingerprintMonitor(
        initial="a" * 64,
        minimum_interval_seconds=60,
    )
    assert monitor() == "a" * 64
    assert monitor() == "a" * 64
    assert calls == []


@pytest.mark.parametrize("name", ["APP_PORT", "RESUME_MAX_UPLOAD_MB", "RESUME_MAX_PAGES"])
def test_web_settings_reject_invalid_positive_values(monkeypatch, name):
    monkeypatch.setenv(name, "0")
    with pytest.raises(ValueError):
        WebSettings.from_env()


def test_web_settings_reject_public_paths(monkeypatch):
    monkeypatch.setenv("RESUME_PUBLIC_ABSOLUTE_PATHS", "true")
    with pytest.raises(ValueError, match="absolute paths"):
        WebSettings.from_env()


def test_health_required_dependencies_available():
    report = application_health(WebSettings())
    assert report["required_dependencies"] == "available"
    assert report["schema_version"] == "2.1.0"


def test_system_report_has_no_personal_paths(tmp_path):
    report = system_capabilities(WebSettings(temp_dir=tmp_path), public=True)
    serialized = json.dumps(report)
    assert str(tmp_path) not in serialized
    assert report["storage"]["absolute_paths_public"] is False


def test_model_status_unreachable_is_nonfatal(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    report = model_status(public=True)
    assert report["fallback_available"] is True
    assert report["ollama"]["reachable"] is False


def test_model_status_detects_configured_ollama_model(monkeypatch):
    payload = json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode()

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setenv("RESUME_AI_PROVIDER", "ollama")
    monkeypatch.setenv("RESUME_AI_MODEL", "llama3.2:3b")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response(payload))
    report = model_status(public=True)
    assert report["ollama"]["reachable"] is True
    assert report["ollama"]["configured_model_available"] is True


def test_ensure_ollama_starts_missing_loopback_service(monkeypatch):
    states = iter(
        [
            {"reachable": False, "models": []},
            {"reachable": True, "models": ["local-model"]},
        ]
    )
    monkeypatch.setattr(
        "scripts.ensure_ollama._service_state", lambda *_args, **_kwargs: next(states)
    )
    monkeypatch.setattr("scripts.ensure_ollama._start_local_service", lambda: 321)
    result = ensure_ollama(
        base_url="http://127.0.0.1:11434",
        model="local-model",
        start=True,
        wait_seconds=1,
    )
    assert result == {
        "status": "ready",
        "service_reachable": True,
        "configured_model": "local-model",
        "configured_model_available": True,
        "service_started": True,
        "service_pid": 321,
    }


def test_ensure_ollama_never_starts_a_remote_endpoint(monkeypatch):
    monkeypatch.setattr(
        "scripts.ensure_ollama._service_state",
        lambda *_args, **_kwargs: {"reachable": False, "models": []},
    )
    monkeypatch.setattr(
        "scripts.ensure_ollama._start_local_service",
        lambda: (_ for _ in ()).throw(AssertionError("must not start")),
    )
    with pytest.raises(RuntimeError, match="loopback"):
        ensure_ollama(
            base_url="http://example.invalid:11434",
            model="local-model",
            start=True,
        )


def test_tesseract_missing_is_warning(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    report = tesseract_status()
    assert report["installed"] is False
    assert report["error"]


def test_tesseract_language_discovery(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: "tesseract")

    class Completed:
        returncode = 0
        stdout = "List of available languages (2):\neng\nara\n"

    monkeypatch.setattr("subprocess.run", lambda *_args, **_kwargs: Completed())
    report = tesseract_status()
    assert report["english_available"] is True
    assert report["arabic_available"] is True
    assert report["usable_languages"] == ["eng", "ara"]


def test_tesseract_rejects_listed_but_unloadable_language(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: "tesseract")

    class Completed:
        def __init__(self, returncode=0, stdout=""):
            self.returncode = returncode
            self.stdout = stdout

    def run(command, **_kwargs):
        if "--list-langs" in command:
            return Completed(stdout="List of available languages (2):\neng\nara\n")
        return Completed(returncode=1 if command[-1] == "ara" else 0)

    monkeypatch.setattr("subprocess.run", run)
    report = tesseract_status()
    assert report["english_available"] is True
    assert report["arabic_available"] is False
    assert report["unusable_languages"] == ["ara"]


def test_doctor_import_and_bootstrap_checks(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    report, required_ok = run_diagnostics()
    assert report["pipeline"]["importable"] is True
    assert report["frontend"]["bootstrap_local"] is True
    assert required_ok is True


@pytest.mark.parametrize(
    "name,expected",
    [
        ("bootstrap.min.css", "3c8f27e6009ccfd710a905e6dcf12d0ee3c6f2ac7da05b0572d3e0d12e736fc8"),
        (
            "bootstrap.bundle.min.js",
            "0833b2e9c3a26c258476c46266e6877fc75218625162e0460be9a3a098a61c6c",
        ),
    ],
)
def test_bootstrap_asset_checksum(name, expected):
    path = Path("resume_analyzer/web/static/vendor/bootstrap") / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_default_diagnostics_do_not_load_transformers():
    import sys

    assert "transformers" not in sys.modules
