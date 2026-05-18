from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthLiveResponse(BaseModel):
    status: str
    app_name: str


class HealthReadyResponse(BaseModel):
    status: str
    app_name: str
    jobs_dir: str
    dependency_checks: dict[str, Any]


class JobAcceptedResponse(BaseModel):
    job_id: str
    trace_id: str
    status: Literal["uploaded", "queued", "submitting", "parsing", "parsed", "converting", "completed", "failed", "canceled"]
    translation_mode: Literal["direct", "en2zh"]


class JobFileResponse(BaseModel):
    file_type: str
    path: str
    storage_backend: str
    object_key: str | None = None
    public_url: str | None = None
    download_url: str | None = None
    created_at: datetime


class JobEventResponse(BaseModel):
    stage: str
    message: str
    status: str
    error_code: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    created_at: datetime


class JobSummaryResponse(BaseModel):
    id: str
    source_filename: str
    status: str
    progress: int
    translation_mode: str
    result_ready: bool
    result_download_url: str | None = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobSummaryResponse]
    page: int
    page_size: int
    total: int
    summary: dict[str, int]


class JobDetailResponse(BaseModel):
    id: str
    source_filename: str
    status: str
    progress: int
    source_kind: str
    translation_mode: str
    document_language: str
    resolved_document_language: str | None = None
    template_id: str | None = None
    mineru_batch_id: str | None = None
    mineru_data_id: str | None = None
    mineru_callback_seed: str | None = None
    mineru_status: str | None = None
    mineru_result_zip_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_ready: bool
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    files: list[JobFileResponse]
    events: list[JobEventResponse]


class JobFileListResponse(BaseModel):
    job_id: str
    files: list[JobFileResponse]


class JobEventListResponse(BaseModel):
    job_id: str
    items: list[JobEventResponse]


class JobOperationAcceptedResponse(BaseModel):
    job_id: str
    operation: str
    accepted: bool
    status: str
    message: str


class JobCleanupLocalFilesResponse(BaseModel):
    job_id: str
    deleted_paths: list[str]
    skipped_paths: list[dict[str, str]]
    status: str
    message: str


class TemplateAssetResponse(BaseModel):
    label: str
    exists: bool
    file_name: str | None = None
    size_bytes: int | None = None
    updated_at: datetime | None = None
    sha256: str | None = None
    download_url: str | None = None


class TemplateListItemResponse(BaseModel):
    id: str
    name: str
    description: str
    is_default: bool
    downloadable: bool
    download_url: str | None = None
    template: TemplateAssetResponse
    layout_config: TemplateAssetResponse
    subscript_config: TemplateAssetResponse


class TemplateDetailResponse(TemplateListItemResponse):
    def to_list_item(self) -> "TemplateListItemResponse":
        return TemplateListItemResponse.model_validate(self.model_dump())


class TemplateListResponse(BaseModel):
    items: list[TemplateListItemResponse]


class TermRuleCategoryListItemResponse(BaseModel):
    id: str
    code: str
    name: str
    priority: int
    enabled: bool
    description: str
    rule_count: int
    enabled_rule_count: int


class TermRuleCategoryListResponse(BaseModel):
    items: list[TermRuleCategoryListItemResponse]


class TermRuleSegmentResponse(BaseModel):
    seq: int
    segment_text: str
    render_type: str


class TermRuleResponse(BaseModel):
    id: str
    category_id: str
    category_code: str
    category_name: str
    source_term: str
    rule_mode: str
    apply_scope: str
    case_sensitive: bool
    enabled: bool
    priority: int
    segments: list[TermRuleSegmentResponse]
    custom_html: str | None = None
    custom_markdown: str | None = None
    notes: str


class TermRuleListResponse(BaseModel):
    items: list[TermRuleResponse]
    page: int
    page_size: int
    total: int


class RuleExportResponse(BaseModel):
    yaml_text: str


class RuleImportRequest(BaseModel):
    yaml_text: str


class RuleSimulationRequest(BaseModel):
    text: str


class RuleSimulationResponse(BaseModel):
    original: str
    markdown_preview: str
    html_preview: str


class TermRuleImportValidationFindingResponse(BaseModel):
    code: str
    message: str
    path: str | None = None


class TermRuleImportValidationSummaryResponse(BaseModel):
    category_count: int
    rule_count: int
    error_count: int
    warning_count: int


class TermRuleImportValidationReportResponse(BaseModel):
    valid: bool
    summary: TermRuleImportValidationSummaryResponse
    errors: list[TermRuleImportValidationFindingResponse]
    warnings: list[TermRuleImportValidationFindingResponse]


class TermRuleFileSyncResponse(BaseModel):
    repository_backend: str
    category_count: int
    rule_count: int
    bootstrap_seed_path: str
    runtime_yaml_path: str
    warnings: list[str]
