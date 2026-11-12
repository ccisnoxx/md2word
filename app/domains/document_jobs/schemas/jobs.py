"""任务创建、详情、列表、生命周期操作、事件、文件、可用动作、重试/克隆、批量操作与下载 URL 的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.domains.document_jobs.views.jobs import DocumentJobDownloadClassification, DocumentJobResponse
from app.domains.files.schemas import DocumentFileSummaryResponse
from app.domains.translation.modes import (
    DocumentJobMode,
    DocumentLanguage,
    LEGACY_DIRECT_TRANSLATION_MODES,
    TranslationMode,
    normalize_translation_mode,
)


TRANSLATION_SELECTION_DESCRIPTION = "仅适用于跨语言翻译任务；原文转换（direct）不得显式绑定翻译资源。"


class DocumentJobCreateRequest(BaseModel):
    source_file_id: str
    mode: DocumentJobMode | None = None
    translation_mode: TranslationMode | None = Field(
        default=None, description="使用五种规范模式；兼容历史 zh2zh / zh_to_zh 输入并归一为 direct。"
    )
    document_language: DocumentLanguage = "auto"
    template_version_id: str | None = None
    term_version_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    debug_full_text: bool = Field(default=False, description="仅 Admin 可为翻译任务开启；direct 请求不得为 true。")

    @field_validator("translation_mode", mode="before")
    @classmethod
    def _normalize_historical_direct_mode(cls, value: Any) -> Any:
        """仅接纳已约定的历史输入，其他值继续由五值 Literal 严格校验。"""

        if isinstance(value, str) and value.strip().lower() in LEGACY_DIRECT_TRANSLATION_MODES:
            return normalize_translation_mode(value)
        return value


class DocumentJobCreateResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    job: DocumentJobResponse


class DocumentJobListResponse(BaseModel):
    items: list[DocumentJobResponse]
    page: int
    page_size: int
    total: int
    summary: dict[str, int] = Field(default_factory=dict)
    filtered_summary: dict[str, int] = Field(default_factory=dict)
    translation_qa_summary: dict[str, int] = Field(default_factory=dict)


class DocumentJobArchiveResponse(BaseModel):
    job_id: str
    archived_at: datetime
    job: DocumentJobResponse


class DocumentJobUnarchiveResponse(BaseModel):
    job_id: str
    restored_at: datetime
    job: DocumentJobResponse


class DocumentJobDeleteExecuteRequest(BaseModel):
    preview_hash: str
    reason: str | None = None
    confirmation: str | None = None


class DocumentJobDeleteFileResponse(BaseModel):
    file_id: str
    file_type: str | None = None
    storage_provider: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    size_bytes: int | None = None
    action: Literal["delete", "keep"]
    outcome: str
    reason: str
    deleted: bool = False
    metadata_updated: bool = False
    s3_delete_contract: dict[str, Any] | None = None


class DocumentJobDeleteSafetyResponse(BaseModel):
    physical_delete_executed: bool = False
    metadata_mutated: bool = False
    audit_events_written: bool = False
    s3_delete_executed: bool = False
    deleted_job_metadata_retained: bool = True


class DocumentJobDeletePreviewResponse(BaseModel):
    job_id: str
    action_mode: Literal["delete_preview"]
    confirmation_phrase: str
    preview_hash: str
    totals: dict[str, int] = Field(default_factory=dict)
    files: list[DocumentJobDeleteFileResponse] = Field(default_factory=list)
    safety: DocumentJobDeleteSafetyResponse


class DocumentJobDeleteExecuteResponse(BaseModel):
    job_id: str
    action_mode: Literal["delete_execute"]
    confirmation_phrase: str
    preview_hash: str
    totals: dict[str, int] = Field(default_factory=dict)
    files: list[DocumentJobDeleteFileResponse] = Field(default_factory=list)
    safety: DocumentJobDeleteSafetyResponse
    job: DocumentJobResponse


class DocumentJobCancelResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    canceled_at: datetime
    job: DocumentJobResponse


class DocumentJobEventResponse(BaseModel):
    id: str
    job_id: str
    tenant_id: str
    company_id: str
    created_by: str
    stage: str
    level: str
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    trace_id: str | None = None
    created_at: datetime


class DocumentJobEventListResponse(BaseModel):
    job_id: str
    items: list[DocumentJobEventResponse]


class DocumentJobFileListResponse(BaseModel):
    """任务详情页使用的文件汇总响应，不包含存储对象定位、raw metadata 或长期下载地址。"""

    job_id: str
    files: list[DocumentFileSummaryResponse]


class DocumentJobDownloadUrlResponse(BaseModel):
    job_id: str
    file_id: str
    download_url: str
    method: Literal["GET"] = "GET"
    expires_at: datetime
    file: DocumentFileSummaryResponse
    classification: DocumentJobDownloadClassification | None = Field(
        default=None, json_schema_extra={"readOnly": True}, description="当前主 DOCX 为 internal_only，普通 Artifact 为空。"
    )
    warning_code: str | None = Field(default=None, json_schema_extra={"readOnly": True})
    warning_message: str | None = Field(default=None, json_schema_extra={"readOnly": True})


class DocumentJobRetryRequest(BaseModel):
    reason: str | None = None
    use_latest_term_assets: bool = False
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)


class DocumentJobCloneRequest(BaseModel):
    reason: str | None = None
    config_strategy: Literal["keep_source_snapshot", "use_current_defaults", "select_published_versions"] = "keep_source_snapshot"
    document_language: DocumentLanguage | None = None
    template_version_id: str | None = None
    term_version_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    debug_full_text: bool | None = Field(default=None, description="仅 Admin 可为翻译任务开启；direct 请求不得为 true。")


class DocumentJobRetryResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    retry_count: int
    job: DocumentJobResponse


class DocumentJobCloneResponse(BaseModel):
    source_job_id: str
    job_id: str
    status: str
    stage: str
    progress: int
    job: DocumentJobResponse


class DocumentJobBulkJobIdsRequest(BaseModel):
    """批量任务操作的 job_id 列表。"""

    job_ids: list[str] = Field(default_factory=list)


class DocumentJobBulkRetryRequest(BaseModel):
    """批量重试请求；重试选项与单任务重试保持一致。"""

    job_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    use_latest_term_assets: bool = False
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)


class DocumentJobBulkItemResponse(BaseModel):
    """批量操作中单个任务的成功或失败结果。"""

    job_id: str
    ok: bool
    status_code: int
    error_code: str | None = None
    detail: str | None = None
    job: DocumentJobResponse | None = None


class DocumentJobBulkResponse(BaseModel):
    """批量任务操作响应；允许部分成功。"""

    action: Literal["retry", "archive", "cancel"]
    total: int
    succeeded: int
    failed: int
    items: list[DocumentJobBulkItemResponse] = Field(default_factory=list)
