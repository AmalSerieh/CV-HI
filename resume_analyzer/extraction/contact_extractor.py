"""Compatibility adapter for the consolidated modular contact extractor."""

from __future__ import annotations

from typing import Any

from .contact import (
    BaseExtractor,
    ContactResolver,
    EmailExtractor,
    JobTitleExtractor,
    LinkExtractor,
    LocationExtractor,
    NameExtractor,
    PhoneExtractor,
)


class ContactExtractor:
    """Preserve the former ``extract_all`` API over ``ContactResolver``."""

    def __init__(self, resolver: ContactResolver | None = None) -> None:
        self.resolver = resolver or ContactResolver()

    def extract_all(
        self,
        text: str,
        *,
        raw_text: str | None = None,
        layout_blocks: list[Any] | None = None,
        file_links: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.resolver.resolve(
            text=text,
            raw_text=raw_text,
            layout_blocks=layout_blocks,
            file_links=file_links,
        )


__all__ = [
    "BaseExtractor",
    "ContactExtractor",
    "ContactResolver",
    "EmailExtractor",
    "JobTitleExtractor",
    "LinkExtractor",
    "LocationExtractor",
    "NameExtractor",
    "PhoneExtractor",
]
