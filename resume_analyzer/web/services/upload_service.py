"""Streaming upload validation and private temporary storage."""

from __future__ import annotations

import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

import fitz
from fastapi import UploadFile

from ..config import WebSettings
from ..models import PreparedUpload


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class UploadService:
    PDF_MIME = {"application/pdf"}
    DOCX_MIME = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    TEXT_MIME = {"text/plain", "application/octet-stream"}

    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings

    async def prepare(
        self,
        resume: UploadFile,
        *,
        job_description_text: str | None,
        job_description_file: UploadFile | None,
    ) -> PreparedUpload:
        directory = Path(
            tempfile.mkdtemp(
                prefix="resume-analysis-",
                dir=str(self.settings.temp_dir) if self.settings.temp_dir else None,
            )
        ).resolve()
        try:
            try:
                directory.chmod(0o700)
            except OSError:
                pass
            original_name, extension = self._validate_resume_metadata(resume)
            destination = directory / f"resume{extension}"
            await self._stream_to_path(resume, destination, self.settings.max_upload_bytes)
            self._validate_document(destination, extension)
            job_description = await self._job_description(
                job_description_text, job_description_file
            )
            return PreparedUpload(
                directory=directory,
                resume_path=destination,
                original_name=original_name,
                job_description=job_description,
            )
        except Exception:
            self.cleanup(directory)
            raise
        finally:
            await resume.close()
            if job_description_file is not None:
                await job_description_file.close()

    def cleanup(self, directory: Path) -> None:
        try:
            resolved = directory.resolve()
            if resolved.name.startswith("resume-analysis-") and resolved.is_dir():
                shutil.rmtree(resolved)
        except OSError:
            pass

    def _validate_resume_metadata(self, upload: UploadFile) -> tuple[str, str]:
        name = upload.filename or ""
        if not name or "\x00" in name:
            raise UploadValidationError("invalid_filename", "Select a PDF or DOCX file.")
        normalized = name.replace("\\", "/")
        if "/" in normalized or normalized in {".", ".."}:
            raise UploadValidationError("invalid_filename", "The uploaded filename is not valid.")
        extension = Path(normalized).suffix.casefold()
        if extension in {".docm", ".dotm", ".xlsm", ".pptm"}:
            raise UploadValidationError(
                "macro_format_rejected", "Macro-enabled Office documents are not supported."
            )
        if extension not in {".pdf", ".docx"}:
            raise UploadValidationError(
                "unsupported_file_type", "Only PDF and DOCX resumes are supported."
            )
        mime = (upload.content_type or "").split(";", 1)[0].strip().casefold()
        allowed = self.PDF_MIME if extension == ".pdf" else self.DOCX_MIME
        if mime not in allowed:
            raise UploadValidationError(
                "invalid_mime_type", "The file content type does not match its extension."
            )
        return Path(normalized).name, extension

    async def _stream_to_path(self, upload: UploadFile, path: Path, maximum: int) -> None:
        size = 0
        with path.open("xb") as destination:
            while chunk := await upload.read(1_048_576):
                size += len(chunk)
                if size > maximum:
                    raise UploadValidationError(
                        "file_too_large",
                        f"The resume exceeds the {self.settings.max_upload_mb} MB upload limit.",
                        413,
                    )
                destination.write(chunk)
        if size == 0:
            raise UploadValidationError("empty_file", "The uploaded resume is empty.")

    def _validate_document(self, path: Path, extension: str) -> None:
        if extension == ".pdf":
            self._validate_pdf(path)
        else:
            self._validate_docx(path)

    def _validate_pdf(self, path: Path) -> None:
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise UploadValidationError("invalid_signature", "The file is not a valid PDF.")
        try:
            with fitz.open(path) as document:
                pages = document.page_count
                if pages < 1:
                    raise UploadValidationError("corrupt_document", "The PDF has no pages.")
                if pages > self.settings.max_pages:
                    raise UploadValidationError(
                        "too_many_pages",
                        f"The PDF exceeds the {self.settings.max_pages}-page limit.",
                        413,
                    )
        except UploadValidationError:
            raise
        except Exception as exc:
            raise UploadValidationError(
                "corrupt_document", "The PDF could not be opened safely."
            ) from exc

    def _validate_docx(self, path: Path) -> None:
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                names = {member.filename for member in members}
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise UploadValidationError(
                        "corrupt_document", "The DOCX package is missing required document parts."
                    )
                if any(name.casefold().endswith("vbaproject.bin") for name in names):
                    raise UploadValidationError(
                        "macro_format_rejected", "Macro-enabled documents are not supported."
                    )
                if len(members) > self.settings.max_docx_files:
                    raise UploadValidationError(
                        "unsafe_archive", "The DOCX package contains too many files."
                    )
                expanded = sum(member.file_size for member in members)
                if expanded > self.settings.max_docx_uncompressed_bytes:
                    raise UploadValidationError(
                        "unsafe_archive", "The DOCX expanded size exceeds the safety limit."
                    )
                for member in members:
                    mode = member.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise UploadValidationError(
                            "unsafe_archive", "Symbolic links are not allowed in DOCX packages."
                        )
                    if (
                        member.file_size > 1_000_000
                        and member.file_size > max(1, member.compress_size) * 200
                    ):
                        raise UploadValidationError(
                            "unsafe_archive", "The DOCX compression ratio is unsafe."
                        )
                bad_member = archive.testzip()
                if bad_member is not None:
                    raise UploadValidationError(
                        "corrupt_document", "The DOCX package failed its integrity check."
                    )
        except UploadValidationError:
            raise
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise UploadValidationError(
                "corrupt_document", "The DOCX could not be opened safely."
            ) from exc

    async def _job_description(self, text: str | None, upload: UploadFile | None) -> str | None:
        parts: list[str] = []
        if text and text.strip():
            parts.append(text.strip())
        if upload is not None and upload.filename:
            name = upload.filename.replace("\\", "/")
            if "/" in name or Path(name).suffix.casefold() != ".txt":
                raise UploadValidationError(
                    "invalid_job_description_file", "Job descriptions must be plain .txt files."
                )
            mime = (upload.content_type or "").split(";", 1)[0].strip().casefold()
            if mime not in self.TEXT_MIME:
                raise UploadValidationError(
                    "invalid_job_description_mime", "The job-description file must be plain text."
                )
            raw = await upload.read(self.settings.max_job_description_chars * 4 + 1)
            if len(raw) > self.settings.max_job_description_chars * 4:
                raise UploadValidationError(
                    "job_description_too_large", "The job description exceeds the text limit.", 413
                )
            try:
                decoded = raw.decode("utf-8-sig").strip()
            except UnicodeDecodeError as exc:
                raise UploadValidationError(
                    "invalid_job_description_encoding", "Use UTF-8 for job-description files."
                ) from exc
            if decoded:
                parts.append(decoded)
        combined = "\n\n".join(parts).strip()
        if len(combined) > self.settings.max_job_description_chars:
            raise UploadValidationError(
                "job_description_too_large",
                f"The job description exceeds {self.settings.max_job_description_chars} characters.",
                413,
            )
        return combined or None
