from __future__ import annotations

# app/domains/files/models.py: 定义独立文件资产的元数据记录和 OSS 引用字段。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domains.jobs.models import utc_now


DocumentFileType = Literal[
    "source_pdf",
    "mineru_raw_result",
    "document_ir",
    "image_asset",
    "generated_word",
    "ai_call_log",
    "ai_debug_archive",
    "template_docx",
    "template_config",
    "term_file",
]
DocumentFileStatus = Literal["pending_upload", "uploaded", "expired", "deleted"]
DocumentFileStorageProvider = Literal["local_file", "local_object", "s3"]


class DocumentFileRecord(BaseModel):
    """独立文件资产元数据；二进制只通过 object_key 指向文件存储。"""

    id: str
    tenant_id: str
    company_id: str
    file_type: DocumentFileType
    storage_provider: DocumentFileStorageProvider
    bucket: str
    object_key: str
    original_filename: str
    mime_type: str
    size_bytes: int
    job_id: str | None = None
    checksum_sha256: str | None = None
    etag: str | None = None
    status: DocumentFileStatus = "pending_upload"
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
