# File: app/domains/files/schemas.py
# Purpose: 定义文件元数据、上传授权、保留期管理和物理删除 API 的 v1 请求/响应模型。

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
