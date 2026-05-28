from __future__ import annotations

# app/core/job_models.py: 定义 jobs 的核心记录模型、双层内部状态和向外兼容的 status 投影。

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

JobStatus = Literal["uploaded", "queued", "submitting", "parsing", "parsed", "converting", "completed", "failed", "canceled"]
JobLifecycleStatus = Literal["uploaded", "parsed", "completed", "failed", "canceled"]
JobExecutionStatus = Literal["idle", "queued", "submitting", "parsing", "converting"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def project_job_status(lifecycle_status: JobLifecycleStatus, execution_status: JobExecutionStatus) -> JobStatus:
    """将内部 lifecycle/execution 双层状态投影成当前对外兼容的单 status 字段。"""

    if execution_status != "idle":
        return execution_status
    return lifecycle_status


def infer_lifecycle_status_from_legacy(status: JobStatus) -> JobLifecycleStatus:
    """兼容旧记录中只有单 status 的场景。"""

    if status in {"parsed", "completed", "failed", "canceled"}:
        return status
    return "uploaded"


def infer_execution_status_from_legacy(status: JobStatus) -> JobExecutionStatus:
    """兼容旧记录中只有单 status 的场景。"""

    if status in {"queued", "submitting", "parsing", "converting"}:
        return status
    return "idle"


class SourcePdfJobContext(BaseModel):
    """收拢 source_pdf workflow 的专属上下文，避免继续平铺在 JobRecord 顶层。"""

    batch_id: str | None = None
    data_id: str | None = None
    callback_seed: str | None = None
    upstream_status: str | None = None
    result_zip_url: str | None = None


class ConversionOptions(BaseModel):
    template_id: str | None = None
    translation_mode: Literal["direct", "en2zh"] = "direct"
    document_language: Literal["auto", "zh", "en"] = "auto"
    use_mineru_header_footer: bool = False


class JobRecord(BaseModel):
    id: str
    source_filename: str
    status: JobStatus
    progress: int = 0
    source_kind: Literal["mineru_package", "source_pdf"] = "mineru_package"
    lifecycle_status: JobLifecycleStatus | None = None
    execution_status: JobExecutionStatus | None = None
    source_pdf_context: SourcePdfJobContext | None = None
    translation_mode: Literal["direct", "en2zh"] = "direct"
    document_language: Literal["auto", "zh", "en"] = "auto"
    use_mineru_header_footer: bool = False
    resolved_document_language: Literal["zh", "en"] | None = None
    template_id: str | None = None
    # 下面这些 mineru_* 字段保留为兼容投影层。
    # 新代码应优先通过 source_pdf_context 和 read_mineru_*()/build_source_pdf_context_patch() 访问。
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

    def resolved_lifecycle_status(self) -> JobLifecycleStatus:
        """返回当前 job 的内部生命周期状态，兼容旧记录。"""

        if self.lifecycle_status is not None:
            return self.lifecycle_status
        return infer_lifecycle_status_from_legacy(self.status)

    def resolved_execution_status(self) -> JobExecutionStatus:
        """返回当前 job 的内部执行状态，兼容旧记录。"""

        if self.execution_status is not None:
            return self.execution_status
        return infer_execution_status_from_legacy(self.status)

    def projected_status(self) -> JobStatus:
        """按当前双层状态重新投影出对外兼容的 status。"""

        return project_job_status(
            self.resolved_lifecycle_status(),
            self.resolved_execution_status(),
        )

    def resolved_source_pdf_context(self) -> SourcePdfJobContext:
        """返回 source_pdf 专属上下文，兼容旧记录仍使用平铺字段的场景。"""

        if self.source_pdf_context is not None:
            return self.source_pdf_context
        return SourcePdfJobContext(
            batch_id=self.mineru_batch_id,
            data_id=self.mineru_data_id,
            callback_seed=self.mineru_callback_seed,
            upstream_status=self.mineru_status,
            result_zip_url=self.mineru_result_zip_url,
        )

    def read_mineru_batch_id(self) -> str | None:
        """优先从 nested source_pdf_context 读取 batch_id，回退旧平铺字段。"""

        return self.resolved_source_pdf_context().batch_id

    def read_mineru_data_id(self) -> str | None:
        """优先从 nested source_pdf_context 读取 data_id，回退旧平铺字段。"""

        return self.resolved_source_pdf_context().data_id

    def read_mineru_callback_seed(self) -> str | None:
        """优先从 nested source_pdf_context 读取 callback_seed，回退旧平铺字段。"""

        return self.resolved_source_pdf_context().callback_seed

    def read_mineru_status(self) -> str | None:
        """优先从 nested source_pdf_context 读取上游状态，回退旧平铺字段。"""

        return self.resolved_source_pdf_context().upstream_status

    def read_mineru_result_zip_url(self) -> str | None:
        """优先从 nested source_pdf_context 读取结果 zip URL，回退旧平铺字段。"""

        return self.resolved_source_pdf_context().result_zip_url


_UNSET = object()


def build_source_pdf_context_patch(
    job: JobRecord,
    *,
    batch_id: str | None | object = _UNSET,
    data_id: str | None | object = _UNSET,
    callback_seed: str | None | object = _UNSET,
    upstream_status: str | None | object = _UNSET,
    result_zip_url: str | None | object = _UNSET,
) -> dict[str, Any]:
    """生成 source_pdf_context 与旧平铺字段同步更新的兼容 patch。"""

    context = job.resolved_source_pdf_context()
    updates: dict[str, Any] = {}
    if batch_id is not _UNSET:
        updates["batch_id"] = batch_id
    if data_id is not _UNSET:
        updates["data_id"] = data_id
    if callback_seed is not _UNSET:
        updates["callback_seed"] = callback_seed
    if upstream_status is not _UNSET:
        updates["upstream_status"] = upstream_status
    if result_zip_url is not _UNSET:
        updates["result_zip_url"] = result_zip_url
    next_context = context.model_copy(update=updates)
    return {
        "source_pdf_context": next_context,
        "mineru_batch_id": next_context.batch_id,
        "mineru_data_id": next_context.data_id,
        "mineru_callback_seed": next_context.callback_seed,
        "mineru_status": next_context.upstream_status,
        "mineru_result_zip_url": next_context.result_zip_url,
    }


def sync_source_pdf_compatibility_fields(job: JobRecord) -> JobRecord:
    """按 nested source_pdf_context 回填兼容平铺字段，供持久化边界统一调用。"""

    if job.source_kind != "source_pdf" or job.source_pdf_context is None:
        return job
    context = job.source_pdf_context
    return job.model_copy(
        update={
            "mineru_batch_id": context.batch_id,
            "mineru_data_id": context.data_id,
            "mineru_callback_seed": context.callback_seed,
            "mineru_status": context.upstream_status,
            "mineru_result_zip_url": context.result_zip_url,
        }
    )


class JobFile(BaseModel):
    file_type: Literal["source_package", "source_pdf", "parsed_result_package", "translation_request", "result_docx"]
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
    stage: Literal["convert_package", "submit_to_mineru", "process_callback", "convert_parsed_result"]
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
