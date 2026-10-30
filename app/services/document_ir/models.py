from __future__ import annotations

# app/services/document_ir/models.py: 定义 DocumentIR v1/v2 的持久化数据结构。

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.services.document_ir.artifact_validator import MinerUValidationReport
from app.services.document_ir.table_placeholder import TablePlaceholderBinding


DocumentIRBlockType = Literal["heading", "paragraph", "table", "image", "list", "formula"]
DocumentIRAssetKind = Literal["image"]
DocumentIRSchemaVersion = Literal["document-ir/v1", "document-ir/v2"]
DocumentIRBlockRole = Literal["body", "page_header", "page_footer", "page_number"]
DocumentIRColumnHint = Literal["left", "right", "wide"]


class SourceSpan(BaseModel):
    """原始数组定位；与归一化后的 layout.source_index 分开保存。"""

    model_config = ConfigDict(extra="forbid")
    json_pointer: str
    source_index: int = Field(ge=0)
    source_index_in_page: int | None = Field(default=None, ge=0)
    source_type: str
    page_index: int | None = Field(default=None, ge=0)
    bbox: tuple[float, float, float, float] | None = None


class RepeatedHeaderHint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_row: Literal[0] = 0
    row_count: int = Field(gt=0)
    signature: str


class TableFragment(BaseModel):
    """原始全文只保存于 raw_fragment；HTML 是定位到该全文的只读投影。"""

    model_config = ConfigDict(extra="forbid")
    fragment_id: str
    source_span: SourceSpan
    block_id: str | None
    render_owner_block_id: str
    raw_fragment: dict[str, JsonValue]
    raw_html_pointer: str | None = None
    html_state: Literal["missing", "empty", "present"]
    raw_html_sha256: str | None = None
    header_signature: str | None = None
    repeated_header_hint: RepeatedHeaderHint | None = None
    normalization_rule_id: str | None = None
    normalization_reason: Literal["explicit_table_placeholder", "strict_empty_table_placeholder"] | None = None

    @property
    def raw_html(self) -> str | None:
        if self.raw_html_pointer is None:
            return None
        value: Any = self.raw_fragment
        try:
            for token in self.raw_html_pointer.split("/")[1:]:
                token = token.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value, list) else value[token]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError("逻辑表格来源合同无效：raw_html_pointer。") from error
        if not isinstance(value, str):
            raise ValueError("逻辑表格来源合同无效：raw_html_type。")
        return value


class ContinuationRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_fragment_id: str
    to_fragment_id: str
    kind: Literal["verified_continuation", "normalized_empty_placeholder"]
    rule_id: str
    evidence_codes: list[Literal["normalization_receipt", "adjacent_page_geometry", "same_table_number_continued",
                                 "matching_header_consecutive_ordinal"]]


class TableContinuationDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_fragment_id: str
    to_fragment_id: str
    reason: Literal["missing_geometry", "geometry_mismatch", "page_not_adjacent", "page_body_boundary",
                    "insufficient_evidence", "header_mismatch", "column_mismatch", "unreliable_columns"]


class LogicalTableGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logical_group_id: str
    fragments: list[TableFragment]
    continuation_relations: list[ContinuationRelation] = Field(default_factory=list)
    diagnostics: list[TableContinuationDiagnostic] = Field(default_factory=list)


class TableReferenceFragment(BaseModel):
    """片段的源检查事实；文件后续是否可读由任务审核入口动态判断。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    fragment_id: str
    source_status: Literal["valid", "missing", "invalid"]
    asset_ref: str | None


class TableReferenceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["table-reference/v1"]
    asset_role: Literal["table_reference"]
    fragments: list[TableReferenceFragment]


class TableReferenceProvenance(BaseModel):
    """审核引用绑定转换原尝试，允许后续翻译重试复用 source IR。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    mineru_raw_result_file_id: str = Field(min_length=1)
    mineru_raw_result_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    retry_count: int = Field(ge=0)


class DocumentIRMetadata(BaseModel):
    """文档追溯、解析信息及受控 Artifact 内的原始表格来源账本。"""

    job_id: str
    source_file_id: str
    document_language: str
    parser: str = "mineru"
    parser_version: str | None = None
    source_block_count: int | None = None
    source_type_counts: dict[str, int] = Field(default_factory=dict)
    mineru_validation: MinerUValidationReport | None = None
    mineru_validation_input: dict[str, Any] | None = None
    logical_table_groups_version: Literal["logical-table-groups/v1"] | None = None
    logical_table_groups: list[LogicalTableGroup] = Field(default_factory=list)
    logical_table_group_counts: dict[str, int] = Field(default_factory=dict)
    table_references_version: Literal["table-reference/v1"] | None = None
    table_placeholders_version: Literal["table-placeholder/v1"] | None = None
    table_placeholders: list[TablePlaceholderBinding] = Field(default_factory=list)


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

    @model_validator(mode="after")
    def _validate_logical_tables(self) -> DocumentIR:
        # 同一 owner 校验首次构建和 Artifact 重读，避免损坏新合同被静默接受。
        from app.services.document_ir.logical_table_group import validate_logical_table_groups
        from app.services.document_ir.table_reference_assets import decode_table_references

        validate_logical_table_groups(self)
        decode_table_references(self)
        from app.services.document_ir.table_placeholder import decode_placeholders
        decode_placeholders(self)
        return self
