from __future__ import annotations

# app/domains/document_jobs/execution.py: 提供 document_jobs Worker 投递端口和幂等执行骨架。

import logging
import hashlib
import io
import json
import secrets
import tempfile
import time
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from app.clients.mineru_client import MinerUClient, MinerUError
from app.core.config import Settings
from app.domains.document_jobs.models import (
    DocumentJobCallbackMessage,
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobRecord,
    DocumentJobStage,
    DocumentJobTranslationBatchRecord,
)
from app.core.errors import ApiError
from app.services.document_ir.models import DocumentIR, DocumentIRAsset
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.resources.models import utc_now
from app.domains.document_jobs.repository import (
    DocumentJobCallbackMessageStoreProtocol,
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
)
from app.services.document_ir import MinerUToDocumentIRService
from app.services.renderer import DocumentIRRenderOptions, DocumentIRWordRenderer
from app.services.renderer.docx_quality import analyze_docx_quality_bytes, build_docx_quality_flags
from app.services.renderer.layout_plan import LayoutPlan, build_layout_plan
from app.domains.translation.audit import (
    TranslationAuditService,
    TranslationCallAuditRecorder,
)
from app.domains.translation.modes import is_translation_document_job_mode, spec_for_document_job_mode
from app.domains.translation.document_ir_translator import (
    DocumentIRTranslationError,
    DocumentIRTranslationService,
    DocumentIRTranslationTarget,
)
from app.domains.translation.models import TranslationProviderResult
from app.domains.translation.provider import TranslationProviderResponseError


class DocumentJobTaskQueueProtocol(Protocol):
    """document_jobs 后台任务投递端口；业务幂等性由 job_id 执行骨架保证。"""

    def enqueue(self, job_id: str, *, trace_id: str | None, run_inline: bool = True) -> str | None:
        """投递一个按 job_id 执行的后台任务，返回底层队列任务 ID。"""


class DocumentTranslationBatchTaskQueueProtocol(Protocol):
    """translation provider batch task 投递端口；批次记录负责幂等和 fan-in。"""

    def enqueue(self, batch_id: str, *, trace_id: str | None, run_inline: bool = True) -> str | None:
        """投递一个按 batch_id 执行的后台任务，返回底层队列任务 ID。"""


class DocumentJobExecutionService:
    """按 job_id 幂等推进 document_jobs 的 P0 Worker 骨架。

    任务从 queued/pending 恢复后，会按顺序执行 MinerU raw result 保存、DocumentIR
    转换、图片资产保存、IR JSON 保存、Word 渲染和结果文件登记。
    """

    def __init__(
        self,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        event_repository: DocumentJobEventRepositoryProtocol,
        callback_message_store: DocumentJobCallbackMessageStoreProtocol,
        translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_service: FileUploadService,
        document_ir_service: MinerUToDocumentIRService,
        template_read_service: Any,
        word_renderer: DocumentIRWordRenderer,
        document_ir_translation_service: DocumentIRTranslationService | None = None,
        term_version_service: Any | None = None,
        translation_audit_service: TranslationAuditService | None = None,
        translation_batch_task_queue: DocumentTranslationBatchTaskQueueProtocol | None = None,
        mineru_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.callback_message_store = callback_message_store
        self.translation_batch_repository = translation_batch_repository
        self.file_repository = file_repository
        self.file_service = file_service
        self.document_ir_service = document_ir_service
        self.template_read_service = template_read_service
        self.word_renderer = word_renderer
        self.document_ir_translation_service = document_ir_translation_service
        self.term_version_service = term_version_service
        self.translation_audit_service = translation_audit_service
        self.translation_batch_task_queue = translation_batch_task_queue
        self.mineru_client_factory = mineru_client_factory or self._build_mineru_client
        self.logger = logging.getLogger("business")

    def set_translation_batch_task_queue(
        self,
        task_queue: DocumentTranslationBatchTaskQueueProtocol | None,
    ) -> None:
        """在 runtime 组装后注入 translation batch queue，避免循环构造依赖。"""

        self.translation_batch_task_queue = task_queue

    def execute_job(self, job_id: str, *, trace_id: str | None = None) -> DocumentJobRecord | None:
        """执行一个 document_job；重复投递时不会重复推进已完成的骨架阶段。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            return None
        job = self._process_replayable_callback_messages(job, trace_id=trace_id)
        if job.status in {"succeeded", "failed", "canceled"}:
            return job
        timed_out = self._mark_timed_out_if_needed(job, trace_id=trace_id)
        if timed_out is not None:
            return timed_out
        if job.status == "running" and job.stage not in {"parsing", "parsed", "ir_converting", "rendering", "uploading"}:
            return job

        try:
            if job.status == "pending":
                job = self._mark_queued_from_worker(job, trace_id=trace_id)
            if job.status == "queued":
                job = self._mark_parsing_started(job, trace_id=trace_id)

            latest = self.job_repository.get_document_job(job_id)
            if latest is None:
                return None
            if latest.status == "running" and latest.stage == "parsing":
                latest = self._run_mineru_parse(latest, trace_id=trace_id)
            if latest.status == "running" and latest.stage == "parsed":
                latest = self._mark_ir_converting_started(latest, trace_id=trace_id)
            if latest.status == "running" and latest.stage == "ir_converting":
                latest = self._convert_and_save_document_ir(latest, trace_id=trace_id)
            if latest.status == "running" and latest.stage in {"rendering", "uploading"}:
                return self._render_and_save_word(latest, trace_id=trace_id)
            return latest
        except (ApiError, FileNotFoundError, OSError, ValueError, RuntimeError, MinerUError, zipfile.BadZipFile) as exc:
            current = self.job_repository.get_document_job(job_id) or job
            failed_stage, error_code = self._classify_worker_failure(exc, current)
            return self._mark_failed(
                current,
                failed_stage=failed_stage,
                error_code=error_code,
                error_message=str(exc),
                trace_id=trace_id,
            )
        except Exception as exc:
            current = self.job_repository.get_document_job(job_id) or job
            failed_stage = self._failed_stage_for_current_job(current)
            error_message = f"Worker 未预期异常: {type(exc).__name__}: {exc}"
            self.logger.exception(
                "[trace_id=%s job_id=%s stage=%s status=unexpected_error]",
                trace_id,
                job_id,
                failed_stage,
            )
            return self._mark_failed(
                current,
                failed_stage=failed_stage,
                error_code="document_job_unexpected_error",
                error_message=error_message,
                trace_id=trace_id,
            )

    def mark_job_timed_out(self, job_id: str, *, trace_id: str | None = None) -> DocumentJobRecord | None:
        """供 Worker 超时保护调用，保证 Celery 超时时 MySQL/file 状态也落到 failed。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None or job.status in {"succeeded", "failed", "canceled"}:
            return job
        return self._mark_timed_out(job, trace_id=trace_id)

    def _mark_queued_from_worker(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        now = utc_now()
        queued = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"pending"},
            allowed_stages={"uploaded"},
            expected_retry_count=job.retry_count,
            status="queued",
            stage="uploaded",
            progress=max(job.progress, 5),
            updated_at=now,
        )
        if queued is None:
            return self.job_repository.get_document_job(job.id) or job
        self._record_event(
            queued,
            event_type="stage_started",
            stage="uploaded",
            message="Worker 收到未标记 queued 的任务，已按 job_id 补记队列状态。",
            payload={"worker_backend": self.settings.document_jobs_worker_backend},
            trace_id=trace_id,
        )
        return queued

    def _mark_parsing_started(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        now = utc_now()
        running = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"queued"},
            allowed_stages={"uploaded"},
            expected_retry_count=job.retry_count,
            status="running",
            stage="parsing",
            progress=max(job.progress, 10),
            started_at=job.started_at or now,
            error_code=None,
            error_message=None,
            failed_stage=None,
            updated_at=now,
        )
        if running is None:
            return self.job_repository.get_document_job(job.id) or job
        self._record_event(
            running,
            event_type="stage_started",
            stage="parsing",
            message="Worker 已开始执行解析阶段骨架。",
            payload={"worker_backend": self.settings.document_jobs_worker_backend},
            trace_id=trace_id,
        )
        return running

    def _run_mineru_parse(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        if job.mineru_raw_result_file_id:
            parsed = self.job_repository.update_document_job_if_current(
                job.id,
                allowed_statuses={"running"},
                allowed_stages={"parsing"},
                expected_retry_count=job.retry_count,
                status="running",
                stage="parsed",
                progress=max(job.progress, 30),
                updated_at=utc_now(),
            )
            return parsed or self.job_repository.get_document_job(job.id) or job

        source_file = self._get_uploaded_file(job.source_file_id)
        with tempfile.TemporaryDirectory(prefix="document_job_mineru_") as temp_dir:
            source_path = Path(temp_dir) / source_file.original_filename
            source_path.write_bytes(self.file_service.read_file_content(source_file))
            client = self.mineru_client_factory()
            data_id = job.mineru_data_id or job.id
            batch_id = job.mineru_batch_id
            if not batch_id:
                callback = self.settings.mineru_callback_url or None
                callback_seed = self._build_callback_seed() if callback else None
                batch_id, _file_urls = client.upload_files_batch(
                    [source_path],
                    task_uuids=[data_id],
                    enable_formula=self.settings.mineru_enable_formula,
                    enable_table=self.settings.mineru_enable_table,
                    language=self._mineru_language_for_job(job),
                    callback=callback,
                    seed=callback_seed,
                )
                updated_job = self.job_repository.update_document_job_if_current(
                    job.id,
                    allowed_statuses={"running"},
                    allowed_stages={"parsing"},
                    expected_retry_count=job.retry_count,
                    mineru_batch_id=batch_id,
                    mineru_data_id=data_id,
                    mineru_callback_seed=callback_seed,
                    progress=max(job.progress, 15),
                    updated_at=utc_now(),
                )
                if updated_job is None:
                    return self.job_repository.get_document_job(job.id) or job
                job = updated_job
                self._record_event(
                    job,
                    event_type="stage_succeeded",
                    stage="parsing",
                    message="MinerU 任务已提交。",
                    payload={"mineru_batch_id": batch_id, "mineru_data_id": data_id},
                    trace_id=trace_id,
                )

            payload = client.query_batch_extract_results(batch_id)
            result_item = self._select_mineru_result(payload, data_id)
            state = str(result_item.get("state") or "").lower()
            full_zip_url = result_item.get("full_zip_url")
            if state not in {"done", "success", "succeeded"} or not full_zip_url:
                waiting = self.job_repository.update_document_job_if_current(
                    job.id,
                    allowed_statuses={"running"},
                    allowed_stages={"parsing"},
                    expected_retry_count=job.retry_count,
                    status="running",
                    stage="parsing",
                    progress=max(job.progress, 20),
                    updated_at=utc_now(),
                )
                if waiting is None:
                    return self.job_repository.get_document_job(job.id) or job
                self._record_event(
                    waiting,
                    event_type="stage_started",
                    stage="parsing",
                    message="MinerU 结果尚未就绪，等待后续重投递或重试。",
                    payload={"mineru_batch_id": batch_id, "mineru_state": state or "unknown"},
                    trace_id=trace_id,
                )
                return waiting

            return self._download_and_register_mineru_result(
                job,
                client=client,
                full_zip_url=str(full_zip_url),
                batch_id=str(batch_id),
                data_id=str(data_id),
                temp_dir=Path(temp_dir),
                trace_id=trace_id,
                expected_retry_count=job.retry_count,
            )

    def find_job_for_mineru_callback(self, payload: dict[str, Any]) -> DocumentJobRecord | None:
        """按 MinerU callback 里的 data_id/batch_id 匹配 document_job。"""

        data_id = str(payload.get("data_id") or "").strip()
        batch_id = str(payload.get("batch_id") or "").strip()
        jobs = self.job_repository.list_document_jobs()
        if data_id:
            for job in jobs:
                if job.mineru_data_id == data_id or job.id == data_id:
                    return job
        if batch_id:
            for job in jobs:
                if job.mineru_batch_id == batch_id:
                    return job
        return None

    def enqueue_mineru_callback_for_job(
        self,
        job: DocumentJobRecord,
        payload: dict[str, Any],
        *,
        trace_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentJobCallbackMessage, bool, bool]:
        """可信 MinerU callback 只落专用消息，并返回是否需要唤醒 Worker。"""

        normalized_payload = self._build_callback_message_payload(job, payload)
        message = DocumentJobCallbackMessage(
            id=f"doccb_{uuid4().hex[:12]}",
            job_id=job.id,
            job_retry_count=job.retry_count,
            dedupe_key=self._build_callback_dedupe_key(
                job_id=job.id,
                retry_count=job.retry_count,
                payload=normalized_payload,
            ),
            payload=normalized_payload,
            trace_id=trace_id,
        )
        stored_message, created = self.callback_message_store.put_or_get_callback_message(message)
        self._record_event(
            job,
            event_type="mineru_callback_received",
            stage=job.stage,
            message="MinerU callback 已接收并通过校验。",
            payload={
                "message_id": stored_message.id,
                "message_created": created,
                "mineru_batch_id": normalized_payload.get("batch_id"),
                "mineru_data_id": normalized_payload.get("data_id"),
                "mineru_state": normalized_payload.get("state") or "unknown",
            },
            trace_id=trace_id,
        )
        if job.status != "running" or job.stage != "parsing":
            if stored_message.status in {"pending", "running"}:
                stored_message = self.callback_message_store.mark_callback_message_ignored(
                    stored_message.id,
                    error_code="job_state_not_accepting_callback",
                    error_message=f"当前任务状态不消费 MinerU callback: status={job.status} stage={job.stage}",
                    updated_at=utc_now(),
                )
            self._record_callback_ignored_event(job, stored_message, trace_id=trace_id)
            return job, stored_message, created, False

        self._record_event(
            job,
            event_type="mineru_callback_queued",
            stage="parsing",
            message="MinerU callback 已进入 document_jobs Worker 队列。",
            payload={
                "message_id": stored_message.id,
                "message_created": created,
                "callback_status": stored_message.status,
            },
            trace_id=trace_id,
        )
        return job, stored_message, created, stored_message.status in {"pending", "running"}

    def _process_replayable_callback_messages(
        self,
        job: DocumentJobRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        latest = job
        for message in self.callback_message_store.list_replayable_callback_messages(job.id):
            refreshed = self.job_repository.get_document_job(job.id)
            if refreshed is None:
                return latest
            latest = self._process_callback_message(refreshed, message, trace_id=message.trace_id or trace_id)
        return latest

    def _process_callback_message(
        self,
        job: DocumentJobRecord,
        message: DocumentJobCallbackMessage,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        now = utc_now()
        running_message = self.callback_message_store.mark_callback_message_running(
            message.id,
            attempts=message.attempts + 1,
            lease_owner="document_jobs_worker",
            leased_at=now,
            lease_expires_at=now + timedelta(seconds=self.settings.stage_message_lease_seconds),
            updated_at=now,
        )
        if running_message is None:
            return job
        if job.status in {"succeeded", "failed", "canceled"}:
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_terminal",
                error_message=f"任务已终态，不消费 callback: status={job.status}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job
        if job.retry_count != running_message.job_retry_count:
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_retry_changed",
                error_message="任务 retry_count 已变化，旧 callback 已忽略。",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job
        if job.status != "running" or job.stage != "parsing":
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_state_not_accepting_callback",
                error_message=f"当前任务状态不消费 MinerU callback: status={job.status} stage={job.stage}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job

        payload = running_message.payload
        state = str(payload.get("state") or "").lower()
        batch_id = str(payload.get("batch_id") or job.mineru_batch_id or "").strip()
        data_id = str(payload.get("data_id") or job.mineru_data_id or job.id).strip()
        job = self._sync_callback_ids(job, batch_id=batch_id, data_id=data_id, trace_id=trace_id)
        if job.status != "running" or job.stage != "parsing":
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_state_not_accepting_callback",
                error_message=f"当前任务状态不消费 MinerU callback: status={job.status} stage={job.stage}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(job, ignored, trace_id=trace_id)
            return job
        if state == "failed":
            updated = self._mark_failed(
                job,
                failed_stage="parsing",
                error_code="mineru_failed",
                error_message="MinerU callback 返回 failed。",
                trace_id=trace_id,
            )
            self.callback_message_store.mark_callback_message_processed(running_message.id, updated_at=utc_now())
            return updated

        full_zip_url = payload.get("full_zip_url")
        if state not in {"done", "success", "succeeded"} or not full_zip_url:
            self._record_event(
                job,
                event_type="mineru_callback_processed",
                stage="parsing",
                message="MinerU callback 已消费，结果尚未就绪。",
                payload={
                    "message_id": running_message.id,
                    "mineru_batch_id": batch_id or None,
                    "mineru_state": state or "unknown",
                },
                trace_id=trace_id,
            )
            self.callback_message_store.mark_callback_message_processed(running_message.id, updated_at=utc_now())
            return job

        with tempfile.TemporaryDirectory(prefix="document_job_mineru_callback_") as temp_dir:
            parsed = self._download_and_register_mineru_result(
                job,
                client=self.mineru_client_factory(),
                full_zip_url=str(full_zip_url),
                batch_id=batch_id or str(job.mineru_batch_id or ""),
                data_id=data_id or job.id,
                temp_dir=Path(temp_dir),
                trace_id=trace_id,
                expected_retry_count=running_message.job_retry_count,
            )
        if parsed.status != "running" or parsed.stage != "parsed":
            ignored = self.callback_message_store.mark_callback_message_ignored(
                running_message.id,
                error_code="job_state_changed_before_callback_completed",
                error_message=f"callback 结果未应用，任务当前状态: status={parsed.status} stage={parsed.stage}",
                updated_at=utc_now(),
            )
            self._record_callback_ignored_event(parsed, ignored, trace_id=trace_id)
            return parsed
        self.callback_message_store.mark_callback_message_processed(running_message.id, updated_at=utc_now())
        self._record_event(
            parsed,
            event_type="mineru_callback_processed",
            stage="parsing",
            message="MinerU callback 已消费，解析结果已交给后续 Worker 阶段。",
            payload={"message_id": running_message.id, "mineru_raw_result_file_id": parsed.mineru_raw_result_file_id},
            trace_id=trace_id,
        )
        return parsed

    def _build_callback_message_payload(self, job: DocumentJobRecord, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload.get("state") or "").lower()
        batch_id = str(payload.get("batch_id") or job.mineru_batch_id or "").strip() or None
        data_id = str(payload.get("data_id") or job.mineru_data_id or job.id).strip() or None
        full_zip_url = payload.get("full_zip_url")
        content = payload.get("content")
        content_hash = None
        if isinstance(content, str) and content.strip():
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "batch_id": batch_id,
            "data_id": data_id,
            "state": state or None,
            "full_zip_url": str(full_zip_url) if full_zip_url is not None else None,
            "content_hash": content_hash,
        }

    def _build_callback_dedupe_key(self, *, job_id: str, retry_count: int, payload: dict[str, Any]) -> str:
        stable_payload = {
            "job_id": job_id,
            "retry_count": retry_count,
            "batch_id": payload.get("batch_id"),
            "data_id": payload.get("data_id"),
            "state": payload.get("state"),
            "full_zip_url": payload.get("full_zip_url"),
            "content_hash": payload.get("content_hash"),
        }
        encoded = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _sync_callback_ids(
        self,
        job: DocumentJobRecord,
        *,
        batch_id: str,
        data_id: str,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        patch: dict[str, Any] = {}
        if batch_id and batch_id != (job.mineru_batch_id or ""):
            patch["mineru_batch_id"] = batch_id
        if data_id and data_id != (job.mineru_data_id or ""):
            patch["mineru_data_id"] = data_id
        if not patch:
            return job
        updated = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"parsing"},
            expected_retry_count=job.retry_count,
            **patch,
            updated_at=utc_now(),
        )
        if updated is None:
            latest = self.job_repository.get_document_job(job.id)
            if latest is not None:
                self._record_event(
                    latest,
                    event_type="mineru_callback_ignored",
                    stage=latest.stage,
                    message="MinerU callback 关联信息写入被跳过，任务状态已变化。",
                    payload={"previous_stage": job.stage, "previous_status": job.status},
                    trace_id=trace_id,
                    level="warning",
                )
                return latest
            return job
        return updated

    def _record_callback_ignored_event(
        self,
        job: DocumentJobRecord,
        message: DocumentJobCallbackMessage,
        *,
        trace_id: str | None,
    ) -> None:
        self._record_event(
            job,
            event_type="mineru_callback_ignored",
            stage=job.stage,
            message="MinerU callback 已忽略。",
            payload={
                "message_id": message.id,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "callback_status": message.status,
            },
            trace_id=trace_id,
            level="warning",
        )

    def _download_and_register_mineru_result(
        self,
        job: DocumentJobRecord,
        *,
        client: Any,
        full_zip_url: str,
        batch_id: str,
        data_id: str,
        temp_dir: Path,
        trace_id: str | None,
        expected_retry_count: int | None = None,
    ) -> DocumentJobRecord:
        """下载 MinerU 原始结果包，登记为 document_file 并把任务推进到 parsed。"""

        latest = self.job_repository.get_document_job(job.id)
        if latest is None:
            return job
        if latest.status in {"succeeded", "failed", "canceled"}:
            return latest
        if latest.mineru_raw_result_file_id:
            updated = self.job_repository.update_document_job_if_current(
                latest.id,
                allowed_statuses={"running"},
                allowed_stages={"parsing"},
                expected_retry_count=expected_retry_count,
                status="running",
                stage="parsed",
                progress=max(latest.progress, 30),
                updated_at=utc_now(),
            )
            return updated or self.job_repository.get_document_job(job.id) or latest
        if latest.status != "running" or latest.stage != "parsing":
            return latest

        raw_zip_path = temp_dir / "mineru_raw_result.zip"
        client.download_result_zip(full_zip_url, raw_zip_path)
        raw_file = self.file_service.register_generated_content(
            tenant_id=latest.tenant_id,
            company_id=latest.company_id,
            job_id=latest.id,
            created_by=latest.created_by,
            file_type="mineru_raw_result",
            filename="mineru_raw_result.zip",
            mime_type="application/zip",
            content=raw_zip_path.read_bytes(),
            metadata={
                "source_file_id": latest.source_file_id,
                "mineru_batch_id": batch_id,
                "mineru_data_id": data_id,
                "full_zip_url": full_zip_url,
                "retry_count": latest.retry_count,
            },
        )
        parsed = self.job_repository.update_document_job_if_current(
            latest.id,
            allowed_statuses={"running"},
            allowed_stages={"parsing"},
            expected_retry_count=expected_retry_count,
            status="running",
            stage="parsed",
            progress=max(latest.progress, 30),
            mineru_raw_result_file_id=raw_file.id,
            updated_at=utc_now(),
        )
        if parsed is None:
            return self.job_repository.get_document_job(latest.id) or latest
        self._record_event(
            parsed,
            event_type="file_registered",
            stage="parsing",
            message="MinerU 原始结果已保存。",
            payload={"file_id": raw_file.id, "file_type": raw_file.file_type, "object_key": raw_file.object_key},
            trace_id=trace_id,
        )
        self._record_event(
            parsed,
            event_type="stage_succeeded",
            stage="parsing",
            message="解析阶段已完成。",
            payload={"mineru_raw_result_file_id": raw_file.id},
            trace_id=trace_id,
        )
        self.logger.info(
            "[trace_id=%s job_id=%s stage=parsing status=parsed] mineru_raw_result_file_id=%s",
            trace_id,
            latest.id,
            raw_file.id,
        )
        return parsed

    def _mark_ir_converting_started(
        self,
        job: DocumentJobRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        now = utc_now()
        converting = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"parsed"},
            expected_retry_count=job.retry_count,
            status="running",
            stage="ir_converting",
            progress=max(job.progress, 40),
            updated_at=now,
        )
        if converting is None:
            return self.job_repository.get_document_job(job.id) or job
        self._record_event(
            converting,
            event_type="stage_started",
            stage="ir_converting",
            message="DocumentIR 转换已开始。",
            payload={"mineru_raw_result_file_id": job.mineru_raw_result_file_id},
            trace_id=trace_id,
        )
        return converting

    def _convert_and_save_document_ir(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        if job.document_ir_file_id:
            rendering = self.job_repository.update_document_job_if_current(
                job.id,
                allowed_statuses={"running"},
                allowed_stages={"ir_converting"},
                expected_retry_count=job.retry_count,
                status="running",
                stage="rendering",
                progress=max(job.progress, 60),
                updated_at=utc_now(),
            )
            return rendering or self.job_repository.get_document_job(job.id) or job
        if is_translation_document_job_mode(job.mode) and job.source_document_ir_file_id:
            source_file = self._get_uploaded_file(job.source_document_ir_file_id)
            source_document_ir = DocumentIR.model_validate_json(self.file_service.read_file_content(source_file))
            return self._ensure_translation_batches_and_enqueue(job, source_document_ir, trace_id=trace_id)

        raw_file = self._get_mineru_raw_result_file(job)
        with tempfile.TemporaryDirectory(prefix="document_job_ir_") as temp_dir:
            raw_zip_path = Path(temp_dir) / raw_file.original_filename
            raw_zip_path.write_bytes(self.file_service.read_file_content(raw_file))
            result = self.document_ir_service.convert_zip(
                raw_zip_path,
                job_id=job.id,
                source_file_id=job.source_file_id,
                document_language=job.document_language,
            )

        image_file_ids: list[str] = []
        for image_asset in result.image_assets:
            image_file = self.file_service.register_generated_content(
                tenant_id=job.tenant_id,
                company_id=job.company_id,
                job_id=job.id,
                created_by=job.created_by,
                file_type="image_asset",
                filename=f"{image_asset.asset_id}_{Path(image_asset.source_path).name}",
                mime_type=image_asset.mime_type,
                content=image_asset.content,
                metadata={
                    "source_file_id": job.source_file_id,
                    "mineru_raw_result_file_id": raw_file.id,
                    "source_path": image_asset.source_path,
                    "asset_id": image_asset.asset_id,
                    "block_id": image_asset.block_id,
                    "retry_count": job.retry_count,
                },
            )
            image_file_ids.append(image_file.id)
            for ir_asset in result.document.assets:
                if ir_asset.id == image_asset.asset_id:
                    ir_asset.file_id = image_file.id
                    ir_asset.object_key = image_file.object_key
                    ir_asset.mime_type = image_file.mime_type
                    ir_asset.checksum_sha256 = image_file.checksum_sha256
                    break
        image_archive_file = self._register_image_assets_archive(
            job,
            raw_file=raw_file,
            image_assets=result.image_assets,
            image_file_ids=image_file_ids,
        )

        document_ir = result.document
        if is_translation_document_job_mode(job.mode):
            return self._register_source_ir_and_enqueue_translation(
                job,
                raw_file=raw_file,
                document_ir=document_ir,
                image_file_ids=image_file_ids,
                image_archive_file=image_archive_file,
                trace_id=trace_id,
            )

        translation_metadata: dict[str, Any] = {"applied": False}
        ir_content = document_ir.model_dump_json(indent=2).encode("utf-8")
        ir_layout_metadata = self._document_ir_layout_metadata(document_ir)
        ir_file = self.file_service.register_generated_content(
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            file_type="document_ir",
            filename="document_ir_v2.json",
            mime_type="application/json",
            content=ir_content,
            metadata={
                "source_file_id": job.source_file_id,
                "mineru_raw_result_file_id": raw_file.id,
                "image_asset_count": len(image_file_ids),
                "image_assets_archive_file_id": image_archive_file.id if image_archive_file is not None else None,
                "retry_count": job.retry_count,
                "translation": translation_metadata,
                **ir_layout_metadata,
            },
        )
        updated = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"ir_converting"},
            expected_retry_count=job.retry_count,
            status="running",
            stage="rendering",
            progress=max(job.progress, 60),
            document_ir_file_id=ir_file.id,
            image_asset_file_ids=image_file_ids,
            updated_at=utc_now(),
        )
        if updated is None:
            return self.job_repository.get_document_job(job.id) or job
        if image_file_ids:
            self._record_event(
                updated,
                event_type="file_registered",
                stage="ir_converting",
                message="DocumentIR 图片资产已保存。",
                payload={
                    "file_ids": image_file_ids,
                    "file_type": "image_asset",
                    "image_assets_archive_file_id": image_archive_file.id if image_archive_file is not None else None,
                },
                trace_id=trace_id,
            )
        if image_archive_file is not None:
            self._record_event(
                updated,
                event_type="file_registered",
                stage="ir_converting",
                message="DocumentIR 图片资源包已保存。",
                payload={
                    "file_id": image_archive_file.id,
                    "file_type": image_archive_file.file_type,
                    "image_asset_count": len(image_file_ids),
                },
                trace_id=trace_id,
            )
        self._record_event(
            updated,
            event_type="file_registered",
            stage="ir_converting",
            message="DocumentIR 已保存。",
            payload={
                "file_id": ir_file.id,
                "file_type": ir_file.file_type,
                "object_key": ir_file.object_key,
                **ir_layout_metadata,
            },
            trace_id=trace_id,
        )
        self._record_event(
            updated,
            event_type="stage_succeeded",
            stage="ir_converting",
            message="DocumentIR 转换已完成，等待 Word 渲染。",
            payload={
                "document_ir_file_id": ir_file.id,
                "image_asset_file_ids": image_file_ids,
                "image_assets_archive_file_id": image_archive_file.id if image_archive_file is not None else None,
                **ir_layout_metadata,
            },
            trace_id=trace_id,
        )
        self.logger.info(
            "[trace_id=%s job_id=%s stage=ir_converting status=rendering] document_ir_file_id=%s image_assets=%s",
            trace_id,
            job.id,
            ir_file.id,
            len(image_file_ids),
        )
        return updated

    def _register_source_ir_and_enqueue_translation(
        self,
        job: DocumentJobRecord,
        *,
        raw_file: DocumentFileRecord,
        document_ir: DocumentIR,
        image_file_ids: list[str],
        image_archive_file: DocumentFileRecord | None,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """保存翻译 source IR，并把后续 provider 调用切换到批次任务。"""

        source_ir_file = self.file_service.register_generated_content(
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            file_type="document_ir",
            filename="document_ir_source_v2.json",
            mime_type="application/json",
            content=document_ir.model_dump_json(indent=2).encode("utf-8"),
            metadata={
                "source_file_id": job.source_file_id,
                "mineru_raw_result_file_id": raw_file.id,
                "image_asset_count": len(image_file_ids),
                "image_assets_archive_file_id": image_archive_file.id if image_archive_file is not None else None,
                "retry_count": job.retry_count,
                "translation": {"applied": False, "role": "source"},
                **self._document_ir_layout_metadata(document_ir),
            },
        )
        updated = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"ir_converting"},
            expected_retry_count=job.retry_count,
            status="running",
            stage="ir_converting",
            progress=max(job.progress, 45),
            source_document_ir_file_id=source_ir_file.id,
            image_asset_file_ids=image_file_ids,
            updated_at=utc_now(),
        )
        if updated is None:
            return self.job_repository.get_document_job(job.id) or job
        self._record_source_ir_events(
            updated,
            source_ir_file=source_ir_file,
            image_file_ids=image_file_ids,
            image_archive_file=image_archive_file,
            document_ir=document_ir,
            trace_id=trace_id,
        )
        return self._ensure_translation_batches_and_enqueue(updated, document_ir, trace_id=trace_id)

    def _record_source_ir_events(
        self,
        job: DocumentJobRecord,
        *,
        source_ir_file: DocumentFileRecord,
        image_file_ids: list[str],
        image_archive_file: DocumentFileRecord | None,
        document_ir: DocumentIR,
        trace_id: str | None,
    ) -> None:
        if image_file_ids:
            self._record_event(
                job,
                event_type="file_registered",
                stage="ir_converting",
                message="DocumentIR 图片资产已保存。",
                payload={
                    "file_ids": image_file_ids,
                    "file_type": "image_asset",
                    "image_assets_archive_file_id": image_archive_file.id if image_archive_file is not None else None,
                },
                trace_id=trace_id,
            )
        if image_archive_file is not None:
            self._record_event(
                job,
                event_type="file_registered",
                stage="ir_converting",
                message="DocumentIR 图片资源包已保存。",
                payload={
                    "file_id": image_archive_file.id,
                    "file_type": image_archive_file.file_type,
                    "image_asset_count": len(image_file_ids),
                },
                trace_id=trace_id,
            )
        self._record_event(
            job,
            event_type="file_registered",
            stage="ir_converting",
            message="DocumentIR source 已保存，等待翻译批次完成。",
            payload={
                "file_id": source_ir_file.id,
                "file_type": source_ir_file.file_type,
                "object_key": source_ir_file.object_key,
                **self._document_ir_layout_metadata(document_ir),
            },
            trace_id=trace_id,
        )

    def _ensure_translation_batches_and_enqueue(
        self,
        job: DocumentJobRecord,
        source_document_ir: DocumentIR,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        if self.document_ir_translation_service is None:
            raise DocumentIRTranslationError("DocumentIR 翻译服务未配置。")
        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            raise DocumentIRTranslationError("当前任务不是翻译任务。")
        if not job.source_document_ir_file_id:
            raise DocumentIRTranslationError("翻译任务缺少 source DocumentIR 文件。")

        generation = job.retry_count
        batches = self.translation_batch_repository.list_translation_batches(job.id, generation=generation)
        if not batches:
            batches = self._create_initial_translation_batches(
                job,
                source_document_ir,
                language_pair=spec.language_pair,
                generation=generation,
                trace_id=trace_id,
            )
        if not batches:
            return self._register_translated_document_ir_and_continue(
                job,
                source_document_ir,
                succeeded_batches=[],
                trace_id=trace_id,
            )
        self._reset_expired_translation_batch_leases(job, generation=generation, trace_id=trace_id)
        self._enqueue_runnable_translation_batches(job, generation=generation, trace_id=trace_id)
        refreshed = self.job_repository.get_document_job(job.id) or job
        return refreshed

    def _create_initial_translation_batches(
        self,
        job: DocumentJobRecord,
        source_document_ir: DocumentIR,
        *,
        language_pair: str,
        generation: int,
        trace_id: str | None,
    ) -> list[DocumentJobTranslationBatchRecord]:
        max_pages, max_chars = self._translation_profile_batch_limits(job)
        term_version = self._resolve_term_version_for_job(job)
        _targets, _items, plans = self.document_ir_translation_service.build_translation_plan(
            source_document_ir,
            max_pages_per_batch=max_pages,
            max_chars_per_batch=max_chars,
            batch_id_prefix=f"{job.id}_retry{generation}_translation_batch",
        )
        deterministic_count = len(plans)
        provider_call_budget = min(200, deterministic_count * 12)
        now = utc_now()
        records: list[DocumentJobTranslationBatchRecord] = []
        for plan in plans:
            record = DocumentJobTranslationBatchRecord(
                id=plan.batch_id,
                job_id=job.id,
                job_retry_count=job.retry_count,
                generation=generation,
                root_batch_id=plan.batch_id,
                parent_batch_id=plan.parent_batch_id,
                status="pending",
                page_start=plan.page_start,
                page_end=plan.page_end,
                item_ids=list(plan.item_ids),
                item_count=plan.item_count,
                char_count=plan.char_count,
                split_level=plan.split_level,
                max_attempts=max(1, self.settings.translation_provider_batch_max_attempts),
                deterministic_batch_count=deterministic_count,
                provider_call_budget=provider_call_budget,
                source_document_ir_file_id=job.source_document_ir_file_id,
                language_pair=language_pair,
                term_version_id=term_version.term_version_id if term_version is not None else job.term_version_id,
                term_snapshot_hash=term_version.snapshot_hash if term_version is not None else None,
                created_at=now,
                updated_at=now,
            )
            records.append(self.translation_batch_repository.create_translation_batch(record))
        self._record_event(
            job,
            event_type="stage_started",
            stage="ir_converting",
            message="DocumentIR 翻译批次已创建。",
            payload={
                "generation": generation,
                "batch_count": len(records),
                "max_pages_per_batch": max_pages,
                "max_chars_per_batch": max_chars,
                "language_pair": language_pair,
            },
            trace_id=trace_id,
        )
        return records

    def execute_translation_batch(self, batch_id: str, *, trace_id: str | None = None) -> DocumentJobTranslationBatchRecord | None:
        """执行单个 provider batch task；重复投递依赖 batch 状态幂等收敛。"""

        batch = self.translation_batch_repository.get_translation_batch(batch_id)
        if batch is None:
            return None
        job = self.job_repository.get_document_job(batch.job_id)
        if job is None:
            return batch
        if job.status == "canceled":
            return self._cancel_translation_batch(batch, trace_id=trace_id)
        if job.status in {"succeeded", "failed"} or job.retry_count != batch.job_retry_count:
            return batch
        if job.status != "running" or job.stage != "ir_converting":
            return batch
        claimed = self._claim_translation_batch(batch, trace_id=trace_id)
        if claimed is None:
            return self.translation_batch_repository.get_translation_batch(batch.id)

        request = None
        result: TranslationProviderResult | None = None
        recorder: TranslationCallAuditRecorder | None = None
        started_at = time.perf_counter()
        try:
            source_file = self._get_uploaded_file(claimed.source_document_ir_file_id)
            source_document_ir = DocumentIR.model_validate_json(self.file_service.read_file_content(source_file))
            _targets, items = self.document_ir_translation_service.extract_translation_items(source_document_ir)
            items_by_id = {item.id: item for item in items}
            batch_items = [items_by_id[item_id] for item_id in claimed.item_ids]
            term_version = self._resolve_term_version_for_job(job)
            recorder = (
                self.translation_audit_service.build_recorder(
                    job=job,
                    term_version=term_version,
                    trace_id=trace_id,
                    save_full_text=job.debug_full_text_enabled,
                )
                if self.translation_audit_service is not None
                else None
            )
            request = self.document_ir_translation_service.build_provider_request(
                source_document_ir,
                batch_items,
                term_version=term_version,
                language_pair=claimed.language_pair,
                batch_id=claimed.id,
                attempt=claimed.attempt_count,
                split_level=claimed.split_level,
                parent_batch_id=claimed.parent_batch_id,
                page_start=claimed.page_start,
                page_end=claimed.page_end,
            )
            result = self.document_ir_translation_service.provider.translate(request)
            replacements = self.document_ir_translation_service.validate_result(batch_items, result)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if recorder is not None:
                recorder.record_success(request, result, duration_ms=duration_ms)
                self._record_translation_audit_events(job, recorder, trace_id=trace_id)
            result_file = self._register_translation_batch_result(
                job,
                batch=claimed,
                result=result,
                replacements=replacements,
                recorder=recorder,
            )
            succeeded = self.translation_batch_repository.update_translation_batch_if_current(
                claimed.id,
                allowed_statuses={"running"},
                expected_generation=claimed.generation,
                status="succeeded",
                result_file_id=result_file.id,
                ai_call_log_file_ids=self._recorder_call_log_file_ids(recorder),
                debug_archive_file_ids=self._recorder_debug_archive_file_ids(recorder),
                finish_reason=result.finish_reason,
                usage=result.usage,
                response_id=result.response_id,
                error_code=None,
                error_message=None,
                retryable=False,
                lease_owner=None,
                leased_at=None,
                lease_expires_at=None,
                updated_at=utc_now(),
            )
            if succeeded is None:
                return self.translation_batch_repository.get_translation_batch(claimed.id)
            self._record_event(
                job,
                event_type="translation_batch_succeeded",
                stage="ir_converting",
                message="翻译批次已完成。",
                payload={
                    "batch_id": succeeded.id,
                    "generation": succeeded.generation,
                    "attempt_count": succeeded.attempt_count,
                    "item_count": succeeded.item_count,
                    "result_file_id": result_file.id,
                    "finish_reason": succeeded.finish_reason,
                },
                trace_id=trace_id,
            )
            self._finalize_translation_generation(job.id, generation=succeeded.generation, trace_id=trace_id)
            return succeeded
        except (KeyError, ValueError, RuntimeError, FileNotFoundError, OSError) as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if recorder is not None and request is not None:
                recorder.record_failure(request, result, error=exc, duration_ms=duration_ms)
                self._record_translation_audit_events(job, recorder, trace_id=trace_id)
            return self._handle_translation_batch_failure(
                claimed,
                job,
                error=exc,
                recorder=recorder,
                trace_id=trace_id,
            )

    def _claim_translation_batch(
        self,
        batch: DocumentJobTranslationBatchRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord | None:
        now = utc_now()
        claimed = self.translation_batch_repository.update_translation_batch_if_current(
            batch.id,
            allowed_statuses={"pending", "queued", "failed"},
            expected_generation=batch.generation,
            status="running",
            attempt_count=batch.attempt_count + 1,
            lease_owner="translation_batch_worker",
            leased_at=now,
            lease_expires_at=now + timedelta(seconds=self.settings.translation_provider_batch_lease_seconds),
            error_code=None,
            error_message=None,
            retryable=False,
            updated_at=now,
        )
        if claimed is None:
            return None
        job = self.job_repository.get_document_job(batch.job_id)
        if job is not None:
            self._record_event(
                job,
                event_type="translation_batch_running",
                stage="ir_converting",
                message="翻译批次已开始执行。",
                payload={
                    "batch_id": claimed.id,
                    "generation": claimed.generation,
                    "attempt_count": claimed.attempt_count,
                    "page_start": claimed.page_start,
                    "page_end": claimed.page_end,
                    "item_count": claimed.item_count,
                },
                trace_id=trace_id,
            )
        return claimed

    def _handle_translation_batch_failure(
        self,
        batch: DocumentJobTranslationBatchRecord,
        job: DocumentJobRecord,
        *,
        error: Exception,
        recorder: TranslationCallAuditRecorder | None,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        error_code = self._translation_batch_error_code(error)
        error_message = str(error)
        if self._should_split_translation_batch(batch, error):
            split = self._split_translation_batch(
                batch,
                job,
                error_code=error_code,
                error_message=error_message,
                error=error,
                recorder=recorder,
                trace_id=trace_id,
            )
            self._enqueue_runnable_translation_batches(job, generation=batch.generation, trace_id=trace_id)
            return split

        retryable = (
            batch.attempt_count < batch.max_attempts
            and self._provider_call_budget_remaining(job, batch)
        )
        failed = self.translation_batch_repository.update_translation_batch_if_current(
            batch.id,
            allowed_statuses={"running"},
            expected_generation=batch.generation,
            status="failed",
            ai_call_log_file_ids=self._recorder_call_log_file_ids(recorder),
            debug_archive_file_ids=self._recorder_debug_archive_file_ids(recorder),
            finish_reason=error.finish_reason if isinstance(error, TranslationProviderResponseError) else None,
            usage=error.usage if isinstance(error, TranslationProviderResponseError) else {},
            response_id=error.response_id if isinstance(error, TranslationProviderResponseError) else None,
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=utc_now(),
        )
        if failed is None:
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        self._record_event(
            job,
            event_type="translation_batch_failed",
            stage="ir_converting",
            message="翻译批次执行失败。",
            payload={
                "batch_id": failed.id,
                "generation": failed.generation,
                "attempt_count": failed.attempt_count,
                "max_attempts": failed.max_attempts,
                "retryable": failed.retryable,
                "error_code": failed.error_code,
                "error_message": failed.error_message,
                "ai_call_log_file_ids": failed.ai_call_log_file_ids,
                "debug_archive_file_ids": failed.debug_archive_file_ids,
            },
            trace_id=trace_id,
            level="warning" if failed.retryable else "error",
        )
        self._finalize_translation_generation(job.id, generation=failed.generation, trace_id=trace_id)
        return failed

    def _should_split_translation_batch(self, batch: DocumentJobTranslationBatchRecord, error: Exception) -> bool:
        return (
            isinstance(error, TranslationProviderResponseError)
            and error.suspected_truncation
            and len(batch.item_ids) > 1
            and self._provider_call_budget_remaining_for_batch(batch)
        )

    def _split_translation_batch(
        self,
        batch: DocumentJobTranslationBatchRecord,
        job: DocumentJobRecord,
        *,
        error_code: str,
        error_message: str,
        error: Exception,
        recorder: TranslationCallAuditRecorder | None,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        source_file = self._get_uploaded_file(batch.source_document_ir_file_id)
        source_document_ir = DocumentIR.model_validate_json(self.file_service.read_file_content(source_file))
        targets, items = self.document_ir_translation_service.extract_translation_items(source_document_ir)
        targets_by_id = {target.item_id: target for target in targets}
        items_by_id = {item.id: item for item in items}
        midpoint = max(1, len(batch.item_ids) // 2)
        child_item_groups = [batch.item_ids[:midpoint], batch.item_ids[midpoint:]]
        now = utc_now()
        split = self.translation_batch_repository.update_translation_batch_if_current(
            batch.id,
            allowed_statuses={"running"},
            expected_generation=batch.generation,
            status="split",
            ai_call_log_file_ids=self._recorder_call_log_file_ids(recorder),
            debug_archive_file_ids=self._recorder_debug_archive_file_ids(recorder),
            finish_reason=error.finish_reason if isinstance(error, TranslationProviderResponseError) else None,
            usage=error.usage if isinstance(error, TranslationProviderResponseError) else {},
            response_id=error.response_id if isinstance(error, TranslationProviderResponseError) else None,
            error_code=error_code,
            error_message=error_message,
            retryable=False,
            truncation_retry=True,
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=now,
        )
        if split is None:
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        for child_index, child_item_ids in enumerate(child_item_groups, start=1):
            if not child_item_ids:
                continue
            child_id = f"{batch.id}_s{batch.split_level + 1}_{child_index:02d}"
            if self.translation_batch_repository.get_translation_batch(child_id) is not None:
                continue
            page_start, page_end = self._page_range_for_item_ids(child_item_ids, targets_by_id)
            char_count = sum(len(items_by_id[item_id].text) for item_id in child_item_ids)
            self.translation_batch_repository.create_translation_batch(
                DocumentJobTranslationBatchRecord(
                    id=child_id,
                    job_id=batch.job_id,
                    job_retry_count=batch.job_retry_count,
                    generation=batch.generation,
                    root_batch_id=batch.root_batch_id,
                    parent_batch_id=batch.id,
                    status="pending",
                    page_start=page_start,
                    page_end=page_end,
                    item_ids=list(child_item_ids),
                    item_count=len(child_item_ids),
                    char_count=char_count,
                    split_level=batch.split_level + 1,
                    max_attempts=batch.max_attempts,
                    deterministic_batch_count=batch.deterministic_batch_count,
                    provider_call_budget=batch.provider_call_budget,
                    source_document_ir_file_id=batch.source_document_ir_file_id,
                    language_pair=batch.language_pair,
                    term_version_id=batch.term_version_id,
                    term_snapshot_hash=batch.term_snapshot_hash,
                    truncation_retry=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        self._record_event(
            job,
            event_type="translation_batch_split",
            stage="ir_converting",
            message="翻译批次疑似截断，已拆分为子批次重试。",
            payload={
                "batch_id": split.id,
                "generation": split.generation,
                "split_level": split.split_level,
                "child_count": sum(1 for item_ids in child_item_groups if item_ids),
                "error_code": error_code,
                "error_message": error_message,
            },
            trace_id=trace_id,
            level="warning",
        )
        return split

    def _finalize_translation_generation(
        self,
        job_id: str,
        *,
        generation: int,
        trace_id: str | None,
    ) -> DocumentJobRecord | None:
        job = self.job_repository.get_document_job(job_id)
        if job is None or job.status in {"succeeded", "failed", "canceled"}:
            return job
        if job.status != "running" or job.stage != "ir_converting":
            return job
        self._reset_expired_translation_batch_leases(job, generation=generation, trace_id=trace_id)
        batches = self.translation_batch_repository.list_translation_batches(job.id, generation=generation)
        leaf_batches = [batch for batch in batches if batch.status != "split"]
        if not leaf_batches:
            return job
        if any(batch.status in {"pending", "queued", "running"} for batch in leaf_batches):
            self._enqueue_runnable_translation_batches(job, generation=generation, trace_id=trace_id)
            return self.job_repository.get_document_job(job.id) or job
        retryable_failures = [
            batch
            for batch in leaf_batches
            if batch.status == "failed"
            and batch.retryable
            and batch.attempt_count < batch.max_attempts
            and self._provider_call_budget_remaining(job, batch)
        ]
        if retryable_failures:
            self._enqueue_runnable_translation_batches(job, generation=generation, trace_id=trace_id)
            return self.job_repository.get_document_job(job.id) or job
        failed_batches = [batch for batch in leaf_batches if batch.status == "failed"]
        if failed_batches:
            first_failure = sorted(failed_batches, key=lambda item: (item.updated_at, item.id))[0]
            return self._mark_failed(
                job,
                failed_stage="ir_converting",
                error_code="translation_failed",
                error_message=f"翻译批次失败: {first_failure.error_code or 'unknown'} {first_failure.error_message or ''}".strip(),
                trace_id=trace_id,
            )
        if all(batch.status == "succeeded" for batch in leaf_batches):
            source_file = self._get_uploaded_file(job.source_document_ir_file_id or leaf_batches[0].source_document_ir_file_id)
            source_document_ir = DocumentIR.model_validate_json(self.file_service.read_file_content(source_file))
            return self._register_translated_document_ir_and_continue(
                job,
                source_document_ir,
                succeeded_batches=leaf_batches,
                trace_id=trace_id,
            )
        return job

    def _register_translated_document_ir_and_continue(
        self,
        job: DocumentJobRecord,
        source_document_ir: DocumentIR,
        *,
        succeeded_batches: list[DocumentJobTranslationBatchRecord],
        trace_id: str | None,
    ) -> DocumentJobRecord:
        translated = source_document_ir.model_copy(deep=True)
        targets, items = self.document_ir_translation_service.extract_translation_items(translated)
        expected_ids = [item.id for item in items]
        replacements = self._load_batch_replacements(succeeded_batches)
        missing_ids = [item_id for item_id in expected_ids if item_id not in replacements]
        extra_ids = sorted(set(replacements) - set(expected_ids))
        if missing_ids or extra_ids:
            return self._mark_failed(
                job,
                failed_stage="ir_converting",
                error_code="translation_fan_in_mismatch",
                error_message=f"翻译批次合并结果不完整: missing={len(missing_ids)} extra={len(extra_ids)}",
                trace_id=trace_id,
            )
        self.document_ir_translation_service.apply_replacements(translated, targets, replacements)
        spec = spec_for_document_job_mode(job.mode)
        translated.metadata.document_language = (
            self.document_ir_translation_service._target_document_language(spec.language_pair or "en2zh")
        )
        ai_call_log_file_ids = [
            file_id
            for batch in succeeded_batches
            for file_id in batch.ai_call_log_file_ids
        ]
        debug_archive_file_ids = [
            file_id
            for batch in succeeded_batches
            for file_id in batch.debug_archive_file_ids
        ]
        translation_metadata = {
            "applied": True,
            "role": "translated",
            "language_pair": spec.language_pair,
            "source_document_ir_file_id": job.source_document_ir_file_id,
            "batch_count": len(succeeded_batches),
            "batch_ids": [batch.id for batch in succeeded_batches],
            "term_version_id": succeeded_batches[0].term_version_id if succeeded_batches else job.term_version_id,
            "term_snapshot_hash": succeeded_batches[0].term_snapshot_hash if succeeded_batches else None,
            "ai_call_log_file_ids": ai_call_log_file_ids,
            "debug_archive_file_ids": debug_archive_file_ids,
        }
        ir_file = self.file_service.register_generated_content(
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            file_type="document_ir",
            filename="document_ir_v2.json",
            mime_type="application/json",
            content=translated.model_dump_json(indent=2).encode("utf-8"),
            metadata={
                "source_file_id": job.source_file_id,
                "source_document_ir_file_id": job.source_document_ir_file_id,
                "image_asset_count": len(job.image_asset_file_ids),
                "retry_count": job.retry_count,
                "translation": translation_metadata,
                **self._document_ir_layout_metadata(translated),
            },
        )
        updated = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"ir_converting"},
            expected_retry_count=job.retry_count,
            status="running",
            stage="rendering",
            progress=max(job.progress, 60),
            document_ir_file_id=ir_file.id,
            updated_at=utc_now(),
        )
        if updated is None:
            return self.job_repository.get_document_job(job.id) or job
        self._record_event(
            updated,
            event_type="file_registered",
            stage="ir_converting",
            message="翻译后的 DocumentIR 已保存。",
            payload={
                "file_id": ir_file.id,
                "file_type": ir_file.file_type,
                "object_key": ir_file.object_key,
                **self._document_ir_layout_metadata(translated),
            },
            trace_id=trace_id,
        )
        self._record_event(
            updated,
            event_type="stage_succeeded",
            stage="ir_converting",
            message="DocumentIR 翻译批次已全部完成，fan-in 合并成功。",
            payload={
                "document_ir_file_id": ir_file.id,
                "source_document_ir_file_id": job.source_document_ir_file_id,
                "batch_count": len(succeeded_batches),
                "ai_call_log_file_ids": ai_call_log_file_ids,
                "debug_archive_file_ids": debug_archive_file_ids,
            },
            trace_id=trace_id,
        )
        return self._render_and_save_word(updated, trace_id=trace_id)

    def _load_batch_replacements(self, batches: list[DocumentJobTranslationBatchRecord]) -> dict[str, str]:
        replacements: dict[str, str] = {}
        for batch in sorted(batches, key=lambda item: (item.page_start or 0, item.created_at, item.id)):
            if not batch.result_file_id:
                continue
            result_file = self._get_uploaded_file(batch.result_file_id)
            payload = json.loads(self.file_service.read_file_content(result_file).decode("utf-8"))
            for item in payload.get("items", []):
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                if item_id in replacements:
                    raise ValueError(f"翻译批次重复返回 item: {item_id}")
                replacements[item_id] = str(item.get("text") or "")
        return replacements

    def _register_translation_batch_result(
        self,
        job: DocumentJobRecord,
        *,
        batch: DocumentJobTranslationBatchRecord,
        result: TranslationProviderResult,
        replacements: dict[str, str],
        recorder: TranslationCallAuditRecorder | None,
    ) -> DocumentFileRecord:
        payload = {
            "schema_version": "translation-batch-result/v1",
            "job_id": job.id,
            "batch_id": batch.id,
            "generation": batch.generation,
            "source_document_ir_file_id": batch.source_document_ir_file_id,
            "language_pair": batch.language_pair,
            "items": [{"id": item_id, "text": replacements[item_id]} for item_id in batch.item_ids],
            "provider": {
                "finish_reason": result.finish_reason,
                "usage": result.usage,
                "response_id": result.response_id,
                "provider_trace_id": result.provider_trace_id,
                "content_length": result.content_length,
                "content_sha256": result.content_sha256,
            },
        }
        return self.file_service.register_generated_content(
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            file_type="translation_batch_result",
            filename=f"{batch.id}.json",
            mime_type="application/json",
            content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            metadata={
                "batch_id": batch.id,
                "generation": batch.generation,
                "source_document_ir_file_id": batch.source_document_ir_file_id,
                "language_pair": batch.language_pair,
                "item_count": batch.item_count,
                "char_count": batch.char_count,
                "attempt_count": batch.attempt_count,
                "ai_call_log_file_ids": self._recorder_call_log_file_ids(recorder),
                "debug_archive_file_ids": self._recorder_debug_archive_file_ids(recorder),
                "retry_count": job.retry_count,
            },
        )

    def _enqueue_runnable_translation_batches(
        self,
        job: DocumentJobRecord,
        *,
        generation: int,
        trace_id: str | None,
    ) -> None:
        if self.translation_batch_task_queue is None:
            return
        while True:
            batches = self.translation_batch_repository.list_translation_batches(job.id, generation=generation)
            leaf_batches = [batch for batch in batches if batch.status != "split"]
            active_count = sum(1 for batch in leaf_batches if batch.status in {"queued", "running"})
            max_active = max(1, self.settings.translation_provider_batch_max_concurrency_per_job)
            if active_count >= max_active:
                return
            candidate = self._next_runnable_translation_batch(job, leaf_batches)
            if candidate is None:
                return
            queued = self.translation_batch_repository.update_translation_batch_if_current(
                candidate.id,
                allowed_statuses={"pending", "failed"},
                expected_generation=candidate.generation,
                status="queued",
                lease_owner=None,
                leased_at=None,
                lease_expires_at=None,
                updated_at=utc_now(),
            )
            if queued is None:
                continue
            self._record_event(
                job,
                event_type="translation_batch_queued",
                stage="ir_converting",
                message="翻译批次已投递。",
                payload={
                    "batch_id": queued.id,
                    "generation": queued.generation,
                    "page_start": queued.page_start,
                    "page_end": queued.page_end,
                    "item_count": queued.item_count,
                    "active_limit": max_active,
                },
                trace_id=trace_id,
            )
            self.translation_batch_task_queue.enqueue(queued.id, trace_id=trace_id)

    def _next_runnable_translation_batch(
        self,
        job: DocumentJobRecord,
        batches: list[DocumentJobTranslationBatchRecord],
    ) -> DocumentJobTranslationBatchRecord | None:
        candidates = [
            batch
            for batch in batches
            if batch.status == "pending"
            or (
                batch.status == "failed"
                and batch.retryable
                and batch.attempt_count < batch.max_attempts
                and self._provider_call_budget_remaining(job, batch)
            )
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.page_start or 0, item.created_at, item.id))[0]

    def _reset_expired_translation_batch_leases(
        self,
        job: DocumentJobRecord,
        *,
        generation: int,
        trace_id: str | None,
    ) -> None:
        now = utc_now()
        for batch in self.translation_batch_repository.list_translation_batches(job.id, generation=generation):
            if batch.status != "running" or batch.lease_expires_at is None or batch.lease_expires_at > now:
                continue
            retryable = batch.attempt_count < batch.max_attempts and self._provider_call_budget_remaining(job, batch)
            expired = self.translation_batch_repository.update_translation_batch_if_current(
                batch.id,
                allowed_statuses={"running"},
                expected_generation=batch.generation,
                status="failed",
                error_code="translation_batch_lease_expired",
                error_message="翻译批次租约已过期，等待重新投递。",
                retryable=retryable,
                lease_owner=None,
                leased_at=None,
                lease_expires_at=None,
                updated_at=now,
            )
            if expired is None:
                continue
            self._record_event(
                job,
                event_type="translation_batch_failed",
                stage="ir_converting",
                message="翻译批次租约已过期。",
                payload={
                    "batch_id": expired.id,
                    "generation": expired.generation,
                    "retryable": expired.retryable,
                    "error_code": expired.error_code,
                },
                trace_id=trace_id,
                level="warning",
            )

    def _cancel_translation_batch(
        self,
        batch: DocumentJobTranslationBatchRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        if batch.status in {"succeeded", "failed", "split", "canceled"}:
            return batch
        canceled = self.translation_batch_repository.update_translation_batch_if_current(
            batch.id,
            allowed_statuses={"pending", "queued", "running"},
            expected_generation=batch.generation,
            status="canceled",
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=utc_now(),
        )
        if canceled is None:
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        job = self.job_repository.get_document_job(batch.job_id)
        if job is not None:
            self._record_event(
                job,
                event_type="translation_batch_failed",
                stage="ir_converting",
                message="任务已取消，翻译批次停止执行。",
                payload={"batch_id": canceled.id, "generation": canceled.generation},
                trace_id=trace_id,
                level="warning",
            )
        return canceled

    def _provider_call_budget_remaining(
        self,
        job: DocumentJobRecord,
        batch: DocumentJobTranslationBatchRecord,
    ) -> bool:
        return self._provider_call_budget_remaining_for_batch(batch)

    def _provider_call_budget_remaining_for_batch(self, batch: DocumentJobTranslationBatchRecord) -> bool:
        batches = self.translation_batch_repository.list_translation_batches(batch.job_id, generation=batch.generation)
        attempts = sum(item.attempt_count for item in batches)
        return attempts < batch.provider_call_budget

    def _translation_batch_error_code(self, error: Exception) -> str:
        if isinstance(error, TranslationProviderResponseError) and error.suspected_truncation:
            return "translation_provider_truncated"
        if isinstance(error, (TranslationProviderResponseError, ValueError, KeyError)):
            return "translation_provider_invalid_response"
        return "translation_provider_failed"

    def _translation_profile_batch_limits(self, job: DocumentJobRecord) -> tuple[int, int]:
        profile = None
        resources = job.request_snapshot.get("resources")
        if isinstance(resources, dict):
            profile = resources.get("translation_profile")
        payload = profile.get("payload") if isinstance(profile, dict) else None
        max_pages = self._positive_int_from_mapping(payload, "max_pages_per_batch") or self.settings.translation_max_pages
        max_chars = self._positive_int_from_mapping(payload, "max_chars_per_batch") or self.settings.translation_max_chars
        return max(1, int(max_pages)), max(1, int(max_chars))

    @staticmethod
    def _positive_int_from_mapping(mapping: Any, key: str) -> int | None:
        if not isinstance(mapping, dict):
            return None
        value = mapping.get(key)
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit() and int(value) > 0:
            return int(value)
        return None

    @staticmethod
    def _page_range_for_item_ids(
        item_ids: list[str],
        targets_by_id: dict[str, DocumentIRTranslationTarget],
    ) -> tuple[int | None, int | None]:
        pages = [
            target.page_number
            for item_id in item_ids
            if (target := targets_by_id.get(item_id)) is not None and target.page_number is not None
        ]
        if not pages:
            return None, None
        return min(pages), max(pages)

    def _register_image_assets_archive(
        self,
        job: DocumentJobRecord,
        *,
        raw_file: DocumentFileRecord,
        image_assets: list[Any],
        image_file_ids: list[str],
    ) -> DocumentFileRecord | None:
        """Package per-image render assets into one downloadable artifact for the job detail UI."""

        if not image_assets:
            return None
        manifest = {
            "schema_version": "document-image-assets-archive/v1",
            "job_id": job.id,
            "source_file_id": job.source_file_id,
            "mineru_raw_result_file_id": raw_file.id,
            "retry_count": job.retry_count,
            "assets": [
                {
                    "asset_id": image_asset.asset_id,
                    "block_id": image_asset.block_id,
                    "source_path": image_asset.source_path,
                    "file_id": image_file_id,
                    "mime_type": image_asset.mime_type,
                }
                for image_asset, image_file_id in zip(image_assets, image_file_ids, strict=True)
            ],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for image_asset in image_assets:
                source_name = Path(image_asset.source_path).name or f"{image_asset.asset_id}.bin"
                archive.writestr(f"images/{image_asset.asset_id}_{source_name}", image_asset.content)
        return self.file_service.register_generated_content(
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            file_type="image_assets_archive",
            filename="image_assets.zip",
            mime_type="application/zip",
            content=buffer.getvalue(),
            metadata={
                "source_file_id": job.source_file_id,
                "mineru_raw_result_file_id": raw_file.id,
                "image_asset_count": len(image_assets),
                "image_asset_file_ids": image_file_ids,
                "retry_count": job.retry_count,
            },
        )

    def _translate_document_ir(
        self,
        job: DocumentJobRecord,
        document_ir: DocumentIR,
        *,
        trace_id: str | None,
    ) -> tuple[DocumentIR, dict[str, Any]]:
        if self.document_ir_translation_service is None:
            raise DocumentIRTranslationError("DocumentIR 翻译服务未配置。")
        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            raise DocumentIRTranslationError("当前任务不是翻译任务。")
        try:
            term_version = self._resolve_term_version_for_job(job)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise DocumentIRTranslationError(str(exc)) from exc
        recorder = (
            self.translation_audit_service.build_recorder(
                job=job,
                term_version=term_version,
                trace_id=trace_id,
                save_full_text=job.debug_full_text_enabled,
            )
            if self.translation_audit_service is not None
            else None
        )
        payload = {
            "language_pair": spec.language_pair,
            "term_version_id": term_version.term_version_id if term_version is not None else job.term_version_id,
            "term_snapshot_hash": term_version.snapshot_hash if term_version is not None else None,
            "debug_full_text_enabled": job.debug_full_text_enabled,
        }
        self._record_event(
            job,
            event_type="stage_started",
            stage="ir_converting",
            message="DocumentIR 翻译已开始。",
            payload=payload,
            trace_id=trace_id,
        )
        try:
            translated = self.document_ir_translation_service.translate(
                document_ir,
                term_version=term_version,
                language_pair=spec.language_pair,
                call_recorder=recorder,
            )
        except DocumentIRTranslationError:
            self._record_translation_audit_events(job, recorder, trace_id=trace_id)
            raise
        self._record_translation_audit_events(job, recorder, trace_id=trace_id)
        self._record_event(
            job,
            event_type="stage_succeeded",
            stage="ir_converting",
            message="DocumentIR 翻译已完成。",
            payload={
                **payload,
                "ai_call_log_file_id": recorder.call_log_file_id if recorder is not None else None,
                "debug_archive_file_id": recorder.debug_archive_file_id if recorder is not None else None,
                "ai_call_log_file_ids": self._recorder_call_log_file_ids(recorder),
                "debug_archive_file_ids": self._recorder_debug_archive_file_ids(recorder),
            },
            trace_id=trace_id,
        )
        metadata = {
            "applied": True,
            "language_pair": spec.language_pair,
            "term_version_id": term_version.term_version_id if term_version is not None else job.term_version_id,
            "term_snapshot_hash": term_version.snapshot_hash if term_version is not None else None,
            "ai_call_log_file_id": recorder.call_log_file_id if recorder is not None else None,
            "debug_archive_file_id": recorder.debug_archive_file_id if recorder is not None else None,
            "ai_call_log_file_ids": self._recorder_call_log_file_ids(recorder),
            "debug_archive_file_ids": self._recorder_debug_archive_file_ids(recorder),
        }
        return translated, metadata

    def _record_translation_audit_events(
        self,
        job: DocumentJobRecord,
        recorder: TranslationCallAuditRecorder | None,
        *,
        trace_id: str | None,
    ) -> None:
        if recorder is None:
            return
        debug_archive_file_ids = self._recorder_debug_archive_file_ids(recorder)
        for index, call_log_file_id in enumerate(self._recorder_call_log_file_ids(recorder)):
            debug_archive_file_id = debug_archive_file_ids[index] if index < len(debug_archive_file_ids) else None
            self._record_event(
                job,
                event_type="ai_call_logged",
                stage="ir_converting",
                message="AI 翻译调用审计记录已保存。",
                payload={
                    "file_id": call_log_file_id,
                    "file_type": "ai_call_log",
                    "debug_archive_file_id": debug_archive_file_id,
                },
                trace_id=trace_id,
            )
        for debug_archive_file_id in debug_archive_file_ids:
            self._record_event(
                job,
                event_type="debug_archive_saved",
                stage="ir_converting",
                message="AI 翻译全文调试归档已保存。",
                payload={
                    "file_id": debug_archive_file_id,
                    "file_type": "ai_debug_archive",
                    "retention_days": max(1, self.settings.translation_debug_archive_retention_days),
                },
                trace_id=trace_id,
            )

    @staticmethod
    def _recorder_call_log_file_ids(recorder: TranslationCallAuditRecorder | None) -> list[str]:
        if recorder is None:
            return []
        file_ids = list(getattr(recorder, "call_log_file_ids", []))
        if file_ids:
            return file_ids
        return [recorder.call_log_file_id] if recorder.call_log_file_id is not None else []

    @staticmethod
    def _recorder_debug_archive_file_ids(recorder: TranslationCallAuditRecorder | None) -> list[str]:
        if recorder is None:
            return []
        file_ids = list(getattr(recorder, "debug_archive_file_ids", []))
        if file_ids:
            return file_ids
        return [recorder.debug_archive_file_id] if recorder.debug_archive_file_id is not None else []

    def _resolve_term_version_for_job(self, job: DocumentJobRecord):
        if self.term_version_service is None:
            return None
        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            return None
        if job.term_version_id:
            return self.term_version_service.load_version(job.term_version_id, language_pair=spec.language_pair)
        return self.term_version_service.resolve_for_job(None, language_pair=spec.language_pair)

    def _mineru_language_for_job(self, job: DocumentJobRecord) -> str:
        spec = spec_for_document_job_mode(job.mode)
        return spec.mineru_language or self.settings.mineru_language

    def _render_and_save_word(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        if job.result_file_id:
            return self._mark_succeeded(job, trace_id=trace_id)
        existing_result = self._get_existing_result_file(job)
        if existing_result is not None:
            recovered = self.job_repository.update_document_job_if_current(
                job.id,
                allowed_statuses={"running"},
                allowed_stages={"rendering", "uploading"},
                expected_retry_count=job.retry_count,
                status="running",
                stage="uploading",
                progress=max(job.progress, 90),
                result_file_id=existing_result.id,
                updated_at=utc_now(),
            )
            if recovered is None:
                return self.job_repository.get_document_job(job.id) or job
            return self._mark_succeeded(recovered, trace_id=trace_id)

        rendering = job
        if job.stage == "rendering":
            self._record_event(
                rendering,
                event_type="stage_started",
                stage="rendering",
                message="Word 渲染已开始。",
                payload={"document_ir_file_id": job.document_ir_file_id, "template_version_id": job.template_version_id},
                trace_id=trace_id,
            )

        ir_file = self._get_document_ir_file(rendering)
        document_ir = DocumentIR.model_validate_json(self.file_service.read_file_content(ir_file))
        layout_plan = build_layout_plan(document_ir)
        renderer_metadata = self._renderer_metadata(document_ir, layout_plan)
        template_selection = self.template_read_service.resolve_template_version(rendering.template_version_id)
        word_content = self.word_renderer.render_to_bytes(
            document_ir,
            template_path=template_selection.template_path,
            config_path=template_selection.layout_config_path,
            image_loader=self._build_image_loader(rendering),
            options=DocumentIRRenderOptions(
                subscript_config_path=self.settings.subscript_config_path,
                document_language=document_ir.metadata.document_language,
            ),
        )
        docx_quality = analyze_docx_quality_bytes(word_content)
        renderer_metadata["docx_quality"] = docx_quality
        renderer_metadata["quality_flags"] = build_docx_quality_flags(docx_quality)
        uploading = self.job_repository.update_document_job_if_current(
            rendering.id,
            allowed_statuses={"running"},
            allowed_stages={"rendering"},
            expected_retry_count=rendering.retry_count,
            status="running",
            stage="uploading",
            progress=max(rendering.progress, 85),
            template_version_id=template_selection.template_version_id,
            updated_at=utc_now(),
        )
        if uploading is None:
            return self.job_repository.get_document_job(rendering.id) or rendering
        self._record_event(
            uploading,
            event_type="stage_succeeded",
            stage="rendering",
            message="Word 渲染已完成。",
            payload={
                "document_ir_file_id": ir_file.id,
                "template_version_id": template_selection.template_version_id,
                "block_count": len(document_ir.blocks),
                **renderer_metadata,
            },
            trace_id=trace_id,
        )
        self._record_event(
            uploading,
            event_type="stage_started",
            stage="uploading",
            message="生成 Word 上传登记已开始。",
            payload={"template_version_id": template_selection.template_version_id},
            trace_id=trace_id,
        )
        word_file = self.file_service.register_generated_content(
            tenant_id=uploading.tenant_id,
            company_id=uploading.company_id,
            job_id=uploading.id,
            created_by=uploading.created_by,
            file_type="generated_word",
            filename=self._result_filename(uploading),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=word_content,
            metadata={
                "source_file_id": uploading.source_file_id,
                "document_ir_file_id": ir_file.id,
                "template_version_id": template_selection.template_version_id,
                "template_id": template_selection.template_id,
                "template_version": template_selection.version,
                "block_count": len(document_ir.blocks),
                "image_asset_file_ids": uploading.image_asset_file_ids,
                "retry_count": uploading.retry_count,
                **renderer_metadata,
            },
        )
        completed = self.job_repository.update_document_job_if_current(
            uploading.id,
            allowed_statuses={"running"},
            allowed_stages={"uploading"},
            expected_retry_count=uploading.retry_count,
            status="succeeded",
            stage="completed",
            progress=100,
            result_file_id=word_file.id,
            completed_at=utc_now(),
            updated_at=utc_now(),
        )
        if completed is None:
            return self.job_repository.get_document_job(uploading.id) or uploading
        self._record_event(
            completed,
            event_type="file_registered",
            stage="uploading",
            message="生成 Word 已保存。",
            payload={
                "file_id": word_file.id,
                "file_type": word_file.file_type,
                "object_key": word_file.object_key,
                **renderer_metadata,
            },
            trace_id=trace_id,
        )
        self._record_event(
            completed,
            event_type="stage_succeeded",
            stage="completed",
            message="文档任务已完成。",
            payload={"result_file_id": word_file.id, "template_version_id": template_selection.template_version_id},
            trace_id=trace_id,
        )
        self.logger.info(
            "[trace_id=%s job_id=%s stage=completed status=succeeded] result_file_id=%s",
            trace_id,
            completed.id,
            word_file.id,
        )
        return completed

    def _document_ir_layout_metadata(self, document_ir: DocumentIR) -> dict[str, Any]:
        """生成 DocumentIR artifact 与事件共用的布局诊断摘要。"""

        return {
            "schema_version": document_ir.schema_version,
            "page_count": len(document_ir.pages),
            "layout_page_count": len(document_ir.pages),
            "block_count": len(document_ir.blocks),
            "layout_block_count": sum(1 for block in document_ir.blocks if block.layout is not None),
            "quality_flags": document_ir.quality_flags,
        }

    def _renderer_metadata(self, document_ir: DocumentIR, layout_plan: LayoutPlan) -> dict[str, Any]:
        """生成 generated_word artifact 与渲染事件共用的 renderer 诊断摘要。"""

        return {
            "schema_version": document_ir.schema_version,
            "renderer_mode": layout_plan.mode,
            "layout_page_count": len(layout_plan.pages),
            "layout_region_count": sum(len(page.regions) for page in layout_plan.pages),
            "layout_block_count": sum(len(region.blocks) for page in layout_plan.pages for region in page.regions),
            "layout_quality_flags": document_ir.quality_flags,
        }

    def _record_event(
        self,
        job: DocumentJobRecord,
        *,
        event_type: DocumentJobEventType,
        stage: DocumentJobStage,
        message: str,
        payload: dict,
        trace_id: str | None,
        level: str = "info",
    ) -> None:
        event = DocumentJobEventRecord(
            id=f"event_{uuid4().hex[:12]}",
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            stage=stage,
            level=level,
            event_type=event_type,
            message=message,
            payload=payload,
            trace_id=trace_id,
        )
        self.event_repository.append_document_job_event(job.id, event)

    def _get_uploaded_file(self, file_id: str) -> DocumentFileRecord:
        record = self.file_repository.get_document_file(file_id)
        if record is None:
            raise FileNotFoundError(f"文件不存在: {file_id}")
        if record.status != "uploaded":
            raise ValueError(f"文件尚未完成上传: {file_id}")
        return record

    def _get_mineru_raw_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        if job.mineru_raw_result_file_id:
            return self._get_uploaded_file(job.mineru_raw_result_file_id)
        candidates = [
            file
            for file in self.file_repository.list_document_files()
            if file.job_id == job.id and file.file_type == "mineru_raw_result" and file.status == "uploaded"
        ]
        if not candidates:
            raise FileNotFoundError(f"任务缺少 MinerU 原始结果文件: {job.id}")
        return sorted(candidates, key=lambda item: (item.created_at, item.id))[-1]

    def _select_mineru_result(self, payload: dict, data_id: str) -> dict:
        results = payload.get("extract_result") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise ValueError("MinerU 查询结果缺少 extract_result 数组。")
        for item in results:
            if isinstance(item, dict) and str(item.get("data_id") or "") == data_id:
                return item
        for item in results:
            if isinstance(item, dict):
                return item
        raise ValueError("MinerU 查询结果为空。")

    def _get_document_ir_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        if job.document_ir_file_id:
            return self._get_uploaded_file(job.document_ir_file_id)
        candidates = [
            file
            for file in self.file_repository.list_document_files()
            if file.job_id == job.id and file.file_type == "document_ir" and file.status == "uploaded"
        ]
        if not candidates:
            raise FileNotFoundError(f"任务缺少 DocumentIR 文件: {job.id}")
        return sorted(candidates, key=lambda item: (item.created_at, item.id))[-1]

    def _get_existing_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord | None:
        candidates = [
            file
            for file in self.file_repository.list_document_files()
            if file.job_id == job.id and file.file_type == "generated_word" and file.status == "uploaded"
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.created_at, item.id))[-1]

    def _build_image_loader(self, job: DocumentJobRecord) -> Callable[[DocumentIRAsset], bytes | None]:
        image_files = {
            file.id: file
            for file in self.file_repository.list_document_files()
            if file.job_id == job.id and file.file_type == "image_asset" and file.status == "uploaded"
        }

        def load_image(asset: DocumentIRAsset) -> bytes | None:
            if asset.file_id is None:
                return None
            record = image_files.get(asset.file_id)
            if record is None:
                return None
            return self.file_service.read_file_content(record)

        return load_image

    def _result_filename(self, job: DocumentJobRecord) -> str:
        source_file = self.file_repository.get_document_file(job.source_file_id)
        if source_file is None:
            return f"{job.id}.docx"
        source_stem = Path(source_file.original_filename).stem.strip() or job.id
        return f"{source_stem}.docx"

    def _mark_succeeded(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        completed = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"uploading"},
            expected_retry_count=job.retry_count,
            status="succeeded",
            stage="completed",
            progress=100,
            completed_at=job.completed_at or utc_now(),
            updated_at=utc_now(),
        )
        if completed is None:
            return self.job_repository.get_document_job(job.id) or job
        self._record_event(
            completed,
            event_type="stage_succeeded",
            stage="completed",
            message="文档任务已确认完成。",
            payload={"result_file_id": completed.result_file_id},
            trace_id=trace_id,
        )
        return completed

    def _failed_stage_for_current_job(self, job: DocumentJobRecord) -> DocumentJobStage:
        if job.stage == "uploaded":
            return "uploaded"
        if job.stage in {"rendering", "uploading"}:
            return job.stage
        if job.stage == "ir_converting":
            return "ir_converting"
        return "parsing"

    def _mark_timed_out_if_needed(
        self,
        job: DocumentJobRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord | None:
        if job.timeout_at is None or utc_now() < job.timeout_at:
            return None
        return self._mark_timed_out(job, trace_id=trace_id)

    def _mark_timed_out(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        return self._mark_failed(
            job,
            failed_stage=self._failed_stage_for_current_job(job),
            error_code="document_job_timeout",
            error_message=f"P0 文档任务超过 {self.settings.p0_document_job_timeout_seconds} 秒超时限制。",
            trace_id=trace_id,
        )

    def _classify_worker_failure(
        self,
        exc: Exception,
        job: DocumentJobRecord,
    ) -> tuple[DocumentJobStage, str]:
        failed_stage = self._failed_stage_for_current_job(job)
        if isinstance(exc, MinerUError) or failed_stage == "parsing":
            return failed_stage, "mineru_failed"
        if isinstance(exc, DocumentIRTranslationError):
            return failed_stage, "translation_failed"
        if isinstance(exc, zipfile.BadZipFile) or failed_stage == "ir_converting":
            return failed_stage, "document_ir_failed"
        if failed_stage == "rendering":
            return failed_stage, "render_failed"
        if failed_stage == "uploading" or isinstance(exc, (ApiError, FileNotFoundError, OSError)):
            return failed_stage, "oss_failed"
        return failed_stage, "document_job_worker_failed"

    def _mark_failed(
        self,
        job: DocumentJobRecord,
        *,
        failed_stage: DocumentJobStage,
        error_code: str,
        error_message: str,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        now = utc_now()
        failed = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"pending", "queued", "running"},
            allowed_stages={"uploaded", "parsing", "parsed", "ir_converting", "rendering", "uploading"},
            expected_retry_count=job.retry_count,
            status="failed",
            stage="failed",
            failed_stage=failed_stage,
            error_code=error_code,
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )
        if failed is None:
            return self.job_repository.get_document_job(job.id) or job
        self._record_event(
            failed,
            event_type="stage_failed",
            stage=failed_stage,
            message="document_jobs Worker 执行失败。",
            payload={"error_code": error_code, "error_message": error_message},
            trace_id=trace_id,
            level="error",
        )
        self.logger.error(
            "[trace_id=%s job_id=%s stage=%s status=failed] %s",
            trace_id,
            job.id,
            failed_stage,
            error_message,
        )
        return failed

    @staticmethod
    def _build_callback_seed(length: int = 32) -> str:
        """生成 MinerU checksum 使用的单任务 seed。"""

        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _build_mineru_client(self) -> MinerUClient:
        if not self.settings.mineru_api_token:
            raise RuntimeError("MINERU_API_TOKEN 未配置，无法提交 MinerU。")
        return MinerUClient(
            api_token=self.settings.mineru_api_token,
            model_version=self.settings.mineru_model_version,
            user_token=self.settings.mineru_uid,
        )


class EagerDocumentJobTaskQueue:
    """测试/本地可用的同步队列 adapter，复用同一幂等执行骨架。"""

    def __init__(self, execution_service: DocumentJobExecutionService) -> None:
        self.execution_service = execution_service

    def enqueue(self, job_id: str, *, trace_id: str | None, run_inline: bool = True) -> str | None:
        if run_inline:
            self.execution_service.execute_job(job_id, trace_id=trace_id)
        return f"eager:{job_id}"


class EagerDocumentTranslationBatchTaskQueue:
    """测试/本地可用的同步 translation batch 队列 adapter。"""

    def __init__(self, execution_service: DocumentJobExecutionService) -> None:
        self.execution_service = execution_service

    def enqueue(self, batch_id: str, *, trace_id: str | None, run_inline: bool = True) -> str | None:
        if run_inline:
            self.execution_service.execute_translation_batch(batch_id, trace_id=trace_id)
        return f"eager-translation-batch:{batch_id}"


class CeleryDocumentJobTaskQueue:
    """生产 Celery 队列 adapter；实际任务函数在 app.workers.document_tasks。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enqueue(self, job_id: str, *, trace_id: str | None, run_inline: bool = True) -> str | None:
        try:
            from celery.exceptions import CeleryError
            from kombu.exceptions import KombuError, OperationalError
            from app.workers.celery_app import create_celery_app
        except ModuleNotFoundError as exc:
            raise RuntimeError("Celery 依赖未安装，请先安装 requirements.txt。") from exc

        try:
            celery_app = create_celery_app(self.settings)
            task = celery_app.send_task(
                "document_jobs.run",
                args=(job_id,),
                kwargs={"trace_id": trace_id},
                queue=self.settings.document_jobs_celery_queue,
                task_id=f"document-job-{job_id}",
            )
        except (CeleryError, KombuError, OperationalError) as exc:
            raise RuntimeError(f"Celery 任务投递失败: {exc}") from exc
        return task.id


class CeleryDocumentTranslationBatchTaskQueue:
    """生产 translation batch Celery 队列 adapter；任务函数在 app.workers.document_tasks。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enqueue(self, batch_id: str, *, trace_id: str | None, run_inline: bool = True) -> str | None:
        try:
            from celery.exceptions import CeleryError
            from kombu.exceptions import KombuError, OperationalError
            from app.workers.celery_app import create_celery_app
        except ModuleNotFoundError as exc:
            raise RuntimeError("Celery 依赖未安装，请先安装 requirements.txt。") from exc

        try:
            celery_app = create_celery_app(self.settings)
            task = celery_app.send_task(
                "document_jobs.translate_batch",
                args=(batch_id,),
                kwargs={"trace_id": trace_id},
                queue=self.settings.document_jobs_translation_batch_celery_queue,
                task_id=f"document-translation-batch-{batch_id}",
            )
        except (CeleryError, KombuError, OperationalError) as exc:
            raise RuntimeError(f"Celery 任务投递失败: {exc}") from exc
        return task.id
