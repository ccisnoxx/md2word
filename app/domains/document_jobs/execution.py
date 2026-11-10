from __future__ import annotations

from app.domains.document_jobs.table_evidence import has_evidence, save_report, verify_report, validate_candidate_binding, recheck_verified_report
from app.services.tables.evidence import TableEvidenceError

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

from billiard.exceptions import SoftTimeLimitExceeded

from app.clients.mineru_client import MinerUClient, MinerUError
from app.core.config import Settings
from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.preview import DocumentJobPreviewService
from app.domains.document_jobs.publication_provenance import capture_render_publication_provenance
from app.domains.document_jobs.translation_execution import TranslationBatchExecution
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.document_jobs.models import (
    DocumentJobCallbackMessage,
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobRecord,
    DocumentJobStage,
)
from app.core.errors import ApiError
from app.services.document_ir.models import DocumentIR, DocumentIRAsset, TableReferenceProvenance
from app.services.document_ir.artifact_validator import MinerUArtifactValidationError
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.page_degradation import (
    PAGE_RASTER_SOURCE_PATH, degradation_closure, drop_degraded_table_groups, replace_degraded_pages,
)
from app.services.document_ir.table_reference_assets import (
    RASTER_EXTENSIONS, TABLE_REFERENCE_ROLE, decode_table_references,
)
from app.services.document_ir.table_placeholder import (
    PdfCropSource, TablePlaceholderError, checksum as placeholder_checksum, decode_placeholders,
)
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
)
from app.services.document_ir import MinerUToDocumentIRService
from app.services.renderer import DocumentIRRenderOptions, DocumentIRWordRenderer
from app.services.renderer.evidence import (
    build_renderer_evidence,
    build_renderer_event_summary, ensure_renderer_integrity, validate_persisted_render_evidence,
    validate_persisted_renderer_content,
)
from app.services.renderer import image_evidence
from app.services.renderer.block_anchors import validate_block_anchor_evidence
from app.services.renderer.layout_plan import build_layout_plan
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.modes import is_translation_document_job_mode, spec_for_document_job_mode
from app.domains.translation.document_ir_translator import (
    DocumentIRTranslationError,
    DocumentIRTranslationService,
)
from app.domains.translation.integrity import (
    TranslationIntegrityError,
    TranslationIntegrityEvidence,
)


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
        word_preview_service: DocumentJobPreviewService | None = None,
    ) -> None:
        self.word_preview_service = word_preview_service or DocumentJobPreviewService(
            settings, job_repository, event_repository, file_repository, file_service)
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.callback_message_store = callback_message_store
        self.file_repository = file_repository
        self.file_service = file_service
        self.document_ir_service = document_ir_service
        self.template_read_service = template_read_service
        self.word_renderer = word_renderer
        self.mineru_config_resolver = mineru_config_resolver
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.mineru_client_factory = mineru_client_factory or self._build_mineru_client
        self.logger = logging.getLogger("business")
        # 翻译专属依赖只交给协作者持有；settings 等共用依赖两边引用同一对象。
        self.translation_batches = TranslationBatchExecution(
            self,
            settings=settings,
            job_repository=job_repository,
            file_service=file_service,
            job_resource_snapshot_service=job_resource_snapshot_service,
            translation_batch_repository=translation_batch_repository,
            document_ir_translation_service=document_ir_translation_service,
            translation_audit_service=translation_audit_service,
            term_version_service=term_version_service,
            translation_batch_task_queue=translation_batch_task_queue,
        )

    def execute_job(self, job_id: str, *, trace_id: str | None = None) -> DocumentJobRecord | None:
        """执行一个 document_job；重复投递时不会重复推进已完成的骨架阶段。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            return None
        latest = job
        try:
            job = self._process_replayable_callback_messages(job, trace_id=trace_id)
            latest = job
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
            if job.status == "pending":
                job = self._mark_queued_from_worker(job, trace_id=trace_id)
                latest = job
            if job.status == "queued":
                job = self._mark_parsing_started(job, trace_id=trace_id)
                latest = job

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
                source_file, source_document_ir = self.translation_batches._read_translation_source(
                    latest, latest.source_document_ir_file_id,
                )
                del source_file
                latest = self.translation_batches._ensure_translation_batches_and_enqueue(
                    latest, source_document_ir, trace_id=trace_id,
                )
            elif latest.status == "running" and latest.stage == "translation_validating":
                latest = self.translation_batches._finalize_translation_generation(
                    latest.id, generation=latest.retry_count, trace_id=trace_id,
                )
            if latest.status == "running" and latest.stage in {"rendering", "quality_checking", "uploading"}:
                return self._render_and_save_word(latest, trace_id=trace_id)
            return latest
        except Exception as exc:
            # latest 是本次阶段调用实际接收的快照，不能拿事后读到的新代归属旧错误。
            return self._fail_stage_attempt(latest, exc, trace_id=trace_id)

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
        started_at = job.started_at or now
        running = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"queued"},
            allowed_stages={"uploaded"},
            expected_retry_count=job.retry_count,
            status="running",
            stage="parsing",
            progress=max(job.progress, 10),
            started_at=started_at,
            timeout_at=job.timeout_at or started_at + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
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
        current, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
        if not can_continue:
            return current
        job = current
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

        with tempfile.TemporaryDirectory(prefix="document_job_mineru_") as temp_dir:
            client = self.mineru_client_factory()
            data_id = job.mineru_data_id or job.id
            batch_id = job.mineru_batch_id
            if not batch_id:
                source_file = self._get_uploaded_file(job.source_file_id)
                source_path = Path(temp_dir) / source_file.original_filename
                source_path.write_bytes(self.file_service.read_file_content(source_file))
                callback = self.settings.mineru_callback_url.strip() or None
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
            current, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
            if not can_continue:
                return current
            result_item = self._select_mineru_result(payload, data_id, batch_id=batch_id)
            state = str(result_item.get("state") or "").lower()
            if state == "failed":
                return self._mark_failed(
                    job, failed_stage="parsing", error_code="mineru_failed",
                    error_message="MinerU 查询返回解析失败。", trace_id=trace_id,
                )
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
                    message="MinerU 结果尚未就绪，等待后续查询或回调。",
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

        latest, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
        if not can_continue:
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
        raw_zip_path = temp_dir / "mineru_raw_result.zip"
        client.download_result_zip(full_zip_url, raw_zip_path)
        latest, can_continue = self._refresh_mineru_parse_attempt(job, trace_id=trace_id)
        if not can_continue:
            return latest
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
            _source_file, source_document_ir = self.translation_batches._read_translation_source(job, job.source_document_ir_file_id)
            return self.translation_batches._ensure_translation_batches_and_enqueue(job, source_document_ir, trace_id=trace_id)

        raw_file = self._get_mineru_raw_result_file(job)
        with tempfile.TemporaryDirectory(prefix="document_job_ir_") as temp_dir:
            raw_zip_path = Path(temp_dir) / raw_file.original_filename
            raw_zip_path.write_bytes(self.file_service.read_file_content(raw_file))
            validation_input = {
                "mineru_raw_result_file_id": raw_file.id,
                "mineru_raw_result_sha256": raw_file.checksum_sha256,
                "retry_count": job.retry_count,
            }
            try:
                result = self.document_ir_service.convert_zip(
                    raw_zip_path,
                    job_id=job.id,
                    source_file_id=job.source_file_id,
                    document_language=job.document_language,
                    placeholder_source_loader=lambda: self._load_placeholder_source(job),
                )
            except (MinerUArtifactValidationError, DocumentIntegrityError, TablePlaceholderError) as error:
                error.mineru_validation_input = validation_input
                return self._fail_stage_attempt(job, error, trace_id=trace_id)
            result.document.metadata.mineru_validation_input = validation_input

        image_file_ids: list[str] = []
        for image_asset in result.image_assets:
            image_file = self.file_service.register_generated_content(
                tenant_id=job.tenant_id,
                company_id=job.company_id,
                job_id=job.id,
                created_by=job.created_by,
                file_type="image_asset",
                filename=f"{image_asset.asset_id}_{image_asset.stored_name}",
                mime_type=image_asset.mime_type,
                content=image_asset.content,
                metadata={
                    "source_file_id": job.source_file_id,
                    "mineru_raw_result_file_id": raw_file.id,
                    "source_path": image_asset.source_path,
                    "asset_id": image_asset.asset_id,
                    "block_id": image_asset.block_id,
                    "retry_count": job.retry_count,
                    **({"normalized_from_format": image_asset.normalized_from[0],
                        "normalized_from_sha256": image_asset.normalized_from[1]} if image_asset.normalized_from else {}),
                    **({"origin": "pdf_region_crop", "pdf_fallback": image_asset.pdf_fallback}
                       if image_asset.pdf_fallback else {}),
                    **({"origin": "pdf_page_raster", "page_raster": image_asset.page_raster}
                       if image_asset.page_raster else {}),
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

        # QA 图只由 IR 引用，不能混入渲染图片列表、资源包或主记录 image_asset_file_ids。
        assets_by_id = {asset.id: asset for asset in result.document.assets}
        for reference in result.table_reference_assets:
            reference_file = self.file_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="image_asset",
                filename=f"table_reference_{reference.asset_id.split(':')[-1]}.{RASTER_EXTENSIONS[reference.mime_type]}",
                mime_type=reference.mime_type, content=reference.content,
                object_version=f"g{job.retry_count}_{uuid4().hex}",
                metadata={
                    "asset_role": TABLE_REFERENCE_ROLE, "asset_id": reference.asset_id,
                    "block_id": reference.block_id, "fragment_id": reference.fragment_id,
                    "logical_group_id": reference.logical_group_id, "source_file_id": job.source_file_id,
                    "mineru_raw_result_file_id": raw_file.id, "source_path": reference.source_path,
                    "retry_count": job.retry_count,
                },
            )
            asset = assets_by_id[reference.asset_id]
            asset.file_id, asset.object_key = reference_file.id, reference_file.object_key
            asset.mime_type, asset.checksum_sha256 = reference_file.mime_type, reference_file.checksum_sha256

        for pending in result.table_placeholder_assets:
            binding = next(item for item in result.document.metadata.table_placeholders if item.asset_ref == pending.asset_id)
            file = self.file_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="image_asset", filename="table_placeholder.png", mime_type=pending.mime_type,
                content=pending.content, object_version=f"g{job.retry_count}_{uuid4().hex}",
                metadata={"asset_role": "table_placeholder", "asset_id": pending.asset_id,
                          "source_file_id": job.source_file_id, "source_pdf_sha256": binding.source_pdf_sha256,
                          "fragment_id": binding.fragment_id, "retry_count": job.retry_count},
            )
            asset = next(asset for asset in result.document.assets if asset.id == pending.asset_id)
            asset.file_id, asset.object_key = file.id, file.object_key
        document_ir = result.document
        decode_table_references(document_ir, require_bound=True)
        decode_placeholders(document_ir, require_bound=True)
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
            object_version=(f"g{job.retry_count}_{uuid4().hex}" if document_ir.metadata.table_references_version else None),
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

        decode_table_references(document_ir, require_bound=True)
        source_ir_file = self.file_service.register_generated_content(
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            file_type="document_ir",
            filename="document_ir_source_v2.json",
            object_version=(f"g{job.retry_count}_{uuid4().hex}" if document_ir.metadata.table_references_version else None),
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
        return self.translation_batches._ensure_translation_batches_and_enqueue(updated, document_ir, trace_id=trace_id)

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
                archive.writestr(f"images/{image_asset.asset_id}_{image_asset.stored_name}", image_asset.content)
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
            try:
                ir_bytes = self.file_service.read_file_content(ir_file)
                document_ir = DocumentIR.model_validate_json(ir_bytes)
            except ValueError:
                raise TablePlaceholderError("table_placeholder_integrity_failed") from None
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
            def render(job: DocumentJobRecord, document: DocumentIR):
                return self.word_renderer.render_to_result(
                    document,
                    template_path=template_selection.template_path,
                    config_path=template_selection.layout_config_path,
                    image_loader=self._build_image_loader(job, document),
                    options=DocumentIRRenderOptions(
                        subscript_config_path=self.settings.subscript_config_path,
                        document_language=document.metadata.document_language,
                        template_version_id=template_selection.template_version_id,
                    ),
                )

            degradation_attempts = 0
            while True:
                try:
                    render_result = render(rendering, document_ir)
                    break
                except Exception as exc:
                    if degradation_attempts >= self.settings.render_degradation_max_attempts:
                        raise
                    degraded = self._degrade_render_failure_page(rendering, ir_file, document_ir, exc, trace_id=trace_id)
                    if degraded is None:
                        raise
                    if isinstance(degraded, DocumentJobRecord):
                        return self._finish_selected_or_current(degraded, trace_id=trace_id)
                    # 降级后的新 IR 已成为任务权威指针；后续失败基于它继续判断，不回到旧 IR。
                    rendering, ir_file, ir_bytes, document_ir = degraded
                    attempt = rendering
                    degradation_attempts += 1
            layout_plan = build_layout_plan(document_ir)
            word_content = render_result.content
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
                renderer_metadata = build_renderer_evidence(
                    document_ir, word_content, layout_plan, render_result=render_result, formula_report=render_result.formula_report,
                    image_layout_report=render_result.image_layout_report,
                    renderer_content_contract_version=render_result.renderer_content_contract_version,
                    formula_source_coverage=render_result.formula_source_coverage,
                    expected_template_version_id=template_selection.template_version_id,
                    expected_generation_policy=image_evidence.IMAGE_GENERATION_POLICY,
                )
                ensure_renderer_integrity(renderer_metadata)
            except Exception as exc:
                failed = self._mark_failed(
                    checking, failed_stage="quality_checking", error_code="render_failed",
                    error_message=failure_policy.worker_failure_message(exc), trace_id=trace_id,
                    failure_evidence=failure_policy.worker_failure_evidence(exc),
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
                message="Word 文档质量检查已通过。",
                payload={"document_ir_file_id": ir_file.id, **build_renderer_event_summary(renderer_metadata)},
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
            renderer_metadata, preparation = save_report(uploading, ir_file, ir_bytes, renderer_metadata, self.file_service)
            publication_provenance = capture_render_publication_provenance(uploading, ir_file, document_ir, render_result,
                renderer=self.word_renderer, snapshot_service=self.job_resource_snapshot_service, file_service=self.file_service)
            renderer_metadata["publication_provenance_file_id"] = publication_provenance.id
            word_file = self.file_service.register_result_candidate(
                tenant_id=uploading.tenant_id,
                company_id=uploading.company_id,
                job_id=uploading.id,
                created_by=uploading.created_by,
                filename=self._result_filename(uploading),
                content=word_content,
                expires_at=preparation.docx_expires_at,
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
            verify_report(uploading, word_file, file_repository=self.file_repository,
                          file_service=self.file_service, job_repository=self.job_repository)
            prepared = self.job_repository.prepare_document_job_result(
                uploading.id, expected_retry_count=uploading.retry_count,
                expected_document_ir_file_id=ir_file.id, candidate=word_file,
            )
            if prepared is None:
                return self._finish_selected_or_current(uploading, trace_id=trace_id)
            return self._finish_prepared_result(prepared, trace_id=trace_id)
        except Exception as exc:
            failed_stage, error_code, unexpected_log_stage = failure_policy.render_failure(
                exc, attempt.stage, validating_legacy=validating_legacy,
            )
            if unexpected_log_stage is not None:
                self.logger.exception("[trace_id=%s job_id=%s stage=%s status=unexpected_error]", trace_id, job.id, unexpected_log_stage)
            failed = self._mark_failed(attempt, failed_stage=failed_stage, error_code=error_code,
                                       error_message=failure_policy.worker_failure_message(exc), trace_id=trace_id,
                                       failure_evidence=failure_policy.worker_failure_evidence(exc))
            if failed.status == "running" and failed.retry_count == attempt.retry_count and failed.prepared_result is not None:
                return self._finish_prepared_result(failed, trace_id=trace_id)
            return failed

    def _degrade_render_failure_page(
        self, job: DocumentJobRecord, ir_file: DocumentFileRecord, document_ir: DocumentIR, error: Exception,
        *, trace_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord, bytes, DocumentIR] | DocumentJobRecord | None:
        """第三批 C3：带页定位的渲染失败把该页（及表格依赖页）降级为整页图像，另存新 IR 并条件切换任务指针。

        返回 None 表示不满足降级前提，调用方按原错误失败；返回任务记录表示指针切换落败（已被并发推进）。
        """
        context = failure_policy.worker_failure_evidence(error).get("failure_context")
        rasterizer = getattr(self.document_ir_service, "page_rasterizer", None)
        if (not isinstance(context, dict) or context.get("source_page_index") is None or rasterizer is None
                or is_translation_document_job_mode(job.mode)
                or isinstance(error, (ApiError, OSError, MinerUError, TablePlaceholderError, DocumentIntegrityError,
                                      SoftTimeLimitExceeded))):
            return None
        page_index = context["source_page_index"]
        already = {record.get("page_index") for record in document_ir.metadata.degraded_pages}
        degraded = degradation_closure(document_ir.metadata.logical_table_groups, {page_index})
        if (degraded is None or degraded & already
                or not self.document_ir_service.degradation_policy.allows(len(degraded | already), len(document_ir.pages))):
            return None
        try:
            source = self._load_placeholder_source(job)
            if source.file_id != job.source_file_id or placeholder_checksum(source.content) != source.checksum_sha256:
                return None
            rasters = {page: rasterizer.rasterize(source, page) for page in sorted(degraded)}
            candidate = document_ir.model_copy(deep=True)
            reason = {"reason_codes": ["render_failed"], "operation_kind": context.get("operation_kind"),
                      "render_reason_code": context.get("reason_code")}
            removed_ids, pending = replace_degraded_pages(
                candidate, rasters, {page_index: reason}, source_pdf_sha256=source.checksum_sha256,
                dpi=getattr(rasterizer, "DPI", None), trigger="render")
            drop_degraded_table_groups(candidate, removed_ids)
            candidate = DocumentIR.model_validate(candidate.model_dump(mode="python"))
        except (TablePlaceholderError, ValueError):
            # 栅格失败或替换后 IR 不再自洽（如保留组的续表诊断指向被删片段）：放弃降级。
            return None
        raster_file_ids: list[str] = []
        for item in pending:
            image_file = self.file_service.register_generated_content(
                tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
                file_type="image_asset", filename=f"{item.asset_id}_page.png", mime_type="image/png",
                content=item.content, object_version=f"g{job.retry_count}_{uuid4().hex}",
                metadata={"source_file_id": job.source_file_id,
                          "mineru_raw_result_file_id": ir_file.metadata.get("mineru_raw_result_file_id"),
                          "source_path": PAGE_RASTER_SOURCE_PATH, "asset_id": item.asset_id, "block_id": item.block_id,
                          "retry_count": job.retry_count, "origin": "pdf_page_raster", "page_raster": item.page_raster},
            )
            raster_file_ids.append(image_file.id)
            asset = next(asset for asset in candidate.assets if asset.id == item.asset_id)
            asset.file_id, asset.object_key = image_file.id, image_file.object_key
            asset.mime_type, asset.checksum_sha256 = image_file.mime_type, image_file.checksum_sha256
        ir_content = candidate.model_dump_json(indent=2).encode("utf-8")
        new_ir_file = self.file_service.register_generated_content(
            tenant_id=job.tenant_id, company_id=job.company_id, job_id=job.id, created_by=job.created_by,
            file_type="document_ir", filename=ir_file.original_filename,
            object_version=f"g{job.retry_count}_{uuid4().hex}", mime_type="application/json", content=ir_content,
            metadata={**ir_file.metadata, **self._document_ir_layout_metadata(candidate),
                      "degraded_from_document_ir_file_id": ir_file.id},
        )
        switched = self.job_repository.update_document_job_if_current(
            job.id, allowed_statuses={"running"}, allowed_stages={"rendering"},
            expected_retry_count=job.retry_count, expected_document_ir_file_id=ir_file.id,
            require_no_prepared_result=True, document_ir_file_id=new_ir_file.id,
            image_asset_file_ids=[*job.image_asset_file_ids, *raster_file_ids], updated_at=utc_now(),
        )
        if switched is None:
            return job
        self._record_event(
            switched, event_type="file_registered", stage="rendering",
            message=f"第 {', '.join(str(page + 1) for page in sorted(degraded))} 页渲染失败，已按原 PDF 页面图像降级并重新渲染。",
            payload={"file_id": new_ir_file.id, "file_type": "document_ir", "document_ir_file_id": new_ir_file.id,
                     "degraded_from_document_ir_file_id": ir_file.id, "degraded_page_indexes": sorted(degraded),
                     "image_asset_file_ids": raster_file_ids, "failure_context": context},
            trace_id=trace_id,
        )
        return switched, new_ir_file, ir_content, candidate

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
            validate_candidate_binding(job, receipt.file)
            word_file = self.file_repository.materialize_prepared_result(receipt.file)
            ir_file, final_ir, _ = self._validate_render_result_file(word_file)
            verified_report = verify_report(job, word_file, file_repository=self.file_repository,
                          file_service=self.file_service, job_repository=self.job_repository)
            # 恢复只核对原 receipt 的实物，不重裁图、不重渲染或更换同代身份。
            proof = word_file.metadata.get("table_placeholder_rendering")
            placeholders = decode_placeholders(final_ir, require_bound=True)
            if placeholders or proof is not None:
                if final_ir.metadata.job_id != job.id or final_ir.metadata.source_file_id != job.source_file_id:
                    raise TablePlaceholderError("table_placeholder_integrity_failed")
                self._verify_placeholder_dependencies(job, final_ir)
                for file in (ir_file, word_file):
                    self._ensure_placeholder_file_current(job, file, "table_placeholder_integrity_failed")
            preview_job, preview_finished = self.word_preview_service.ensure_initial(current, trace_id=trace_id)
            if not preview_finished:
                return self._mark_timed_out_if_needed(preview_job, trace_id=trace_id) or preview_job
            if verified_report is not None:
                recheck_verified_report(verified_report, file_repository=self.file_repository,
                                        job_repository=self.job_repository)
            completed = self.job_repository.update_document_job_if_current(
                job.id, allowed_statuses={"running"}, allowed_stages={"uploading"},
                expected_retry_count=receipt.generation, expected_document_ir_file_id=receipt.document_ir_file_id,
                expected_prepared_result_file_id=word_file.id, status="succeeded", stage="completed",
                progress=100, result_file_id=word_file.id, completed_at=utc_now(), updated_at=utc_now(),
            )
        except Exception as exc:
            return self._mark_failed(job,
                failed_stage="quality_checking" if isinstance(exc, (TablePlaceholderError, DocumentIntegrityError, TableEvidenceError)) else "uploading",
                error_code="render_failed" if isinstance(exc, (TablePlaceholderError, DocumentIntegrityError, TableEvidenceError)) else "oss_failed",
                error_message=(failure_policy.worker_failure_message(exc) if isinstance(exc, (TablePlaceholderError, TableEvidenceError, DocumentIntegrityError)) or
                    "table_placeholder_rendering" not in receipt.file.metadata else "表格占位结果文件读取或完整性校验失败。"),
                trace_id=trace_id, expected_prepared_result_file_id=receipt.file.id)
        if completed is None:
            current = self.job_repository.get_document_job(job.id) or job
            return self._mark_timed_out_if_needed(current, trace_id=trace_id) or current
        self._record_event(completed, event_type="file_registered", stage="uploading", message="生成 Word 已保存。",
                           payload={"file_id": word_file.id, "file_type": word_file.file_type,
                                    **build_renderer_event_summary(word_file.metadata)}, trace_id=trace_id)
        self._record_event(completed, event_type="stage_succeeded", stage="completed", message="文档任务已完成。",
                           payload={"result_file_id": word_file.id, "template_version_id": completed.template_version_id},
                           trace_id=trace_id)
        return completed

    def _validate_render_result_file(self, record: DocumentFileRecord) -> tuple[DocumentFileRecord, DocumentIR, bytes]:
        """先核实原件及绑定 IR 的实物，再由 renderer 按保存的版本认证内容。"""

        if (record.file_type != "generated_word" or record.status != "uploaded"
                or record.expires_at is not None and record.expires_at <= utc_now()
                or record.expires_at is None and any(key in record.metadata for key in (
                    "renderer_content_contract_version", "formula_source_coverage"))):
            raise ValueError("主 DOCX 的类型、状态或保留期无效。")
        content = self.file_service.read_file_content(record)
        if record.size_bytes != len(content) or record.checksum_sha256 != f"sha256:{hashlib.sha256(content).hexdigest()}":
            raise ValueError("主 DOCX 字节与 SHA-256 描述不一致。")
        ir_id = record.metadata.get("document_ir_file_id")
        if not isinstance(ir_id, str) or not ir_id:
            raise ValueError("主 DOCX 缺少原始 IR 绑定。")
        ir_file = self._get_uploaded_file(ir_id)
        if ((ir_file.tenant_id, ir_file.company_id, ir_file.job_id)
                != (record.tenant_id, record.company_id, record.job_id) or ir_file.file_type != "document_ir"
                or ir_file.expires_at is not None and ir_file.expires_at <= utc_now()):
            raise ValueError("主 DOCX 的原始 IR 与文件归属不一致。")
        ir_bytes = self.file_service.read_file_content(ir_file)
        if ir_file.size_bytes != len(ir_bytes) or ir_file.checksum_sha256 != placeholder_checksum(ir_bytes):
            raise ValueError("主 DOCX 的原始 IR 字节与描述不一致。")
        ir = DocumentIR.model_validate_json(ir_bytes)
        validate_persisted_renderer_content(ir, content, record.metadata,
            expected_template_version_id=record.metadata.get("template_version_id"))
        self._validate_optional_block_anchors(ir, content, record.metadata)
        return ir_file, ir, content

    def _validate_optional_block_anchors(self, document_ir: DocumentIR, content: bytes, metadata: dict[str, Any]) -> None:
        """历史恢复只局部认证可选锚点；保留原 metadata，不重建或升级创建事实。"""
        if "block_anchor_evidence" not in metadata:
            return
        verified = validate_persisted_render_evidence(document_ir, content,
            render_plan=metadata.get("render_plan"), block_render_evidence=metadata.get("block_render_evidence"))
        anchors = None
        if verified is not None:
            plan, trace = verified
            anchors = validate_block_anchor_evidence(metadata["block_anchor_evidence"], plan=plan,
                block_evidence=trace, word_content=content)
        if anchors is None:
            self.logger.warning("[reason_code=anchor_missing] 历史主件的可选锚点证据不可用。")

    def _document_ir_layout_metadata(self, document_ir: DocumentIR) -> dict[str, Any]:
        """保存私有 IR 诊断；事件出口另行投影。"""

        return {
            "schema_version": document_ir.schema_version,
            "page_count": len(document_ir.pages),
            "layout_page_count": len(document_ir.pages),
            "block_count": len(document_ir.blocks),
            "layout_block_count": sum(1 for block in document_ir.blocks if block.layout is not None),
            "quality_flags": document_ir.quality_flags,
            "mineru_validation": (document_ir.metadata.mineru_validation.model_dump(mode="json")
                                  if document_ir.metadata.mineru_validation is not None else None),
            "mineru_validation_input": document_ir.metadata.mineru_validation_input,
            "table_reference_asset_count": sum(item.asset is not None for item in decode_table_references(document_ir)),
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
        # renderer 事件只允许固定外层身份与安全摘要；未知新字段不能借嵌套值透传。
        if (payload.get("file_type") == "generated_word"
                or any(key in payload for key in ("renderer_content_contract_version", "formula_source_coverage",
                    "render_plan", "block_render_evidence", "block_anchor_evidence", "page_mapping"))):
            outer_keys = {"file_id", "file_type", "document_ir_file_id", "result_file_id", "template_version_id",
                "error_code", "error_message", "prepared_result_file_id"}
            payload = {**{key: value for key, value in payload.items() if key in outer_keys},
                **build_renderer_event_summary(payload)}
        if payload.get("schema_version") in {"document-ir/v1", "document-ir/v2"}:
            outer_keys = {
                "file_id", "file_type", "document_ir_file_id", "source_document_ir_file_id",
                "image_asset_file_ids", "image_assets_archive_file_id", "image_asset_count",
                "translation", "translation_batch_count", "translation_item_count",
            }
            payload = {
                **{key: value for key, value in payload.items() if key in outer_keys},
                **build_renderer_event_summary(payload),
            }
        if payload.get("mineru_validation") is not None or payload.get("failure_context") is not None:
            payload = {**payload, "retry_count": job.retry_count}
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

    def _refresh_mineru_parse_attempt(
        self, job: DocumentJobRecord, *, trace_id: str | None,
    ) -> tuple[DocumentJobRecord, bool]:
        """解析外端调用前后核对本次身份和固定期限，避免旧结果归入新代。"""

        latest = self.job_repository.get_document_job(job.id)
        if latest is None:
            return job, False
        if (latest.retry_count != job.retry_count or latest.status != "running" or latest.stage != "parsing"
                or latest.mineru_batch_id != job.mineru_batch_id or latest.mineru_data_id != job.mineru_data_id):
            return latest, False
        if latest.timeout_at is None:
            # 旧新代可能已提交批次却未保存期限；只能沿本代稳定起点补齐，不能从每轮 now 续期。
            if latest.started_at is None:
                return self._mark_failed(
                    latest, failed_stage="parsing", error_code="document_job_timeout",
                    error_message="解析记录缺少本代开始时间，无法确定绝对截止期限，已停止执行。",
                    trace_id=trace_id,
                ), False
            updated = self.job_repository.update_document_job_if_current(
                latest.id, allowed_statuses={"running"}, allowed_stages={"parsing"},
                expected_retry_count=latest.retry_count,
                timeout_at=latest.started_at + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
                updated_at=utc_now(),
            )
            if updated is None:
                return self.job_repository.get_document_job(latest.id) or latest, False
            latest = updated
        timed_out = self._mark_timed_out_if_needed(latest, trace_id=trace_id)
        return (timed_out, False) if timed_out is not None else (latest, True)

    def _select_mineru_result(self, payload: dict, data_id: str, *, batch_id: str) -> dict:
        results = payload.get("extract_result") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise ValueError("MinerU 查询结果缺少 extract_result 数组。")
        if payload.get("batch_id") and str(payload["batch_id"]) != batch_id:
            raise MinerUError("MinerU 查询结果的 batch_id 与当前批次不一致。")
        for item in results:
            if isinstance(item, dict) and str(item.get("data_id") or "") == data_id:
                return item
        if not results:
            return {}
        # 历史单文件结果和既有适配器可能不回传 data_id；显式异身份不能借此兜底。
        if len(results) == 1 and isinstance(results[0], dict) and not results[0].get("data_id"):
            return results[0]
        raise MinerUError("MinerU 查询结果缺少匹配当前 data_id 的记录。")

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
            if (any(key in record.metadata for key in ("renderer_content_contract_version", "formula_source_coverage",
                    "formula_report", "formula_summary"))
                    or image_evidence.IMAGE_EVIDENCE_KEYS.intersection(record.metadata)
                    or has_evidence(record.metadata)):
                self._validate_render_result_file(record)
            elif image_evidence.has_image_markers(self.file_service.read_file_content(record)):
                raise ValueError("主 DOCX 含图片布局标记但缺少报告。")
            # 显式历史指针原本允许无报告、无 IR 绑定；仅该已验收路径保留原门。
            if has_evidence(record.metadata):
                verify_report(job, record, file_repository=self.file_repository,
                              file_service=self.file_service, job_repository=self.job_repository)
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
        self._validate_render_result_file(record)
        if has_evidence(record.metadata):
            verify_report(job, record, file_repository=self.file_repository,
                          file_service=self.file_service, job_repository=self.job_repository)
        return record

    def _ensure_placeholder_attempt_current(self, job: DocumentJobRecord, error_code: str) -> None:
        """慢读两侧核对仍在执行的同代/最终 IR；质量摘要等无关并发更新不影响快照。"""
        current = self.job_repository.get_document_job(job.id)
        if (current is None or current.status != "running" or current.deleted_at is not None
                or current.archived_at is not None or current.retry_count != job.retry_count
                or current.document_ir_file_id != job.document_ir_file_id
                or (current.tenant_id, current.company_id, current.source_file_id, current.source_job_id) !=
                   (job.tenant_id, job.company_id, job.source_file_id, job.source_job_id)):
            raise TablePlaceholderError(error_code)

    def _ensure_placeholder_file_current(self, job: DocumentJobRecord, file: DocumentFileRecord, error_code: str) -> None:
        """与 IR-206 相同：按 ID 重取并比较完整描述，不把有 file_id 当作当前可读。"""
        if (self.file_repository.get_document_file(file.id) != file or file.status != "uploaded"
                or file.expires_at is not None and file.expires_at <= utc_now()):
            raise TablePlaceholderError(error_code)
        self._ensure_placeholder_attempt_current(job, error_code)

    def _read_current_placeholder_file(self, job: DocumentJobRecord, file: DocumentFileRecord,
                                       error_code: str = "table_placeholder_integrity_failed") -> bytes:
        """字节读取前后核验同一描述、生命周期、任务快照与实际 hash；错误不带存储定位。"""
        snapshot = file.model_copy(deep=True)
        self._ensure_placeholder_file_current(job, snapshot, error_code)
        try:
            content = self.file_service.read_file_content(snapshot)
        except Exception:
            raise TablePlaceholderError(error_code) from None
        self._ensure_placeholder_file_current(job, snapshot, error_code)
        if len(content) != snapshot.size_bytes or placeholder_checksum(content) != snapshot.checksum_sha256:
            raise TablePlaceholderError("table_placeholder_integrity_failed")
        return content

    def _get_placeholder_source_file(self, job: DocumentJobRecord,
                                      error_code: str = "table_placeholder_source_unavailable") -> DocumentFileRecord:
        """裁图或未完成 receipt 只认绑定源；clone 沿既有同源父链核验归属。"""
        file = self.file_repository.get_document_file(job.source_file_id)
        if (file is None or file.file_type != "source_pdf" or file.status != "uploaded"
                or (file.tenant_id, file.company_id) != (job.tenant_id, job.company_id)
                or file.expires_at is not None and file.expires_at <= utc_now()
                or not file.checksum_sha256):
            raise TablePlaceholderError(error_code)
        owner = job
        seen = set()
        while file.job_id != owner.id:
            if owner.id in seen or owner.source_job_id is None:
                raise TablePlaceholderError(error_code)
            seen.add(owner.id)
            owner = self.job_repository.get_document_job(owner.source_job_id)
            if (owner is None or owner.source_file_id != file.id
                    or (owner.tenant_id, owner.company_id) != (job.tenant_id, job.company_id)):
                raise TablePlaceholderError(error_code)
        return file

    def _load_placeholder_source(self, job: DocumentJobRecord) -> PdfCropSource:
        file = self._get_placeholder_source_file(job)
        content = self._read_current_placeholder_file(job, file, "table_placeholder_source_unavailable")
        return PdfCropSource(file.id, file.checksum_sha256, content)

    def _read_placeholder_asset(self, job: DocumentJobRecord, document: DocumentIR, asset: DocumentIRAsset, binding):
        """仅显式消费的占位图按当前 ID 读取；来源 attempt 可早于翻译 retry，不能硬套最新代。"""
        file = self.file_repository.get_document_file(asset.file_id)
        try:
            provenance = TableReferenceProvenance.model_validate(document.metadata.mineru_validation_input)
        except ValueError:
            raise TablePlaceholderError("table_placeholder_integrity_failed") from None
        expected = {"asset_id": asset.id, "source_file_id": job.source_file_id,
                    "fragment_id": binding.fragment_id, "retry_count": provenance.retry_count}
        if binding.source_kind == "mineru_reference":
            reference = next(item for item in decode_table_references(document, require_bound=True)
                             if item.fragment.fragment_id == binding.fragment_id)
            expected.update(asset_role=TABLE_REFERENCE_ROLE, block_id=reference.block_id,
                logical_group_id=reference.logical_group_id, source_path=asset.source_path,
                mineru_raw_result_file_id=provenance.mineru_raw_result_file_id)
        else:
            expected.update(asset_role="table_placeholder", source_pdf_sha256=binding.source_pdf_sha256)
        if (file is None or file.file_type != "image_asset" or file.mime_type != asset.mime_type
                or (file.tenant_id, file.company_id, file.job_id) != (job.tenant_id, job.company_id, job.id)
                or file.checksum_sha256 != asset.checksum_sha256 or file.object_key != asset.object_key
                or not provenance.retry_count <= job.retry_count
                or type(file.metadata.get("retry_count")) is not int
                or any(file.metadata.get(key) != value for key, value in expected.items())):
            raise TablePlaceholderError("table_placeholder_integrity_failed")
        return file, self._read_current_placeholder_file(job, file)

    def _verify_placeholder_dependencies(self, job: DocumentJobRecord, document: DocumentIR) -> None:
        """未完成 receipt 复核原绑定依赖；只读取原件，不重渲染、重裁图或替换身份。"""
        bindings = decode_placeholders(document, require_bound=True)
        if not bindings:
            return
        source = self._get_placeholder_source_file(job, "table_placeholder_integrity_failed")
        snapshots = [source]
        crop_hashes = {item.source_pdf_sha256 for item in bindings if item.source_kind == "source_pdf_crop"}
        if crop_hashes:
            self._read_current_placeholder_file(job, source)
            if crop_hashes != {source.checksum_sha256}:
                raise TablePlaceholderError("table_placeholder_integrity_failed")
        assets = {asset.id: asset for asset in document.assets}
        for binding in bindings:
            file, _ = self._read_placeholder_asset(job, document, assets[binding.asset_ref], binding)
            snapshots.append(file)
        # 后续图片慢读也可能使前面的源/图片失效；所有 I/O 完成后再次对账。
        for file in snapshots:
            self._ensure_placeholder_file_current(job, file, "table_placeholder_integrity_failed")

    def _build_image_loader(self, job: DocumentJobRecord, document_ir: DocumentIR) -> Callable[[DocumentIRAsset], bytes | None]:
        bindings = {item.asset_ref: item for item in decode_placeholders(document_ir, require_bound=True)}
        image_files = {
            file.id: file
            for file in self.file_repository.list_document_files()
            if file.job_id == job.id and file.file_type == "image_asset" and file.status == "uploaded"
        }

        def load_image(asset: DocumentIRAsset) -> bytes | None:
            if asset.id in bindings:
                return self._read_placeholder_asset(job, document_ir, asset, bindings[asset.id])[1]
            if asset.id.startswith(("table-reference:", "table-placeholder:")):
                # 普通 QA 参考图不能借普通 image loader 绕过显式占位消费及其来源核验。
                raise TablePlaceholderError("table_placeholder_integrity_failed")
            if asset.file_id is None:
                return None
            record = image_files.get(asset.file_id)
            return self.file_service.read_file_content(record) if record is not None else None

        return load_image

    def _result_filename(self, job: DocumentJobRecord) -> str:
        source_file = self.file_repository.get_document_file(job.source_file_id)
        if source_file is None:
            return f"{job.id}.docx"
        source_stem = Path(source_file.original_filename).stem.strip() or job.id
        return f"{source_stem}.docx"

    def _mark_succeeded(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        # legacy 明确主件可下载，但无 receipt 不能生成或伪造与当前来源绑定的预览。
        preview_contribution = None
        if "word_preview" in job.request_snapshot:
            from app.services.preview.models import PreviewPolicy
            policy = PreviewPolicy.model_validate(job.request_snapshot["word_preview"])
            preview_contribution = {"quality_status": "blocked" if policy.required else "pending",
                "status": "unavailable", "error_code": "preview_provider_unavailable",
                "source_generation": job.retry_count, "source_result_file_id": job.result_file_id,
                "profile_id": policy.profile_id, "profile_sha256": policy.profile_sha256,
                "manifest_file_id": None}
        completed = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"uploading"},
            expected_retry_count=job.retry_count,
            expected_document_ir_file_id=job.document_ir_file_id, require_no_prepared_result=True,
            preview_contribution=preview_contribution,
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
            failed_stage=failure_policy.failed_stage_for_current_stage(job.stage),
            error_code="document_job_timeout",
            allow_prepared_result=True,
            error_message=f"P0 文档任务超过 {self.settings.p0_document_job_timeout_seconds} 秒超时限制。",
            trace_id=trace_id,
        )

    def _fail_stage_attempt(
        self, job: DocumentJobRecord, error: Exception, *, trace_id: str | None,
    ) -> DocumentJobRecord:
        """只使用本调用已接收的阶段快照归类失败，持久化仍核对代数、IR 和结果空槽。"""

        if isinstance(error, SoftTimeLimitExceeded):
            self.logger.error(
                "[trace_id=%s job_id=%s generation=%s stage=%s status=failure_observed error_code=document_job_timeout]",
                trace_id, job.id, job.retry_count, job.stage,
            )
            return self._mark_timed_out(job, trace_id=trace_id)
        failed_stage, error_code, error_message = failure_policy.stage_attempt_failure(error, job.stage)
        # CAS 落败也保留原调用的安全诊断；外端异常正文和异常链不进入普通日志。
        self.logger.error(
            "[trace_id=%s job_id=%s generation=%s stage=%s status=failure_observed error_code=%s error_type=%s]",
            trace_id, job.id, job.retry_count, failed_stage, error_code, type(error).__name__,
        )
        return self._mark_failed(
            job, failed_stage=failed_stage, error_code=error_code,
            error_message=error_message, trace_id=trace_id,
            integrity=error.evidence if isinstance(error, (DocumentIRTranslationError, TranslationIntegrityError)) else None,
            formula_protection=error.formula_protection if isinstance(error, DocumentIRTranslationError) else None,
            failure_evidence=failure_policy.worker_failure_evidence(error),
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
        formula_protection: dict[str, str | int] | None = None,
        duration_ms: int | None = None,
        expected_prepared_result_file_id: str | None = None,
        allow_prepared_result: bool = False,
        failure_evidence: dict[str, Any] | None = None,
    ) -> DocumentJobRecord:
        now = utc_now()
        # 同代另一执行可能已经提交目标 IR；失败 CAS 不能跨过其原子 rendering 推进。
        failed = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"pending", "queued", "running"},
            allowed_stages={job.stage},
            expected_retry_count=job.retry_count,
            expected_document_ir_file_id=job.document_ir_file_id,
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
            **build_renderer_event_summary(failure_evidence or {}),
            **({"prepared_result_file_id": failed.prepared_result.file.id} if failed.prepared_result else {}),
        }
        if integrity is not None:
            payload["integrity"] = integrity.to_dict()
        if formula_protection is not None:
            payload["formula_protection"] = formula_protection
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
            result_host_allowlist=self.settings.allowed_mineru_result_hosts,
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
            self.execution_service.translation_batches.execute_translation_batch(batch_id, trace_id=trace_id)
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
