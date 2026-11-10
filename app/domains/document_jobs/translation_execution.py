"""翻译批次执行：根计划、领取与租约、Provider 调用、失败与拆分、汇合回填。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.document_jobs import _failure_policy as failure_policy
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.publication_provenance import (
    actual_call_fact,
    batch_publication_provenance,
    save_translation_publication_provenance,
)
from app.domains.document_jobs.repository import (
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
    TranslationBatchTreeInvalidError,
)
from app.domains.document_jobs.review import digest
from app.domains.document_jobs.workflow import (
    TranslationGenerationSummary,
    TranslationRootPlan,
    reduce_translation_generation,
)
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.jobs.models import JobResourceSnapshot
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError, JobResourceSnapshotService
from app.domains.resources.models import utc_now
from app.domains.translation.audit import TranslationAuditService, TranslationCallAuditRecorder
from app.domains.translation.document_ir_translator import (
    DocumentIRTranslationError,
    DocumentIRTranslationService,
    DocumentIRTranslationTarget,
)
from app.domains.translation.integrity import (
    TranslationIntegrityBinding,
    TranslationIntegrityError,
    TranslationIntegrityEvidence,
    ValidatedTranslationBatch,
)
from app.domains.translation.models import (
    TranslationProfileSnapshot,
    TranslationProviderResult,
    TranslationTextItem,
    TermVersionSnapshot,
)
from app.domains.translation.modes import is_translation_document_job_mode, spec_for_document_job_mode
from app.domains.translation.provider import (
    OpenAICompatibleTranslationProvider,
    TranslationProviderCallError,
    TranslationProviderResponseError,
)
from app.services.document_ir.models import DocumentIR
from app.services.document_ir.table_reference_assets import decode_table_references

if TYPE_CHECKING:
    # execution.py 在运行时导入本模块；这里只为类型标注引用，避免循环导入。
    from app.domains.document_jobs.execution import (
        DocumentJobExecutionService,
        DocumentTranslationBatchTaskQueueProtocol,
    )


class _TranslationBatchStorageError(RuntimeError):
    """翻译成功响应已审计，但批次结果或状态提交写入失败。"""


def _is_metadata_storage_error(error: Exception) -> bool:
    """识别仓储驱动异常，避免把数据库故障当成 Provider 失败重试。"""

    error_module = type(error).__module__
    return isinstance(error, (OSError, sqlite3.Error)) or error_module.startswith("pymysql.")


class TranslationBatchExecution:
    """翻译批次执行：由 DocumentJobExecutionService 构造并持有，负责批次计划、领取、调用、失败收口与汇合回填。

    任务级状态与事件仍由宿主收口。对宿主只允许调用 _record_event、_mark_failed、
    _fail_stage_attempt、_mark_timed_out_if_needed、execute_job、_get_uploaded_file、
    _document_ir_layout_metadata，且必须在调用时经 self._host 查找，不得在构造时捕获绑定方法，
    否则对宿主方法的替换（例如测试中的 patch.object）不会作用到翻译收口后的续跑。
    """

    def __init__(
        self,
        host: DocumentJobExecutionService,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_service: FileUploadService,
        job_resource_snapshot_service: JobResourceSnapshotService | None,
        translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol,
        document_ir_translation_service: DocumentIRTranslationService | None,
        translation_audit_service: TranslationAuditService | None,
        term_version_service: Any | None,
        translation_batch_task_queue: DocumentTranslationBatchTaskQueueProtocol | None,
    ) -> None:
        self._host = host
        self.settings = settings
        self.job_repository = job_repository
        self.file_service = file_service
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.translation_batch_repository = translation_batch_repository
        self.document_ir_translation_service = document_ir_translation_service
        self.translation_audit_service = translation_audit_service
        self.term_version_service = term_version_service
        self.translation_batch_task_queue = translation_batch_task_queue

    def set_translation_batch_task_queue(
        self,
        task_queue: DocumentTranslationBatchTaskQueueProtocol | None,
    ) -> None:
        """在 runtime 组装后注入 translation batch queue，避免循环构造依赖。"""

        self.translation_batch_task_queue = task_queue

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
                self._host._record_event(
                    job,
                    event_type="stage_started",
                    stage="translating",
                    message="DocumentIR 翻译已开始。",
                    payload={"source_document_ir_file_id": job.source_document_ir_file_id},
                    trace_id=trace_id,
                )
            except Exception as exc:
                return self._host._fail_stage_attempt(job, exc, trace_id=trace_id)
        if job.status != "running" or job.stage != "translating" or job.retry_count != generation:
            return job
        try:
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
                return self._host._mark_failed(
                    job,
                    failed_stage="translating",
                    error_code=exc.code,
                    error_message="翻译批次树与当前权威计划不一致。",
                    trace_id=trace_id,
                )
            except TranslationIntegrityError as exc:
                return self._host._mark_failed(
                    job,
                    failed_stage="translating",
                    error_code="translation_failed",
                    error_message=failure_policy.worker_failure_message(exc),
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
        except Exception as exc:
            return self._host._fail_stage_attempt(job, exc, trace_id=trace_id)

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
            except TranslationProviderCallError:
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
                    publication_provenance=batch_publication_provenance(result=result, integrity=integrity,
                        batch=claimed, profile=translation_profile, term_version=term_version),
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
            self._host._record_event(
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
            self._host._mark_failed(
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
                error_message=failure_policy.worker_failure_message(exc),
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
                self._host._mark_failed(
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
            self._host._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return None
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
            self._host._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if _is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划校验失败。",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
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
                    error_message=failure_policy.worker_failure_message(exc),
                    retryable=False,
                    updated_at=utc_now(),
                )
                self._host._mark_failed(
                    current_job,
                    failed_stage="translating",
                    error_code="translation_failed",
                    error_message=failure_policy.worker_failure_message(exc),
                    trace_id=trace_id,
                )
                return None
            self._host._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="oss_failed" if _is_metadata_storage_error(exc) else "translation_failed",
                error_message="翻译批次计划校验失败。",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
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
            self._host._mark_failed(
                current_job,
                failed_stage="translating",
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
            return None
        except (FileNotFoundError, OSError, sqlite3.Error) as exc:
            self._host._mark_failed(
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
            self._host._mark_failed(
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
            self._host._record_event(
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
            self._host._mark_failed(
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
        self._host._mark_failed(
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
            self._host._record_event(
                translating,
                event_type="stage_succeeded",
                stage="ir_converting",
                message="源 DocumentIR 转换已完成。",
                payload={"source_document_ir_file_id": translating.source_document_ir_file_id},
                trace_id=trace_id,
            )
            self._host._record_event(
                translating,
                event_type="stage_started",
                stage="translating",
                message="DocumentIR 翻译已开始。",
                payload={"source_document_ir_file_id": translating.source_document_ir_file_id},
                trace_id=trace_id,
            )
        except Exception as exc:
            return self._host._fail_stage_attempt(translating, exc, trace_id=trace_id)
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
            self._host._mark_failed(
                current,
                failed_stage="translating",
                error_code="oss_failed" if isinstance(exc, (FileNotFoundError, OSError)) else "translation_failed",
                error_message="翻译批次计划重建失败。",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
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
                self._host._mark_failed(
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
            self._host._mark_failed(
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
        self._host._record_event(
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
        self._host._record_event(
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
            return self._host._mark_failed(
                job,
                failed_stage=failure_stage,
                error_code="translation_batch_tree_invalid",
                error_message="翻译批次计划与当前 source/config 不一致。",
                trace_id=trace_id,
            )
        except (DocumentIRTranslationError, TranslationIntegrityError, FileNotFoundError, OSError, ValueError) as exc:
            return self._host._mark_failed(
                job,
                failed_stage=failure_stage,
                error_code="translation_failed",
                error_message=f"翻译批次计划校验失败: {self._translation_batch_error_code(exc)}",
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
                    _source_file, source_ir = self._read_translation_source(job, job.source_document_ir_file_id)
                    self._build_expected_translation_plans(job, source_ir)
                except (FileNotFoundError, OSError, sqlite3.Error):
                    error_code = "oss_failed"
                except DocumentIRTranslationError as exc:
                    error_code = "translation_failed"
                    formula_protection = exc.formula_protection
                except (TranslationIntegrityError, ValueError):
                    error_code = "translation_failed"
            return self._host._mark_failed(
                job,
                failed_stage=failure_stage,
                error_code=error_code,
                error_message="翻译批次无法由当前 source/config 重建权威计划。",
                trace_id=trace_id,
                formula_protection=formula_protection,
            )
        leaf_batches = [batch for batch in batches if batch.status != "split"]
        if summary.outcome == "failed":
            return self._host._mark_failed(
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
                    self._host._record_event(
                        validating,
                        event_type="stage_succeeded",
                        stage="translating",
                        message="翻译批次已全部完成。",
                        payload={"batch_count": len(leaf_batches)},
                        trace_id=trace_id,
                        duration_ms=int((time.perf_counter() - stage_started_at) * 1000),
                    )
                    self._host._record_event(
                        validating,
                        event_type="stage_started",
                        stage="translation_validating",
                        message="翻译完整性校验已开始。",
                        payload={"batch_count": len(leaf_batches)},
                        trace_id=trace_id,
                    )
                except Exception as exc:
                    return self._host._fail_stage_attempt(validating, exc, trace_id=trace_id)
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
                return self._host._mark_failed(
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
                self._host._record_event(
                    updated,
                    event_type="stage_succeeded",
                    stage="translation_validating",
                    message="翻译结果完整性校验通过，DocumentIR 已保存。",
                    payload={"document_ir_file_id": updated.document_ir_file_id, "batch_count": len(leaf_batches)},
                    trace_id=trace_id,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
            except Exception as exc:
                return self._host._fail_stage_attempt(updated, exc, trace_id=trace_id)
            return self._host.execute_job(updated.id, trace_id=trace_id) or updated
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
            return self._host._mark_failed(
                job,
                failed_stage="translation_validating",
                error_code="translation_failed",
                error_message=f"翻译 source 校验失败: {self._translation_batch_error_code(exc)}",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except (FileNotFoundError, OSError) as exc:
            return self._host._mark_failed(
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
            publication_calls = []
            replacements = self._load_batch_replacements(job, source_file, items, succeeded_batches,
                                                        publication_calls=publication_calls)
        except (DocumentIRTranslationError, TranslationIntegrityError, TranslationProviderResponseError, ValueError, FileNotFoundError, OSError) as exc:
            error_code = (
                "oss_failed" if isinstance(exc, (FileNotFoundError, OSError))
                else "translation_fan_in_mismatch" if getattr(exc, "code", None) == "translation_fan_in_mismatch"
                else "translation_failed"
            )
            return self._host._mark_failed(
                job,
                failed_stage="translation_validating",
                error_code=error_code,
                error_message=f"翻译批次合并校验失败: {self._translation_batch_error_code(exc)}",
                trace_id=trace_id,
                formula_protection=exc.formula_protection if isinstance(exc, DocumentIRTranslationError) else None,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        expected_ids = [item.id for item in items]
        missing_ids = [item_id for item_id in expected_ids if item_id not in replacements]
        extra_ids = sorted(set(replacements) - set(expected_ids))
        if missing_ids or extra_ids:
            return self._host._mark_failed(
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
            "skipped_degraded_page_numbers": sorted(record["page_index"] + 1
                                                    for record in translated.metadata.degraded_pages),
        }
        translation_provenance = save_translation_publication_provenance(job, publication_calls, file_service=self.file_service)
        translation_metadata["publication_provenance_file_id"] = translation_provenance.id
        decode_table_references(translated, require_bound=True)
        ir_content = translated.model_dump_json(indent=2).encode("utf-8")
        try:
            ir_file = self.file_service.register_generated_content(
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
                    **self._host._document_ir_layout_metadata(translated),
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
        self._host._record_event(
            updated,
            event_type="file_registered",
            stage="translation_validating",
            message="翻译后的 DocumentIR 已保存。",
            payload={
                "file_id": ir_file.id,
                "file_type": ir_file.file_type,
                "object_key": ir_file.object_key,
                **self._host._document_ir_layout_metadata(translated),
            },
            trace_id=trace_id,
        )
        return updated

    def _read_translation_artifact(
        self, job: DocumentJobRecord, file_id: str, *, file_type: str,
    ) -> tuple[DocumentFileRecord, bytes]:
        """按已登记的对象读取并验证字节；路径模板和 payload 不能自证归属。"""
        record = self._host._get_uploaded_file(file_id)
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
        *, publication_calls: list | None = None,
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
            candidate = self._host._get_uploaded_file(batch.result_file_id)
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
            if publication_calls is not None:
                provenance = payload.get("publication_provenance")
                if provenance is not None:
                    if (not isinstance(provenance, dict) or provenance.get("schema_version") != "publication-batch/v1"
                            or provenance.get("integrity_sha256") != digest(payload["integrity"])
                            or type(provenance.get("attempt")) is not int or provenance["attempt"] != batch.attempt_count):
                        raise DocumentIRTranslationError("翻译发布来源与成功尝试不一致。", code="translation_integrity_evidence_mismatch")
                    actual_call_fact(provenance.get("call"))
                publication_calls.append({"batch_id": batch.id, "attempt": batch.attempt_count,
                    "result_file_id": result_file.id, "result_sha256": result_file.checksum_sha256,
                    "provenance": provenance} if provenance is not None else None)
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
                or self._host._mark_timed_out_if_needed(current, trace_id=trace_id) is not None
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
                self._host._mark_failed(
                    job,
                    failed_stage=job.stage,
                    error_code="translation_batch_tree_invalid",
                    error_message="翻译批次计划与当前 source/config 不一致。",
                    trace_id=trace_id,
                )
                return
            except (FileNotFoundError, OSError):
                self._host._mark_failed(
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
            self._host._record_event(
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
            self._host._record_event(
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
            self._host._record_event(
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
        self._host._record_event(
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
        self._host._record_event(
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
            self._host._record_event(
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
            self._host._record_event(
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
