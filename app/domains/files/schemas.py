# File: app/domains/files/schemas.py
# Purpose: 定义文件元数据、上传授权、文件库搜索、保留期管理和物理删除 API 的 v1 请求/响应模型。

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FileUploadUrlRequest(BaseModel):
    """创建 source_pdf 上传授权的请求。"""

    filename: str
    mime_type: str = "application/pdf"
    size_bytes: int
    file_type: Literal["source_pdf"] = "source_pdf"
    checksum_sha256: str | None = None
    job_id: str | None = None


class DocumentFileResponse(BaseModel):
    """返回单个 document_file 的元数据，不包含文件内容。"""

    id: str
    tenant_id: str
    company_id: str
    job_id: str | None = None
    file_type: str
    storage_provider: str
    bucket: str
    object_key: str
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str | None = None
    etag: str | None = None
    status: str
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class FileLibrarySearchItemResponse(BaseModel):
    """返回文件库搜索中的安全文件摘要，不包含对象定位或 raw metadata。"""

    file_id: str
    job_id: str | None = None
    file_type: str
    storage_provider: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    expires_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    expired: bool
    physical_delete_candidate: bool


class FileLibrarySearchResponse(BaseModel):
    """返回 Admin-only 文件库搜索分页结果。"""

    generated_at: datetime
    page: int
    page_size: int
    total: int
    sort: Literal[
        "created_at_desc",
        "created_at_asc",
        "updated_at_desc",
        "updated_at_asc",
        "expires_at_desc",
        "expires_at_asc",
        "size_bytes_desc",
        "size_bytes_asc",
    ]
    filters: dict[str, str] = Field(default_factory=dict)
    items: list[FileLibrarySearchItemResponse] = Field(default_factory=list)


class FileUploadUrlResponse(BaseModel):
    """返回上传授权和已登记文件元数据。"""

    file_id: str
    upload_url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_at: datetime
    object_key: str
    max_bytes: int
    file: DocumentFileResponse


class FileUploadResponse(BaseModel):
    """返回代理上传完成后的文件元数据。"""

    file: DocumentFileResponse


class FileRetentionCandidateResponse(BaseModel):
    """返回一条过期 document_file 候选；仅用于计划展示，不代表会被物理删除。"""

    file_id: str
    job_id: str | None = None
    file_type: str
    storage_provider: str
    bucket: str
    object_key: str
    size_bytes: int
    status: str
    expires_at: datetime
    reason: str


class FileRetentionPlanResponse(BaseModel):
    """返回 document_files 保留期 dry-run 或 metadata 标记结果。"""

    generated_at: datetime
    retention_days: int
    deletion_supported: bool = False
    action_mode: Literal["dry_run", "mark_expired"]
    totals: dict[str, int] = Field(default_factory=dict)
    candidates: list[FileRetentionCandidateResponse] = Field(default_factory=list)
    marked_file_ids: list[str] = Field(default_factory=list)


class FileRetentionDeletePreviewRequest(BaseModel):
    """请求预览 selected expired document_files 的物理删除结果。"""

    file_ids: list[str] = Field(default_factory=list)


class FileRetentionDeleteExecuteRequest(BaseModel):
    """请求执行 selected expired document_files 的物理删除。"""

    file_ids: list[str] = Field(default_factory=list)
    reason: str
    confirmation: str


class FileRetentionDeleteItemResponse(BaseModel):
    """返回单个文件的物理删除预览或执行结果。"""

    file_id: str
    job_id: str | None = None
    file_type: str | None = None
    storage_provider: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    object_key: str | None = None
    size_bytes: int | None = None
    outcome: Literal[
        "deletable",
        "deleted",
        "already_missing",
        "skipped_not_found",
        "skipped_not_expired_status",
        "skipped_not_expired_time",
        "skipped_already_deleted",
        "skipped_unsupported_storage",
        "skipped_missing_object_key",
        "failed",
    ]
    reason: str
    deleted: bool = False
    metadata_updated: bool = False


class FileRetentionDeleteResponse(BaseModel):
    """返回 selected expired document_files 物理删除预览或执行汇总。"""

    generated_at: datetime
    action_mode: Literal["delete_preview", "delete_execute"]
    requested_file_ids: list[str] = Field(default_factory=list)
    confirmation_phrase: str
    totals: dict[str, int] = Field(default_factory=dict)
    items: list[FileRetentionDeleteItemResponse] = Field(default_factory=list)


class FileRetentionPolicyCreateRequest(BaseModel):
    """创建 draft document_files retention policy 的请求。"""

    name: str
    scope_type: Literal["global", "file_type"]
    file_type: str | None = None
    retention_days: int = Field(ge=1, le=3650)
    description: str | None = None


class FileRetentionPolicyUpdateRequest(BaseModel):
    """更新 draft document_files retention policy 的请求。"""

    name: str | None = None
    scope_type: Literal["global", "file_type"] | None = None
    file_type: str | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    description: str | None = None


class FileRetentionPolicyReasonRequest(BaseModel):
    """发布、设为默认或禁用 retention policy 的请求。"""

    reason: str


class FileRetentionPolicyImpactPreviewRequest(BaseModel):
    """请求预览 retention policy 对现有 document_files 的影响。"""

    mode: Literal["candidate_policy"] = "candidate_policy"


class EffectiveFileRetentionPolicyResponse(BaseModel):
    """返回某个 file_type 的有效 retention policy 摘要。"""

    retention_days: int
    source: Literal["published_policy", "settings_fallback"]
    policy_id: str | None = None
    scope_type: Literal["global", "file_type"] | None = None
    file_type: str | None = None
    reason: str


class FileRetentionPolicyResponse(BaseModel):
    """返回单个 document_files retention policy。"""

    policy_id: str
    name: str
    status: Literal["draft", "published", "disabled"]
    scope_type: Literal["global", "file_type"]
    file_type: str | None = None
    retention_days: int
    description: str | None = None
    is_default: bool = False
    is_effective: bool = False
    effective_reason: str | None = None
    matching_file_count: int = 0
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    published_by: str | None = None
    published_at: datetime | None = None
    disabled_by: str | None = None
    disabled_at: datetime | None = None
    reason: str | None = None


class FileRetentionPolicyListResponse(BaseModel):
    """返回 retention policies 列表和 settings fallback 摘要。"""

    generated_at: datetime
    fallback_retention_days: int
    effective: list[EffectiveFileRetentionPolicyResponse] = Field(default_factory=list)
    items: list[FileRetentionPolicyResponse] = Field(default_factory=list)


class FileRetentionPolicyImpactItemResponse(BaseModel):
    """返回单个 document_file 在候选 retention policy 下的影响。"""

    file_id: str
    job_id: str | None = None
    file_type: str
    status: str
    storage_provider: str
    current_expires_at: datetime | None = None
    projected_expires_at: datetime
    currently_expired: bool
    would_be_expired: bool
    would_change_expires_at: bool


class FileRetentionPolicyImpactResponse(BaseModel):
    """返回 retention policy impact dry-run 结果。"""

    generated_at: datetime
    policy: FileRetentionPolicyResponse
    totals: dict[str, int] = Field(default_factory=dict)
    items: list[FileRetentionPolicyImpactItemResponse] = Field(default_factory=list)


class FileStorageUsageGroupResponse(BaseModel):
    """返回一个 document_files storage usage 分组汇总。"""

    key: str
    file_count: int
    size_bytes: int
    expired_count: int
    expired_size_bytes: int
    estimated_reclaimable_count: int
    estimated_reclaimable_size_bytes: int


class FileStorageUsageResponse(BaseModel):
    """返回 document_files storage usage 和 quota readiness 只读汇总。"""

    generated_at: datetime
    artifact_storage: str
    artifact_root_writable: bool | None = None
    artifact_disk_free_bytes: int | None = None
    totals: dict[str, int] = Field(default_factory=dict)
    reclaim: dict[str, int | str] = Field(default_factory=dict)
    quota: dict[str, int | float | bool | str | None] = Field(default_factory=dict)
    by_storage_provider: list[FileStorageUsageGroupResponse] = Field(default_factory=list)
    by_file_type: list[FileStorageUsageGroupResponse] = Field(default_factory=list)
    by_status: list[FileStorageUsageGroupResponse] = Field(default_factory=list)
