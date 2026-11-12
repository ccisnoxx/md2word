"""翻译 QA 与表格参考的用例输出模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentJobTableReferenceResponse(BaseModel):
    """审核白名单投影，不包含包内路径、对象定位或原始 metadata。"""

    block_id: str
    fragment_id: str
    logical_group_id: str
    page_index: int | None
    bbox: tuple[float, float, float, float] | None
    asset_id: str | None
    file_id: str | None
    source_status: Literal["valid", "missing", "invalid"]
    availability: Literal["available", "source_missing", "source_invalid", "missing", "expired", "deleted", "not_uploaded"]
    mime_type: str | None
    checksum_sha256: str | None
    size_bytes: int | None
    warning_codes: list[str] = Field(default_factory=list)
    display_supported: bool
    content_path: str | None


class DocumentJobTableReferenceListResponse(BaseModel):
    job_id: str
    generation: int
    ir_file_id: str | None
    evidence_status: Literal["not_ready", "legacy_unavailable", "registered"]
    items: list[DocumentJobTableReferenceResponse] = Field(default_factory=list)


class DocumentJobTranslationQaStateResponse(BaseModel):
    """任务级翻译 QA 复核状态。"""

    status: Literal["unreviewed", "approved", "needs_fix", "blocked"]
    issue_type: Literal[
        "translation",
        "terminology",
        "layout",
        "source_quality",
        "artifact_missing",
        "other",
    ] | None = None
    note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class DocumentJobTranslationQaArtifactsResponse(BaseModel):
    document_ir_file_id: str | None = None
    ai_call_log_file_ids: list[str] = Field(default_factory=list)
    ai_debug_archive_file_ids: list[str] = Field(default_factory=list)
    ai_debug_archive_expires_at: datetime | None = None
    ai_debug_archive_expired: bool = False
    ai_debug_archive_contains_full_text: bool = False


class DocumentJobTranslationQaSummaryResponse(BaseModel):
    final_segment_count: int = 0
    returned_segment_count: int = 0
    quality_flags: list[str] = Field(default_factory=list)
    ai_call_count: int = 0
    ai_call_statuses: dict[str, int] = Field(default_factory=dict)
    term_trace_count: int = 0
    debug_full_text_enabled: bool = False
    source_comparison_available: bool = False
    source_comparison_reason: str | None = None


class DocumentJobTranslationQaSegmentResponse(BaseModel):
    id: str
    block_id: str
    page_index: int | None = None
    order: int
    block_type: str
    field: str
    index: int | None = None
    source_text: str | None = None
    ai_translation_text: str | None = None
    final_text: str
    source_available: bool = False


class DocumentJobTranslationQaTermTraceResponse(BaseModel):
    segment_id: str | None = None
    batch_id: str | None = None
    translation_term_set_id: str | None = None
    translation_term_version: str | None = None
    source_term: str | None = None
    target_term: str | None = None
    match_start: int | None = None
    match_end: int | None = None
    context: dict[str, Any] | None = None
    injected_to_glossary: bool = False
    provider_trace_id: str | None = None


class DocumentJobTranslationQaAiCallResponse(BaseModel):
    file_id: str
    call_id: str | None = None
    status: str | None = None
    provider: dict[str, Any] = Field(default_factory=dict)
    language_pair: str | None = None
    source_language: str | None = None
    target_language: str | None = None
    term_version_id: str | None = None
    term_snapshot_hash: str | None = None
    term_count: int = 0
    item_count: int = 0
    char_count: int = 0
    duration_ms: int | None = None
    created_at: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class DocumentJobTranslationQaResponse(BaseModel):
    job_id: str
    available: bool
    availability_reason: str | None = None
    qa: DocumentJobTranslationQaStateResponse
    artifacts: DocumentJobTranslationQaArtifactsResponse
    summary: DocumentJobTranslationQaSummaryResponse
    segments: list[DocumentJobTranslationQaSegmentResponse] = Field(default_factory=list)
    term_traces: list[DocumentJobTranslationQaTermTraceResponse] = Field(default_factory=list)
    ai_calls: list[DocumentJobTranslationQaAiCallResponse] = Field(default_factory=list)
