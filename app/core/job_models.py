from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConversionOptions(BaseModel):
    template_id: str | None = None
    translation_mode: Literal["direct", "en2zh"] = "direct"
    document_language: Literal["auto", "zh", "en"] = "auto"
    use_mineru_header_footer: bool = False


class JobRecord(BaseModel):
    id: str
    source_filename: str
    status: Literal["uploaded", "queued", "submitting", "parsing", "parsed", "converting", "completed", "failed", "canceled"]
    progress: int = 0
    source_kind: Literal["mineru_package", "source_pdf"] = "mineru_package"
    translation_mode: Literal["direct", "en2zh"] = "direct"
    document_language: Literal["auto", "zh", "en"] = "auto"
    use_mineru_header_footer: bool = False
    resolved_document_language: Literal["zh", "en"] | None = None
    template_id: str | None = None
    mineru_batch_id: str | None = None
    mineru_data_id: str | None = None
    mineru_callback_seed: str | None = None
    mineru_status: str | None = None
    mineru_result_zip_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_ready: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobFile(BaseModel):
    file_type: Literal["source_package", "source_pdf", "translation_request", "result_docx"]
    path: str
    storage_backend: Literal["local"] = "local"
    object_key: str | None = None
    public_url: str | None = None
    download_url: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class JobEvent(BaseModel):
    stage: str
    message: str
    status: Literal["accepted", "running", "succeeded", "failed", "skipped"]
    error_code: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    created_at: datetime = Field(default_factory=utc_now)


class JobStageMessage(BaseModel):
    id: str
    job_id: str
    stage: Literal["convert_package", "submit_to_mineru", "process_callback"]
    trace_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "running", "failed"] = "pending"
    attempts: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class UploadedPackage:
    source_filename: str
    temp_path: Path
