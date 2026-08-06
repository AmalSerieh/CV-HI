from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from resume_analyzer.target_roles.cli import main


class CliTests(unittest.TestCase):
    def test_success_prints_json_with_arabic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(
                json.dumps(
                    {
                        "summary": "مهندس ذكاء اصطناعي",
                        "skills": ["Python", "RAG", "LLM", "ذكاء اصطناعي"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([str(path), "--pretty"])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["target_role"]["primary"]["role_id"], "ai_engineer")

    def test_invalid_json_returns_nonzero_and_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                code = main([str(path)])
            self.assertEqual(code, 2)
            self.assertIn("target-role error", error.getvalue())

    def test_non_object_root_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "list.json"
            path.write_text("[]", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
