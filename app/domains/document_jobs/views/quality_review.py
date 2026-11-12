"""质量、预览、复核与复核内容的严格读模型；仅服务新复核 API，不改变旧 QA 与任务详情的序列化合同。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.document_jobs.models import (
    DocumentJobDeliveryStatus,
    DocumentJobQualityStatus,
    DocumentJobReviewStatus,
)
from app.domains.document_jobs.views.jobs import DocumentJobActionId, DocumentJobAvailableActionResponse
from app.domains.document_jobs.views.translation import DocumentJobTableReferenceResponse


# 新复核 API 使用独立严格 DTO；不改变旧 QA 和任务详情的序列化合同。
QualityId = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:\-]+$")]


QualityCount = Annotated[int, Field(strict=True, ge=0)]


QualityHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


QualityChecksum = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


QualityVersion = Annotated[str, Field(max_length=100, pattern=r"^[a-z][a-z0-9-]*/v[0-9]+$")]


QualityAvailability = Literal["available", "legacy_unavailable", "not_ready", "disabled", "unavailable"]


QualityRule = Literal["clipping", "overflow", "blank", "overlap", "density"]


QualityIssue = Literal["conversion", "translation", "terminology", "table_structure", "layout", "source_quality", "artifact_missing", "other"]


QualityMetric = Literal["native_outside_area_pt2", "foreground_union_area_pt2", "outside_area_ratio", "outside_object_count",
    "max_outside_distance_pt", "edge_ink_ratio", "outside_body_area_ratio", "clearance_pt", "excluded_object_count",
    "ink_area_ratio", "foreground_object_count", "char_count", "positive_pair_count", "max_intersection_min_area_ratio",
    "body_ink_ratio", "native_foreground_body_area_ratio", "char_density", "group_median", "median_absolute_deviation"]


class QualityReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class DocumentQualitySourceResponse(QualityReviewModel):
    generation: QualityCount
    ir_file_id: QualityId | None
    result_file_id: QualityId | None
    result_sha256: QualityChecksum | None
    file_review_source_revision: QualityCount | None
    receipt_sha256: QualityChecksum | None


class DocumentQualityCountsResponse(QualityReviewModel):
    formula_count: QualityCount | None = None
    omml_count: QualityCount | None = None
    semantic_count: QualityCount | None = None
    fallback_count: QualityCount | None = None
    table_count: QualityCount | None = None
    fragment_count: QualityCount | None = None
    native_count: QualityCount | None = None
    placeholder_count: QualityCount | None = None
    blocker_count: QualityCount | None = None
    warning_count: QualityCount | None = None
    page_count: QualityCount | None = None
    complete_page_count: QualityCount | None = None
    flag_count: QualityCount | None = None
    count: QualityCount | None = None
    pages: QualityCount | None = None
    observed_pages: QualityCount | None = None
    flags: QualityCount | None = None
    manual_checks: QualityCount | None = None
    checked_rules: QualityCount | None = None
    not_checked_rules: QualityCount | None = None


class DocumentQualityProducerResponse(QualityReviewModel):
    producer: Literal["formula", "table_evidence", "table_placeholder", "word_preview", "word_page_quality", "document_base", "unattributed"]
    schema_version: QualityVersion | None = None
    quality_status: DocumentJobQualityStatus | None = None
    evaluation_state: Literal["complete", "incomplete"] | None = None
    availability: QualityAvailability | None = None
    coverage: Literal["complete", "unavailable"] | None = None
    report_sha256: QualityHash | None = None
    reason_code: str | None = None
    counts: DocumentQualityCountsResponse
    flags: list[str] = Field(default_factory=list)
    unknown_flag_count: QualityCount = 0


class DocumentQualityProducersResponse(QualityReviewModel):
    items: list[DocumentQualityProducerResponse]
    unknown_producer_count: QualityCount


class DocumentQualitySummaryResponse(QualityReviewModel):
    quality_flags: list[str] = Field(default_factory=list)
    layout_quality_flags: list[str] = Field(default_factory=list)
    blocking_quality_flags: list[str] = Field(default_factory=list)
    unknown_flag_count: QualityCount = 0


class DocumentReviewBindingResponse(QualityReviewModel):
    generation: QualityCount
    result_file_id: QualityId | None
    binding_state: Literal["verified", "no_result", "unverified_result", "legacy_unbound"]
    result_sha256: QualityChecksum | None
    file_review_source_revision: QualityCount | None
    receipt_sha256: QualityChecksum | None


class DocumentReviewQualityResponse(QualityReviewModel):
    quality_status: DocumentJobQualityStatus
    summary_sha256: QualityChecksum
    summary: DocumentQualitySummaryResponse
    producers: DocumentQualityProducersResponse


class DocumentReviewResponse(QualityReviewModel):
    status: DocumentJobReviewStatus
    current_record_id: QualityId | None
    sequence: QualityCount | None
    issue_type: QualityIssue | None
    note: str | None
    reviewed_by: QualityId | None
    reviewed_at: datetime | None
    binding: DocumentReviewBindingResponse | None
    validity_reason: Literal["legacy_unbound", "source_changed", "artifact_missing", "artifact_unavailable", "integrity_conflict", "quality_blocked"] | None
    quality: DocumentReviewQualityResponse | None


class DocumentReviewHistoryItemResponse(QualityReviewModel):
    id: QualityId
    sequence: QualityCount
    record_status: DocumentJobReviewStatus
    issue_type: QualityIssue | None
    note: str | None
    reviewed_by: QualityId | None
    reviewed_at: datetime | None
    origin: Literal["live", "legacy_import"]
    legacy_observed_status: DocumentJobReviewStatus | None
    binding: DocumentReviewBindingResponse
    quality: DocumentReviewQualityResponse


class DocumentQualityStatesResponse(QualityReviewModel):
    execution_status: Literal["pending", "queued", "running", "succeeded", "failed", "canceled"]
    quality_status: DocumentJobQualityStatus
    review_status: DocumentJobReviewStatus
    delivery_status: DocumentJobDeliveryStatus


class DocumentQualityResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    states: DocumentQualityStatesResponse
    summary: DocumentQualitySummaryResponse
    producers: DocumentQualityProducersResponse
    review: DocumentReviewResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]


class DocumentQualitySourceSpanResponse(QualityReviewModel):
    fragment_id: QualityId | None = None
    source_page_index: QualityCount | None
    bbox: tuple[float, float, float, float] | None
    html_state: Literal["missing", "empty", "present"] | None = None
    row_start: QualityCount | None = None
    row_count: QualityCount | None = None
    columns: QualityCount | None = None


class DocumentQualityGridResponse(QualityReviewModel):
    rows: QualityCount
    columns: QualityCount
    header_rows: list[QualityCount]
    rowspan_count: QualityCount
    colspan_count: QualityCount


class DocumentQualityTableReferenceResponse(QualityReviewModel):
    fragment_id: QualityId
    source_status: Literal["valid", "missing", "invalid", "unavailable"]
    asset_id: QualityId | None
    file_id: QualityId | None
    mime_type: str | None
    registered: bool


class DocumentQualityCellShapeResponse(QualityReviewModel):
    grid_span: QualityCount
    vertical_merge: Literal["restart", "continue"] | None


class DocumentQualityRowShapeResponse(QualityReviewModel):
    cells: list[DocumentQualityCellShapeResponse]
    header: bool
    cant_split: bool


class DocumentQualityFragmentResponse(QualityReviewModel):
    fragment_id: QualityId
    block_id: QualityId | None
    render_owner_block_id: QualityId
    source_rows: list[QualityCount]
    retained_source_rows: list[QualityCount]
    output_rows: list[QualityCount]
    removed_header_rows: list[QualityCount] | None
    shared_header_rows: list[QualityCount] | None
    status: Literal["rendered", "header_only", "empty", "missing"]


class DocumentQualityNativeTableResponse(QualityReviewModel):
    output_table_key: QualityId
    anchor_block_id: QualityId
    table_index: QualityCount
    grid_columns: QualityCount
    rows: list[DocumentQualityRowShapeResponse]
    fragments: list[DocumentQualityFragmentResponse]


class DocumentQualityPlaceholderResponse(QualityReviewModel):
    placeholder_id: QualityId
    fragment_id: QualityId
    owner_block_id: QualityId
    asset_ref: QualityId
    source_kind: Literal["mineru_reference", "source_pdf_crop"]
    issue_code: Literal["table_noneditable_placeholder"]


class DocumentQualityTableFlagResponse(QualityReviewModel):
    producer: Literal["table_validator", "table_rendering", "table_reference", "table_placeholder"]
    code: str
    severity: Literal["blocker", "warning"]
    fragment_id: QualityId | None


class DocumentQualityTableItemResponse(QualityReviewModel):
    table_id: QualityId
    logical_group_id: QualityId
    member_block_ids: list[QualityId]
    anchor_block_id: QualityId
    source_spans: list[DocumentQualitySourceSpanResponse]
    source_grid: DocumentQualityGridResponse
    references: list[DocumentQualityTableReferenceResponse]
    outputs: list[DocumentQualityNativeTableResponse]
    placeholders: list[DocumentQualityPlaceholderResponse]
    render_state: Literal["native", "placeholder", "mixed", "excluded_margin_artifact"]
    flags: list[DocumentQualityTableFlagResponse]
    unknown_flag_count: QualityCount
    status: DocumentJobQualityStatus


class DocumentQualityTableReportResponse(QualityReviewModel):
    schema_version: QualityVersion
    report_file_id: QualityId
    report_sha256: QualityHash
    coverage: Literal["complete", "unavailable"] | None
    status: DocumentJobQualityStatus | None
    counts: DocumentQualityCountsResponse


class DocumentQualityTablesResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    availability: QualityAvailability
    reason_code: str | None
    report: DocumentQualityTableReportResponse | None
    items: list[DocumentQualityTableItemResponse]
    next_cursor: str | None


class DocumentQualityPageRuleResponse(QualityReviewModel):
    rule_version: Literal["v1"]
    checked: bool
    reason_code: str | None
    metrics: dict[QualityMetric, float | int | None]
    units: dict[QualityMetric, Literal["pt", "pt2", "ratio", "count", "char/pt2"]]


class DocumentQualityPageFlagResponse(QualityReviewModel):
    code: Literal["page_clip_risk", "page_overflow_risk", "unexpected_blank_page_suspected", "page_overlap_suspected", "page_density_low", "page_density_high"]
    severity: Literal["warning", "info"]
    rule_version: Literal["v1"]
    preview_page_index: QualityCount
    metric_refs: list[str]
    evidence_kind: Literal["native_and_raster"]
    manual_check_required: Literal[True]


class DocumentQualityBlockCandidateResponse(QualityReviewModel):
    block_id: QualityId
    association: Literal["single_page", "estimated_start", "navigation_fallback"]
    confidence: Literal["high", "low"]
    source_page_indices: list[QualityCount]
    source_spans: list[DocumentQualitySourceSpanResponse]


class DocumentQualityPageItemResponse(QualityReviewModel):
    preview_page_index: QualityCount
    rules: dict[QualityRule, DocumentQualityPageRuleResponse]
    flags: list[DocumentQualityPageFlagResponse]
    unknown_flag_count: QualityCount
    manual_checks: list[str]
    block_candidates: list[DocumentQualityBlockCandidateResponse]


class DocumentQualityCoverageResponse(QualityReviewModel):
    checked: QualityCount
    not_checked: QualityCount


class DocumentQualityPageReportResponse(QualityReviewModel):
    schema_version: QualityVersion
    analyzer_version: QualityVersion
    id: QualityId
    run_sha256: QualityHash
    generation: QualityCount
    preview_run_id: QualityId
    revision: QualityCount
    attempt: QualityCount
    manifest_file_id: QualityId
    profile_id: QualityId
    profile_sha256: QualityChecksum
    page_count: QualityCount
    evaluation_state: Literal["complete", "incomplete"]
    quality_status: Literal["pending", "passed", "warning"]
    reason_code: str | None
    manual_checks: list[str]
    coverage: dict[QualityRule, DocumentQualityCoverageResponse]
    counts: DocumentQualityCountsResponse


class DocumentQualityPagesResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    availability: QualityAvailability
    reason_code: str | None
    report: DocumentQualityPageReportResponse | None
    items: list[DocumentQualityPageItemResponse]
    next_cursor: str | None


class DocumentPreviewPageResponse(QualityReviewModel):
    file_id: QualityId
    page_index: QualityCount
    width: QualityCount
    height: QualityCount


class DocumentPreviewRunResponse(QualityReviewModel):
    run_id: QualityId
    revision: QualityCount
    attempt: QualityCount
    status: Literal["pending", "running", "succeeded", "failed", "unavailable"]
    profile_id: QualityId
    profile_sha256: QualityChecksum
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None


class DocumentPreviewResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    status: Literal["not_ready", "disabled", "pending", "running", "succeeded", "failed", "unavailable"]
    availability: QualityAvailability
    reason_code: str | None
    run: DocumentPreviewRunResponse | None
    pdf_file_id: QualityId | None
    page_count: QualityCount | None
    items: list[DocumentPreviewPageResponse]
    next_cursor: str | None


class DocumentCurrentReviewResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    review: DocumentReviewResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]


class DocumentReviewComponentResponse(QualityReviewModel):
    availability: Literal["available", "unavailable", "not_ready", "disabled", "not_applicable"]
    reason_code: str | None = None


class DocumentReviewContentSnapshotResponse(QualityReviewModel):
    snapshot_id: QualityHash
    source_pdf_file_id: QualityId
    source_ir_file_id: QualityId | None
    final_ir_file_id: QualityId | None
    preview_run_id: QualityId | None
    preview_revision: QualityCount | None
    preview_attempt: QualityCount | None
    basis: Literal["source", "final", "none"]
    source_content: DocumentReviewComponentResponse
    target_content: DocumentReviewComponentResponse
    translation: DocumentReviewComponentResponse
    preview: DocumentReviewComponentResponse
    mapping: DocumentReviewComponentResponse
    tables: DocumentReviewComponentResponse


class DocumentReviewSourceSpanResponse(QualityReviewModel):
    source_page_index: QualityCount | None
    bbox: tuple[float, float, float, float] | None
    page_width: float | None
    page_height: float | None
    coordinate_unit: Literal["mineru"] = "mineru"
    coordinate_verified: bool
    reason_code: Literal["coordinate_space_unverified"] | None
    fragment_id: QualityId | None = None


class DocumentReviewLocationResponse(QualityReviewModel):
    kind: Literal["single_page", "estimated_start", "unavailable"]
    preview_page_index: QualityCount | None
    confidence: Literal["high", "low", "none"]
    reason_code: str | None
    bookmark_label: str | None = Field(default=None, max_length=100)
    disposition: Literal["rendered", "coalesced", "suppressed", "superseded", "not_emitted"] | None = None
    representative_block_id: QualityId | None = None
    fallback_page_index: QualityCount | None = None
    fallback_block_id: QualityId | None = None
    provenance_status: Literal["verified_ir205", "legacy_layout", "unavailable"] = "unavailable"


class DocumentReviewBlockFlagResponse(QualityReviewModel):
    code: str
    severity: Literal["blocker", "warning", "info"]
    table_id: QualityId | None = None


class DocumentReviewBlockItemResponse(QualityReviewModel):
    block_id: QualityId
    order: QualityCount
    block_type: Literal["heading", "paragraph", "table", "image", "list", "formula"]
    source_type: str | None = Field(default=None, max_length=100)
    excerpt: str = Field(max_length=240)
    source_spans: list[DocumentReviewSourceSpanResponse]
    location: DocumentReviewLocationResponse
    flags: list[DocumentReviewBlockFlagResponse]
    table_ids: list[QualityId]


class DocumentReviewBlocksResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    content_snapshot: DocumentReviewContentSnapshotResponse
    availability: Literal["available", "not_ready", "unavailable"]
    reason_code: str | None
    total: QualityCount
    items: list[DocumentReviewBlockItemResponse]
    next_cursor: str | None


class DocumentReviewTermResponse(QualityReviewModel):
    unit_id: QualityId
    batch_id: QualityId
    source_term: str = Field(max_length=4096)
    target_term: str = Field(max_length=4096)
    version: str | None = Field(default=None, max_length=100)


class DocumentReviewTokenCountsResponse(QualityReviewModel):
    formula: QualityCount = 0
    literal_placeholder: QualityCount = 0
    address: QualityCount = 0
    bit_field: QualityCount = 0
    model: QualityCount = 0
    standard: QualityCount = 0
    version: QualityCount = 0
    signal: QualityCount = 0
    quantity: QualityCount = 0
    unit: QualityCount = 0
    url: QualityCount = 0
    email: QualityCount = 0
    number: QualityCount = 0
    symbol: QualityCount = 0
    technical_literal: QualityCount = 0


class DocumentReviewBatchResponse(QualityReviewModel):
    scope: Literal["batch"] = "batch"
    batch_id: QualityId
    attempt: QualityCount
    status: Literal["succeeded", "failed"]
    provider_backend: Literal["fake", "openai_compatible"] | None = None
    provider_model: str | None = Field(default=None, max_length=200)
    schema_version: QualityVersion | None = None
    validator_version: QualityVersion | None = None
    codec_version: Literal["MD2W_PT_v1"] | None = None
    instruction_version: QualityVersion | None = None
    instruction_sha256: QualityChecksum | None = None
    integrity_status: Literal["passed", "failed", "pending"] | None = None
    error_code: str | None = None
    expected_item_count: QualityCount | None = None
    actual_item_count: QualityCount | None = None
    checked_item_count: QualityCount | None = None
    failed_item_count: QualityCount | None = None
    expected_token_counts: DocumentReviewTokenCountsResponse | None = None
    actual_token_counts: DocumentReviewTokenCountsResponse | None = None
    source_sha256: QualityChecksum | None = None
    restored_sha256: QualityChecksum | None = None


class DocumentReviewContentPartResponse(QualityReviewModel):
    kind: Literal["text", "list_item", "caption", "footnote", "latex", "table_text", "html_summary", "term", "batch", "table", "reference"]
    side: Literal["source", "target", "shared"]
    field: str
    index: QualityCount | None = None
    unit_id: QualityId | None = None
    fragment_id: QualityId | None = None
    offset: QualityCount = 0
    text: str | None = Field(default=None, max_length=4096)
    total_chars: QualityCount | None = None
    truncated: bool = False
    html_state: Literal["missing", "empty", "present"] | None = None
    sha256: QualityHash | None = None
    term: DocumentReviewTermResponse | None = None
    batch: DocumentReviewBatchResponse | None = None
    table: DocumentQualityTableItemResponse | None = None
    reference: DocumentJobTableReferenceResponse | None = None


class DocumentReviewBlockDetailResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    content_snapshot: DocumentReviewContentSnapshotResponse
    block: DocumentReviewBlockItemResponse
    items: list[DocumentReviewContentPartResponse]
    next_cursor: str | None


class DocumentReviewHistoryResponse(QualityReviewModel):
    job_id: QualityId
    through_sequence: QualityCount
    items: list[DocumentReviewHistoryItemResponse]
    next_cursor: str | None


class DocumentReviewUpdateResponse(QualityReviewModel):
    job_id: QualityId
    accepted_record_id: QualityId
    accepted_sequence: QualityCount
    source: DocumentQualitySourceResponse
    review: DocumentReviewResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]
