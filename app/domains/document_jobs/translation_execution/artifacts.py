"""翻译制品持久化：批次结果 Artifact 与译后 DocumentIR 的登记。"""

from __future__ import annotations

import json
import sqlite3
import time
from uuid import uuid4

from app.domains.document_jobs.execution_support import document_ir_layout_metadata
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.publication_provenance import save_translation_publication_provenance
from app.domains.document_jobs.translation_execution._support import (
    TranslationBatchStorageError,
    is_metadata_storage_error,
    recorder_call_log_file_ids,
    recorder_debug_archive_file_ids,
    translation_batch_error_code,
)
from app.domains.document_jobs.translation_execution.deps import TranslationExecutionDeps
from app.domains.document_jobs.translation_execution.integrity_binding import TranslationIntegrityBinder
from app.domains.document_jobs.translation_execution.planning import TranslationPlanner
from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now
from app.domains.translation.audit import TranslationCallAuditRecorder
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import (
    TranslationIntegrityError,
    TranslationIntegrityEvidence,
    ValidatedTranslationBatch,
)
from app.domains.translation.models import TranslationProviderResult
from app.domains.translation.modes import spec_for_document_job_mode
from app.domains.translation.provider import TranslationProviderResponseError
from app.services.document_ir.table_reference_assets import decode_table_references


class TranslationArtifactStore:
    """登记批次结果与译后 DocumentIR；译后 IR 登记成功即把任务推进到 rendering。"""

    def __init__(
        self,
        deps: TranslationExecutionDeps,
        *,
        planner: TranslationPlanner,
        binder: TranslationIntegrityBinder,
    ) -> None:
        self.deps = deps
        self.planner = planner
        self.binder = binder

    def register_batch_result(
        self,
        job: DocumentJobRecord,
        *,
        batch: DocumentJobTranslationBatchRecord,
        result: TranslationProviderResult,
        validated: ValidatedTranslationBatch,
        integrity: TranslationIntegrityEvidence,
        recorder: TranslationCallAuditRecorder | None,
        publication_provenance: dict | None = None,
    ) -> DocumentFileRecord:
        payload = {
            "schema_version": "translation-batch-result/v1",
            "publication_provenance": publication_provenance,
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
            return self.deps.file_service.register_generated_content(
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
                    "ai_call_log_file_ids": recorder_call_log_file_ids(recorder),
                    "debug_archive_file_ids": recorder_debug_archive_file_ids(recorder),
                    "retry_count": job.retry_count,
                },
            )
        except (RuntimeError, ValueError, FileNotFoundError, OSError, sqlite3.Error) as exc:
            raise TranslationBatchStorageError("翻译批次结果 Artifact 写入失败。") from exc
        except Exception as exc:
            if not is_metadata_storage_error(exc):
                raise
            raise TranslationBatchStorageError("翻译批次结果 Artifact 写入失败。") from exc

    def register_translated_document_ir(
        self,
        job: DocumentJobRecord,
        *,
        succeeded_batches: list[DocumentJobTranslationBatchRecord],
        trace_id: str | None,
    ) -> DocumentJobRecord:
        current = self.deps.job_repository.get_document_job(job.id)
        if current is None or current.retry_count != job.retry_count or current.status != "running" or current.stage != "translation_validating":
            return current or job
        job = current
        started_at = time.perf_counter()
        try:
            source_file, source_document_ir = self.planner.read_source(job, job.source_document_ir_file_id)
        except (DocumentIRTranslationError, TranslationIntegrityError, ValueError) as exc:
            return self.deps.lifecycle.mark_failed(
                job,
                failed_stage="translation_validating",
                error_code="translation_failed",
                error_message=f"翻译 source 校验失败: {translation_batch_error_code(exc)}",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except (FileNotFoundError, OSError) as exc:
            return self.deps.lifecycle.mark_failed(
                job,
                failed_stage="translation_validating",
                error_code="oss_failed",
                error_message=f"翻译 source 校验失败: {translation_batch_error_code(exc)}",
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        try:
            translated = source_document_ir.model_copy(deep=True)
            targets, items = self.deps.document_ir_translation_service.extract_translation_items(translated)
            publication_calls = []
            replacements = self.binder.load_batch_replacements(job, source_file, items, succeeded_batches,
                                                        publication_calls=publication_calls)
        except (DocumentIRTranslationError, TranslationIntegrityError, TranslationProviderResponseError, ValueError, FileNotFoundError, OSError) as exc:
            error_code = (
                "oss_failed" if isinstance(exc, (FileNotFoundError, OSError))
                else "translation_fan_in_mismatch" if getattr(exc, "code", None) == "translation_fan_in_mismatch"
                else "translation_failed"
            )
            return self.deps.lifecycle.mark_failed(
                job,
                failed_stage="translation_validating",
                error_code=error_code,
                error_message=f"翻译批次合并校验失败: {translation_batch_error_code(exc)}",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        expected_ids = [item.id for item in items]
        missing_ids = [item_id for item_id in expected_ids if item_id not in replacements]
        extra_ids = sorted(set(replacements) - set(expected_ids))
        if missing_ids or extra_ids:
            return self.deps.lifecycle.mark_failed(
                job,
                failed_stage="translation_validating",
                error_code="translation_fan_in_mismatch",
                error_message=f"翻译批次合并结果不完整: missing={len(missing_ids)} extra={len(extra_ids)}",
                trace_id=trace_id,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        self.deps.document_ir_translation_service.apply_replacements(translated, targets, replacements)
        spec = spec_for_document_job_mode(job.mode)
        if spec.language_pair is None:
            raise DocumentIRTranslationError("当前任务不是翻译任务。")
        translated.metadata.document_language = self.deps.document_ir_translation_service._target_document_language(spec.language_pair)
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
            "skipped_degraded_page_numbers": sorted(record["page_index"] + 1
                                                    for record in translated.metadata.degraded_pages),
        }
        translation_provenance = save_translation_publication_provenance(job, publication_calls, file_service=self.deps.file_service)
        translation_metadata["publication_provenance_file_id"] = translation_provenance.id
        decode_table_references(translated, require_bound=True)
        ir_content = translated.model_dump_json(indent=2).encode("utf-8")
        try:
            ir_file = self.deps.file_service.register_generated_content(
                tenant_id=job.tenant_id,
                company_id=job.company_id,
                job_id=job.id,
                created_by=job.created_by,
                file_type="document_ir",
                filename="document_ir_v2.json",
                object_version=(f"g{job.retry_count}_{uuid4().hex}" if translated.metadata.table_references_version else None),
                mime_type="application/json",
                content=ir_content,
                metadata={
                    "source_file_id": job.source_file_id,
                    "source_document_ir_file_id": job.source_document_ir_file_id,
                    "image_asset_count": len(job.image_asset_file_ids),
                    "retry_count": job.retry_count,
                    "translation": translation_metadata,
                    **document_ir_layout_metadata(translated),
                },
            )
        except (RuntimeError, ValueError) as exc:
            raise OSError(str(exc)) from exc
        updated = self.deps.job_repository.update_document_job_if_current(
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
            return self.deps.job_repository.get_document_job(job.id) or job
        self.deps.lifecycle.record_event(
            updated,
            event_type="file_registered",
            stage="translation_validating",
            message="翻译后的 DocumentIR 已保存。",
            payload={
                "file_id": ir_file.id,
                "file_type": ir_file.file_type,
                "object_key": ir_file.object_key,
                **document_ir_layout_metadata(translated),
            },
            trace_id=trace_id,
        )
        return updated
