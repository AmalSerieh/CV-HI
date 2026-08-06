"""Repository-friendly wrapper for the installed diagnostic entry point."""

from pathlib import Path

from resume_analyzer.diagnostics.environment import main
from resume_analyzer.environment import load_env_file

if __name__ == "__main__":
    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    raise SystemExit(main())
