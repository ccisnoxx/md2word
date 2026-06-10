from __future__ import annotations

# app/domains/document_jobs/execution.py: 提供 document_jobs Worker 投递端口和幂等执行骨架。

import logging
import secrets
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from app.clients.mineru_client import MinerUClient, MinerUError
from app.core.config import Settings
from app.domains.document_jobs.models import (
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobRecord,
    DocumentJobStage,
)
from app.core.errors import ApiError
from app.services.document_ir.models import DocumentIR, DocumentIRAsset
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import utc_now
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
)
from app.services.document_ir import MinerUToDocumentIRService
from app.services.renderer import DocumentIRWordRenderer
from app.services.renderer.layout_plan import LayoutPlan, build_layout_plan
from app.domains.translation.audit import (
    TranslationAuditService,
    TranslationCallAuditRecorder,
)
from app.domains.translation.document_ir_translator import (
    DocumentIRTranslationError,
    DocumentIRTranslationService,
)


class DocumentJobTaskQueueProtocol(Protocol):
    """document_jobs 后台任务投递端口；业务幂等性由 job_id 执行骨架保证。"""

    def enqueue(self, job_id: str, *, trace_id: str | None) -> str | None:
        """投递一个按 job_id 执行的后台任务，返回底层队列任务 ID。"""


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
        file_repository: DocumentFileRepositoryProtocol,
        file_service: FileUploadService,
        document_ir_service: MinerUToDocumentIRService,
        template_read_service: Any,
        word_renderer: DocumentIRWordRenderer,
        document_ir_translation_service: DocumentIRTranslationService | None = None,
        term_version_service: Any | None = None,
        translation_audit_service: TranslationAuditService | None = None,
        mineru_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.file_repository = file_repository
        self.file_service = file_service
        self.document_ir_service = document_ir_service
        self.template_read_service = template_read_service
        self.word_renderer = word_renderer
        self.document_ir_translation_service = document_ir_translation_service
        self.term_version_service = term_version_service
        self.translation_audit_service = translation_audit_service
        self.mineru_client_factory = mineru_client_factory or self._build_mineru_client
        self.logger = logging.getLogger("business")

    def execute_job(self, job_id: str, *, trace_id: str | None = None) -> DocumentJobRecord | None:
        """执行一个 document_job；重复投递时不会重复推进已完成的骨架阶段。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            return None
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
        queued = self.job_repository.update_document_job(
            job.id,
            status="queued",
            stage="uploaded",
            progress=max(job.progress, 5),
            updated_at=now,
        )
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
        running = self.job_repository.update_document_job(
            job.id,
            status="running",
            stage="parsing",
            progress=max(job.progress, 10),
            started_at=job.started_at or now,
            error_code=None,
            error_message=None,
            failed_stage=None,
            updated_at=now,
        )
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
            return self.job_repository.update_document_job(
                job.id,
                status="running",
                stage="parsed",
                progress=max(job.progress, 30),
                updated_at=utc_now(),
            )

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
                    language=self.settings.mineru_language,
                    callback=callback,
                    seed=callback_seed,
                )
                job = self.job_repository.update_document_job(
                    job.id,
                    mineru_batch_id=batch_id,
                    mineru_data_id=data_id,
                    mineru_callback_seed=callback_seed,
                    progress=max(job.progress, 15),
                    updated_at=utc_now(),
                )
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
                waiting = self.job_repository.update_document_job(
                    job.id,
                    status="running",
                    stage="parsing",
                    progress=max(job.progress, 20),
                    updated_at=utc_now(),
                )
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

    def process_mineru_callback_for_job(
        self,
        job: DocumentJobRecord,
        payload: dict[str, Any],
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """消费 document_job 的 MinerU callback，并在结果就绪时继续推进后续阶段。"""

        if job.status in {"succeeded", "failed", "canceled"}:
            return job
        if job.status != "running" or job.stage != "parsing":
            raise ValueError(f"当前 document_job 状态不允许处理 MinerU callback: status={job.status} stage={job.stage}")

        state = str(payload.get("state") or "").lower()
        batch_id = str(payload.get("batch_id") or job.mineru_batch_id or "").strip()
        data_id = str(payload.get("data_id") or job.mineru_data_id or job.id).strip()
        if batch_id and batch_id != (job.mineru_batch_id or ""):
            job = self.job_repository.update_document_job(job.id, mineru_batch_id=batch_id, updated_at=utc_now())
        if data_id and data_id != (job.mineru_data_id or ""):
            job = self.job_repository.update_document_job(job.id, mineru_data_id=data_id, updated_at=utc_now())

        if state == "failed":
            return self._mark_failed(
                job,
                failed_stage="parsing",
                error_code="mineru_failed",
                error_message="MinerU callback 返回 failed。",
                trace_id=trace_id,
            )

        full_zip_url = payload.get("full_zip_url")
        if state not in {"done", "success", "succeeded"} or not full_zip_url:
            waiting = self.job_repository.update_document_job(
                job.id,
                status="running",
                stage="parsing",
                progress=max(job.progress, 20),
                updated_at=utc_now(),
            )
            self._record_event(
                waiting,
                event_type="stage_started",
                stage="parsing",
                message="MinerU callback 已接收，结果尚未就绪。",
                payload={"mineru_batch_id": batch_id or None, "mineru_state": state or "unknown"},
                trace_id=trace_id,
            )
            return waiting

        with tempfile.TemporaryDirectory(prefix="document_job_mineru_callback_") as temp_dir:
            parsed = self._download_and_register_mineru_result(
                job,
                client=self.mineru_client_factory(),
                full_zip_url=str(full_zip_url),
                batch_id=batch_id or str(job.mineru_batch_id or ""),
                data_id=data_id or job.id,
                temp_dir=Path(temp_dir),
                trace_id=trace_id,
            )
        return self.execute_job(parsed.id, trace_id=trace_id) or parsed

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
    ) -> DocumentJobRecord:
        """下载 MinerU 原始结果包，登记为 document_file 并把任务推进到 parsed。"""

        raw_zip_path = temp_dir / "mineru_raw_result.zip"
        client.download_result_zip(full_zip_url, raw_zip_path)
        raw_file = self.file_service.register_generated_content(
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            file_type="mineru_raw_result",
            filename="mineru_raw_result.zip",
            mime_type="application/zip",
            content=raw_zip_path.read_bytes(),
            metadata={
                "source_file_id": job.source_file_id,
                "mineru_batch_id": batch_id,
                "mineru_data_id": data_id,
                "full_zip_url": full_zip_url,
            },
        )
        parsed = self.job_repository.update_document_job(
            job.id,
            status="running",
            stage="parsed",
            progress=max(job.progress, 30),
            mineru_raw_result_file_id=raw_file.id,
            updated_at=utc_now(),
        )
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
            job.id,
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
        converting = self.job_repository.update_document_job(
            job.id,
            status="running",
            stage="ir_converting",
            progress=max(job.progress, 40),
            updated_at=now,
        )
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
            return self.job_repository.update_document_job(
                job.id,
                status="running",
                stage="rendering",
                progress=max(job.progress, 60),
                updated_at=utc_now(),
            )

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

        document_ir = result.document
        translation_metadata: dict[str, Any] = {"applied": False}
        if job.mode == "en2zh_pdf_to_word":
            document_ir, translation_metadata = self._translate_document_ir(
                job,
                document_ir,
                trace_id=trace_id,
            )

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
                "translation": translation_metadata,
                **ir_layout_metadata,
            },
        )
        updated = self.job_repository.update_document_job(
            job.id,
            status="running",
            stage="rendering",
            progress=max(job.progress, 60),
            document_ir_file_id=ir_file.id,
            image_asset_file_ids=image_file_ids,
            updated_at=utc_now(),
        )
        if image_file_ids:
            self._record_event(
                updated,
                event_type="file_registered",
                stage="ir_converting",
                message="DocumentIR 图片资产已保存。",
                payload={"file_ids": image_file_ids, "file_type": "image_asset"},
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
            payload={"document_ir_file_id": ir_file.id, "image_asset_file_ids": image_file_ids, **ir_layout_metadata},
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

    def _translate_document_ir(
        self,
        job: DocumentJobRecord,
        document_ir: DocumentIR,
        *,
        trace_id: str | None,
    ) -> tuple[DocumentIR, dict[str, Any]]:
        if self.document_ir_translation_service is None:
            raise DocumentIRTranslationError("DocumentIR 翻译服务未配置。")
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
            "language_pair": "en2zh",
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
                language_pair="en2zh",
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
            },
            trace_id=trace_id,
        )
        metadata = {
            "applied": True,
            "language_pair": "en2zh",
            "term_version_id": term_version.term_version_id if term_version is not None else job.term_version_id,
            "term_snapshot_hash": term_version.snapshot_hash if term_version is not None else None,
            "ai_call_log_file_id": recorder.call_log_file_id if recorder is not None else None,
            "debug_archive_file_id": recorder.debug_archive_file_id if recorder is not None else None,
        }
        return translated, metadata

    def _record_translation_audit_events(
        self,
        job: DocumentJobRecord,
        recorder: TranslationCallAuditRecorder | None,
        *,
        trace_id: str | None,
    ) -> None:
        if recorder is None or recorder.call_log_file_id is None:
            return
        self._record_event(
            job,
            event_type="ai_call_logged",
            stage="ir_converting",
            message="AI 翻译调用审计记录已保存。",
            payload={
                "file_id": recorder.call_log_file_id,
                "file_type": "ai_call_log",
                "debug_archive_file_id": recorder.debug_archive_file_id,
            },
            trace_id=trace_id,
        )
        if recorder.debug_archive_file_id is None:
            return
        self._record_event(
            job,
            event_type="debug_archive_saved",
            stage="ir_converting",
            message="AI 翻译全文调试归档已保存。",
            payload={
                "file_id": recorder.debug_archive_file_id,
                "file_type": "ai_debug_archive",
                "retention_days": max(1, self.settings.translation_debug_archive_retention_days),
            },
            trace_id=trace_id,
        )

    def _resolve_term_version_for_job(self, job: DocumentJobRecord):
        if self.term_version_service is None:
            return None
        if job.term_version_id:
            return self.term_version_service.load_version(job.term_version_id, language_pair="en2zh")
        return self.term_version_service.resolve_for_job(None, language_pair="en2zh")

    def _render_and_save_word(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        if job.result_file_id:
            return self._mark_succeeded(job, trace_id=trace_id)
        existing_result = self._get_existing_result_file(job)
        if existing_result is not None:
            recovered = self.job_repository.update_document_job(
                job.id,
                status="running",
                stage="uploading",
                progress=max(job.progress, 90),
                result_file_id=existing_result.id,
                updated_at=utc_now(),
            )
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
        )
        uploading = self.job_repository.update_document_job(
            rendering.id,
            status="running",
            stage="uploading",
            progress=max(rendering.progress, 85),
            template_version_id=template_selection.template_version_id,
            updated_at=utc_now(),
        )
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
                **renderer_metadata,
            },
        )
        completed = self.job_repository.update_document_job(
            uploading.id,
            status="succeeded",
            stage="completed",
            progress=100,
            result_file_id=word_file.id,
            completed_at=utc_now(),
            updated_at=utc_now(),
        )
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
        completed = self.job_repository.update_document_job(
            job.id,
            status="succeeded",
            stage="completed",
            progress=100,
            completed_at=job.completed_at or utc_now(),
            updated_at=utc_now(),
        )
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
        failed = self.job_repository.update_document_job(
            job.id,
            status="failed",
            stage="failed",
            failed_stage=failed_stage,
            error_code=error_code,
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )
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

    def enqueue(self, job_id: str, *, trace_id: str | None) -> str | None:
        self.execution_service.execute_job(job_id, trace_id=trace_id)
        return f"eager:{job_id}"


class CeleryDocumentJobTaskQueue:
    """生产 Celery 队列 adapter；实际任务函数在 app.workers.document_tasks。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enqueue(self, job_id: str, *, trace_id: str | None) -> str | None:
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
