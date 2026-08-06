from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline import PipelineConfig, ResumePipeline
from resume_analyzer.contracts import RecommendationProvider
from resume_analyzer.evidence import EvidenceRegistry
from resume_analyzer.schema_migration import SchemaMigrator
from resume_analyzer.schemas import PipelineReport

TOP_LEVEL_KEYS = [
    "schema_version",
    "document",
    "extraction",
    "entities",
    "quality",
    "data_quality",
    "evidence",
    "target_role",
    "recommendations",
    "ats",
    "rewrites",
    "warnings",
    "errors",
    "module_status",
]


def legacy_payload() -> dict:
    return {
        "success": True,
        "file": {"name": "candidate.pdf", "extension": ".pdf", "size_bytes": 1200},
        "text_extraction": {
            "success": True,
            "pages": 1,
            "words": 85,
            "chars": 620,
            "engine": "pymupdf",
            "quality_score": 91,
        },
        "contact": {"name": "Jane Doe", "email": "jane@example.com"},
        "sections": {
            "sections": {
                "summary": {
                    "heading": "Summary",
                    "content": "Backend engineer building reliable production APIs and services with Python, SQL, and FastAPI.",
                    "confidence": 95,
                },
                "skills": {"content": "Python, FastAPI, SQL, Docker, Git, REST API"},
            }
        },
        "skills": {"all_skills": ["Python", "FastAPI", "SQL", "Docker", "Git", "REST API"]},
        "experience": {
            "experiences": [
                {
                    "job_title": "Backend Engineer",
                    "company": "Example Labs",
                    "start_date": "2022",
                    "end_date": "Present",
                    "responsibilities": ["Built Python APIs"],
                    "technologies": ["Python", "FastAPI"],
                    "confidence": 90,
                }
            ]
        },
        "education": {"education": []},
        "projects": {"projects": []},
        "languages": {"languages": [{"language": "English", "proficiency": "Fluent"}]},
    }


def canonical_report() -> PipelineReport:
    return SchemaMigrator().migrate(legacy_payload()).report


class FakeBackend:
    def __init__(self, report: PipelineReport | None = None) -> None:
        self.report = report or canonical_report()
        self.calls: list[tuple[str, str]] = []

    def extract(self, file_path: str) -> PipelineReport:
        self.calls.append(("file", file_path))
        return self.report

    def extract_text(self, text: str, *, document_name: str = "inline.txt") -> PipelineReport:
        self.calls.append(("text", document_name))
        return self.report


@pytest.mark.parametrize("key", TOP_LEVEL_KEYS)
def test_canonical_report_has_each_required_top_level_key(key: str) -> None:
    assert key in canonical_report().to_json_dict()


def test_canonical_report_has_no_extra_top_level_keys() -> None:
    assert list(canonical_report().to_json_dict()) == TOP_LEVEL_KEYS


@pytest.mark.parametrize(
    ("payload", "shape"),
    [
        (legacy_payload(), "legacy_top_level"),
        ({"analysis": {"facts": legacy_payload()}}, "analysis.facts"),
        ({"entities": {"skills": [{"value": "Python"}]}}, "strict_entities"),
    ],
)
def test_legacy_shapes_migrate_explicitly(payload: dict, shape: str) -> None:
    result = SchemaMigrator().migrate(payload)
    assert result.source_shape == shape
    assert result.warnings[0] == f"migrated_from:{shape}"


@pytest.mark.parametrize("value", ["Python", "PYTHON", " Jane   Doe ", 42, None])
def test_evidence_ids_are_stable(value) -> None:
    first = EvidenceRegistry.stable_id(kind="present", field_path="entities.test", value=value)
    second = EvidenceRegistry.stable_id(kind="present", field_path="entities.test", value=value)
    assert first == second
    assert first.startswith("ev-") and len(first) == 19


def test_evidence_id_normalizes_case_and_space() -> None:
    assert EvidenceRegistry.stable_id(
        kind="present", field_path="x", value="  PYTHON "
    ) == EvidenceRegistry.stable_id(kind="present", field_path="x", value="python")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ai_timeout_seconds": 0},
        {"ai_timeout_seconds": -1},
        {"ai_retries": -1},
        {"allow_model_download": True},
    ],
)
def test_invalid_pipeline_config_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        PipelineConfig(**kwargs)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("YES", True), ("0", False), ("off", False)],
)
def test_environment_boolean_parsing(monkeypatch, raw: str, expected: bool) -> None:
    monkeypatch.setenv("RESUME_ENABLE_OCR", raw)
    assert PipelineConfig.from_env().enable_ocr is expected


def test_invalid_environment_boolean_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("RESUME_ENABLE_OCR", "sometimes")
    with pytest.raises(ValueError):
        PipelineConfig.from_env()


def test_ocr_returns_no_words_when_unavailable(monkeypatch) -> None:
    import resume_analyzer.extraction.text_extractor as module

    monkeypatch.setattr(module, "OCR_AVAILABLE", False)
    assert module.TextExtractor()._ocr_words(object()) == []


def test_ocr_word_extraction_uses_mocked_local_engine(monkeypatch) -> None:
    import resume_analyzer.extraction.text_extractor as module

    class Pixmap:
        width = 20
        height = 10
        samples = b""

    class Page:
        @staticmethod
        def get_pixmap(matrix, alpha):
            assert alpha is False
            return Pixmap()

    class ImageFactory:
        @staticmethod
        def frombytes(mode, size, samples):
            return {"mode": mode, "size": size, "samples": samples}

    class Tesseract:
        @staticmethod
        def image_to_data(image, *, lang, config, output_type):
            assert image["mode"] == "RGB"
            assert (lang, config, output_type) == ("eng", "--psm 3", "DICT")
            return {
                "text": ["Python", "noise"],
                "conf": ["95", "10"],
                "left": [4, 0],
                "top": [6, 0],
                "width": [12, 1],
                "height": [4, 1],
                "block_num": [1, 1],
                "par_num": [1, 1],
                "line_num": [1, 1],
                "word_num": [1, 2],
            }

    class Output:
        DICT = "DICT"

    monkeypatch.setattr(module, "OCR_AVAILABLE", True)
    monkeypatch.setattr(module, "Image", ImageFactory)
    monkeypatch.setattr(module, "pytesseract", Tesseract)
    monkeypatch.setattr(module, "Output", Output)
    words = module.TextExtractor()._ocr_words(Page())
    assert [item["text"] for item in words] == ["Python"]
    assert words[0]["x0"] == 2.0
    assert words[0]["line_id"] == "ocr:1:1:1"


def test_ocr_lines_preserve_tesseract_rtl_word_order() -> None:
    from resume_analyzer.extraction.text_extractor import TextExtractor

    words = [
        {
            "text": "مهندس",
            "x0": 300.0,
            "x1": 360.0,
            "top": 10.0,
            "bottom": 30.0,
            "line_id": "ocr:1:1:1",
            "word_no": 1,
        },
        {
            "text": "برمجيات",
            "x0": 200.0,
            "x1": 290.0,
            "top": 10.0,
            "bottom": 30.0,
            "line_id": "ocr:1:1:1",
            "word_no": 2,
        },
    ]
    lines = TextExtractor()._words_to_lines(words, 1, 600.0, "ocr")
    assert [line["text"] for line in lines] == ["مهندس برمجيات"]


def test_pipeline_calls_file_backend() -> None:
    backend = FakeBackend()
    ResumePipeline(extraction_backend=backend).analyze("resume.pdf")
    assert backend.calls == [("file", "resume.pdf")]


def test_pipeline_calls_text_backend() -> None:
    backend = FakeBackend()
    ResumePipeline(extraction_backend=backend).analyze_text("text", document_name="x.txt")
    assert backend.calls == [("text", "x.txt")]


def test_target_role_is_attached_through_canonical_pipeline() -> None:
    result = ResumePipeline(extraction_backend=FakeBackend()).analyze("resume.pdf")
    assert result["target_role"]["primary"]["role_id"] == "backend_engineer"
    assert result["module_status"]["target_role"]["provider"] == "deterministic_target_roles"


def test_target_role_can_be_disabled_explicitly() -> None:
    config = PipelineConfig(integrate_target_role=False, enable_recommendations=False)
    result = ResumePipeline(config, extraction_backend=FakeBackend()).analyze("resume.pdf")
    assert result["target_role"] is None
    assert result["module_status"]["target_role"]["status"] == "not_run"


def test_recommendations_can_be_disabled_explicitly() -> None:
    config = PipelineConfig(enable_recommendations=False)
    result = ResumePipeline(config, extraction_backend=FakeBackend()).analyze("resume.pdf")
    assert result["recommendations"] == []
    assert result["module_status"]["recommendations"]["status"] == "not_run"


def test_default_recommendations_use_grounded_fallback() -> None:
    result = ResumePipeline(extraction_backend=FakeBackend()).analyze("resume.pdf")
    assert result["module_status"]["recommendations"]["status"] == "fallback"
    assert all(item["source"] == "fallback" for item in result["recommendations"])
    evidence = {item["id"] for item in result["evidence"]}
    assert all(set(item["evidence_ids"]) <= evidence for item in result["recommendations"])


def test_runtime_and_exported_json_are_identical(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    result = ResumePipeline(extraction_backend=FakeBackend()).analyze(
        "resume.pdf", output_path=output
    )
    assert json.loads(output.read_text(encoding="utf-8")) == result
    assert "exported_json" not in result


def test_export_validates_report_before_writing(tmp_path: Path) -> None:
    invalid = canonical_report().to_json_dict()
    invalid["unexpected"] = True
    with pytest.raises(ValidationError):
        ResumePipeline.export(invalid, tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()


def test_schema_rejects_unknown_top_level_field() -> None:
    invalid = canonical_report().to_json_dict()
    invalid["surprise"] = 1
    with pytest.raises(ValidationError):
        PipelineReport.model_validate(invalid)


def test_schema_rejects_unknown_evidence_reference() -> None:
    invalid = canonical_report().to_json_dict()
    invalid["entities"]["skills"][0]["evidence_ids"] = ["ev-0000000000000000"]
    with pytest.raises(ValidationError, match="Unknown evidence IDs"):
        PipelineReport.model_validate(invalid)


def test_schema_rejects_duplicate_evidence_ids() -> None:
    invalid = canonical_report().to_json_dict()
    invalid["evidence"].append(dict(invalid["evidence"][0]))
    with pytest.raises(ValidationError, match="unique"):
        PipelineReport.model_validate(invalid)


def test_json_serialization_rejects_nan() -> None:
    registry = EvidenceRegistry()
    with pytest.raises(ValidationError):
        registry.register(field_path="x", value=math.nan, extractor="test")


@pytest.mark.parametrize("field", ["email", "phone", "linkedin"])
def test_missing_contact_has_explicit_evidence(field: str) -> None:
    report = SchemaMigrator().migrate({"entities": {"skills": [{"value": "Python"}]}}).report
    evidence_ids = report.entities.contact.evidence_ids[field]
    item = next(value for value in report.evidence if value.id == evidence_ids[0])
    assert item.kind == "missing"
    assert item.field_path == f"entities.contact.{field}"


def test_migration_does_not_mutate_input() -> None:
    payload = legacy_payload()
    snapshot = json.dumps(payload, sort_keys=True)
    SchemaMigrator().migrate(payload)
    assert json.dumps(payload, sort_keys=True) == snapshot


def test_migration_omits_ungrounded_legacy_recommendations_with_warning() -> None:
    payload = legacy_payload()
    payload["recommendations"] = [{"message": "invent something"}]
    result = SchemaMigrator().migrate(payload)
    assert result.report.recommendations == []
    assert "legacy_recommendations_omitted:missing_grounded_contract" in result.warnings


def test_ats_runs_by_default_and_rewrites_remain_explicitly_not_run() -> None:
    result = ResumePipeline(extraction_backend=FakeBackend()).analyze("resume.pdf")
    assert result["ats"]["status"] in {"complete", "partial"}
    assert result["rewrites"]["status"] == "not_run"
    assert result["module_status"]["ats"]["status"] == result["ats"]["status"]
    assert result["module_status"]["rewrites"]["status"] == "not_run"


def test_legacy_wrapper_emits_deprecation_warning() -> None:
    import importlib
    import sys

    sys.modules.pop("pipeline2", None)
    with pytest.warns(DeprecationWarning, match="resume_analyzer"):
        legacy = importlib.import_module("pipeline2")
    assert legacy.ResumePipeline is ResumePipeline


def test_recommendation_protocol_is_runtime_checkable() -> None:
    class Engine:
        def recommend(self, report):
            raise NotImplementedError

    assert isinstance(Engine(), RecommendationProvider)
