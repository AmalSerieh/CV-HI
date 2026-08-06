"""Install verified official Tesseract language data into a local runtime directory."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

OFFICIAL_BASE_URL = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main"
SUPPORTED_LANGUAGES = ("eng", "ara")
MIN_TRAINEDDATA_BYTES = 100_000
MAX_TRAINEDDATA_BYTES = 20_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _looks_like_traineddata(path: Path) -> bool:
    size = path.stat().st_size
    if not MIN_TRAINEDDATA_BYTES <= size <= MAX_TRAINEDDATA_BYTES:
        return False
    with path.open("rb") as traineddata:
        prefix = traineddata.read(512).lstrip().lower()
    return not prefix.startswith((b"<!doctype html", b"<html", b"<?xml"))


def _tesseract_usable(executable: Path, tessdata: Path, language: str) -> bool:
    environment = os.environ.copy()
    environment["TESSDATA_PREFIX"] = str(tessdata.resolve())
    completed = subprocess.run(
        [str(executable), "--print-parameters", "-l", language],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
        env=environment,
    )
    return completed.returncode == 0


def _download(language: str, destination: Path) -> tuple[int, str]:
    url = f"{OFFICIAL_BASE_URL}/{language}.traineddata"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "resume-intelligence-tessdata-installer/1.0"},
    )
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{language}.", suffix=".download", dir=destination, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            temporary_path.open("wb") as output,
        ):
            content_type = response.headers.get_content_type()
            if content_type in {"text/html", "application/xhtml+xml"}:
                raise RuntimeError(f"Official source returned unexpected {content_type}")
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if not _looks_like_traineddata(temporary_path):
            raise RuntimeError("Downloaded content is not a plausible traineddata binary")
        target = destination / f"{language}.traineddata"
        os.replace(temporary_path, target)
        return target.stat().st_size, _sha256(target)
    finally:
        temporary_path.unlink(missing_ok=True)


def install_languages(destination: Path, executable: Path) -> int:
    if not executable.is_file():
        raise FileNotFoundError(f"Tesseract executable not found: {executable}")
    for language in SUPPORTED_LANGUAGES:
        size, digest = _download(language, destination)
        print(f"installed {language}: {size} bytes, sha256={digest}")
    failed = [
        language
        for language in (*SUPPORTED_LANGUAGES, "+".join(SUPPORTED_LANGUAGES))
        if not _tesseract_usable(executable, destination, language)
    ]
    if failed:
        print(f"Tesseract could not initialize: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"verified eng, ara, and eng+ara using {destination.resolve()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("runtime/tessdata"),
        help="Local tessdata directory (default: runtime/tessdata)",
    )
    detected = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    parser.add_argument("--tesseract", type=Path, default=Path(detected))
    arguments = parser.parse_args()
    try:
        return install_languages(arguments.destination, arguments.tesseract)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"OCR language installation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
