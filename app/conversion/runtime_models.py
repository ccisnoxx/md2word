from __future__ import annotations

# app/conversion/runtime_models.py: 定义 MinerU 到 DOCX 转换 runtime 的块、页面和渲染配置模型。

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Block:
    type: str
    bbox: tuple[float, float, float, float]
    text: str = ""
    items: list[str] = field(default_factory=list)
    level: int = 1
    image_path: Path | None = None
    captions: list[str] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    html: str | None = None
    page_idx: int | None = None
    block_idx: int | None = None
    continuation_heights: list[float] = field(default_factory=list)

    @property
    def x1(self) -> float:
        return self.bbox[0]

    @property
    def y1(self) -> float:
        return self.bbox[1]

    @property
    def x2(self) -> float:
        return self.bbox[2]

    @property
    def y2(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def mid_y(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2


@dataclass(slots=True)
class Region:
    kind: str
    blocks: list[Block]


@dataclass(slots=True)
class PageData:
    page_idx: int
    blocks: list[Block]
    page_size: tuple[float, float] | None = None


@dataclass(slots=True)
class MiddlePage:
    page_idx: int
    page_size: tuple[float, float] | None = None
    discarded_blocks: list[Block] = field(default_factory=list)
    visual_blocks: list[Block] = field(default_factory=list)


@dataclass(slots=True)
class SectionLayout:
    top_margin: Any
    bottom_margin: Any
    left_margin: Any
    right_margin: Any
    header_distance: Any
    footer_distance: Any


@dataclass(slots=True)
class RenderConfig:
    section_layout: SectionLayout
    use_mineru_header_footer: bool
    terminology: "TerminologyReplacer | None" = None
    paragraph_styles: dict[str, "ParagraphStyleConfig"] = field(default_factory=dict)
    table_style: "TableStyleConfig" = field(default_factory=lambda: TableStyleConfig())


@dataclass(slots=True)
class TableStyleConfig:
    header_bold: bool = True


@dataclass(slots=True)
class ParagraphStyleConfig:
    font_name: str | None = None
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    color: str | None = None
    alignment: str | None = None
    line_spacing: float | None = None
    space_before: float | None = None
    space_after: float | None = None
    first_line_indent_pt: float | None = None
    left_indent_pt: float | None = None
    right_indent_pt: float | None = None
