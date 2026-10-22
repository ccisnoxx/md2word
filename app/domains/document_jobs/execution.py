from __future__ import annotations

# app/domains/document_jobs/execution.py: 提供 document_jobs Worker 投递端口和幂等执行骨架。

import logging
import hashlib
import io
import json
import secrets
import sqlite3
import tempfile
import time
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from app.clients.mineru_client import MinerUClient, MinerUError
from app.core.config import Settings
from app.domains.jobs.models import JobResourceSnapshot
from app.domains.jobs.resource_snapshots import (
    JobResourceSnapshotError,
    JobResourceSnapshotService,
)
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
from app.domains.mineru.config import EffectiveMinerUConfig
from app.domains.resources.models import utc_now
from app.domains.document_jobs.repository import (
    DocumentJobCallbackMessageStoreProtocol,
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
    TranslationBatchTreeInvalidError,
)
from app.domains.document_jobs.workflow import (
    TranslationGenerationSummary,
    TranslationRootPlan,
    reduce_translation_generation,
)
from app.services.document_ir import MinerUToDocumentIRService
from app.services.renderer import DocumentIRRenderOptions, DocumentIRWordRenderer
from app.services.renderer.evidence import build_renderer_evidence, ensure_renderer_integrity
from app.services.renderer.layout_plan import build_layout_plan
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
from app.domains.translation.models import (
    TranslationProfileSnapshot,
    TranslationProviderResult,
    TranslationTextItem,
    TermVersionSnapshot,
)
from app.domains.translation.integrity import (
    TranslationIntegrityBinding,
    TranslationIntegrityError,
    TranslationIntegrityEvidence,
    ValidatedTranslationBatch,
)
from app.domains.translation.provider import OpenAICompatibleTranslationProvider, TranslationProviderResponseError


class _TranslationBatchStorageError(RuntimeError):
    """翻译成功响应已审计，但批次结果或状态提交写入失败。"""


def _is_metadata_storage_error(error: Exception) -> bool:
    """识别仓储驱动异常，避免把数据库故障当成 Provider 失败重试。"""

    error_module = type(error).__module__
    return isinstance(error, (OSError, sqlite3.Error)) or error_module.startswith("pymysql.")


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
        mineru_config_resolver: Callable[[], EffectiveMinerUConfig],
        document_ir_translation_service: DocumentIRTranslationService | None = None,
        term_version_service: Any | None = None,
        translation_audit_service: TranslationAuditService | None = None,
        job_resource_snapshot_service: JobResourceSnapshotService | None = None,
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
        self.mineru_config_resolver = mineru_config_resolver
        self.document_ir_translation_service = document_ir_translation_service
        self.term_version_service = term_version_service
        self.translation_audit_service = translation_audit_service
        self.job_resource_snapshot_service = job_resource_snapshot_service
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
        if job.status == "running" and job.stage not in {
            "parsing", "parsed", "ir_converting", "translating", "translation_validating",
            "rendering", "quality_checking", "uploading",
        }:
            return job

        latest = job
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
            elif latest.status == "running" and latest.stage == "translating":
                source_file, source_document_ir = self._read_translation_source(
                    latest, latest.source_document_ir_file_id,
                )
                del source_file
                latest = self._ensure_translation_batches_and_enqueue(
                    latest, source_document_ir, trace_id=trace_id,
                )
            elif latest.status == "running" and latest.stage == "translation_validating":
                latest = self._finalize_translation_generation(
                    latest.id, generation=latest.retry_count, trace_id=trace_id,
                )
            if latest.status == "running" and latest.stage in {"rendering", "quality_checking", "uploading"}:
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
                integrity=exc.evidence if isinstance(exc, (DocumentIRTranslationError, TranslationIntegrityError)) else None,
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
        try:
            self._record_event(
                running,
                event_type="stage_started",
                stage="parsing",
                message="Worker 已开始执行解析阶段骨架。",
                payload={"worker_backend": self.settings.document_jobs_worker_backend},
                trace_id=trace_id,
            )
        except Exception as exc:
            return self._fail_stage_attempt(running, exc, trace_id=trace_id)
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
        try:
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
        except Exception as exc:
            return self._fail_stage_attempt(parsed, exc, trace_id=trace_id)
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
        try:
            self._record_event(
                converting,
                event_type="stage_started",
                stage="ir_converting",
                message="DocumentIR 转换已开始。",
                payload={"mineru_raw_result_file_id": job.mineru_raw_result_file_id},
                trace_id=trace_id,
            )
        except Exception as exc:
            return self._fail_stage_attempt(converting, exc, trace_id=trace_id)
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
            _source_file, source_document_ir = self._read_translation_source(job, job.source_document_ir_file_id)
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
        try:
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
        except Exception as exc:
            return self._fail_stage_attempt(updated, exc, trace_id=trace_id)
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
        generation = job.retry_count
        if job.stage == "ir_converting":
            transitioned = self.job_repository.update_document_job_if_current(
                job.id,
                allowed_statuses={"running"},
                allowed_stages={"ir_converting"},
                expected_retry_count=generation,
                stage="translating",
                updated_at=utc_now(),
            )
            if transitioned is None:
                return self.job_repository.get_document_job(job.id) or job
            job = transitioned
            try:
                self._record_event(
                    job,
                    event_type="stage_started",
                    stage="translating",
                    message="DocumentIR 翻译已开始。",
                    payload={"source_document_ir_file_id": job.source_document_ir_file_id},
                    trace_id=trace_id,
                )
            except Exception as exc:
                return self._fail_stage_attempt(job, exc, trace_id=trace_id)
        if job.status != "running" or job.stage != "translating" or job.retry_count != generation:
            return job
        if self.document_ir_translation_service is None:
            raise DocumentIRTranslationError("DocumentIR 翻译服务未配置。")
        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            raise DocumentIRTranslationError("当前任务不是翻译任务。")
        if not job.source_document_ir_file_id:
            raise DocumentIRTranslationError("翻译任务缺少 source DocumentIR 文件。")
        expected_plans = self._build_expected_translation_plans(job, source_document_ir)
        try:
            batches = self.translation_batch_repository.ensure_translation_batch_roots(
                job.id,
                generation=generation,
                expected_plans=expected_plans,
            )
        except TranslationBatchTreeInvalidError as exc:
            return self._mark_failed(
                job,
                failed_stage="translating",
                error_code=exc.code,
                error_message="翻译批次树与当前权威计划不一致。",
                trace_id=trace_id,
            )
        except TranslationIntegrityError as exc:
            return self._mark_failed(
                job,
                failed_stage="translating",
                error_code="translation_failed",
                error_message=str(exc),
                trace_id=trace_id,
                integrity=exc.evidence,
            )
        if not batches:
            return self._finalize_translation_generation(
                job.id, generation=generation, trace_id=trace_id,
            ) or job
        self._reset_expired_translation_batch_leases(job, generation=generation, trace_id=trace_id)
        self._enqueue_runnable_translation_batches(job, generation=generation, trace_id=trace_id)
        return self._finalize_translation_generation(job.id, generation=generation, trace_id=trace_id) or job

    def _get_translation_execution_snapshot(
        self,
        job_id: str,
        *,
        generation: int,
    ) -> tuple[DocumentJobRecord | None, list[DocumentJobTranslationBatchRecord]]:
        """从批次仓储的同任务锁快照读取 job 与当前代批次。"""

        try:
            snapshot_job, batches = self.translation_batch_repository.get_translation_batch_snapshot(job_id)
        except (FileNotFoundError, OSError):
            return None, []
        if snapshot_job.retry_count != generation:
            return snapshot_job, []
        return snapshot_job, [batch for batch in batches if batch.generation == snapshot_job.retry_count]

    def summarize_translation_generation(
        self,
        job: DocumentJobRecord,
        batches: list[DocumentJobTranslationBatchRecord] | None = None,
    ) -> TranslationGenerationSummary | None:
        """以当前 job 的 source/config 重新计算权威批次结论。

        API 和执行入口共用这条纯 reducer 接线；权威根计划来自 source/config，不能
        从已落库批次反推。direct 任务不读取翻译资源，旧记录无法重建计划时返回 None。
        """

        current_batches = batches
        if current_batches is None:
            requested_generation = job.retry_count
            job, current_batches = self._get_translation_execution_snapshot(
                job.id, generation=requested_generation,
            )
            if job is None or job.retry_count != requested_generation:
                return None
        if not is_translation_document_job_mode(job.mode):
            return None
        if self.document_ir_translation_service is None or not job.source_document_ir_file_id:
            return None
        try:
            _source_file, source_document_ir = self._read_translation_source(
                job, job.source_document_ir_file_id,
            )
            expected_plans = self._build_expected_translation_plans(job, source_document_ir)
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError):
            # 旧任务可能缺少本轮重建所需的 source；API 仍返回旧诊断字段，不伪造新结论。
            return None
        return reduce_translation_generation(
            job_id=job.id,
            job_status=job.status,
            job_stage=job.stage,
            generation=job.retry_count,
            expected_plans=expected_plans,
            batches=current_batches,
            provider_call_budget=(
                expected_plans[0].provider_call_budget if expected_plans else 0
            ),
        )

    def _build_expected_translation_plans(
        self,
        job: DocumentJobRecord,
        source_document_ir: DocumentIR,
    ) -> list[TranslationRootPlan]:
        """由不可变 source、资源快照计算本代根计划，供 reducer 与安装端口共用。"""

        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            return []
        if self.document_ir_translation_service is None:
            raise DocumentIRTranslationError("DocumentIR 翻译服务未配置。")
        profile = self._translation_profile_for_job(job, language_pair=spec.language_pair)
        max_pages, max_chars = self._translation_profile_batch_limits(profile)
        term_version = self._resolve_term_version_for_job(job)
        _targets, _items, plans = self.document_ir_translation_service.build_translation_plan(
            source_document_ir,
            max_pages_per_batch=max_pages,
            max_chars_per_batch=max_chars,
            batch_id_prefix=f"{job.id}_retry{job.retry_count}_translation_batch",
        )
        provider_call_budget = min(200, len(plans) * 12)
        max_attempts = max(1, self.settings.translation_provider_batch_max_attempts)
        return [
            TranslationRootPlan(
                batch_id=plan.batch_id,
                job_id=job.id,
                generation=job.retry_count,
                job_retry_count=job.retry_count,
                source_document_ir_file_id=job.source_document_ir_file_id or "",
                language_pair=spec.language_pair,
                item_ids=tuple(plan.item_ids),
                item_count=plan.item_count,
                char_count=plan.char_count,
                page_start=plan.page_start,
                page_end=plan.page_end,
                term_version_id=(
                    term_version.term_version_id
                    if term_version is not None else job.term_version_id
                ),
                term_snapshot_hash=(
                    term_version.snapshot_hash if term_version is not None else None
                ),
                split_level=plan.split_level,
                deterministic_batch_count=len(plans),
                provider_call_budget=provider_call_budget,
                max_attempts=max_attempts,
            )
            for plan in plans
        ]

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
        if job.status in {"succeeded", "failed"} or job.retry_count != batch.job_retry_count or job.retry_count != batch.generation:
            return batch
        if job.status == "running" and job.stage == "ir_converting" and job.source_document_ir_file_id:
            job = self._mark_translating_started(job, trace_id=trace_id)
        if (
            job.status != "running" or job.stage != "translating"
            or job.retry_count != batch.job_retry_count or job.retry_count != batch.generation
        ):
            return batch
        if batch.status == "failed" and not batch.retryable:
            self._finalize_translation_generation(
                job.id, generation=batch.generation, trace_id=trace_id,
            )
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        claimed = self._claim_translation_batch(batch, trace_id=trace_id)
        if claimed is None:
            reconciled = self._reconcile_translation_batch_atomic_rejection(
                batch, generation=batch.generation, trace_id=trace_id,
            )
            # _claim 已完成预算失败的条件写与任务收口；保留 execute 既有失败批次返回合同，
            # 但绝不把该记录当作已获 lease 的批次继续执行。
            if (
                reconciled.status == "failed"
                and reconciled.error_code == "translation_request_budget_exceeded"
            ):
                return reconciled
            return None

        prepared = None
        request = None
        binding = None
        provider_called = False
        audit_started = False
        audit_completed = False
        result: TranslationProviderResult | None = None
        recorder: TranslationCallAuditRecorder | None = None
        started_at = time.perf_counter()
        try:
            source_file, source_document_ir = self._read_translation_source(job, claimed.source_document_ir_file_id)
            _targets, items = self.document_ir_translation_service.extract_translation_items(source_document_ir)
            items_by_id = {item.id: item for item in items}
            batch_items = [items_by_id[item_id] for item_id in claimed.item_ids]
            term_version = self._resolve_term_version_for_job(job)
            translation_profile = self._translation_profile_for_job(
                job,
                language_pair=claimed.language_pair,
            )
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
            prepared = self.document_ir_translation_service.build_provider_request(
                source_document_ir,
                batch_items,
                term_version=term_version,
                language_pair=claimed.language_pair,
                prompt=(
                    translation_profile.prompt
                    if translation_profile is not None
                    else None
                ),
                batch_id=claimed.id,
                attempt=claimed.attempt_count,
                split_level=claimed.split_level,
                parent_batch_id=claimed.parent_batch_id,
                page_start=claimed.page_start,
                page_end=claimed.page_end,
                max_chars_per_request=self._translation_profile_batch_limits(translation_profile)[1],
            )
            request = prepared.request
            binding = self._translation_integrity_binding(job, claimed, source_file, translation_profile, term_version)
            provider_called = True
            try:
                result = self.document_ir_translation_service.provider.translate(request)
            except TranslationProviderResponseError:
                raise
            except Exception:
                # 外部异常可夹带正文；在调用边界转成固定安全描述，保留既有失败路径。
                raise RuntimeError("翻译 Provider 调用失败。") from None
            validated = self.document_ir_translation_service.validator.validate(
                prepared.source_items, prepared.encoded_batch, result,
            )
            integrity = validated.evidence.bind(binding)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if recorder is not None:
                audit_started = True
                recorder.record_success(request, result, duration_ms=duration_ms, integrity=integrity)
                self._record_translation_audit_events(job, recorder, trace_id=trace_id)
                audit_completed = True
            current = self.job_repository.get_document_job(job.id)
            if current is None or current.retry_count != claimed.generation or current.status != "running" or current.stage != "translating":
                return self.translation_batch_repository.get_translation_batch(claimed.id)
            current_summary = self.summarize_translation_generation(current)
            if current_summary is not None and current_summary.outcome in {
                "failed", "completed", "canceled", "validating",
            }:
                # Provider 调用已经真实发生，但终态闸门先于结果登记；该响应只能保留审计。
                self._finalize_translation_generation(
                    current.id, generation=claimed.generation, trace_id=trace_id,
                )
                return self.translation_batch_repository.get_translation_batch(claimed.id) or claimed
            _source_file, current_source_ir = self._read_translation_source(
                current, claimed.source_document_ir_file_id,
            )
            expected_plans = self._build_expected_translation_plans(current, current_source_ir)
            try:
                result_file = self._register_translation_batch_result(
                    job,
                    batch=claimed,
                    result=result,
                    validated=validated,
                    integrity=integrity,
                    recorder=recorder,
                )
            except (RuntimeError, ValueError, FileNotFoundError, OSError) as exc:
                # Provider 已成功且审计已落盘；结果 Artifact 的 I/O 失败不能再次调用 Provider。
                raise _TranslationBatchStorageError("翻译批次结果 Artifact 写入失败。") from exc
            try:
                succeeded = self.translation_batch_repository.update_translation_batch_if_current(
                    claimed.id,
                    allowed_statuses={"running"},
                    expected_generation=claimed.generation,
                    expected_attempt_count=claimed.attempt_count,
                    expected_lease_owner=claimed.lease_owner,
                    expected_job_id=claimed.job_id,
                    expected_job_status={"running"},
                    expected_job_stages={"translating"},
                    expected_plans=expected_plans,
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
            except TranslationBatchTreeInvalidError:
                raise
            except (RuntimeError, ValueError, FileNotFoundError, OSError, sqlite3.Error) as exc:
                raise _TranslationBatchStorageError("翻译批次状态提交失败。") from exc
            except Exception as exc:
                if not _is_metadata_storage_error(exc):
                    raise
                raise _TranslationBatchStorageError("翻译批次状态提交失败。") from exc
            if succeeded is None:
                return self._reconcile_translation_batch_atomic_rejection(
                    claimed, generation=claimed.generation, trace_id=trace_id,
                )
            self._record_event(
                job,
                event_type="translation_batch_succeeded",
                stage="translating",
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
                duration_ms=duration_ms,
            )
            self._finalize_translation_generation(job.id, generation=succeeded.generation, trace_id=trace_id)
            return succeeded
        except TranslationBatchTreeInvalidError:
            # 权威 source/config 与持久化批次树不一致时，不能把它伪装成 Provider 失败。
            current = self.job_repository.get_document_job(claimed.job_id)
            if current is None or current.retry_count != claimed.generation:
                return self.translation_batch_repository.get_translation_batch(claimed.id) or claimed
            self._mark_failed(
                job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return self.translation_batch_repository.get_translation_batch(claimed.id) or claimed
        except _TranslationBatchStorageError as exc:
            return self._fail_translation_batch_storage(
                claimed,
                job,
                expected_plans=expected_plans,
                error_message=str(exc),
                trace_id=trace_id,
            )
        except (KeyError, ValueError, RuntimeError, FileNotFoundError, OSError) as exc:
            # 审计自身失败须可见，不能再把同一次调用登记成另一份失败审计。
            if audit_started and not audit_completed:
                raise
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if recorder is not None and provider_called and not audit_started:
                integrity = exc.evidence if isinstance(exc, TranslationIntegrityError) else self.document_ir_translation_service.validator.call_failure_evidence(
                    prepared.source_items, prepared.encoded_batch, error_code=self._translation_batch_error_code(exc),
                )
                recorder.record_failure(request, result, error=exc, duration_ms=duration_ms, integrity=integrity.bind(binding))
                self._record_translation_audit_events(job, recorder, trace_id=trace_id)
            try:
                return self._handle_translation_batch_failure(
                    claimed,
                    job,
                    error=exc,
                    recorder=recorder,
                    trace_id=trace_id,
                    duration_ms=duration_ms,
                )
            except TranslationBatchTreeInvalidError:
                current = self.job_repository.get_document_job(claimed.job_id)
                if current is None or current.retry_count != claimed.generation:
                    return self.translation_batch_repository.get_translation_batch(claimed.id) or claimed
                self._mark_failed(
                    job,
                    failed_stage="translating",
                    error_code="translation_batch_tree_invalid",
                    error_message="翻译批次计划与当前 source/config 不一致。",
                    trace_id=trace_id,
                )
                return self.translation_batch_repository.get_translation_batch(claimed.id) or claimed

    def _claim_translation_batch(
        self,
        batch: DocumentJobTranslationBatchRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord | None:
        current_job = self.job_repository.get_document_job(batch.job_id)
        if (
            current_job is None
            or current_job.status != "running"
            or current_job.stage != "translating"
            or current_job.retry_count != batch.generation
        ):
            return None
        try:
            summary = self.summarize_translation_generation(current_job)
        except TranslationBatchTreeInvalidError:
            self._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return None
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
            self._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if _is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划校验失败。",
                trace_id=trace_id,
            )
            return None
        if summary is not None and summary.outcome in {"failed", "completed", "canceled", "validating"}:
            self._finalize_translation_generation(
                current_job.id, generation=batch.generation, trace_id=trace_id,
            )
            return None
        try:
            _source_file, source_document_ir = self._read_translation_source(
                current_job, current_job.source_document_ir_file_id,
            )
            expected_plans = self._build_expected_translation_plans(current_job, source_document_ir)
        except TranslationBatchTreeInvalidError:
            self._finalize_translation_generation(
                current_job.id, generation=batch.generation, trace_id=trace_id,
            )
            return None
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
            if isinstance(exc, TranslationIntegrityError) and exc.code == "translation_request_budget_exceeded":
                _snapshot_job, installed_batches = self._get_translation_execution_snapshot(
                    current_job.id, generation=batch.generation,
                )
                failed = self.translation_batch_repository.update_translation_batch_if_current(
                    batch.id,
                    allowed_statuses={"pending", "queued"},
                    expected_generation=batch.generation,
                    expected_attempt_count=batch.attempt_count,
                    expected_lease_owner=batch.lease_owner,
                    expected_job_id=batch.job_id,
                    expected_job_status={"running"},
                    expected_job_stages={"translating"},
                    expected_plans=installed_batches,
                    status="failed",
                    error_code=exc.code,
                    error_message=str(exc),
                    retryable=False,
                    updated_at=utc_now(),
                )
                self._mark_failed(
                    current_job,
                    failed_stage="translating",
                    error_code="translation_failed",
                    error_message=str(exc),
                    trace_id=trace_id,
                )
                return None
            self._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if _is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划校验失败。",
                trace_id=trace_id,
            )
            return None
        now = utc_now()
        lease_owner = f"translation_batch_worker:{uuid4().hex}"
        try:
            claimed = self.translation_batch_repository.claim_translation_batch(
                batch.id,
                expected_generation=batch.generation,
                expected_attempt_count=batch.attempt_count,
                lease_owner=lease_owner,
                leased_at=now,
                lease_expires_at=now + timedelta(seconds=self.settings.translation_provider_batch_lease_seconds),
                provider_call_budget=batch.provider_call_budget,
                expected_plans=expected_plans,
            )
        except TranslationBatchTreeInvalidError:
            self._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return None
        except (FileNotFoundError, OSError, sqlite3.Error) as exc:
            self._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if _is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划读取失败。",
                trace_id=trace_id,
            )
            return None
        except Exception as exc:
            if not _is_metadata_storage_error(exc):
                raise
            self._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed",
                error_message="翻译批次计划读取失败。",
                trace_id=trace_id,
            )
            return None
        if claimed is None:
            self._reconcile_translation_batch_atomic_rejection(
                batch, generation=batch.generation, trace_id=trace_id,
            )
            return None
        job = self.job_repository.get_document_job(batch.job_id)
        if job is not None:
            self._record_event(
                job,
                event_type="translation_batch_running",
                stage="translating",
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

    def _reconcile_translation_batch_atomic_rejection(
        self,
        batch: DocumentJobTranslationBatchRecord,
        *,
        generation: int,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        """原子端口拒绝后重读同代快照，收口终态而不把普通竞争误报为失败。"""

        current_job, current_batches = self._get_translation_execution_snapshot(
            batch.job_id, generation=generation,
        )
        current_batch = next((item for item in current_batches if item.id == batch.id), None)
        if current_batch is None:
            current_batch = self.translation_batch_repository.get_translation_batch(batch.id) or batch
        if (
            current_job is None
            or current_job.retry_count != generation
            or current_job.status in {"succeeded", "failed", "canceled"}
            or current_job.stage not in {"translating", "translation_validating"}
        ):
            return current_batch
        try:
            summary = self.summarize_translation_generation(current_job, current_batches)
        except TranslationBatchTreeInvalidError:
            self._mark_failed(
                current_job,
                failed_stage=current_job.stage,
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return current_batch
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError):
            return current_batch
        if summary is not None and summary.outcome in {"failed", "completed", "canceled", "validating"}:
            self._finalize_translation_generation(
                current_job.id, generation=current_job.retry_count, trace_id=trace_id,
            )
            return self.translation_batch_repository.get_translation_batch(batch.id) or current_batch
        return current_batch

    def _fail_translation_batch_storage(
        self,
        batch: DocumentJobTranslationBatchRecord,
        job: DocumentJobRecord,
        *,
        expected_plans: list[TranslationRootPlan],
        error_message: str,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        """批次结果或状态写入失败时，以原代次安全收口且不重调 Provider。"""

        current = self.job_repository.get_document_job(batch.job_id)
        if current is None or current.retry_count != batch.generation:
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        self._mark_failed(
            job,
            failed_stage="translating",
            error_code="oss_failed",
            error_message=error_message,
            trace_id=trace_id,
        )
        failed_batch = self.translation_batch_repository.update_translation_batch_if_current(
            batch.id,
            allowed_statuses={"running"},
            expected_generation=batch.generation,
            expected_attempt_count=batch.attempt_count,
            expected_lease_owner=batch.lease_owner,
            expected_plans=expected_plans,
            status="failed",
            error_code="oss_failed",
            error_message=error_message,
            retryable=False,
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=utc_now(),
        )
        return failed_batch or self.translation_batch_repository.get_translation_batch(batch.id) or batch

    def _mark_translating_started(
        self, job: DocumentJobRecord, *, trace_id: str | None,
    ) -> DocumentJobRecord:
        """源 IR 已落盘后提交翻译阶段；事件失败时沿用已提交阶段收尾。"""

        if job.stage != "ir_converting":
            return job
        translating = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"ir_converting"},
            expected_retry_count=job.retry_count,
            stage="translating",
            progress=max(job.progress, 45),
            updated_at=utc_now(),
        )
        if translating is None:
            return self.job_repository.get_document_job(job.id) or job
        try:
            self._record_event(
                translating,
                event_type="stage_succeeded",
                stage="ir_converting",
                message="源 DocumentIR 转换已完成。",
                payload={"source_document_ir_file_id": translating.source_document_ir_file_id},
                trace_id=trace_id,
            )
            self._record_event(
                translating,
                event_type="stage_started",
                stage="translating",
                message="DocumentIR 翻译已开始。",
                payload={"source_document_ir_file_id": translating.source_document_ir_file_id},
                trace_id=trace_id,
            )
        except Exception as exc:
            return self._fail_stage_attempt(translating, exc, trace_id=trace_id)
        return translating

    def _handle_translation_batch_failure(
        self,
        batch: DocumentJobTranslationBatchRecord,
        job: DocumentJobRecord,
        *,
        error: Exception,
        recorder: TranslationCallAuditRecorder | None,
        trace_id: str | None,
        duration_ms: int,
    ) -> DocumentJobTranslationBatchRecord:
        error_code = self._translation_batch_error_code(error)
        error_message = str(error) if isinstance(error, TranslationIntegrityError) else "翻译 Provider 调用或批次处理失败。"
        current = self.job_repository.get_document_job(job.id)
        if current is None or current.retry_count != batch.generation or current.status != "running" or current.stage != "translating":
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        try:
            _source_file, source_document_ir = self._read_translation_source(
                current, batch.source_document_ir_file_id,
            )
            expected_plans = self._build_expected_translation_plans(current, source_document_ir)
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError) as exc:
            self._mark_failed(
                current,
                failed_stage="translating",
                error_code="oss_failed" if isinstance(exc, (FileNotFoundError, OSError)) else "translation_failed",
                error_message="翻译批次计划重建失败。",
                trace_id=trace_id,
            )
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        if self._should_split_translation_batch(batch, error):
            try:
                split = self._split_translation_batch(
                    batch,
                    job,
                    error_code=error_code,
                    error_message=error_message,
                    error=error,
                    recorder=recorder,
                    trace_id=trace_id,
                    duration_ms=duration_ms,
                )
            except TranslationBatchTreeInvalidError:
                latest = self.job_repository.get_document_job(batch.job_id)
                if latest is None or latest.retry_count != batch.generation:
                    return self.translation_batch_repository.get_translation_batch(batch.id) or batch
                self._mark_failed(
                    job,
                    failed_stage="translating",
                    error_code="translation_batch_tree_invalid",
                    error_message="翻译批次计划与当前 source/config 不一致。",
                    trace_id=trace_id,
                )
                return self.translation_batch_repository.get_translation_batch(batch.id) or batch
            self._enqueue_runnable_translation_batches(job, generation=batch.generation, trace_id=trace_id)
            return split

        retryable = (
            batch.attempt_count < batch.max_attempts
            and self._provider_call_budget_remaining(job, batch)
        )
        try:
            failed = self.translation_batch_repository.update_translation_batch_if_current(
                batch.id,
                allowed_statuses={"running"},
                expected_generation=batch.generation,
                expected_attempt_count=batch.attempt_count,
                expected_lease_owner=batch.lease_owner,
                expected_job_id=batch.job_id,
                expected_job_status={"running"},
                expected_job_stages={"translating"},
                expected_plans=expected_plans,
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
        except Exception as exc:
            if not _is_metadata_storage_error(exc):
                raise
            self._mark_failed(
                current,
                failed_stage="translating",
                error_code="oss_failed",
                error_message="翻译批次状态写入失败。",
                trace_id=trace_id,
            )
            return self.translation_batch_repository.get_translation_batch(batch.id) or batch
        if failed is None:
            return self._reconcile_translation_batch_atomic_rejection(
                batch, generation=batch.generation, trace_id=trace_id,
            )
        self._record_event(
            job,
            event_type="translation_batch_failed",
            stage="translating",
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
            duration_ms=duration_ms,
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
        duration_ms: int,
    ) -> DocumentJobTranslationBatchRecord:
        _source_file, source_document_ir = self._read_translation_source(job, batch.source_document_ir_file_id)
        targets, items = self.document_ir_translation_service.extract_translation_items(source_document_ir)
        targets_by_id = {target.item_id: target for target in targets}
        items_by_id = {item.id: item for item in items}
        midpoint = max(1, len(batch.item_ids) // 2)
        child_item_groups = [batch.item_ids[:midpoint], batch.item_ids[midpoint:]]
        now = utc_now()
        child_records: list[DocumentJobTranslationBatchRecord] = []
        for child_index, child_item_ids in enumerate(child_item_groups, start=1):
            if not child_item_ids:
                continue
            child_id = f"{batch.id}_s{batch.split_level + 1}_{child_index:02d}"
            page_start, page_end = self._page_range_for_item_ids(child_item_ids, targets_by_id)
            char_count = sum(len(items_by_id[item_id].text) for item_id in child_item_ids)
            child_records.append(
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
        expected_plans = self._build_expected_translation_plans(job, source_document_ir)
        split_result = self.translation_batch_repository.split_translation_batch(
            batch.id,
            expected_generation=batch.generation,
            expected_attempt_count=batch.attempt_count,
            expected_lease_owner=batch.lease_owner or "",
            expected_plans=expected_plans,
            children=child_records,
        )
        if split_result is None:
            return self._reconcile_translation_batch_atomic_rejection(
                batch, generation=batch.generation, trace_id=trace_id,
            )
        split, _children = split_result
        annotated = self.translation_batch_repository.update_translation_batch_if_current(
            split.id,
            allowed_statuses={"split"},
            expected_generation=split.generation,
            expected_attempt_count=split.attempt_count,
            expected_lease_owner=None,
            expected_job_id=split.job_id,
            expected_job_status={"running"},
            expected_job_stages={"translating"},
            expected_plans=expected_plans,
            ai_call_log_file_ids=self._recorder_call_log_file_ids(recorder),
            debug_archive_file_ids=self._recorder_debug_archive_file_ids(recorder),
            finish_reason=error.finish_reason if isinstance(error, TranslationProviderResponseError) else None,
            usage=error.usage if isinstance(error, TranslationProviderResponseError) else {},
            response_id=error.response_id if isinstance(error, TranslationProviderResponseError) else None,
            error_code=error_code,
            error_message=error_message,
            retryable=False,
            truncation_retry=True,
            updated_at=now,
        )
        if annotated is not None:
            split = annotated
        else:
            return self._reconcile_translation_batch_atomic_rejection(
                split, generation=split.generation, trace_id=trace_id,
            )
        self._record_event(
            job,
            event_type="translation_batch_split",
            stage="translating",
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
            duration_ms=duration_ms,
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
        if job.status != "running" or job.stage not in {"translating", "translation_validating"} or job.retry_count != generation:
            return job
        failure_stage = job.stage
        self._reset_expired_translation_batch_leases(job, generation=generation, trace_id=trace_id)
        snapshot_job, batches = self._get_translation_execution_snapshot(job.id, generation=generation)
        if snapshot_job is None or snapshot_job.retry_count != generation:
            return snapshot_job or job
        job = snapshot_job
        if job.status in {"succeeded", "failed", "canceled"}:
            return job
        failure_stage = job.stage
        try:
            summary = self.summarize_translation_generation(job, batches)
        except TranslationBatchTreeInvalidError:
            return self._mark_failed(
                job,
                failed_stage=failure_stage,
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError) as exc:
            return self._mark_failed(
                job,
                failed_stage=failure_stage,
                error_code="translation_failed",
                error_message=f"翻译批次计划校验失败: {self._translation_batch_error_code(exc)}",
                trace_id=trace_id,
            )
        if summary is None:
            error_code = "translation_batch_tree_invalid"
            batch_source_ids = {batch.source_document_ir_file_id for batch in batches}
            if batches and job.source_document_ir_file_id not in batch_source_ids:
                # 当前任务指针与本代批次绑定不一致，属于完整性/代次错误，不是对象存储缺失。
                error_code = "translation_failed"
            else:
                try:
                    self._read_translation_source(job, job.source_document_ir_file_id)
                except (FileNotFoundError, OSError, sqlite3.Error):
                    error_code = "oss_failed"
                except (DocumentIRTranslationError, TranslationIntegrityError, ValueError):
                    error_code = "translation_failed"
            return self._mark_failed(
                job,
                failed_stage=failure_stage,
                error_code=error_code,
                error_message="翻译批次无法由当前 source/config 重建权威计划。",
                trace_id=trace_id,
            )
        leaf_batches = [batch for batch in batches if batch.status != "split"]
        if summary.outcome == "failed":
            return self._mark_failed(
                job,
                failed_stage=failure_stage,
                error_code="translation_failed",
                error_message=(
                    f"翻译批次失败: {summary.reason_code or 'translation_failed'}"
                    f" {summary.reason_message or ''}"
                ).strip(),
                trace_id=trace_id,
            )
        if summary.outcome in {"not_started", "running", "retrying"}:
            self._enqueue_runnable_translation_batches(job, generation=generation, trace_id=trace_id)
            return self.job_repository.get_document_job(job.id) or job
        if summary.outcome == "canceled":
            return job
        if summary.outcome not in {"completed", "validating"}:
            return job
        if all(batch.status == "succeeded" for batch in leaf_batches):
            if job.stage == "translating":
                stage_started_at = time.perf_counter()
                validating = self.job_repository.update_document_job_if_current(
                    job.id,
                    allowed_statuses={"running"},
                    allowed_stages={"translating"},
                    expected_retry_count=generation,
                    stage="translation_validating",
                    progress=max(job.progress, 55),
                    updated_at=utc_now(),
                )
                if validating is None:
                    return self.job_repository.get_document_job(job.id) or job
                try:
                    self._record_event(
                        validating,
                        event_type="stage_succeeded",
                        stage="translating",
                        message="翻译批次已全部完成。",
                        payload={"batch_count": len(leaf_batches)},
                        trace_id=trace_id,
                        duration_ms=int((time.perf_counter() - stage_started_at) * 1000),
                    )
                    self._record_event(
                        validating,
                        event_type="stage_started",
                        stage="translation_validating",
                        message="翻译完整性校验已开始。",
                        payload={"batch_count": len(leaf_batches)},
                        trace_id=trace_id,
                    )
                except Exception as exc:
                    return self._fail_stage_attempt(validating, exc, trace_id=trace_id)
                job = validating
            started_at = time.perf_counter()
            try:
                updated = self._register_translated_document_ir_and_continue(
                    job,
                    succeeded_batches=leaf_batches,
                    trace_id=trace_id,
                )
            except Exception as exc:
                error_code = (
                    "oss_failed" if isinstance(exc, (ApiError, FileNotFoundError, OSError))
                    else "translation_failed"
                )
                return self._mark_failed(
                    job,
                    failed_stage="translation_validating",
                    error_code=error_code,
                    error_message=str(exc),
                    trace_id=trace_id,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
            if updated.status != "running" or updated.stage != "rendering" or updated.retry_count != generation:
                return updated
            try:
                self._record_event(
                    updated,
                    event_type="stage_succeeded",
                    stage="translation_validating",
                    message="翻译结果完整性校验通过，DocumentIR 已保存。",
                    payload={"document_ir_file_id": updated.document_ir_file_id, "batch_count": len(leaf_batches)},
                    trace_id=trace_id,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
            except Exception as exc:
                return self._fail_stage_attempt(updated, exc, trace_id=trace_id)
            return self.execute_job(updated.id, trace_id=trace_id) or updated
        return job

    def _register_translated_document_ir_and_continue(
        self,
        job: DocumentJobRecord,
        *,
        succeeded_batches: list[DocumentJobTranslationBatchRecord],
        trace_id: str | None,
    ) -> DocumentJobRecord:
        current = self.job_repository.get_document_job(job.id)
        if current is None or current.retry_count != job.retry_count or current.status != "running" or current.stage != "translation_validating":
            return current or job
        job = current
        started_at = time.perf_counter()
        try:
            source_file, source_document_ir = self._read_translation_source(job, job.source_document_ir_file_id)
        except (DocumentIRTranslationError, TranslationIntegrityError, ValueError) as exc:
            return self._mark_failed(
                job,
                failed_stage="translation_validating",
                error_code="translation_failed",
                error_message=f"翻译 source 校验失败: {self._translation_batch_error_code(exc)}",
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except (FileNotFoundError, OSError) as exc:
            return self._mark_failed(
                job,
                failed_stage="translation_validating",
                error_code="oss_failed",
                error_message=f"翻译 source 校验失败: {self._translation_batch_error_code(exc)}",
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        try:
            translated = source_document_ir.model_copy(deep=True)
            targets, items = self.document_ir_translation_service.extract_translation_items(translated)
            replacements = self._load_batch_replacements(job, source_file, items, succeeded_batches)
        except (DocumentIRTranslationError, TranslationIntegrityError, TranslationProviderResponseError, ValueError, FileNotFoundError, OSError) as exc:
            error_code = (
                "oss_failed" if isinstance(exc, (FileNotFoundError, OSError))
                else "translation_fan_in_mismatch" if getattr(exc, "code", None) == "translation_fan_in_mismatch"
                else "translation_failed"
            )
            return self._mark_failed(
                job,
                failed_stage="translation_validating",
                error_code=error_code,
                error_message=f"翻译批次合并校验失败: {self._translation_batch_error_code(exc)}",
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        expected_ids = [item.id for item in items]
        missing_ids = [item_id for item_id in expected_ids if item_id not in replacements]
        extra_ids = sorted(set(replacements) - set(expected_ids))
        if missing_ids or extra_ids:
            return self._mark_failed(
                job,
                failed_stage="translation_validating",
                error_code="translation_fan_in_mismatch",
                error_message=f"翻译批次合并结果不完整: missing={len(missing_ids)} extra={len(extra_ids)}",
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        self.document_ir_translation_service.apply_replacements(translated, targets, replacements)
        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            raise DocumentIRTranslationError("当前任务不是翻译任务。")
        translated.metadata.document_language = self.document_ir_translation_service._target_document_language(spec.language_pair)
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
        ir_content = translated.model_dump_json(indent=2).encode("utf-8")
        try:
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
                    "source_document_ir_file_id": job.source_document_ir_file_id,
                    "image_asset_count": len(job.image_asset_file_ids),
                    "retry_count": job.retry_count,
                    "translation": translation_metadata,
                    **self._document_ir_layout_metadata(translated),
                },
            )
        except (RuntimeError, ValueError) as exc:
            raise OSError(str(exc)) from exc
        updated = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"translation_validating"},
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
            stage="translation_validating",
            message="翻译后的 DocumentIR 已保存。",
            payload={
                "file_id": ir_file.id,
                "file_type": ir_file.file_type,
                "object_key": ir_file.object_key,
                **self._document_ir_layout_metadata(translated),
            },
            trace_id=trace_id,
        )
        return updated

    def _read_translation_artifact(
        self, job: DocumentJobRecord, file_id: str, *, file_type: str,
    ) -> tuple[DocumentFileRecord, bytes]:
        """按已登记的对象读取并验证字节；路径模板和 payload 不能自证归属。"""
        record = self._get_uploaded_file(file_id)
        if (
            record.job_id != job.id or record.tenant_id != job.tenant_id
            or record.company_id != job.company_id or record.file_type != file_type
            or (file_type == "translation_batch_result" and (
                type(record.metadata.get("retry_count")) is not int
                or record.metadata["retry_count"] != job.retry_count
            ))
        ):
            raise DocumentIRTranslationError("翻译 Artifact 来源或代次不一致。", code="translation_integrity_evidence_mismatch")
        content = self.file_service.read_file_content(record)
        checksum = "sha256:" + hashlib.sha256(content).hexdigest()
        if record.checksum_sha256 != checksum or record.size_bytes != len(content):
            raise DocumentIRTranslationError("翻译 Artifact 字节校验失败。", code="translation_integrity_evidence_mismatch")
        return record, content

    def _read_translation_source(
        self, job: DocumentJobRecord, file_id: str | None,
    ) -> tuple[DocumentFileRecord, DocumentIR]:
        if not file_id or file_id != job.source_document_ir_file_id:
            raise DocumentIRTranslationError("翻译 source IR 引用不一致。", code="translation_integrity_evidence_mismatch")
        # retry 沿用任务权威指针指向的不可变源件；创建代次不等于本次消费代次。
        record, content = self._read_translation_artifact(job, file_id, file_type="document_ir")
        translation = record.metadata.get("translation")
        if not isinstance(translation, dict) or translation.get("role") != "source" or translation.get("applied") is not False:
            raise DocumentIRTranslationError("翻译 source IR 角色不一致。", code="translation_integrity_evidence_mismatch")
        document_ir = DocumentIR.model_validate_json(content)
        if document_ir.metadata.job_id != job.id or document_ir.metadata.source_file_id != job.source_file_id:
            raise DocumentIRTranslationError("翻译 source IR 文档来源不一致。", code="translation_integrity_evidence_mismatch")
        return record, document_ir

    def _translation_integrity_binding(
        self, job: DocumentJobRecord, batch: DocumentJobTranslationBatchRecord,
        source_file: DocumentFileRecord, profile: TranslationProfileSnapshot | None,
        term_version: TermVersionSnapshot | None,
    ) -> TranslationIntegrityBinding:
        spec = spec_for_document_job_mode(job.mode)
        term_hash = term_version.snapshot_hash if term_version is not None else None
        term_id = term_version.term_version_id if term_version is not None else job.term_version_id
        if (
            batch.job_id != job.id or batch.job_retry_count != job.retry_count
            or batch.generation != job.retry_count or batch.source_document_ir_file_id != source_file.id
            or batch.language_pair != spec.language_pair or batch.term_snapshot_hash != term_hash
            or batch.term_version_id != term_id
        ):
            raise DocumentIRTranslationError("翻译批次绑定与当前任务快照不一致。", code="translation_integrity_evidence_mismatch")
        return TranslationIntegrityBinding(
            job_id=job.id, batch_id=batch.id, root_batch_id=batch.root_batch_id,
            parent_batch_id=batch.parent_batch_id, attempt=batch.attempt_count, generation=batch.generation,
            source_document_ir_file_id=source_file.id, source_document_ir_sha256=source_file.checksum_sha256,
            profile_snapshot_hash=profile.snapshot_hash if profile is not None else None,
            prompt_content_hash=profile.prompt.content_hash if profile is not None else None,
            term_snapshot_hash=term_hash,
        )

    def _load_batch_replacements(
        self, job: DocumentJobRecord, source_file: DocumentFileRecord,
        source_items: list[TranslationTextItem], batches: list[DocumentJobTranslationBatchRecord],
    ) -> dict[str, str]:
        """对全部叶子的本地来源、恢复文本和证据重核，全部通过后才交给 apply。"""
        replacements: dict[str, str] = {}
        spec = spec_for_document_job_mode(job.mode)
        profile = self._translation_profile_for_job(job, language_pair=spec.language_pair)
        term_version = self._resolve_term_version_for_job(job)
        for selected in sorted(batches, key=lambda item: (item.page_start or 0, item.created_at, item.id)):
            batch = self.translation_batch_repository.get_translation_batch(selected.id)
            if batch is None or batch.status != "succeeded" or not batch.result_file_id or (
                batch.attempt_count != selected.attempt_count
            ):
                raise DocumentIRTranslationError("翻译成功批次已变化或缺少结果。", code="translation_integrity_evidence_mismatch")
            binding = self._translation_integrity_binding(job, batch, source_file, profile, term_version)
            local_items = tuple(item for item in source_items if item.id in batch.item_ids)
            if (
                tuple(item.id for item in local_items) != tuple(batch.item_ids)
                or batch.item_count != len(local_items)
                or batch.char_count != sum(len(item.text) for item in local_items)
            ):
                raise DocumentIRTranslationError("翻译批次有序源项边界不一致。", code="translation_integrity_evidence_mismatch")
            candidate = self._get_uploaded_file(batch.result_file_id)
            candidate_payload = json.loads(self.file_service.read_file_content(candidate))
            candidate_items = candidate_payload.get("items") if isinstance(candidate_payload, dict) else None
            if isinstance(candidate_items, list):
                candidate_ids = [item.get("id") for item in candidate_items if isinstance(item, dict)]
                if set(candidate_ids) != set(batch.item_ids) and len(candidate_ids) == len(set(candidate_ids)):
                    raise DocumentIRTranslationError(
                        "翻译批次合并结果不完整。", code="translation_fan_in_mismatch",
                    )
            result_file, content = self._read_translation_artifact(job, batch.result_file_id, file_type="translation_batch_result")
            payload = json.loads(content)
            raw_items = payload.get("items") if isinstance(payload, dict) else None
            if isinstance(raw_items, list):
                raw_item_ids = [item.get("id") for item in raw_items if isinstance(item, dict)]
                if set(raw_item_ids) != set(batch.item_ids) and len(raw_item_ids) == len(set(raw_item_ids)):
                    raise DocumentIRTranslationError(
                        "翻译批次合并结果不完整。", code="translation_fan_in_mismatch",
                    )
            envelope = {
                "job_id": job.id, "batch_id": batch.id, "root_batch_id": batch.root_batch_id,
                "parent_batch_id": batch.parent_batch_id, "generation": batch.generation,
                "attempt": batch.attempt_count, "source_document_ir_file_id": source_file.id,
                "language_pair": batch.language_pair,
            }
            if (
                not isinstance(payload, dict) or payload.get("schema_version") != "translation-batch-result/v1"
                or any(key not in payload or type(payload[key]) is not type(value) or payload[key] != value for key, value in envelope.items())
                or any(key not in result_file.metadata or type(result_file.metadata[key]) is not type(value) or result_file.metadata[key] != value for key, value in envelope.items() if key not in {"job_id", "attempt"})
                or type(result_file.metadata.get("attempt_count")) is not int
                or result_file.metadata["attempt_count"] != batch.attempt_count
            ):
                raise DocumentIRTranslationError("翻译结果 Artifact 关联不一致。", code="translation_integrity_evidence_mismatch")
            restored = OpenAICompatibleTranslationProvider._parse_items({"items": payload.get("items")})
            validated = self.document_ir_translation_service.validator.validate_persisted(
                local_items, restored, payload.get("integrity"), binding=binding,
            )
            if replacements.keys() & validated.replacements.keys():
                raise DocumentIRTranslationError("翻译叶子批次包含重复合并项。", code="translation_integrity_item_duplicate")
            replacements.update(validated.replacements)
        return replacements

    def _register_translation_batch_result(
        self,
        job: DocumentJobRecord,
        *,
        batch: DocumentJobTranslationBatchRecord,
        result: TranslationProviderResult,
        validated: ValidatedTranslationBatch,
        integrity: TranslationIntegrityEvidence,
        recorder: TranslationCallAuditRecorder | None,
    ) -> DocumentFileRecord:
        payload = {
            "schema_version": "translation-batch-result/v1",
            "job_id": job.id,
            "batch_id": batch.id,
            "root_batch_id": batch.root_batch_id,
            "parent_batch_id": batch.parent_batch_id,
            "attempt": batch.attempt_count,
            "generation": batch.generation,
            "source_document_ir_file_id": batch.source_document_ir_file_id,
            "language_pair": batch.language_pair,
            "items": [{"id": item.id, "text": item.text} for item in validated.items],
            "integrity": integrity.to_dict(),
            "provider": {
                "finish_reason": result.finish_reason,
                "usage": result.usage,
                "response_id": result.response_id,
                "provider_trace_id": result.provider_trace_id,
                "content_length": result.content_length,
                "content_sha256": result.content_sha256,
            },
        }
        try:
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
                    "root_batch_id": batch.root_batch_id,
                    "parent_batch_id": batch.parent_batch_id,
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
        except (RuntimeError, ValueError, FileNotFoundError, OSError, sqlite3.Error) as exc:
            raise _TranslationBatchStorageError("翻译批次结果 Artifact 写入失败。") from exc
        except Exception as exc:
            if not _is_metadata_storage_error(exc):
                raise
            raise _TranslationBatchStorageError("翻译批次结果 Artifact 写入失败。") from exc

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
            current, batches = self._get_translation_execution_snapshot(
                job.id, generation=generation,
            )
            if (
                current is None or current.status != "running" or current.stage != "translating"
                or current.retry_count != generation
                or self._mark_timed_out_if_needed(current, trace_id=trace_id) is not None
            ):
                return
            job = current
            summary = self.summarize_translation_generation(job, batches)
            if summary is not None and summary.outcome in {"failed", "completed", "validating", "canceled"}:
                self._finalize_translation_generation(job.id, generation=generation, trace_id=trace_id)
                return
            leaf_batches = [batch for batch in batches if batch.status != "split"]
            active_count = sum(1 for batch in leaf_batches if batch.status in {"queued", "running"})
            max_active = max(1, self.settings.translation_provider_batch_max_concurrency_per_job)
            if active_count >= max_active:
                return
            candidate = self._next_runnable_translation_batch(job, leaf_batches)
            if candidate is None:
                return
            try:
                _source_file, source_document_ir = self._read_translation_source(
                    job, job.source_document_ir_file_id,
                )
                expected_plans = self._build_expected_translation_plans(job, source_document_ir)
            except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError):
                self._finalize_translation_generation(job.id, generation=generation, trace_id=trace_id)
                return
            try:
                queued = self.translation_batch_repository.enqueue_translation_batch(
                    candidate.id,
                    expected_generation=candidate.generation,
                    expected_attempt_count=candidate.attempt_count,
                    provider_call_budget=candidate.provider_call_budget,
                    expected_plans=expected_plans,
                )
            except TranslationBatchTreeInvalidError:
                self._mark_failed(
                    job,
                    failed_stage=job.stage,
                    error_code="translation_batch_tree_invalid",
                    error_message="翻译批次计划与当前 source/config 不一致。",
                    trace_id=trace_id,
                )
                return
            except (FileNotFoundError, OSError):
                self._mark_failed(
                    job,
                    failed_stage=job.stage,
                    error_code="oss_failed",
                    error_message="翻译批次队列状态写入失败。",
                    trace_id=trace_id,
                )
                return
            if queued is None:
                self._reconcile_translation_batch_atomic_rejection(
                    candidate, generation=generation, trace_id=trace_id,
                )
                return
            self._record_event(
                job,
                event_type="translation_batch_queued",
                stage="translating",
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
        current, batches = self._get_translation_execution_snapshot(
            job.id, generation=generation,
        )
        if (
            current is None or current.status != "running" or current.stage != "translating"
            or current.retry_count != generation
        ):
            return
        now = utc_now()
        try:
            _source_file, source_document_ir = self._read_translation_source(
                current, current.source_document_ir_file_id,
            )
            expected_plans = self._build_expected_translation_plans(current, source_document_ir)
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError):
            # finalizer 随后会用同一 source/config 失败结论收口；这里不以旧批次自证根树。
            return
        for batch in batches:
            if batch.status != "running" or batch.lease_expires_at is None or batch.lease_expires_at > now:
                continue
            retryable = batch.attempt_count < batch.max_attempts and self._provider_call_budget_remaining(job, batch)
            expired = self.translation_batch_repository.release_translation_batch_lease(
                batch.id,
                expected_generation=batch.generation,
                expected_attempt_count=batch.attempt_count,
                expected_lease_owner=batch.lease_owner or "",
                now=now,
                expected_plans=expected_plans,
                error_code="translation_batch_lease_expired",
                error_message="翻译批次租约已过期，等待重新投递。",
                retryable=retryable,
                updated_at=now,
            )
            if expired is None:
                self._reconcile_translation_batch_atomic_rejection(
                    batch, generation=generation, trace_id=trace_id,
                )
                continue
            self._record_event(
                job,
                event_type="translation_batch_failed",
                stage="translating",
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
            expected_attempt_count=batch.attempt_count,
            expected_lease_owner=batch.lease_owner,
            expected_job_id=batch.job_id,
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
                stage="translating",
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
        snapshot_job, batches = self._get_translation_execution_snapshot(
            batch.job_id, generation=batch.generation,
        )
        if snapshot_job is None or snapshot_job.retry_count != batch.generation:
            return False
        attempts = sum(item.attempt_count for item in batches)
        return attempts < batch.provider_call_budget

    def _translation_batch_error_code(self, error: Exception) -> str:
        if isinstance(error, (TranslationIntegrityError, DocumentIRTranslationError)):
            return error.code
        if isinstance(error, TranslationProviderResponseError) and error.suspected_truncation:
            return "translation_provider_truncated"
        if isinstance(error, (TranslationProviderResponseError, ValueError, KeyError)):
            return "translation_provider_invalid_response"
        return "translation_provider_failed"

    def _translation_profile_batch_limits(
        self,
        profile: TranslationProfileSnapshot | None,
    ) -> tuple[int, int]:
        if profile is None:
            return (
                max(1, int(self.settings.translation_max_pages)),
                max(1, int(self.settings.translation_max_chars)),
            )
        return (
            max(1, int(profile.max_pages_per_batch)),
            max(1, int(profile.max_chars_per_batch)),
        )

    def _translation_profile_for_job(
        self,
        job: DocumentJobRecord,
        *,
        language_pair: str,
    ) -> TranslationProfileSnapshot | None:
        """读取任务绑定的不可变 Profile；无资源快照仅表示 legacy mode。"""

        resources = job.request_snapshot.get("resources")
        if resources is None:
            return None
        if not isinstance(resources, dict):
            raise DocumentIRTranslationError("任务资源快照格式非法。")
        try:
            snapshot = JobResourceSnapshot.model_validate(resources)
        except ValueError as exc:
            raise DocumentIRTranslationError(f"任务资源快照格式非法: {exc}") from exc
        if snapshot.translation_profile is None:
            raise DocumentIRTranslationError("翻译任务缺少绑定的 Translation Profile。")
        if self.job_resource_snapshot_service is None:
            raise DocumentIRTranslationError(
                "当前 Worker 缺少 resource snapshot service。"
            )
        try:
            profile = self.job_resource_snapshot_service.materialize_translation_profile(
                snapshot.translation_profile
            )
        except (JobResourceSnapshotError, FileNotFoundError, ValueError) as exc:
            raise DocumentIRTranslationError(str(exc)) from exc
        if profile.language_pair != language_pair:
            raise DocumentIRTranslationError(
                "任务绑定的 Translation Profile 语言方向不匹配: "
                f"expected={language_pair} actual={profile.language_pair}"
            )

        prompt_metadata = (
            snapshot.translation_prompt_id,
            snapshot.translation_prompt_content_hash,
        )
        if any(value is not None for value in prompt_metadata):
            if (
                snapshot.translation_prompt_id != profile.prompt.id
                or snapshot.translation_prompt_content_hash
                != profile.prompt.content_hash
            ):
                raise DocumentIRTranslationError(
                    "任务绑定的 Translation Profile Prompt 元数据不匹配。"
                )
        return profile

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
            translation_profile = self._translation_profile_for_job(
                job,
                language_pair=spec.language_pair,
            )
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
            "prompt_id": (
                translation_profile.prompt.id
                if translation_profile is not None
                else None
            ),
            "prompt_content_hash": (
                translation_profile.prompt.content_hash
                if translation_profile is not None
                else None
            ),
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
                prompt=(
                    translation_profile.prompt
                    if translation_profile is not None
                    else None
                ),
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
                stage="translating",
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
                stage="translating",
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
        attempt = job
        validating_legacy = False
        try:
            current = self.job_repository.get_document_job(job.id) or job
            if current.retry_count != job.retry_count or current.status != "running":
                return current
            if current.prepared_result is not None:
                return self._finish_prepared_result(current, trace_id=trace_id)
            # 明确历史指针优先保留；legacy 扫描必须唯一且可验证。
            if job.stage != "quality_checking":
                validating_legacy = True
                existing_result = self._get_existing_result_file(job)
                validating_legacy = False
                if existing_result is not None:
                    uploading = self.job_repository.update_document_job_if_current(
                        job.id, allowed_statuses={"running"}, allowed_stages={"rendering", "uploading"},
                        expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id,
                        require_no_prepared_result=True, stage="uploading", updated_at=utc_now(),
                    )
                    if uploading is None:
                        return self._finish_selected_or_current(job, trace_id=trace_id)
                    if job.result_file_id is not None:
                        return self._mark_succeeded(uploading, trace_id=trace_id)
                    prepared = self.job_repository.prepare_document_job_result(
                        job.id, expected_retry_count=job.retry_count,
                        expected_document_ir_file_id=job.document_ir_file_id, candidate=existing_result,
                    )
                    if prepared is None:
                        return self._finish_selected_or_current(job, trace_id=trace_id)
                    return self._finish_prepared_result(prepared, trace_id=trace_id)
            attempt = job
            recovery_from = job.stage if job.stage in {"quality_checking", "uploading"} else None
            rendering = job
            if recovery_from is not None:
                rendering = self.job_repository.update_document_job_if_current(
                    job.id, allowed_statuses={"running"}, allowed_stages={recovery_from},
                    expected_retry_count=job.retry_count, expected_document_ir_file_id=job.document_ir_file_id,
                    require_no_prepared_result=True, stage="rendering", updated_at=utc_now(),
                )
                if rendering is None:
                    return self._finish_selected_or_current(job, trace_id=trace_id)
            attempt = rendering
            self._record_event(
                rendering,
                event_type="stage_started",
                stage="rendering",
                message="内存中的 Word 内容已丢失，重新渲染并校验。" if recovery_from else "Word 渲染已开始。",
                payload={
                    "document_ir_file_id": rendering.document_ir_file_id,
                    "template_version_id": rendering.template_version_id,
                    **({"recovery_from": recovery_from} if recovery_from else {}),
                },
                trace_id=trace_id,
            )
            render_started_at = time.perf_counter()

            ir_file = self._get_document_ir_file(rendering)
            document_ir = DocumentIR.model_validate_json(self.file_service.read_file_content(ir_file))
            layout_plan = build_layout_plan(document_ir)
            snapshot_resources = rendering.request_snapshot.get("resources")
            snapshot_template = snapshot_resources.get("template") if isinstance(snapshot_resources, dict) else None
            draft_was_authorized_at_creation = (
                isinstance(snapshot_template, dict)
                and snapshot_template.get("status") == "draft"
                and rendering.template_version_id
                == f"{snapshot_template.get('resource_id')}@{snapshot_template.get('version')}"
            )
            # 仅允许执行创建阶段已固化 draft 快照的验证任务，legacy 或不一致记录继续按 published 校验。
            template_selection = self.template_read_service.resolve_template_version(
                rendering.template_version_id,
                allow_draft=draft_was_authorized_at_creation,
            )
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
            checking = self.job_repository.update_document_job_if_current(
                rendering.id,
                allowed_statuses={"running"},
                allowed_stages={"rendering"},
                expected_retry_count=rendering.retry_count,
                expected_document_ir_file_id=rendering.document_ir_file_id, require_no_prepared_result=True,
                status="running",
                stage="quality_checking",
                progress=max(rendering.progress, 80),
                template_version_id=template_selection.template_version_id,
                updated_at=utc_now(),
            )
            if checking is None:
                return self._finish_selected_or_current(rendering, trace_id=trace_id)
            attempt = checking
            self._record_event(
                checking,
                event_type="stage_succeeded",
                stage="rendering",
                message="Word 渲染已完成。",
                payload={
                    "document_ir_file_id": ir_file.id,
                    "template_version_id": template_selection.template_version_id,
                    "block_count": len(document_ir.blocks),
                },
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - render_started_at) * 1000),
            )
            self._record_event(
                checking, event_type="stage_started", stage="quality_checking",
                message="Word 文档质量检查已开始。", payload={"document_ir_file_id": ir_file.id}, trace_id=trace_id,
            )
            quality_started_at = time.perf_counter()
            try:
                renderer_metadata = build_renderer_evidence(document_ir, word_content, layout_plan)
                ensure_renderer_integrity(renderer_metadata)
            except Exception as exc:
                failed = self._mark_failed(
                    checking, failed_stage="quality_checking", error_code="render_failed",
                    error_message=str(exc), trace_id=trace_id,
                    duration_ms=int((time.perf_counter() - quality_started_at) * 1000),
                )
                if failed.status == "running" and failed.retry_count == checking.retry_count and failed.prepared_result is not None:
                    return self._finish_prepared_result(failed, trace_id=trace_id)
                return failed
            uploading = self.job_repository.update_document_job_if_current(
                checking.id, allowed_statuses={"running"}, allowed_stages={"quality_checking"},
                expected_retry_count=checking.retry_count, expected_document_ir_file_id=checking.document_ir_file_id,
                require_no_prepared_result=True, stage="uploading",
                progress=max(checking.progress, 85), updated_at=utc_now(),
            )
            if uploading is None:
                return self._finish_selected_or_current(checking, trace_id=trace_id)
            attempt = uploading
            self._record_event(
                uploading, event_type="stage_succeeded", stage="quality_checking",
                message="Word 文档质量检查已通过。", payload={"document_ir_file_id": ir_file.id, **renderer_metadata},
                trace_id=trace_id, duration_ms=int((time.perf_counter() - quality_started_at) * 1000),
            )
            self._record_event(
                uploading,
                event_type="stage_started",
                stage="uploading",
                message="生成 Word 上传登记已开始。",
                payload={"template_version_id": template_selection.template_version_id},
                trace_id=trace_id,
            )
            word_file = self.file_service.register_result_candidate(
                tenant_id=uploading.tenant_id,
                company_id=uploading.company_id,
                job_id=uploading.id,
                created_by=uploading.created_by,
                filename=self._result_filename(uploading),
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
            prepared = self.job_repository.prepare_document_job_result(
                uploading.id, expected_retry_count=uploading.retry_count,
                expected_document_ir_file_id=ir_file.id, candidate=word_file,
            )
            if prepared is None:
                return self._finish_selected_or_current(uploading, trace_id=trace_id)
            return self._finish_prepared_result(prepared, trace_id=trace_id)
        except Exception as exc:
            failed_stage, error_code = self._classify_worker_failure(exc, attempt)
            if not isinstance(exc, (ApiError, FileNotFoundError, OSError, ValueError, RuntimeError, MinerUError, zipfile.BadZipFile)):
                error_code = "document_job_unexpected_error"
                self.logger.exception("[trace_id=%s job_id=%s stage=%s status=unexpected_error]", trace_id, job.id, failed_stage)
            if validating_legacy:
                failed_stage, error_code = "uploading", "oss_failed"
            failed = self._mark_failed(attempt, failed_stage=failed_stage, error_code=error_code,
                                       error_message=str(exc), trace_id=trace_id)
            if failed.status == "running" and failed.retry_count == attempt.retry_count and failed.prepared_result is not None:
                return self._finish_prepared_result(failed, trace_id=trace_id)
            return failed

    def _finish_selected_or_current(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        current = self.job_repository.get_document_job(job.id) or job
        timed_out = self._mark_timed_out_if_needed(current, trace_id=trace_id)
        if timed_out is not None:
            return timed_out
        if current.status == "running" and current.retry_count == job.retry_count and current.prepared_result is not None:
            return self._finish_prepared_result(current, trace_id=trace_id)
        return current

    def _finish_prepared_result(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        """receipt 后只物化同一身份；两步之间中断可由任意重投继续。"""

        current = self.job_repository.get_document_job(job.id) or job
        if current.status != "running" or current.retry_count != job.retry_count:
            return current
        receipt = job.prepared_result
        if receipt is None:
            raise ValueError("任务没有选定结果凭据。")
        timed_out = self._mark_timed_out_if_needed(job, trace_id=trace_id)
        if timed_out is not None:
            return timed_out
        try:
            word_file = self.file_repository.materialize_prepared_result(receipt.file)
            completed = self.job_repository.update_document_job_if_current(
                job.id, allowed_statuses={"running"}, allowed_stages={"uploading"},
                expected_retry_count=receipt.generation, expected_document_ir_file_id=receipt.document_ir_file_id,
                expected_prepared_result_file_id=word_file.id, status="succeeded", stage="completed",
                progress=100, result_file_id=word_file.id, completed_at=utc_now(), updated_at=utc_now(),
            )
        except Exception as exc:
            return self._mark_failed(job, failed_stage="uploading", error_code="oss_failed",
                                     error_message=str(exc), trace_id=trace_id,
                                     expected_prepared_result_file_id=receipt.file.id)
        if completed is None:
            current = self.job_repository.get_document_job(job.id) or job
            return self._mark_timed_out_if_needed(current, trace_id=trace_id) or current
        self._record_event(completed, event_type="file_registered", stage="uploading", message="生成 Word 已保存。",
                           payload={"file_id": word_file.id, "file_type": word_file.file_type,
                                    "object_key": word_file.object_key, **word_file.metadata}, trace_id=trace_id)
        self._record_event(completed, event_type="stage_succeeded", stage="completed", message="文档任务已完成。",
                           payload={"result_file_id": word_file.id, "template_version_id": completed.template_version_id},
                           trace_id=trace_id)
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
        duration_ms: int | None = None,
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
            payload={"retry_count": job.retry_count, "generation": job.retry_count, **payload},
            duration_ms=duration_ms,
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
        if job.document_ir_file_id is None:
            raise FileNotFoundError(f"任务缺少权威最终 DocumentIR 指针: {job.id}")
        record = self._get_uploaded_file(job.document_ir_file_id)
        if ((record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id)
                or record.file_type != "document_ir"):
            raise ValueError("最终 DocumentIR 文件与任务归属不一致。")
        return record

    def _get_existing_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord | None:
        if job.result_file_id:
            record = self._get_uploaded_file(job.result_file_id)
            if ((record.tenant_id, record.company_id, record.job_id) != (job.tenant_id, job.company_id, job.id)
                    or record.file_type != "generated_word"
                    or (record.expires_at is not None and record.expires_at <= utc_now())):
                raise ValueError("任务指定的结果文件不属于该任务的可用主 DOCX。")
            return record
        candidates = [
            file for file in self.file_repository.list_document_files()
            if (file.tenant_id, file.company_id, file.job_id) == (job.tenant_id, job.company_id, job.id)
            and file.file_type == "generated_word" and file.status == "uploaded"
            and "document_job_result_protocol" not in file.metadata
            and type(file.metadata.get("retry_count")) is int and file.metadata["retry_count"] == job.retry_count
            and job.document_ir_file_id is not None
            and file.metadata.get("document_ir_file_id") == job.document_ir_file_id
        ]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise ValueError("同代最终 IR 存在多份历史主件，不能猜测结果身份。")
        record = candidates[0]
        if record.expires_at is None or record.expires_at <= utc_now():
            raise ValueError("历史主件已过期或缺少保留期。")
        content = self.file_service.read_file_content(record)
        if record.size_bytes != len(content) or record.checksum_sha256 != f"sha256:{hashlib.sha256(content).hexdigest()}":
            raise ValueError("历史主件字节与 SHA-256 描述不一致。")
        ir = DocumentIR.model_validate_json(self.file_service.read_file_content(self._get_document_ir_file(job)))
        evidence = build_renderer_evidence(ir, content)
        ensure_renderer_integrity(evidence)
        if any(record.metadata.get(key) != value for key, value in evidence.items()):
            raise ValueError("历史主件缺少与实际字节一致的质量证据。")
        return record

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
            expected_document_ir_file_id=job.document_ir_file_id, require_no_prepared_result=True,
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
        if job.stage in {"translating", "translation_validating", "rendering", "quality_checking", "uploading"}:
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
        if job.status in {"succeeded", "failed", "canceled"} or job.timeout_at is None or utc_now() < job.timeout_at:
            return None
        return self._mark_timed_out(job, trace_id=trace_id)

    def _mark_timed_out(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        return self._mark_failed(
            job,
            failed_stage=self._failed_stage_for_current_job(job),
            error_code="document_job_timeout",
            allow_prepared_result=True,
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
        if isinstance(exc, (DocumentIRTranslationError, TranslationIntegrityError)):
            return failed_stage, "translation_failed"
        if isinstance(exc, zipfile.BadZipFile) or failed_stage == "ir_converting":
            return failed_stage, "document_ir_failed"
        if failed_stage in {"rendering", "quality_checking"}:
            return failed_stage, "render_failed"
        if failed_stage in {"translating", "translation_validating"}:
            if isinstance(exc, (ApiError, FileNotFoundError, OSError)):
                return failed_stage, "oss_failed"
            return failed_stage, "translation_failed"
        if failed_stage == "uploading" or isinstance(exc, (ApiError, FileNotFoundError, OSError)):
            return failed_stage, "oss_failed"
        return failed_stage, "document_job_worker_failed"

    def _fail_stage_attempt(
        self, job: DocumentJobRecord, error: Exception, *, trace_id: str | None,
    ) -> DocumentJobRecord:
        """只使用本调用已接收的阶段快照归类失败，持久化仍核对代数、IR 和结果空槽。"""

        failed_stage, error_code = self._classify_worker_failure(error, job)
        error_message = str(error)
        if not isinstance(error, (ApiError, FileNotFoundError, OSError, ValueError, RuntimeError, MinerUError, zipfile.BadZipFile)):
            error_code = "document_job_unexpected_error"
            error_message = f"Worker 未预期异常: {type(error).__name__}: {error}"
            self.logger.exception(
                "[trace_id=%s job_id=%s stage=%s status=unexpected_error]", trace_id, job.id, failed_stage,
            )
        return self._mark_failed(
            job, failed_stage=failed_stage, error_code=error_code,
            error_message=error_message, trace_id=trace_id,
        )

    def _mark_failed(
        self,
        job: DocumentJobRecord,
        *,
        failed_stage: DocumentJobStage,
        error_code: str,
        error_message: str,
        trace_id: str | None,
        integrity: TranslationIntegrityEvidence | None = None,
        duration_ms: int | None = None,
        expected_prepared_result_file_id: str | None = None,
        allow_prepared_result: bool = False,
    ) -> DocumentJobRecord:
        now = utc_now()
        failed = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"pending", "queued", "running"},
            allowed_stages={
                "uploaded", "parsing", "parsed", "ir_converting", "translating",
                "translation_validating", "rendering", "quality_checking", "uploading",
            },
            expected_retry_count=job.retry_count,
            require_no_prepared_result=not allow_prepared_result and expected_prepared_result_file_id is None,
            expected_prepared_result_file_id=expected_prepared_result_file_id,
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
        payload = {
            "error_code": error_code,
            "error_message": error_message,
            **({"prepared_result_file_id": failed.prepared_result.file.id} if failed.prepared_result else {}),
        }
        if integrity is not None:
            payload["integrity"] = integrity.to_dict()
        self._record_event(
            failed,
            event_type="stage_failed",
            stage=failed_stage,
            message="document_jobs Worker 执行失败。",
            payload=payload,
            trace_id=trace_id,
            level="error",
            duration_ms=duration_ms,
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
        config = self.mineru_config_resolver()
        if not config.api_token:
            raise RuntimeError("MINERU_API_TOKEN 未配置，无法提交 MinerU。")
        return MinerUClient(
            api_token=config.api_token,
            model_version=self.settings.mineru_model_version,
            user_token=config.uid or "",
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
