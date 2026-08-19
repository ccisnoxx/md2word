from __future__ import annotations

# app/services/document_ir/models.py: 定义 DocumentIR v1/v2 的持久化数据结构。

from typing import Any, Literal

from pydantic import BaseModel, Field


DocumentIRBlockType = Literal["heading", "paragraph", "table", "image", "list", "formula"]
DocumentIRAssetKind = Literal["image"]
DocumentIRSchemaVersion = Literal["document-ir/v1", "document-ir/v2"]
DocumentIRBlockRole = Literal["body", "page_header", "page_footer", "page_number"]
DocumentIRColumnHint = Literal["left", "right", "wide"]


class DocumentIRMetadata(BaseModel):
    """DocumentIR 文档级元数据；只保存追溯和粗粒度解析信息。"""

    job_id: str
    source_file_id: str
    document_language: str
    parser: str = "mineru"
    parser_version: str | None = None
    source_block_count: int | None = None
    source_type_counts: dict[str, int] = Field(default_factory=dict)


class DocumentIRAsset(BaseModel):
    """DocumentIR 引用的外部资产，二进制由 document_files 追溯。"""

    id: str
    kind: DocumentIRAssetKind
    source_path: str
    file_id: str | None = None
    object_key: str | None = None
    mime_type: str | None = None
    checksum_sha256: str | None = None


class DocumentIRPage(BaseModel):
    """DocumentIR v2 页级布局事实；坐标单位保持 MinerU 原始空间。"""

    index: int
    width: float | None = None
    height: float | None = None
    coordinate_unit: Literal["mineru"] = "mineru"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIRBlockLayout(BaseModel):
    """DocumentIR v2 块级布局事实；不包含 Word 样式决策。"""

    page_index: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    role: DocumentIRBlockRole = "body"
    source_index: int | None = None
    continuation_heights: list[float] = Field(default_factory=list)
    column_hint: DocumentIRColumnHint | None = None


class DocumentIRBlock(BaseModel):
    """DocumentIR 内容块；v2 可携带布局事实，v1 缺省为空。"""

    id: str
    type: DocumentIRBlockType
    order: int
    page_index: int | None = None
    text: str | None = None
    level: int | None = None
    html: str | None = None
    latex: str | None = None
    list_items: list[str] | None = None
    asset_ref: str | None = None
    layout: DocumentIRBlockLayout | None = None
    captions: list[str] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIR(BaseModel):
    """DocumentIR 文档根对象；默认保持 v1，显式 schema_version 可启用 v2。"""

    schema_version: DocumentIRSchemaVersion = "document-ir/v1"
    metadata: DocumentIRMetadata
    pages: list[DocumentIRPage] = Field(default_factory=list)
    blocks: list[DocumentIRBlock] = Field(default_factory=list)
    assets: list[DocumentIRAsset] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
