"""文档发布、发布记录与最终件下载的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.domains.document_jobs.publication import PublicationExpectedSource
from app.domains.document_jobs.schemas.jobs import DocumentJobActionId, DocumentJobAvailableActionResponse
from app.domains.document_jobs.schemas.quality_review import QualityChecksum


class DocumentPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=36, max_length=36, description="客户端生成并保留的规范 UUID 幂等键。")
    note: str = Field(min_length=1, max_length=1000)
    expected_source: PublicationExpectedSource

    @field_validator("request_id")
    @classmethod
    def _publication_key(cls, value):
        from uuid import UUID
        try:
            parsed = str(UUID(value))
        except ValueError:
            raise ValueError("request_id 必须是 UUID。") from None
        if parsed != value:
            raise ValueError("request_id 必须使用规范 UUID 格式。")
        return parsed

    @field_validator("note")
    @classmethod
    def _publication_note(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("发布备注不能为空。")
        return value


class DocumentPublicationResourceVersionResponse(BaseModel):
    resource_id: str
    version: str
    snapshot_hash: str


class DocumentPublicationVersionsResponse(BaseModel):
    template: DocumentPublicationResourceVersionResponse
    symbol_rules: DocumentPublicationResourceVersionResponse
    renderer_implementation_sha256: str
    translation_status: Literal["complete", "not_applicable"]
    models: list[str]


class DocumentPublicationRecordResponse(BaseModel):
    publication_id: str
    job_id: str
    generation: int
    source_file_id: str
    source_sha256: str
    result_file_id: str
    result_sha256: str
    review_record_id: str
    review_sequence: int
    preview_run_id: str
    published_by: str
    published_at: datetime
    note: str
    versions: DocumentPublicationVersionsResponse


class DocumentPublishResponse(BaseModel):
    publication: DocumentPublicationRecordResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]


class DocumentPublicationPreflightCheckResponse(BaseModel):
    code: str
    status: Literal["passed", "blocked", "not_checked"]
    reason_code: str | None
    message: str


class DocumentPublicationDownloadUrlResponse(BaseModel):
    publication_id: str
    job_id: str
    result_file_id: str
    result_sha256: QualityChecksum
    size_bytes: int = Field(ge=0)
    download_url: str
    expires_at: datetime
    method: Literal["GET"] = "GET"
    classification: Literal["final_delivery"] = "final_delivery"


class DocumentPublicationsResponse(BaseModel):
    preflight_checks: list[DocumentPublicationPreflightCheckResponse]
    download_actions: dict[str, DocumentJobAvailableActionResponse]
    job_id: str
    expected_source: PublicationExpectedSource
    items: list[DocumentPublicationRecordResponse]
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]
