from __future__ import annotations

import json
from pathlib import Path


def test_marketing_regression_fixture_is_synthetic_and_relative() -> None:
    root = Path(__file__).parent / "regression" / "fixtures" / "marketing_resume"
    case = json.loads((root / "case.json").read_text(encoding="utf-8"))
    expected = json.loads((root / case["expected"]).read_text(encoding="utf-8"))
    source = (root / case["source"]).read_text(encoding="utf-8")

    assert case["privacy"] == expected["privacy"] == "synthetic"
    assert not Path(case["source"]).is_absolute()
    assert "@example.test" in source
    assert "C:\\" not in source
