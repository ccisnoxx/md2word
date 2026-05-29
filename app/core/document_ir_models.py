from __future__ import annotations

# app/core/document_ir_models.py: 定义 DocumentIR v1 的持久化数据结构。

from typing import Any, Literal

from pydantic import BaseModel, Field


DocumentIRBlockType = Literal["heading", "paragraph", "table", "image", "list", "formula"]
DocumentIRAssetKind = Literal["image"]


class DocumentIRMetadata(BaseModel):
    """DocumentIR 文档级元数据；只保存追溯和粗粒度解析信息。"""

    job_id: str
    source_file_id: str
    document_language: str
    parser: str = "mineru"
    parser_version: str | None = None


class DocumentIRAsset(BaseModel):
    """DocumentIR 引用的外部资产，二进制由 document_files 追溯。"""

    id: str
    kind: DocumentIRAssetKind
    source_path: str
    file_id: str | None = None
    object_key: str | None = None
    mime_type: str | None = None
    checksum_sha256: str | None = None


class DocumentIRBlock(BaseModel):
    """DocumentIR v1 内容块；保持顺序，复杂结构先保留原始摘要。"""

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
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIR(BaseModel):
    """DocumentIR v1 文档根对象。"""

    schema_version: Literal["document-ir/v1"] = "document-ir/v1"
    metadata: DocumentIRMetadata
    blocks: list[DocumentIRBlock] = Field(default_factory=list)
    assets: list[DocumentIRAsset] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
