"""翻译批次执行：领取与租约、Provider 调用、调用审计与成功提交。"""

from __future__ import annotations

import sqlite3
import time
from datetime import timedelta
from uuid import uuid4

from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.publication_provenance import batch_publication_provenance
from app.domains.document_jobs.repository import TranslationBatchTreeInvalidError
from app.domains.document_jobs.translation_execution._support import (
    TranslationBatchStorageError,
    is_metadata_storage_error,
    recorder_call_log_file_ids,
    recorder_debug_archive_file_ids,
    translation_batch_error_code,
)
from app.domains.document_jobs.translation_execution.artifacts import TranslationArtifactStore
from app.domains.document_jobs.translation_execution.deps import TranslationExecutionDeps
from app.domains.document_jobs.translation_execution.failure import TranslationFailureHandler
from app.domains.document_jobs.translation_execution.generation import TranslationGenerationCoordinator
from app.domains.document_jobs.translation_execution.integrity_binding import TranslationIntegrityBinder
from app.domains.document_jobs.translation_execution.planning import TranslationPlanner
from app.domains.resources.models import utc_now
from app.domains.translation.audit import TranslationCallAuditRecorder
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError
from app.domains.translation.models import TranslationProviderResult
from app.domains.translation.provider import TranslationProviderCallError


class TranslationBatchRunner:
    """执行单个 provider batch task；重复投递依赖批次状态与租约幂等收敛。"""

    def __init__(
        self,
        deps: TranslationExecutionDeps,
        *,
        planner: TranslationPlanner,
        binder: TranslationIntegrityBinder,
        artifacts: TranslationArtifactStore,
        generation: TranslationGenerationCoordinator,
        failures: TranslationFailureHandler,
    ) -> None:
        self.deps = deps
        self.planner = planner
        self.binder = binder
        self.artifacts = artifacts
        self.generation = generation
        self.failures = failures

    def run(self, batch_id: str, *, trace_id: str | None = None) -> DocumentJobTranslationBatchRecord | None:
        """执行单个 provider batch task；重复投递依赖 batch 状态幂等收敛。"""

        batch = self.deps.translation_batch_repository.get_translation_batch(batch_id)
        if batch is None:
            return None
        job = self.deps.job_repository.get_document_job(batch.job_id)
        if job is None:
            return batch
        if job.status == "canceled":
            return self.generation.cancel_batch(batch, trace_id=trace_id)
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
            self.generation.finalize(
                job.id, generation=batch.generation, trace_id=trace_id,
            )
            return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
        claimed = self.claim(batch, trace_id=trace_id)
        if claimed is None:
            reconciled = self.generation.reconcile_atomic_rejection(
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
            source_file, source_document_ir = self.planner.read_source(job, claimed.source_document_ir_file_id)
            _targets, items = self.deps.document_ir_translation_service.extract_translation_items(source_document_ir)
            items_by_id = {item.id: item for item in items}
            batch_items = [items_by_id[item_id] for item_id in claimed.item_ids]
            term_version = self.planner.resolve_term_version(job)
            translation_profile = self.planner.profile_for_job(
                job,
                language_pair=claimed.language_pair,
            )
            recorder = (
                self.deps.translation_audit_service.build_recorder(
                    job=job,
                    term_version=term_version,
                    trace_id=trace_id,
                    save_full_text=job.debug_full_text_enabled,
                )
                if self.deps.translation_audit_service is not None
                else None
            )
            prepared = self.deps.document_ir_translation_service.build_provider_request(
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
                max_chars_per_request=self.planner.profile_batch_limits(translation_profile)[1],
            )
            request = prepared.request
            binding = self.binder.binding(job, claimed, source_file, translation_profile, term_version)
            provider_called = True
            try:
                result = self.deps.document_ir_translation_service.provider.translate(request)
            except TranslationProviderCallError:
                raise
            except Exception:
                # 外部异常可夹带正文；在调用边界转成固定安全描述，保留既有失败路径。
                raise RuntimeError("翻译 Provider 调用失败。") from None
            validated = self.deps.document_ir_translation_service.validator.validate(
                prepared.source_items, prepared.encoded_batch, result,
            )
            integrity = validated.evidence.bind(binding)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if recorder is not None:
                audit_started = True
                recorder.record_success(request, result, duration_ms=duration_ms, integrity=integrity)
                self._record_audit_events(job, recorder, trace_id=trace_id)
                audit_completed = True
            current = self.deps.job_repository.get_document_job(job.id)
            if current is None or current.retry_count != claimed.generation or current.status != "running" or current.stage != "translating":
                return self.deps.translation_batch_repository.get_translation_batch(claimed.id)
            current_summary = self.generation.summarize(current)
            if current_summary is not None and current_summary.outcome in {
                "failed", "completed", "canceled", "validating",
            }:
                # Provider 调用已经真实发生，但终态闸门先于结果登记；该响应只能保留审计。
                self.generation.finalize(
                    current.id, generation=claimed.generation, trace_id=trace_id,
                )
                return self.deps.translation_batch_repository.get_translation_batch(claimed.id) or claimed
            _source_file, current_source_ir = self.planner.read_source(
                current, claimed.source_document_ir_file_id,
            )
            expected_plans = self.planner.build_expected_plans(current, current_source_ir)
            try:
                result_file = self.artifacts.register_batch_result(
                    job,
                    batch=claimed,
                    result=result,
                    validated=validated,
                    integrity=integrity,
                    recorder=recorder,
                    publication_provenance=batch_publication_provenance(result=result, integrity=integrity,
                        batch=claimed, profile=translation_profile, term_version=term_version),
                )
            except (RuntimeError, ValueError, FileNotFoundError, OSError) as exc:
                # Provider 已成功且审计已落盘；结果 Artifact 的 I/O 失败不能再次调用 Provider。
                raise TranslationBatchStorageError("翻译批次结果 Artifact 写入失败。") from exc
            try:
                succeeded = self.deps.translation_batch_repository.update_translation_batch_if_current(
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
                    ai_call_log_file_ids=recorder_call_log_file_ids(recorder),
                    debug_archive_file_ids=recorder_debug_archive_file_ids(recorder),
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
                raise TranslationBatchStorageError("翻译批次状态提交失败。") from exc
            except Exception as exc:
                if not is_metadata_storage_error(exc):
                    raise
                raise TranslationBatchStorageError("翻译批次状态提交失败。") from exc
            if succeeded is None:
                return self.generation.reconcile_atomic_rejection(
                    claimed, generation=claimed.generation, trace_id=trace_id,
                )
            self.deps.lifecycle.record_event(
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
            self.generation.finalize(job.id, generation=succeeded.generation, trace_id=trace_id)
            return succeeded
        except TranslationBatchTreeInvalidError:
            # 权威 source/config 与持久化批次树不一致时，不能把它伪装成 Provider 失败。
            current = self.deps.job_repository.get_document_job(claimed.job_id)
            if current is None or current.retry_count != claimed.generation:
                return self.deps.translation_batch_repository.get_translation_batch(claimed.id) or claimed
            self.deps.lifecycle.mark_failed(
                job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return self.deps.translation_batch_repository.get_translation_batch(claimed.id) or claimed
        except TranslationBatchStorageError as exc:
            return self.failures.fail_storage(
                claimed,
                job,
                expected_plans=expected_plans,
                error_message=failure_policy.worker_failure_message(exc),
                trace_id=trace_id,
            )
        except (KeyError, ValueError, RuntimeError, FileNotFoundError, OSError) as exc:
            # 审计自身失败须可见，不能再把同一次调用登记成另一份失败审计。
            if audit_started and not audit_completed:
                raise
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if recorder is not None and provider_called and not audit_started:
                integrity = exc.evidence if isinstance(exc, TranslationIntegrityError) else self.deps.document_ir_translation_service.validator.call_failure_evidence(
                    prepared.source_items, prepared.encoded_batch, error_code=translation_batch_error_code(exc),
                )
                recorder.record_failure(request, result, error=exc, duration_ms=duration_ms, integrity=integrity.bind(binding))
                self._record_audit_events(job, recorder, trace_id=trace_id)
            try:
                return self.failures.handle_failure(
                    claimed,
                    job,
                    error=exc,
                    recorder=recorder,
                    trace_id=trace_id,
                    duration_ms=duration_ms,
                )
            except TranslationBatchTreeInvalidError:
                current = self.deps.job_repository.get_document_job(claimed.job_id)
                if current is None or current.retry_count != claimed.generation:
                    return self.deps.translation_batch_repository.get_translation_batch(claimed.id) or claimed
                self.deps.lifecycle.mark_failed(
                    job,
                    failed_stage="translating",
                    error_code="translation_batch_tree_invalid",
                    error_message="翻译批次计划与当前 source/config 不一致。",
                    trace_id=trace_id,
                )
                return self.deps.translation_batch_repository.get_translation_batch(claimed.id) or claimed

    def claim(
        self,
        batch: DocumentJobTranslationBatchRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord | None:
        current_job = self.deps.job_repository.get_document_job(batch.job_id)
        if (
            current_job is None
            or current_job.status != "running"
            or current_job.stage != "translating"
            or current_job.retry_count != batch.generation
        ):
            return None
        try:
            summary = self.generation.summarize(current_job)
        except TranslationBatchTreeInvalidError:
            self.deps.lifecycle.mark_failed(
                current_job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return None
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
            self.deps.lifecycle.mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划校验失败。",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
            )
            return None
        if summary is not None and summary.outcome in {"failed", "completed", "canceled", "validating"}:
            self.generation.finalize(
                current_job.id, generation=batch.generation, trace_id=trace_id,
            )
            return None
        try:
            _source_file, source_document_ir = self.planner.read_source(
                current_job, current_job.source_document_ir_file_id,
            )
            expected_plans = self.planner.build_expected_plans(current_job, source_document_ir)
        except TranslationBatchTreeInvalidError:
            self.generation.finalize(
                current_job.id, generation=batch.generation, trace_id=trace_id,
            )
            return None
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
            if isinstance(exc, TranslationIntegrityError) and exc.code == "translation_request_budget_exceeded":
                _snapshot_job, installed_batches = self.generation.snapshot(
                    current_job.id, generation=batch.generation,
                )
                failed = self.deps.translation_batch_repository.update_translation_batch_if_current(
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
                    error_message=failure_policy.worker_failure_message(exc),
                    retryable=False,
                    updated_at=utc_now(),
                )
                self.deps.lifecycle.mark_failed(
                    current_job,
                    failed_stage="translating",
                    error_code="translation_failed",
                    error_message=failure_policy.worker_failure_message(exc),
                    trace_id=trace_id,
                )
                return None
            self.deps.lifecycle.mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划校验失败。",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
            )
            return None
        now = utc_now()
        lease_owner = f"translation_batch_worker:{uuid4().hex}"
        try:
            claimed = self.deps.translation_batch_repository.claim_translation_batch(
                batch.id,
                expected_generation=batch.generation,
                expected_attempt_count=batch.attempt_count,
                lease_owner=lease_owner,
                leased_at=now,
                lease_expires_at=now + timedelta(seconds=self.deps.settings.translation_provider_batch_lease_seconds),
                provider_call_budget=batch.provider_call_budget,
                expected_plans=expected_plans,
            )
        except TranslationBatchTreeInvalidError:
            self.deps.lifecycle.mark_failed(
                current_job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return None
        except (FileNotFoundError, OSError, sqlite3.Error) as exc:
            self.deps.lifecycle.mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划读取失败。",
                trace_id=trace_id,
            )
            return None
        except Exception as exc:
            if not is_metadata_storage_error(exc):
                raise
            self.deps.lifecycle.mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed",
                error_message="翻译批次计划读取失败。",
                trace_id=trace_id,
            )
            return None
        if claimed is None:
            self.generation.reconcile_atomic_rejection(
                batch, generation=batch.generation, trace_id=trace_id,
            )
            return None
        job = self.deps.job_repository.get_document_job(batch.job_id)
        if job is not None:
            self.deps.lifecycle.record_event(
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

    def _mark_translating_started(
        self, job: DocumentJobRecord, *, trace_id: str | None,
    ) -> DocumentJobRecord:
        """源 IR 已落盘后提交翻译阶段；事件失败时沿用已提交阶段收尾。"""

        if job.stage != "ir_converting":
            return job
        translating = self.deps.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses={"running"},
            allowed_stages={"ir_converting"},
            expected_retry_count=job.retry_count,
            stage="translating",
            progress=max(job.progress, 45),
            updated_at=utc_now(),
        )
        if translating is None:
            return self.deps.job_repository.get_document_job(job.id) or job
        try:
            self.deps.lifecycle.record_event(
                translating,
                event_type="stage_succeeded",
                stage="ir_converting",
                message="源 DocumentIR 转换已完成。",
                payload={"source_document_ir_file_id": translating.source_document_ir_file_id},
                trace_id=trace_id,
            )
            self.deps.lifecycle.record_event(
                translating,
                event_type="stage_started",
                stage="translating",
                message="DocumentIR 翻译已开始。",
                payload={"source_document_ir_file_id": translating.source_document_ir_file_id},
                trace_id=trace_id,
            )
        except Exception as exc:
            return self.deps.lifecycle.fail_stage_attempt(translating, exc, trace_id=trace_id)
        return translating

    def _record_audit_events(
        self,
        job: DocumentJobRecord,
        recorder: TranslationCallAuditRecorder | None,
        *,
        trace_id: str | None,
    ) -> None:
        if recorder is None:
            return
        debug_archive_file_ids = recorder_debug_archive_file_ids(recorder)
        for index, call_log_file_id in enumerate(recorder_call_log_file_ids(recorder)):
            debug_archive_file_id = debug_archive_file_ids[index] if index < len(debug_archive_file_ids) else None
            self.deps.lifecycle.record_event(
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
            self.deps.lifecycle.record_event(
                job,
                event_type="debug_archive_saved",
                stage="translating",
                message="AI 翻译全文调试归档已保存。",
                payload={
                    "file_id": debug_archive_file_id,
                    "file_type": "ai_debug_archive",
                    "retention_days": max(1, self.deps.settings.translation_debug_archive_retention_days),
                },
                trace_id=trace_id,
            )
