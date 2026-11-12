"""翻译代次协调：快照、权威结论、租约回收、可运行批次投递与幂等收口。

finalize 与 enqueue_runnable 互相调用（收口时补投递、投递前发现终态即收口），因此同属本模块。"""

from __future__ import annotations

import sqlite3
import time

from app.core.errors import ApiError
from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.repository import TranslationBatchTreeInvalidError
from app.domains.document_jobs.translation_execution._support import translation_batch_error_code
from app.domains.document_jobs.translation_execution.artifacts import TranslationArtifactStore
from app.domains.document_jobs.translation_execution.deps import TranslationExecutionDeps
from app.domains.document_jobs.translation_execution.planning import TranslationPlanner
from app.domains.document_jobs.workflow import TranslationGenerationSummary, reduce_translation_generation
from app.domains.resources.models import utc_now
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError
from app.domains.translation.modes import is_translation_document_job_mode


class TranslationGenerationCoordinator:
    """同一代翻译批次的调度与收口 owner；所有终态判断经 workflow.reduce_translation_generation。"""

    def __init__(
        self,
        deps: TranslationExecutionDeps,
        *,
        planner: TranslationPlanner,
        artifacts: TranslationArtifactStore,
    ) -> None:
        self.deps = deps
        self.planner = planner
        self.artifacts = artifacts

    def snapshot(
        self,
        job_id: str,
        *,
        generation: int,
    ) -> tuple[DocumentJobRecord | None, list[DocumentJobTranslationBatchRecord]]:
        """从批次仓储的同任务锁快照读取 job 与当前代批次。"""

        try:
            snapshot_job, batches = self.deps.translation_batch_repository.get_translation_batch_snapshot(job_id)
        except (FileNotFoundError, OSError):
            return None, []
        if snapshot_job.retry_count != generation:
            return snapshot_job, []
        return snapshot_job, [batch for batch in batches if batch.generation == snapshot_job.retry_count]

    def summarize(
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
            job, current_batches = self.snapshot(
                job.id, generation=requested_generation,
            )
            if job is None or job.retry_count != requested_generation:
                return None
        if not is_translation_document_job_mode(job.mode):
            return None
        if self.deps.document_ir_translation_service is None or not job.source_document_ir_file_id:
            return None
        try:
            _source_file, source_document_ir = self.planner.read_source(
                job, job.source_document_ir_file_id,
            )
            expected_plans = self.planner.build_expected_plans(job, source_document_ir)
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

    def finalize(
        self,
        job_id: str,
        *,
        generation: int,
        trace_id: str | None,
    ) -> DocumentJobRecord | None:
        job = self.deps.job_repository.get_document_job(job_id)
        if job is None or job.status in {"succeeded", "failed", "canceled"}:
            return job
        if job.status != "running" or job.stage not in {"translating", "translation_validating"} or job.retry_count != generation:
            return job
        failure_stage = job.stage
        self.reset_expired_leases(job, generation=generation, trace_id=trace_id)
        snapshot_job, batches = self.snapshot(job.id, generation=generation)
        if snapshot_job is None or snapshot_job.retry_count != generation:
            return snapshot_job or job
        job = snapshot_job
        if job.status in {"succeeded", "failed", "canceled"}:
            return job
        failure_stage = job.stage
        try:
            summary = self.summarize(job, batches)
        except TranslationBatchTreeInvalidError:
            return self.deps.lifecycle.mark_failed(
                job,
                failed_stage=failure_stage,
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError) as exc:
            return self.deps.lifecycle.mark_failed(
                job,
                failed_stage=failure_stage,
                error_code="translation_failed",
                error_message=f"翻译批次计划校验失败: {translation_batch_error_code(exc)}",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
            )
        if summary is None:
            error_code = "translation_batch_tree_invalid"
            formula_protection = None
            batch_source_ids = {batch.source_document_ir_file_id for batch in batches}
            if batches and job.source_document_ir_file_id not in batch_source_ids:
                # 当前任务指针与本代批次绑定不一致，属于完整性/代次错误，不是对象存储缺失。
                error_code = "translation_failed"
            else:
                try:
                    _source_file, source_ir = self.planner.read_source(job, job.source_document_ir_file_id)
                    self.planner.build_expected_plans(job, source_ir)
                except (FileNotFoundError, OSError, sqlite3.Error):
                    error_code = "oss_failed"
                except DocumentIRTranslationError as exc:
                    error_code = "translation_failed"
                    formula_protection = exc.formula_protection
                except (TranslationIntegrityError, ValueError):
                    error_code = "translation_failed"
            return self.deps.lifecycle.mark_failed(
                job,
                failed_stage=failure_stage,
                error_code=error_code,
                error_message="翻译批次无法由当前 source/config 重建权威计划。",
                trace_id=trace_id,
                formula_protection=formula_protection,
            )
        leaf_batches = [batch for batch in batches if batch.status != "split"]
        if summary.outcome == "failed":
            return self.deps.lifecycle.mark_failed(
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
            self.enqueue_runnable(job, generation=generation, trace_id=trace_id)
            return self.deps.job_repository.get_document_job(job.id) or job
        if summary.outcome == "canceled":
            return job
        if summary.outcome not in {"completed", "validating"}:
            return job
        if all(batch.status == "succeeded" for batch in leaf_batches):
            if job.stage == "translating":
                stage_started_at = time.perf_counter()
                validating = self.deps.job_repository.update_document_job_if_current(
                    job.id,
                    allowed_statuses={"running"},
                    allowed_stages={"translating"},
                    expected_retry_count=generation,
                    stage="translation_validating",
                    progress=max(job.progress, 55),
                    updated_at=utc_now(),
                )
                if validating is None:
                    return self.deps.job_repository.get_document_job(job.id) or job
                try:
                    self.deps.lifecycle.record_event(
                        validating,
                        event_type="stage_succeeded",
                        stage="translating",
                        message="翻译批次已全部完成。",
                        payload={"batch_count": len(leaf_batches)},
                        trace_id=trace_id,
                        duration_ms=int((time.perf_counter() - stage_started_at) * 1000),
                    )
                    self.deps.lifecycle.record_event(
                        validating,
                        event_type="stage_started",
                        stage="translation_validating",
                        message="翻译完整性校验已开始。",
                        payload={"batch_count": len(leaf_batches)},
                        trace_id=trace_id,
                    )
                except Exception as exc:
                    return self.deps.lifecycle.fail_stage_attempt(validating, exc, trace_id=trace_id)
                job = validating
            started_at = time.perf_counter()
            try:
                updated = self.artifacts.register_translated_document_ir(
                    job,
                    succeeded_batches=leaf_batches,
                    trace_id=trace_id,
                )
            except Exception as exc:
                error_code = (
                    "oss_failed" if isinstance(exc, (ApiError, FileNotFoundError, OSError))
                    else "translation_failed"
                )
                return self.deps.lifecycle.mark_failed(
                    job,
                    failed_stage="translation_validating",
                    error_code=error_code,
                    error_message=failure_policy.worker_failure_message(exc),
                    trace_id=trace_id,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
            if updated.status != "running" or updated.stage != "rendering" or updated.retry_count != generation:
                return updated
            try:
                self.deps.lifecycle.record_event(
                    updated,
                    event_type="stage_succeeded",
                    stage="translation_validating",
                    message="翻译结果完整性校验通过，DocumentIR 已保存。",
                    payload={"document_ir_file_id": updated.document_ir_file_id, "batch_count": len(leaf_batches)},
                    trace_id=trace_id,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
            except Exception as exc:
                return self.deps.lifecycle.fail_stage_attempt(updated, exc, trace_id=trace_id)
            return self.deps.resume_job(updated.id, trace_id=trace_id) or updated
        return job

    def reconcile_atomic_rejection(
        self,
        batch: DocumentJobTranslationBatchRecord,
        *,
        generation: int,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        """原子端口拒绝后重读同代快照，收口终态而不把普通竞争误报为失败。"""

        current_job, current_batches = self.snapshot(
            batch.job_id, generation=generation,
        )
        current_batch = next((item for item in current_batches if item.id == batch.id), None)
        if current_batch is None:
            current_batch = self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
        if (
            current_job is None
            or current_job.retry_count != generation
            or current_job.status in {"succeeded", "failed", "canceled"}
            or current_job.stage not in {"translating", "translation_validating"}
        ):
            return current_batch
        try:
            summary = self.summarize(current_job, current_batches)
        except TranslationBatchTreeInvalidError:
            self.deps.lifecycle.mark_failed(
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
            self.finalize(
                current_job.id, generation=current_job.retry_count, trace_id=trace_id,
            )
            return self.deps.translation_batch_repository.get_translation_batch(batch.id) or current_batch
        return current_batch

    def reset_expired_leases(
        self,
        job: DocumentJobRecord,
        *,
        generation: int,
        trace_id: str | None,
    ) -> None:
        current, batches = self.snapshot(
            job.id, generation=generation,
        )
        if (
            current is None or current.status != "running" or current.stage != "translating"
            or current.retry_count != generation
        ):
            return
        now = utc_now()
        try:
            _source_file, source_document_ir = self.planner.read_source(
                current, current.source_document_ir_file_id,
            )
            expected_plans = self.planner.build_expected_plans(current, source_document_ir)
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError):
            # finalizer 随后会用同一 source/config 失败结论收口；这里不以旧批次自证根树。
            return
        for batch in batches:
            if batch.status != "running" or batch.lease_expires_at is None or batch.lease_expires_at > now:
                continue
            retryable = batch.attempt_count < batch.max_attempts and self.provider_call_budget_remaining(job, batch)
            expired = self.deps.translation_batch_repository.release_translation_batch_lease(
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
                self.reconcile_atomic_rejection(
                    batch, generation=generation, trace_id=trace_id,
                )
                continue
            self.deps.lifecycle.record_event(
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

    def enqueue_runnable(
        self,
        job: DocumentJobRecord,
        *,
        generation: int,
        trace_id: str | None,
    ) -> None:
        if self.deps.translation_batch_task_queue is None:
            return
        while True:
            current, batches = self.snapshot(
                job.id, generation=generation,
            )
            if (
                current is None or current.status != "running" or current.stage != "translating"
                or current.retry_count != generation
                or self.deps.lifecycle.mark_timed_out_if_needed(current, trace_id=trace_id) is not None
            ):
                return
            job = current
            summary = self.summarize(job, batches)
            if summary is not None and summary.outcome in {"failed", "completed", "validating", "canceled"}:
                self.finalize(job.id, generation=generation, trace_id=trace_id)
                return
            leaf_batches = [batch for batch in batches if batch.status != "split"]
            active_count = sum(1 for batch in leaf_batches if batch.status in {"queued", "running"})
            max_active = max(1, self.deps.settings.translation_provider_batch_max_concurrency_per_job)
            if active_count >= max_active:
                return
            candidate = self._next_runnable(job, leaf_batches)
            if candidate is None:
                return
            try:
                _source_file, source_document_ir = self.planner.read_source(
                    job, job.source_document_ir_file_id,
                )
                expected_plans = self.planner.build_expected_plans(job, source_document_ir)
            except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError):
                self.finalize(job.id, generation=generation, trace_id=trace_id)
                return
            try:
                queued = self.deps.translation_batch_repository.enqueue_translation_batch(
                    candidate.id,
                    expected_generation=candidate.generation,
                    expected_attempt_count=candidate.attempt_count,
                    provider_call_budget=candidate.provider_call_budget,
                    expected_plans=expected_plans,
                )
            except TranslationBatchTreeInvalidError:
                self.deps.lifecycle.mark_failed(
                    job,
                    failed_stage=job.stage,
                    error_code="translation_batch_tree_invalid",
                    error_message="翻译批次计划与当前 source/config 不一致。",
                    trace_id=trace_id,
                )
                return
            except (FileNotFoundError, OSError):
                self.deps.lifecycle.mark_failed(
                    job,
                    failed_stage=job.stage,
                    error_code="oss_failed",
                    error_message="翻译批次队列状态写入失败。",
                    trace_id=trace_id,
                )
                return
            if queued is None:
                self.reconcile_atomic_rejection(
                    candidate, generation=generation, trace_id=trace_id,
                )
                return
            self.deps.lifecycle.record_event(
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
            self.deps.translation_batch_task_queue.enqueue(queued.id, trace_id=trace_id)

    def _next_runnable(
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
                and self.provider_call_budget_remaining(job, batch)
            )
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.page_start or 0, item.created_at, item.id))[0]

    def cancel_batch(
        self,
        batch: DocumentJobTranslationBatchRecord,
        *,
        trace_id: str | None,
    ) -> DocumentJobTranslationBatchRecord:
        if batch.status in {"succeeded", "failed", "split", "canceled"}:
            return batch
        canceled = self.deps.translation_batch_repository.update_translation_batch_if_current(
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
            return self.deps.translation_batch_repository.get_translation_batch(batch.id) or batch
        job = self.deps.job_repository.get_document_job(batch.job_id)
        if job is not None:
            self.deps.lifecycle.record_event(
                job,
                event_type="translation_batch_failed",
                stage="translating",
                message="任务已取消，翻译批次停止执行。",
                payload={"batch_id": canceled.id, "generation": canceled.generation},
                trace_id=trace_id,
                level="warning",
            )
        return canceled

    def provider_call_budget_remaining(
        self,
        job: DocumentJobRecord,
        batch: DocumentJobTranslationBatchRecord,
    ) -> bool:
        return self.provider_call_budget_remaining_for_batch(batch)

    def provider_call_budget_remaining_for_batch(self, batch: DocumentJobTranslationBatchRecord) -> bool:
        snapshot_job, batches = self.snapshot(
            batch.job_id, generation=batch.generation,
        )
        if snapshot_job is None or snapshot_job.retry_count != batch.generation:
            return False
        attempts = sum(item.attempt_count for item in batches)
        return attempts < batch.provider_call_budget
