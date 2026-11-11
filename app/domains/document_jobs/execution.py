from __future__ import annotations

# app/domains/document_jobs/execution.py: 提供 document_jobs Worker 投递端口和幂等执行骨架。

import logging
import io
import json
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded

from app.core.config import Settings
from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.preview import DocumentJobPreviewService
from app.domains.document_jobs.mineru_execution import MinerUExecution
from app.domains.document_jobs.render_execution import WordRenderExecution
from app.domains.document_jobs.translation_execution import TranslationBatchExecution
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.document_jobs.models import (
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobRecord,
    DocumentJobStage,
)
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.artifact_validator import MinerUArtifactValidationError
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.table_reference_assets import (
    RASTER_EXTENSIONS, TABLE_REFERENCE_ROLE, decode_table_references,
)
from app.services.document_ir.table_placeholder import TablePlaceholderError, decode_placeholders
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
from app.services.renderer import DocumentIRWordRenderer
from app.services.renderer.evidence import build_renderer_event_summary
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.modes import is_translation_document_job_mode
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
        word_preview_service = word_preview_service or DocumentJobPreviewService(
            settings, job_repository, event_repository, file_repository, file_service)
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.file_repository = file_repository
        self.file_service = file_service
        self.document_ir_service = document_ir_service
        self.logger = logging.getLogger("business")
        # MinerU 专属依赖只交给协作者持有，未传入客户端工厂时由协作者取默认构造。
        self.mineru = MinerUExecution(
            self,
            settings=settings,
            job_repository=job_repository,
            file_service=file_service,
            callback_message_store=callback_message_store,
            mineru_config_resolver=mineru_config_resolver,
            mineru_client_factory=mineru_client_factory,
        )
        # 渲染专属依赖只交给协作者持有；settings 等共用依赖两边引用同一对象。
        self.rendering = WordRenderExecution(
            self,
            settings=settings,
            job_repository=job_repository,
            file_repository=file_repository,
            file_service=file_service,
            document_ir_service=document_ir_service,
            job_resource_snapshot_service=job_resource_snapshot_service,
            template_read_service=template_read_service,
            word_renderer=word_renderer,
            word_preview_service=word_preview_service,
        )
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
            job = self.mineru._process_replayable_callback_messages(job, trace_id=trace_id)
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
                latest = self.mineru._run_mineru_parse(latest, trace_id=trace_id)
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
                return self.rendering._render_and_save_word(latest, trace_id=trace_id)
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
                    placeholder_source_loader=lambda: self.rendering._load_placeholder_source(job),
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
