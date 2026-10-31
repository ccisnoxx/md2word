from __future__ import annotations

# app/domains/document_jobs/repository.py: 定义 document_jobs domain 依赖的持久化端口。

from collections.abc import Sequence
from datetime import datetime
from app.domains.document_jobs.review import ReviewSubmission, ReviewRecord
from typing import TYPE_CHECKING, Any, Literal, Protocol

from app.domains.files.models import DocumentFileRecord
from app.domains.document_jobs.new_generation import NewGenerationAcceptance, NewGenerationSubmission
from app.domains.document_jobs.publication import PublicationRecord, PublicationSubmission
from app.domains.document_jobs.preview_state import PreviewArtifactObservation, PreviewClaim, PreviewClaimRequest

from app.domains.document_jobs.models import (
    DocumentJobCallbackMessage,
    DocumentJobEventRecord,
    DocumentJobRecord,
    DocumentJobTranslationBatchRecord,
)

if TYPE_CHECKING:
    from app.domains.document_jobs.list_query import DocumentJobListQuery, DocumentJobListResult
    from app.domains.document_jobs.workflow import TranslationGenerationSummary, TranslationRootPlan


class TranslationBatchTreeInvalidError(ValueError):
    """权威根计划与已持久化批次树不一致。"""

    code = "translation_batch_tree_invalid"


def _plan_value(plan: Any, name: str, default: Any = None) -> Any:
    """读取 workflow 计划或兼容的批次记录，避免仓储重新定义计划结构。"""

    return getattr(plan, name, default)


def translation_plan_record(plan: Any) -> DocumentJobTranslationBatchRecord:
    """把锁外计算的权威计划转换为待安装的持久化根记录。"""

    if isinstance(plan, DocumentJobTranslationBatchRecord):
        return plan
    batch_id = _plan_value(plan, "batch_id")
    return DocumentJobTranslationBatchRecord(
        id=batch_id,
        job_id=_plan_value(plan, "job_id"),
        job_retry_count=_plan_value(plan, "job_retry_count", _plan_value(plan, "generation", 0)),
        generation=_plan_value(plan, "generation", 0),
        root_batch_id=batch_id,
        parent_batch_id=None,
        page_start=_plan_value(plan, "page_start"),
        page_end=_plan_value(plan, "page_end"),
        item_ids=list(_plan_value(plan, "item_ids", ())),
        item_count=_plan_value(plan, "item_count", 0),
        char_count=_plan_value(plan, "char_count", 0),
        split_level=_plan_value(plan, "split_level", 0),
        max_attempts=_plan_value(plan, "max_attempts", 2),
        deterministic_batch_count=_plan_value(plan, "deterministic_batch_count", 1),
        provider_call_budget=_plan_value(plan, "provider_call_budget", 0),
        source_document_ir_file_id=_plan_value(plan, "source_document_ir_file_id"),
        language_pair=_plan_value(plan, "language_pair"),
        term_version_id=_plan_value(plan, "term_version_id"),
        term_snapshot_hash=_plan_value(plan, "term_snapshot_hash"),
    )


def _workflow_plans(expected_plans: Sequence[Any]) -> tuple[Any, ...]:
    """把兼容的持久化记录转换为 workflow 计划，保留唯一业务校验归属。"""

    from app.domains.document_jobs.workflow import TranslationRootPlan

    plans = tuple(expected_plans)
    if not plans or not isinstance(plans[0], DocumentJobTranslationBatchRecord):
        return plans
    return tuple(
        TranslationRootPlan(
            batch_id=record.id,
            job_id=record.job_id,
            generation=record.generation,
            job_retry_count=record.job_retry_count,
            source_document_ir_file_id=record.source_document_ir_file_id,
            language_pair=record.language_pair,
            item_ids=tuple(record.item_ids),
            item_count=record.item_count,
            char_count=record.char_count,
            page_start=record.page_start,
            page_end=record.page_end,
            term_version_id=record.term_version_id,
            term_snapshot_hash=record.term_snapshot_hash,
            split_level=record.split_level,
            deterministic_batch_count=record.deterministic_batch_count,
            provider_call_budget=record.provider_call_budget,
            max_attempts=record.max_attempts,
        )
        for record in plans
    )


def validate_translation_batch_tree_or_raise(
    *,
    job_id: str,
    generation: int,
    expected_plans: Sequence[Any],
    batches: Sequence[DocumentJobTranslationBatchRecord],
) -> None:
    """在存储边界复用 workflow 唯一树校验，不以当前记录自证完整性。"""

    from app.domains.document_jobs.workflow import validate_translation_batch_tree

    plans = _workflow_plans(expected_plans)
    check = validate_translation_batch_tree(
        job_id=job_id,
        generation=generation,
        expected_plans=plans,
        batches=batches,
    )
    if not check.valid:
        raise TranslationBatchTreeInvalidError(check.reason_message or "翻译批次树与权威计划不一致。")


def reduce_translation_batch_generation(
    *,
    job: DocumentJobRecord,
    expected_plans: Sequence[Any],
    batches: Sequence[DocumentJobTranslationBatchRecord],
    provider_call_budget: int | None,
    as_of: datetime,
) -> "TranslationGenerationSummary":
    """在原子边界复用 workflow 唯一 reducer，返回当前代的停止结论。"""

    from app.domains.document_jobs.workflow import reduce_translation_generation

    plans = _workflow_plans(expected_plans)
    return reduce_translation_generation(
        job_id=job.id,
        job_status=job.status,
        job_stage=job.stage,
        generation=job.retry_count,
        expected_plans=plans,
        batches=batches,
        provider_call_budget=provider_call_budget,
        as_of=as_of,
    )


def reducer_blocks_result_promotion(summary: Any) -> bool:
    """reducer 已给出终态时一律停止结果晋升，避免锁外结论被兄弟终态改变。"""

    return summary.outcome in {"failed", "completed", "canceled"}


def validate_expected_root_plans_or_raise(
    *,
    job_id: str,
    generation: int,
    expected_plans: Sequence[Any],
) -> None:
    """在第一次写入前检查计划自身，避免坏计划触发部分根落盘。"""

    plans = [translation_plan_record(plan) for plan in expected_plans]
    if len({plan.id for plan in plans}) != len(plans):
        raise TranslationBatchTreeInvalidError("权威根计划含重复 ID。")
    item_ids = [item_id for plan in plans for item_id in plan.item_ids]
    if len(item_ids) != len(set(item_ids)):
        raise TranslationBatchTreeInvalidError("权威根计划的 item 分区存在重复。")
    if any(
        plan.job_id != job_id
        or plan.generation != generation
        or plan.job_retry_count != generation
        or plan.root_batch_id != plan.id
        or plan.parent_batch_id is not None
        or not plan.item_ids
        or plan.item_count != len(plan.item_ids)
        or plan.char_count < 0
        for plan in plans
    ):
        raise TranslationBatchTreeInvalidError("权威根计划与当前任务代次或 item 计数不一致。")


class DocumentJobRepositoryProtocol(Protocol):
    """主记录元数据合同；所有写方法共享同 job 的局部序列化点。"""

    def accept_document_job_new_generation(
        self, job_id: str, *, submission: NewGenerationSubmission, max_retries: int,
    ) -> tuple[NewGenerationAcceptance, DocumentJobRecord, bool]: ...
    def get_document_job_generation_request(
        self, job_id: str, *, request_id: str, actor_id: str,
    ) -> tuple[NewGenerationAcceptance, DocumentJobRecord] | None: ...

    def update_document_job_lifecycle_if_current(
        self, job_id: str, *, expected_retry_count: int, action: Literal["archive", "delete"],
        actor_id: str, occurred_at: datetime, delete_reason: str | None = None,
    ) -> DocumentJobRecord | None: ...

    def publish_document_job(self, job_id: str, *, submission: PublicationSubmission) -> tuple[PublicationRecord, bool]: ...
    def list_document_job_publications(self, job_id: str) -> list[PublicationRecord]: ...
    def is_document_file_protected(self, file_id: str) -> bool: ...

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord: ...
    def get_document_job(self, job_id: str) -> DocumentJobRecord | None: ...
    def list_document_jobs(self) -> list[DocumentJobRecord]: ...
    def query_document_jobs(self, query: DocumentJobListQuery) -> DocumentJobListResult: ...
    def is_document_job_table_evidence_snapshot_current(self, expected: DocumentJobRecord) -> bool: ...
    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord: ...
    def update_document_job_if_current(
        self,
        job_id: str,
        *,
        allowed_statuses: set[str],
        allowed_stages: set[str],
        expected_retry_count: int | None = None,
        expected_document_ir_file_id: str | None = None,
        require_no_prepared_result: bool = False,
        expected_prepared_result_file_id: str | None = None,
        preview_contribution: dict | None = None,
        **patch: Any,
    ) -> DocumentJobRecord | None: ...

    def prepare_document_job_result(
        self, job_id: str, *, expected_retry_count: int,
        expected_document_ir_file_id: str, candidate: DocumentFileRecord,
    ) -> DocumentJobRecord | None: ...
    def retry_document_job(
        self, job_id: str, *, expected_retry_count: int, max_retries: int, **patch: Any,
    ) -> DocumentJobRecord | None: ...

    def claim_document_job_preview(
        self, job_id: str, *, request: PreviewClaimRequest, observation: PreviewArtifactObservation | None = None,
    ) -> PreviewClaim: ...
    def begin_document_job_preview_registration(
        self, job_id: str, *, request: PreviewClaimRequest, revision: int, lease_token: str, attempt: int,
    ) -> DocumentJobRecord | None: ...
    def finish_document_job_preview(
        self, job_id: str, *, request: PreviewClaimRequest, revision: int, lease_token: str,
        status: str, manifest_file_id: str, error_code: str | None, retryable: bool, evidence: dict,
        page_quality_contribution: dict | None = None,
    ) -> DocumentJobRecord | None: ...
    def update_document_job_review_if_current(
        self, job_id: str, *, submission: ReviewSubmission,
    ) -> DocumentJobRecord | None: ...

    def backfill_document_job_state_if_missing(self, job_id: str) -> bool:
        """锁内重读 raw 并补缺，返回 payload 是否补键；SQL 同时校准投影列。"""
        ...


    def list_document_job_reviews(
        self, job_id: str, *, after_sequence: int = 0, limit: int = 100,
    ) -> list[ReviewRecord]: ...


class DocumentJobEventRepositoryProtocol(Protocol):
    """document_jobs 事件读写合同。"""

    def append_document_job_event(self, job_id: str, event: DocumentJobEventRecord) -> None: ...
    def list_document_job_events(self, job_id: str) -> list[DocumentJobEventRecord]: ...


class DocumentJobCallbackMessageStoreProtocol(Protocol):
    """document_jobs MinerU callback 专用消息合同。"""

    def put_or_get_callback_message(self, message: DocumentJobCallbackMessage) -> tuple[DocumentJobCallbackMessage, bool]: ...
    def get_callback_message(self, message_id: str) -> DocumentJobCallbackMessage | None: ...
    def list_callback_messages(
        self,
        job_id: str | None = None,
        *,
        statuses: set[str] | None = None,
        limit: int | None = None,
    ) -> list[DocumentJobCallbackMessage]: ...
    def list_replayable_callback_messages(self, job_id: str | None = None) -> list[DocumentJobCallbackMessage]: ...
    def mark_callback_message_running(
        self,
        message_id: str,
        *,
        attempts: int,
        lease_owner: str | None,
        leased_at: Any,
        lease_expires_at: Any,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage | None: ...
    def mark_callback_message_processed(self, message_id: str, *, updated_at: Any) -> DocumentJobCallbackMessage: ...
    def mark_callback_message_failed(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage: ...
    def mark_callback_message_ignored(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage: ...
    def count_callback_messages_by_status(self, job_id: str | None = None) -> dict[str, int]: ...


class DocumentJobTranslationBatchRepositoryProtocol(Protocol):
    """Provider 翻译批次元数据仓储合同。"""

    def create_translation_batch(self, record: DocumentJobTranslationBatchRecord) -> DocumentJobTranslationBatchRecord: ...
    def get_translation_batch(self, batch_id: str) -> DocumentJobTranslationBatchRecord | None: ...
    def list_translation_batches(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> list[DocumentJobTranslationBatchRecord]: ...
    def update_translation_batch(self, batch_id: str, **patch: Any) -> DocumentJobTranslationBatchRecord: ...
    def update_translation_batch_if_current(
        self,
        batch_id: str,
        *,
        allowed_statuses: set[str],
        expected_generation: int,
        expected_attempt_count: int | None = None,
        expected_lease_owner: str | None = None,
        expected_job_id: str | None = None,
        expected_job_status: set[str] | None = None,
        expected_job_stages: set[str] | None = None,
        expected_plans: Sequence["TranslationRootPlan"] | None = None,
        **patch: Any,
    ) -> DocumentJobTranslationBatchRecord | None: ...

    def ensure_translation_batch_roots(
        self,
        job_id: str,
        *,
        generation: int,
        expected_plans: Sequence["TranslationRootPlan"],
    ) -> list[DocumentJobTranslationBatchRecord]: ...

    def get_translation_batch_snapshot(
        self,
        job_id: str,
        *,
        generation: int | None = None,
    ) -> tuple[DocumentJobRecord, list[DocumentJobTranslationBatchRecord]]: ...

    def enqueue_translation_batch(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        provider_call_budget: int,
        expected_plans: Sequence["TranslationRootPlan"],
    ) -> DocumentJobTranslationBatchRecord | None: ...

    def claim_translation_batch(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        lease_owner: str,
        leased_at: datetime,
        lease_expires_at: datetime,
        provider_call_budget: int,
        expected_plans: Sequence["TranslationRootPlan"],
    ) -> DocumentJobTranslationBatchRecord | None: ...

    def release_translation_batch_lease(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        expected_lease_owner: str,
        now: datetime,
        expected_plans: Sequence["TranslationRootPlan"],
        **patch: Any,
    ) -> DocumentJobTranslationBatchRecord | None: ...

    def split_translation_batch(
        self,
        batch_id: str,
        *,
        expected_generation: int,
        expected_attempt_count: int,
        expected_lease_owner: str,
        expected_plans: Sequence["TranslationRootPlan"],
        children: Sequence[DocumentJobTranslationBatchRecord],
    ) -> tuple[DocumentJobTranslationBatchRecord, tuple[DocumentJobTranslationBatchRecord, ...]] | None: ...
