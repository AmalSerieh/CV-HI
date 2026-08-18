"""Allowlisted Word-template and preview metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class TemplateNotFound(KeyError):
    pass


@dataclass(frozen=True)
class TemplateDefinition:
    id: str
    name: str
    description: str
    docx_path: Path
    preview_path: Path

    def public_metadata(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "preview_url": f"/api/resume-templates/{self.id}/preview",
        }


class TemplateRegistry:
    def __init__(self, definitions: list[TemplateDefinition]) -> None:
        self._definitions = {item.id: item for item in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("Template identifiers must be unique")

    def get(self, template_id: str) -> TemplateDefinition:
        try:
            return self._definitions[template_id]
        except KeyError as exc:
            raise TemplateNotFound(template_id) from exc

    def public_metadata(self) -> list[dict[str, str]]:
        return [item.public_metadata() for item in self._definitions.values()]

    def definitions(self) -> tuple[TemplateDefinition, ...]:
        return tuple(self._definitions.values())


def _template_directory() -> Path:
    packaged_directory = Path(__file__).resolve().parent / "templates"
    if packaged_directory.is_dir():
        return packaged_directory
    return Path(__file__).resolve().parents[2] / "Template"


_TEMPLATE_DIRECTORY = _template_directory()
DEFAULT_TEMPLATE_REGISTRY = TemplateRegistry(
    [
        TemplateDefinition(
            id="template-1",
            name="Template 1",
            description="A two-column resume with a compact skills and contact sidebar.",
            docx_path=_TEMPLATE_DIRECTORY / "Template-1.docx",
            preview_path=_TEMPLATE_DIRECTORY / "Template-1.jpg",
        ),
        TemplateDefinition(
            id="template-2",
            name="Template 2",
            description="A clean single-column resume with strong section hierarchy.",
            docx_path=_TEMPLATE_DIRECTORY / "Template-2.docx",
            preview_path=_TEMPLATE_DIRECTORY / "Template-2.jpg",
        ),
    ]
)
