"""翻译批次失败收口：重试/终态判定、疑似截断拆分与存储失败收口。"""

from __future__ import annotations

from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.repository import TranslationBatchTreeInvalidError
from app.domains.document_jobs.translation_execution._support import (
    is_metadata_storage_error,
    recorder_call_log_file_ids,
    recorder_debug_archive_file_ids,
    translation_batch_error_code,
)
from app.domains.document_jobs.translation_execution.deps import TranslationExecutionDeps
from app.domains.document_jobs.translation_execution.generation import TranslationGenerationCoordinator
from app.domains.document_jobs.translation_execution.planning import TranslationPlanner
from app.domains.document_jobs.workflow import TranslationRootPlan
from app.domains.resources.models import utc_now
from app.domains.translation.audit import TranslationCallAuditRecorder
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError
from app.domains.translation.provider import TranslationProviderResponseError


class TranslationFailureHandler:
    """处理单批次失败：可拆分时原子拆分为子批次，否则按剩余 attempt 与调用预算登记 retryable。"""

    def __init__(
        self,
        deps: TranslationExecutionDeps,
        *,
        planner: TranslationPlanner,
        generation: TranslationGenerationCoordinator,
    ) -> None:
        self.deps = deps
        self.planner = planner
        self.generation = generation

    def handle_failure(
        self,
        batch: DocumentJobTranslationBatchRecord,
        job: DocumentJobRecord,
        *,
        error: Exception,
        recorder: TranslationCallAuditRecorder | None,
        trace_id: str | None,
        duration_ms: int,
    ) -> DocumentJobTranslationBatchRecord:
        error_code = translation_batch_error_code(error)
        error_message = str(error) if isinstance(error, TranslationIntegrityError) else "翻译 Provider 调用或批次处理失败。"
        current = self.deps.job_repository.get_document_job(job.id)
        if current is None or current.retry_count != batch.generation or current.status != "running" or current.stage != "translating":
            return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
        try:
            _source_file, source_document_ir = self.planner.read_source(
                current, batch.source_document_ir_file_id,
            )
            expected_plans = self.planner.build_expected_plans(current, source_document_ir)
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError) as exc:
            self.deps.lifecycle.mark_failed(
                current,
                failed_stage="translating",
                error_code="oss_failed" if isinstance(exc, (FileNotFoundError, OSError)) else "translation_failed",
                error_message="翻译批次计划重建失败。",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
            )
            return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
        if self._should_split(batch, error):
            try:
                split = self._split(
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
                latest = self.deps.job_repository.get_document_job(batch.job_id)
                if latest is None or latest.retry_count != batch.generation:
                    return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
                self.deps.lifecycle.mark_failed(
                    job,
                    failed_stage="translating",
                    error_code="translation_batch_tree_invalid",
                    error_message="翻译批次计划与当前 source/config 不一致。",
                    trace_id=trace_id,
                )
                return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
            self.generation.enqueue_runnable(job, generation=batch.generation, trace_id=trace_id)
            return split

        retryable = (
            batch.attempt_count < batch.max_attempts
            and self.generation.provider_call_budget_remaining(job, batch)
        )
        try:
            failed = self.deps.translation_batch_repository.update_translation_batch_if_current(
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
                ai_call_log_file_ids=recorder_call_log_file_ids(recorder),
                debug_archive_file_ids=recorder_debug_archive_file_ids(recorder),
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
            if not is_metadata_storage_error(exc):
                raise
            self.deps.lifecycle.mark_failed(
                current,
                failed_stage="translating",
                error_code="oss_failed",
                error_message="翻译批次状态写入失败。",
                trace_id=trace_id,
            )
            return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
        if failed is None:
            return self.generation.reconcile_atomic_rejection(
                batch, generation=batch.generation, trace_id=trace_id,
            )
        self.deps.lifecycle.record_event(
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
        self.generation.finalize(job.id, generation=failed.generation, trace_id=trace_id)
        return failed

    def _should_split(self, batch: DocumentJobTranslationBatchRecord, error: Exception) -> bool:
        return (
            isinstance(error, TranslationProviderResponseError)
            and error.suspected_truncation
            and len(batch.item_ids) > 1
            and self.generation.provider_call_budget_remaining_for_batch(batch)
        )

    def _split(
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
        _source_file, source_document_ir = self.planner.read_source(job, batch.source_document_ir_file_id)
        targets, items = self.deps.document_ir_translation_service.extract_translation_items(source_document_ir)
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
            page_start, page_end = self.planner.page_range_for_item_ids(child_item_ids, targets_by_id)
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
        expected_plans = self.planner.build_expected_plans(job, source_document_ir)
        split_result = self.deps.translation_batch_repository.split_translation_batch(
            batch.id,
            expected_generation=batch.generation,
            expected_attempt_count=batch.attempt_count,
            expected_lease_owner=batch.lease_owner or "",
            expected_plans=expected_plans,
            children=child_records,
        )
        if split_result is None:
            return self.generation.reconcile_atomic_rejection(
                batch, generation=batch.generation, trace_id=trace_id,
            )
        split, _children = split_result
        annotated = self.deps.translation_batch_repository.update_translation_batch_if_current(
            split.id,
            allowed_statuses={"split"},
            expected_generation=split.generation,
            expected_attempt_count=split.attempt_count,
            expected_lease_owner=None,
            expected_job_id=split.job_id,
            expected_job_status={"running"},
            expected_job_stages={"translating"},
            expected_plans=expected_plans,
            ai_call_log_file_ids=recorder_call_log_file_ids(recorder),
            debug_archive_file_ids=recorder_debug_archive_file_ids(recorder),
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
            return self.generation.reconcile_atomic_rejection(
                split, generation=split.generation, trace_id=trace_id,
            )
        self.deps.lifecycle.record_event(
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

    def fail_storage(
        self,
        batch: DocumentJobTranslationBatchRecord,
        job: DocumentJobRecord,
        *,
        expected_plans: list[TranslationRootPlan],
        error_message: str,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        """批次结果或状态写入失败时，以原代次安全收口且不重调 Provider。"""

        current = self.deps.job_repository.get_document_job(batch.job_id)
        if current is None or current.retry_count != batch.generation:
            return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
        self.deps.lifecycle.mark_failed(
            job,
            failed_stage="translating",
            error_code="oss_failed",
            error_message=error_message,
            trace_id=trace_id,
        )
        failed_batch = self.deps.translation_batch_repository.update_translation_batch_if_current(
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
        return failed_batch or self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
