from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base class for every project schema."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class BoundingBox(StrictModel):
    x0: float
    top: float
    x1: float
    bottom: float

    @model_validator(mode="after")
    def validate_coordinates(self) -> BoundingBox:
        if self.x1 < self.x0:
            raise ValueError("bbox.x1 must be greater than or equal to bbox.x0")
        if self.bottom < self.top:
            raise ValueError("bbox.bottom must be greater than or equal to bbox.top")
        return self

    def as_list(self) -> list[float]:
        return [self.x0, self.top, self.x1, self.bottom]


class SourceReference(StrictModel):
    page: int = Field(ge=1)
    text: str
    bbox: BoundingBox | None = None
    engine: Literal["pymupdf", "pdfplumber", "ocr", "docx", "unknown"] = "unknown"
    block_id: str | None = None


class Evidence(StrictModel):
    id: str = Field(min_length=1)
    kind: Literal[
        "present",
        "missing",
        "rejected",
        "layout",
        "quality",
        "rule",
    ]
    field: str
    message: str
    source: SourceReference | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


ValueT = TypeVar("ValueT")


class ExtractedValue(StrictModel, Generic[ValueT]):
    value: ValueT | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source: SourceReference | None = None


class LayoutBlock(StrictModel):
    id: str
    page: int = Field(ge=1)
    text: str
    bbox: BoundingBox | None = None
    column: Literal["left", "right", "full_width", "single", "unknown"] = "unknown"
    order: int = Field(ge=0)
    engine: Literal["pymupdf", "pdfplumber", "ocr", "docx", "unknown"] = "unknown"
    block_type: Literal[
        "line",
        "paragraph",
        "table",
        "table_cell",
        "header",
        "footer",
        "ocr_line",
        "rotated_text",
    ] = "line"
    is_repeated_header_footer: bool = False
    zone_id: str | None = None
    zone_kind: Literal["header", "footer", "full_width", "column_pair", "single", "unknown"] = (
        "unknown"
    )
    row_id: str | None = None
    font_size: float | None = Field(default=None, ge=0)
    font_family: str | None = None
    font_weight: Literal["normal", "bold", "unknown"] = "unknown"
    font_style: Literal["normal", "italic", "unknown"] = "unknown"
    alignment: Literal["left", "center", "right", "justified", "unknown"] = "unknown"
    rotation: float = Field(default=0.0, ge=-360.0, le=360.0)
    image_overlap: bool = False
    link_annotations: list[str] = Field(default_factory=list)
    bullet_marker: str | None = None
    probable_table_cell: bool = False
    is_template_residue: bool = False
    excluded_from_entities: bool = False
    quality_flags: list[str] = Field(default_factory=list)
    heading_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    section_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    neighbors: dict[str, list[str]] = Field(default_factory=dict)


class LayoutZone(StrictModel):
    id: str
    kind: Literal["header", "footer", "full_width", "column_pair", "single"]
    bbox: BoundingBox | None = None
    column: Literal["left", "right", "full_width", "single", "mixed", "unknown"] = "unknown"
    order: int = Field(ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    block_ids: list[str] = Field(default_factory=list)


class PageLayout(StrictModel):
    page: int = Field(ge=1)
    width: float = Field(ge=0)
    height: float = Field(ge=0)
    layout: Literal["single_column", "two_column", "mixed", "unknown"] = "unknown"
    reading_order: Literal["top_to_bottom", "row_wise", "column_wise", "mixed", "unknown"] = (
        "unknown"
    )
    split_x: float | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    engine: Literal["pymupdf", "pdfplumber", "ocr", "unknown"] = "unknown"
    block_ids: list[str] = Field(default_factory=list)
    zones: list[LayoutZone] = Field(default_factory=list)
    reading_order_risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    useful_text_density: float | None = Field(default=None, ge=0.0, le=1.0)
    whitespace_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    minimum_font_size: float | None = Field(default=None, ge=0.0)
    small_font_proportion: float | None = Field(default=None, ge=0.0, le=1.0)
    decorative_shape_count: int = Field(default=0, ge=0)
    image_only_contact_risk: bool = False
    sparse_trailing_page: bool = False
    column_complexity: int = Field(default=1, ge=0)
    warnings: list[str] = Field(default_factory=list)


class TextExtractionResult(StrictModel):
    success: bool
    file_name: str
    file_type: Literal["pdf", "docx", ""]
    pages: int = Field(ge=0)
    words: int = Field(ge=0)
    chars: int = Field(ge=0)
    links: list[str] = Field(default_factory=list)

    # Backward-compatible field used by the current pipeline.
    text: str = ""

    # New layout-aware fields.
    raw_text: str = ""
    ordered_text: str = ""
    raw_layout_blocks: list[LayoutBlock] = Field(default_factory=list)
    page_layouts: list[PageLayout] = Field(default_factory=list)
    layout: Literal["single_column", "two_column", "mixed", "unknown"] = "unknown"
    reading_order: Literal[
        "top_to_bottom",
        "row_wise",
        "column_wise",
        "mixed",
        "unknown",
    ] = "unknown"
    engine: Literal[
        "pymupdf",
        "pdfplumber",
        "ocr",
        "docx",
        "docx_ooxml",
        "mixed",
        "unknown",
    ] = "unknown"

    ocr_used: bool = False
    ocr_available: bool | None = None
    quality_score: int = Field(default=0, ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)
    visual_metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    ocr_error: str | None = None
