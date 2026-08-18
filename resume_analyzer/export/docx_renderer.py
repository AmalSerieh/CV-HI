"""Render a semantic FinalResume through an allowlisted docxtpl template."""

from __future__ import annotations

import io
import re
import unicodedata
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

from docx import Document
from docxtpl import DocxTemplate

from .schemas import FinalResume
from .template_registry import DEFAULT_TEMPLATE_REGISTRY, TemplateRegistry

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_UNRESOLVED_TEMPLATE = re.compile(r"(?:\{\{|\{%|\{#).+?(?:\}\}|%\}|#\})", re.DOTALL)


class DocxRenderError(RuntimeError):
    pass


class DocxRenderer:
    def __init__(self, registry: TemplateRegistry = DEFAULT_TEMPLATE_REGISTRY) -> None:
        self.registry = registry

    def render(self, resume: FinalResume, template_id: str) -> bytes:
        definition = self.registry.get(template_id)
        if not definition.docx_path.is_file():
            raise DocxRenderError("The selected resume template is unavailable.")
        try:
            template = DocxTemplate(str(definition.docx_path))
            template.render(self.context(resume), autoescape=True)
            output = io.BytesIO()
            template.save(output)
            value = output.getvalue()
            self._validate(value)
            return value
        except DocxRenderError:
            raise
        except (BadZipFile, OSError, ValueError) as exc:
            raise DocxRenderError("The selected resume template could not be rendered.") from exc
        except Exception as exc:
            raise DocxRenderError("The selected resume template could not be rendered.") from exc

    @staticmethod
    def context(resume: FinalResume) -> dict[str, object]:
        contact = resume.contact
        name_parts = (contact.name or "").split(maxsplit=1)
        skills = [item.model_dump(mode="json") for item in resume.skills]
        contact_items = [
            {"label": label, "value": value}
            for label, value in (
                ("Location", contact.location),
                ("Email", contact.email),
                ("Phone", contact.phone),
                ("LinkedIn", contact.linkedin),
                ("GitHub", contact.github),
                ("Portfolio", contact.portfolio),
            )
            if value
        ]
        return {
            "name": contact.name or "",
            "name_first": name_parts[0] if name_parts else "",
            "name_rest": name_parts[1] if len(name_parts) > 1 else "",
            "job_title": contact.job_title or "",
            "email": contact.email or "",
            "phone": contact.phone or "",
            "location": contact.location or "",
            "linkedin": contact.linkedin or "",
            "github": contact.github or "",
            "portfolio": contact.portfolio or "",
            "contact_line": " | ".join(str(item["value"]) for item in contact_items),
            "contact_items": contact_items,
            "summary": resume.summary,
            "experience": [
                {
                    **item.model_dump(mode="json"),
                    "date_range": _date_range(item.start_date, item.end_date, item.current),
                    "organization_line": " | ".join(
                        value
                        for value in (
                            item.company,
                            item.location,
                            item.employment_type,
                            "Volunteer" if item.volunteer else None,
                        )
                        if value
                    ),
                    "bullets": [*item.responsibilities, *item.achievements],
                }
                for item in resume.experience
            ],
            "education": [
                {
                    **item.model_dump(mode="json"),
                    "date_range": _education_date_range(
                        item.start_date, item.end_date, item.graduation_year
                    ),
                    "institution_line": " | ".join(
                        value for value in (item.institution, item.location) if value
                    ),
                    "degree_line": " - ".join(
                        value for value in (item.degree, item.field, item.specialization) if value
                    ),
                }
                for item in resume.education
            ],
            "skills": skills,
            "projects": [
                {
                    **item.model_dump(mode="json"),
                    "date_range": _date_range(item.start_date, item.end_date, item.current),
                }
                for item in resume.projects
            ],
            "languages": [item.model_dump(mode="json") for item in resume.languages],
            "certifications": [item.model_dump(mode="json") for item in resume.certifications],
        }

    @staticmethod
    def _validate(value: bytes) -> None:
        try:
            Document(io.BytesIO(value))
            with ZipFile(io.BytesIO(value)) as package:
                xml = "\n".join(
                    package.read(name).decode("utf-8", errors="ignore")
                    for name in package.namelist()
                    if name.startswith("word/") and name.endswith(".xml")
                )
        except (BadZipFile, OSError, ValueError) as exc:
            raise DocxRenderError("The generated resume is not a valid Word document.") from exc
        if _UNRESOLVED_TEMPLATE.search(xml):
            raise DocxRenderError("The generated resume contains an unresolved template field.")


def safe_resume_filename(candidate_name: str | None) -> str:
    name = unicodedata.normalize("NFKC", candidate_name or "")
    name = "".join(character for character in name if character.isalnum() or character in " -_")
    name = re.sub(r"[\s_-]+", "-", name).strip("-.")[:80]
    return f"{name}-Resume.docx" if name else "Optimized-Resume.docx"


def content_disposition(candidate_name: str | None) -> str:
    filename = safe_resume_filename(candidate_name)
    ascii_stem = (
        unicodedata.normalize("NFKD", filename).encode("ascii", errors="ignore").decode("ascii")
    )
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_stem).strip("-.")
    if not ascii_stem.lower().endswith(".docx"):
        ascii_stem = "Optimized-Resume.docx"
    return f"attachment; filename=\"{ascii_stem}\"; filename*=UTF-8''{quote(filename)}"


def _date_range(start_date: str | None, end_date: str | None, current: bool) -> str:
    end = "Present" if current and not end_date else end_date
    return " - ".join(value for value in (start_date, end) if value)


def _education_date_range(
    start_date: str | None, end_date: str | None, graduation_year: int | None
) -> str:
    if start_date or end_date:
        return " - ".join(value for value in (start_date, end_date) if value)
    return str(graduation_year) if graduation_year is not None else ""
