"""翻译批次安装：推进到 translating、原子安装完整根集合并触发首轮投递。"""

from __future__ import annotations

from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import TranslationBatchTreeInvalidError
from app.domains.document_jobs.translation_execution.deps import TranslationExecutionDeps
from app.domains.document_jobs.translation_execution.generation import TranslationGenerationCoordinator
from app.domains.document_jobs.translation_execution.planning import TranslationPlanner
from app.domains.resources.models import utc_now
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError
from app.domains.translation.modes import spec_for_document_job_mode
from app.services.document_ir.models import DocumentIR


class TranslationBatchInstaller:
    """把任务推进到 translating 并原子安装本代根批次；安装后交给代次协调器投递与收口。"""

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

    def install_and_enqueue(
        self,
        job: DocumentJobRecord,
        source_document_ir: DocumentIR,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        generation = job.retry_count
        if job.stage == "ir_converting":
            transitioned = self.deps.job_repository.update_document_job_if_current(
                job.id,
                allowed_statuses={"running"},
                allowed_stages={"ir_converting"},
                expected_retry_count=generation,
                stage="translating",
                updated_at=utc_now(),
            )
            if transitioned is None:
                return self.deps.job_repository.get_document_job(job.id) or job
            job = transitioned
            try:
                self.deps.lifecycle.record_event(
                    job,
                    event_type="stage_started",
                    stage="translating",
                    message="DocumentIR 翻译已开始。",
                    payload={"source_document_ir_file_id": job.source_document_ir_file_id},
                    trace_id=trace_id,
                )
            except Exception as exc:
                return self.deps.lifecycle.fail_stage_attempt(job, exc, trace_id=trace_id)
        if job.status != "running" or job.stage != "translating" or job.retry_count != generation:
            return job
        try:
            if self.deps.document_ir_translation_service is None:
                raise DocumentIRTranslationError("DocumentIR 翻译服务未配置。")
            spec = spec_for_document_job_mode(job.mode)
            if spec.language_pair is None:
                raise DocumentIRTranslationError("当前任务不是翻译任务。")
            if not job.source_document_ir_file_id:
                raise DocumentIRTranslationError("翻译任务缺少 source DocumentIR 文件。")
            expected_plans = self.planner.build_expected_plans(job, source_document_ir)
            try:
                batches = self.deps.translation_batch_repository.ensure_translation_batch_roots(
                    job.id,
                    generation=generation,
                    expected_plans=expected_plans,
                )
            except TranslationBatchTreeInvalidError as exc:
                return self.deps.lifecycle.mark_failed(
                    job,
                    failed_stage="translating",
                    error_code=exc.code,
                    error_message="翻译批次树与当前权威计划不一致。",
                    trace_id=trace_id,
                )
            except TranslationIntegrityError as exc:
                return self.deps.lifecycle.mark_failed(
                    job,
                    failed_stage="translating",
                    error_code="translation_failed",
                    error_message=failure_policy.worker_failure_message(exc),
                    trace_id=trace_id,
                    integrity=exc.evidence,
                )
            if not batches:
                return self.generation.finalize(
                    job.id, generation=generation, trace_id=trace_id,
                ) or job
            self.generation.reset_expired_leases(job, generation=generation, trace_id=trace_id)
            self.generation.enqueue_runnable(job, generation=generation, trace_id=trace_id)
            return self.generation.finalize(job.id, generation=generation, trace_id=trace_id) or job
        except Exception as exc:
            return self.deps.lifecycle.fail_stage_attempt(job, exc, trace_id=trace_id)
