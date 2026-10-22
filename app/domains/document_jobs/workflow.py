from __future__ import annotations

# app/domains/document_jobs/workflow.py: 收口 document_jobs 状态组、批次树和代次结论。

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Sequence

from app.domains.document_jobs.models import DocumentJobStatus
from app.domains.document_jobs.models import DocumentJobTranslationBatchRecord


TranslationGenerationOutcome = Literal[
    "not_started",
    "running",
    "retrying",
    "validating",
    "failed",
    "completed",
    "canceled",
]
TranslationBatchFailureDisposition = Literal[
    "none",
    "retrying",
    "terminal",
    "stopped",
    "superseded",
]


@dataclass(frozen=True, slots=True)
class TranslationRootPlan:
    """由 source/config 计算出的本代不可变根计划。"""

    batch_id: str
    job_id: str
    generation: int
    job_retry_count: int
    source_document_ir_file_id: str
    language_pair: str
    item_ids: tuple[str, ...]
    item_count: int
    char_count: int
    page_start: int | None = None
    page_end: int | None = None
    term_version_id: str | None = None
    term_snapshot_hash: str | None = None
    split_level: int = 0
    deterministic_batch_count: int = 1
    provider_call_budget: int = 0
    max_attempts: int = 2


@dataclass(frozen=True, slots=True)
class TranslationBatchDispositionRow:
    """单条批次在当前代的 API 展示判定。"""

    batch_id: str
    is_effective_leaf: bool
    failure_disposition: TranslationBatchFailureDisposition


@dataclass(frozen=True, slots=True)
class TranslationBatchTreeCheck:
    """根计划和实际记录的结构校验结果。"""

    valid: bool
    reason_code: str | None = None
    reason_message: str | None = None
    zero_unit: bool = False


@dataclass(frozen=True, slots=True)
class TranslationGenerationSummary:
    """纯 reducer 输出；仓储、执行和 API 可共同消费。"""

    outcome: TranslationGenerationOutcome
    leaf_count: int
    succeeded_leaf_count: int
    active_leaf_count: int
    retryable_failed_leaf_count: int
    terminal_failed_leaf_count: int
    failure_batch_id: str | None = None
    reason_code: str | None = None
    reason_message: str | None = None
    partial_artifacts_debug_only: bool = True
    rows: tuple[TranslationBatchDispositionRow, ...] = ()
    tree: TranslationBatchTreeCheck = TranslationBatchTreeCheck(valid=True)

    @property
    def is_terminal(self) -> bool:
        return self.outcome in {"failed", "completed", "canceled"}


ACTIVE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"pending", "queued", "running"}
TERMINAL_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"succeeded", "failed", "canceled"}
ARCHIVABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = set(TERMINAL_DOCUMENT_JOB_STATUSES)
CANCELABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = set(ACTIVE_DOCUMENT_JOB_STATUSES)
DOCUMENT_JOB_STATUS_GROUPS: dict[str, set[DocumentJobStatus]] = {
    "active": set(ACTIVE_DOCUMENT_JOB_STATUSES),
}


def is_active_document_job_status(status: str) -> bool:
    return status in ACTIVE_DOCUMENT_JOB_STATUSES


def is_terminal_document_job_status(status: str) -> bool:
    return status in TERMINAL_DOCUMENT_JOB_STATUSES


def reduce_translation_generation(
    *,
    job_id: str,
    job_status: str,
    job_stage: str,
    generation: int,
    expected_plans: Sequence[TranslationRootPlan],
    batches: Sequence[DocumentJobTranslationBatchRecord],
    provider_call_budget: int | None = None,
    as_of: datetime | None = None,
) -> TranslationGenerationSummary:
    """按固定优先级归约一代批次，并返回 API 所需的完整计数与逐行判定。

    `expected_plans` 必须由 source/config 在锁外计算，不能从 `batches` 反推。
    该函数不写仓储、不推进任务，也不把普通条件竞争解释为终态失败。
    """

    if job_status == "canceled":
        rows = tuple(
            TranslationBatchDispositionRow(
                batch_id=batch.id,
                is_effective_leaf=batch.status != "split",
                failure_disposition="stopped" if batch.status != "split" else "superseded",
            )
            for batch in batches
        )
        return _summary(
            outcome="canceled",
            batches=batches,
            rows=rows,
            reason_code="canceled",
            reason_message="任务已取消，当前代不再继续消费。",
        )

    # 终态 job 的 API 结论由主任务权威状态决定；历史批次只生成行级描述，
    # 不在读取旧诊断时重新启动树校验或把已完成件改投影为新结论。
    if job_status in {"failed", "succeeded"}:
        terminal_ids = {
            batch.id
            for batch in batches
            if job_status == "failed" and batch.status == "failed" and not batch.retryable
        }
        return _summary(
            outcome="failed" if job_status == "failed" else "completed",
            batches=batches,
            rows=_rows_for_failure(
                batches,
                terminal_ids=terminal_ids,
                retrying_ids=set(),
                stop_non_success=True,
            ),
            reason_code="translation_failed" if job_status == "failed" else None,
            reason_message="当前任务已进入失败终态。" if job_status == "failed" else None,
        )

    if not batches and expected_plans:
        expected_check = _validate_expected_plans(
            job_id=job_id,
            generation=generation,
            expected_plans=expected_plans,
        )
        if not expected_check.valid:
            return _summary(
                outcome="failed",
                batches=batches,
                rows=(),
                reason_code=expected_check.reason_code,
                reason_message=expected_check.reason_message,
                tree=expected_check,
            )
        # 根计划已由 source/config 计算，但尚未完成持久化安装；不能把它误报为损坏树。
        return _summary(
            outcome="not_started",
            batches=batches,
            rows=(),
            tree=TranslationBatchTreeCheck(valid=True),
        )

    tree = validate_translation_batch_tree(
        job_id=job_id,
        generation=generation,
        expected_plans=expected_plans,
        batches=batches,
    )
    if not tree.valid:
        rows = tuple(
            TranslationBatchDispositionRow(
                batch_id=batch.id,
                is_effective_leaf=batch.status != "split",
                failure_disposition=("superseded" if batch.status == "split" else "terminal"),
            )
            for batch in batches
        )
        return _summary(
            outcome="failed",
            batches=batches,
            rows=rows,
            reason_code=tree.reason_code,
            reason_message=tree.reason_message,
            tree=tree,
        )

    if job_status == "failed":
        return _summary(
            outcome="failed",
            batches=batches,
            rows=_rows_for_failure(
                batches,
                terminal_ids={batch.id for batch in batches if batch.status == "failed" and not batch.retryable},
                retrying_ids=set(),
            ),
            reason_code="translation_failed",
            reason_message="当前代已存在任务失败结论。",
            tree=tree,
        )

    leaves = tuple(batch for batch in batches if batch.status != "split")
    budget = _resolve_provider_call_budget(expected_plans, batches, provider_call_budget)
    used_budget = sum(max(0, batch.attempt_count) for batch in batches)
    now = _normalise_datetime(as_of or datetime.now(timezone.utc))

    terminal_failures: list[tuple[DocumentJobTranslationBatchRecord, str, str]] = []
    retrying: set[str] = set()
    active: set[str] = set()
    succeeded: set[str] = set()
    for batch in leaves:
        if batch.status == "succeeded":
            succeeded.add(batch.id)
            continue
        if batch.status == "canceled":
            terminal_failures.append(
                (batch, "translation_batch_state_invalid", "同代有效叶子不能处于 canceled 状态。")
            )
            continue
        if batch.status == "failed":
            retry_possible, reason_code, reason_message = _retry_decision(
                batch,
                used_budget=used_budget,
                provider_call_budget=budget,
            )
            if batch.retryable and retry_possible:
                retrying.add(batch.id)
            else:
                terminal_failures.append((batch, reason_code, reason_message))
            continue
        if batch.status == "running" and _lease_expired(batch, now):
            retry_possible, reason_code, reason_message = _retry_decision(
                batch,
                used_budget=used_budget,
                provider_call_budget=budget,
                lease_expired=True,
                respect_retryable=False,
            )
            if retry_possible:
                retrying.add(batch.id)
            else:
                terminal_failures.append((batch, reason_code, reason_message))
            continue
        if batch.status in {"pending", "queued", "running"}:
            if batch.status == "running" and (
                not batch.lease_owner or batch.lease_expires_at is None
            ):
                terminal_failures.append(
                    (batch, "translation_batch_state_invalid", "running 批次缺少有效 lease 身份。")
                )
                continue
            active.add(batch.id)
            if batch.status == "running" and batch.attempt_count > 1:
                retrying.add(batch.id)
            continue
        terminal_failures.append(
            (batch, "translation_batch_state_invalid", "批次状态不属于可归约的同代状态。")
        )

    if terminal_failures:
        first_failure, reason_code, reason_message = sorted(
            terminal_failures,
            key=lambda item: (item[0].updated_at, item[0].id),
        )[0]
        rows = _rows_for_failure(
            batches,
            terminal_ids={batch.id for batch, _code, _message in terminal_failures},
            retrying_ids=retrying,
        )
        return _summary(
            outcome="failed",
            batches=batches,
            rows=rows,
            failure_batch_id=first_failure.id,
            reason_code=reason_code,
            reason_message=reason_message,
            tree=tree,
        )

    if retrying:
        return _summary(
            outcome="retrying",
            batches=batches,
            rows=_rows_for_failure(batches, terminal_ids=set(), retrying_ids=retrying),
            tree=tree,
        )

    if active:
        # 合法 running 调用已经占用本次预算时仍保持 running；只有待消费叶子
        # 才会因没有预算而终态失败，避免误杀正在外调的请求。
        pending_without_budget = {
            batch.id
            for batch in leaves
            if batch.status in {"pending", "queued"} and budget is not None and used_budget >= budget
        }
        if pending_without_budget:
            first = sorted(pending_without_budget)[0]
            return _summary(
                outcome="failed",
                batches=batches,
                rows=_rows_for_failure(
                    batches,
                    terminal_ids=pending_without_budget,
                    retrying_ids=set(),
                ),
                failure_batch_id=first,
                reason_code="call_budget_exhausted",
                reason_message="翻译批次尚有待消费叶子，但本代 Provider 调用预算已耗尽。",
                tree=tree,
            )
        if leaves and all(batch.status == "pending" and batch.attempt_count == 0 for batch in leaves):
            return _summary(
                outcome="not_started",
                batches=batches,
                rows=_rows_for_failure(batches, terminal_ids=set(), retrying_ids=set()),
                tree=tree,
            )
        return _summary(
            outcome="running",
            batches=batches,
            rows=_rows_for_failure(batches, terminal_ids=set(), retrying_ids=set()),
            tree=tree,
        )

    if succeeded == {batch.id for batch in leaves}:
        return _summary(
            outcome="validating" if job_stage == "translation_validating" else "completed",
            batches=batches,
            rows=_rows_for_failure(batches, terminal_ids=set(), retrying_ids=set()),
            tree=tree,
        )

    # expected_plans 为空且实际树也为空时，才允许明确的零单元成功。
    if tree.zero_unit:
        return _summary(
            outcome="completed",
            batches=batches,
            rows=(),
            tree=tree,
        )
    return _summary(
        outcome="failed",
        batches=batches,
        rows=_rows_for_failure(batches, terminal_ids=set(), retrying_ids=set()),
        reason_code="translation_batch_state_invalid",
        reason_message="当前代没有可运行或已完成的有效叶子。",
        tree=tree,
    )


def validate_translation_batch_tree(
    *,
    job_id: str,
    generation: int,
    expected_plans: Sequence[TranslationRootPlan],
    batches: Sequence[DocumentJobTranslationBatchRecord],
) -> TranslationBatchTreeCheck:
    """核对权威根集合、不可变字段和 split 子树覆盖关系。"""

    expected_check = _validate_expected_plans(
        job_id=job_id,
        generation=generation,
        expected_plans=expected_plans,
    )
    if not expected_check.valid:
        return expected_check
    expected_by_id = {plan.batch_id: plan for plan in expected_plans}
    if not expected_plans and not batches:
        return TranslationBatchTreeCheck(valid=True, zero_unit=True)
    if not expected_plans:
        return _invalid_tree("存在批次记录但权威计划为空。")

    by_id: dict[str, DocumentJobTranslationBatchRecord] = {}
    for batch in batches:
        if batch.id in by_id:
            return _invalid_tree("批次记录含重复 ID。")
        by_id[batch.id] = batch
        if batch.job_id != job_id or batch.generation != generation or batch.job_retry_count != generation:
            return _invalid_tree("批次记录与当前任务代次不一致。")
        if batch.root_batch_id not in expected_by_id:
            return _invalid_tree("批次引用了不在权威计划中的根。")

    roots = [batch for batch in batches if batch.parent_batch_id is None]
    root_ids = {batch.id for batch in roots}
    if root_ids != set(expected_by_id):
        return _invalid_tree("实际根集合与权威根计划不完整匹配。")
    if len(roots) != len(root_ids):
        return _invalid_tree("实际根集合含重复记录。")
    for root in roots:
        plan = expected_by_id[root.id]
        if root.root_batch_id != root.id or not _root_matches_plan(root, plan):
            return _invalid_tree("根批次不可变字段与权威计划不一致。")

    children_by_parent: dict[str, list[DocumentJobTranslationBatchRecord]] = {}
    for batch in batches:
        if batch.parent_batch_id is None:
            continue
        parent = by_id.get(batch.parent_batch_id)
        if parent is None or parent.status != "split":
            return _invalid_tree("批次存在孤立子节点或父节点未处于 split。")
        if batch.root_batch_id != parent.root_batch_id or not _same_immutable_binding(parent, batch):
            return _invalid_tree("split 子节点身份或绑定字段不一致。")
        children_by_parent.setdefault(parent.id, []).append(batch)

    for parent in by_id.values():
        children = children_by_parent.get(parent.id, [])
        if parent.status == "split":
            if len(children) != 2:
                return _invalid_tree("split 父节点必须恰好有两个子节点。")
            expected_ids = {
                f"{parent.id}_s{parent.split_level + 1}_01",
                f"{parent.id}_s{parent.split_level + 1}_02",
            }
            if {child.id for child in children} != expected_ids:
                return _invalid_tree("split 子节点 ID 不符合确定性身份。")
            child_ids = [item_id for child in children for item_id in child.item_ids]
            if any(not child.item_ids for child in children) or len(child_ids) != len(set(child_ids)):
                return _invalid_tree("split 子节点不能是空分区或含重复 item。")
            ordered_child_ids = [
                item_id
                for child in sorted(children, key=lambda item: item.id)
                for item_id in child.item_ids
            ]
            if ordered_child_ids != list(parent.item_ids):
                return _invalid_tree("split 子节点未严格覆盖父节点 item 分区。")
        elif children:
            return _invalid_tree("未 split 的叶子不能拥有子节点。")

    return TranslationBatchTreeCheck(valid=True)


def _validate_expected_plans(
    *,
    job_id: str,
    generation: int,
    expected_plans: Sequence[TranslationRootPlan],
) -> TranslationBatchTreeCheck:
    if len({plan.batch_id for plan in expected_plans}) != len(expected_plans):
        return _invalid_tree("根计划含重复 ID。")
    if any(
        plan.job_id != job_id
        or plan.generation != generation
        or plan.job_retry_count != generation
        for plan in expected_plans
    ):
        return _invalid_tree("根计划与当前任务代次不一致。")
    if any(
        not plan.item_ids
        or plan.item_count != len(plan.item_ids)
        or plan.char_count < 0
        for plan in expected_plans
    ):
        return _invalid_tree("权威根计划的 item 计数或分区无效。")
    if _duplicate_item_ids(expected_plans):
        return _invalid_tree("权威根计划的 item 分区存在重复。")
    return TranslationBatchTreeCheck(valid=True)


def _summary(
    *,
    outcome: TranslationGenerationOutcome,
    batches: Sequence[DocumentJobTranslationBatchRecord],
    rows: tuple[TranslationBatchDispositionRow, ...],
    failure_batch_id: str | None = None,
    reason_code: str | None = None,
    reason_message: str | None = None,
    tree: TranslationBatchTreeCheck | None = None,
) -> TranslationGenerationSummary:
    leaves = [batch for batch in batches if batch.status != "split"]
    disposition_by_id = {row.batch_id: row.failure_disposition for row in rows}
    return TranslationGenerationSummary(
        outcome=outcome,
        leaf_count=len(leaves),
        succeeded_leaf_count=sum(batch.status == "succeeded" for batch in leaves),
        active_leaf_count=sum(
            batch.status in {"pending", "queued", "running"}
            and disposition_by_id.get(batch.id) in {"none", "retrying"}
            for batch in leaves
        ),
        retryable_failed_leaf_count=sum(
            disposition_by_id.get(batch.id) == "retrying" for batch in leaves
        ),
        terminal_failed_leaf_count=sum(
            disposition_by_id.get(batch.id) == "terminal" for batch in leaves
        ),
        failure_batch_id=failure_batch_id,
        reason_code=reason_code,
        reason_message=reason_message,
        rows=rows,
        tree=tree or TranslationBatchTreeCheck(valid=True),
    )


def _invalid_tree(message: str) -> TranslationBatchTreeCheck:
    return TranslationBatchTreeCheck(
        valid=False,
        reason_code="translation_batch_tree_invalid",
        reason_message=message,
    )


def _duplicate_item_ids(plans: Sequence[TranslationRootPlan]) -> bool:
    item_ids = [item_id for plan in plans for item_id in plan.item_ids]
    return len(item_ids) != len(set(item_ids))


def _root_matches_plan(
    batch: DocumentJobTranslationBatchRecord,
    plan: TranslationRootPlan,
) -> bool:
    return (
        batch.id == plan.batch_id
        and batch.job_id == plan.job_id
        and batch.generation == plan.generation
        and batch.job_retry_count == plan.job_retry_count
        and batch.root_batch_id == plan.batch_id
        and batch.parent_batch_id is None
        and batch.source_document_ir_file_id == plan.source_document_ir_file_id
        and batch.language_pair == plan.language_pair
        and batch.term_version_id == plan.term_version_id
        and batch.term_snapshot_hash == plan.term_snapshot_hash
        and tuple(batch.item_ids) == tuple(plan.item_ids)
        and batch.item_count == plan.item_count == len(plan.item_ids)
        and batch.char_count == plan.char_count
        and batch.page_start == plan.page_start
        and batch.page_end == plan.page_end
        and batch.split_level == plan.split_level == 0
        and batch.deterministic_batch_count == plan.deterministic_batch_count
        and batch.provider_call_budget == plan.provider_call_budget
        and batch.max_attempts == plan.max_attempts
    )


def _same_immutable_binding(
    parent: DocumentJobTranslationBatchRecord,
    child: DocumentJobTranslationBatchRecord,
) -> bool:
    return (
        child.job_id == parent.job_id
        and child.job_retry_count == parent.job_retry_count
        and child.generation == parent.generation
        and child.source_document_ir_file_id == parent.source_document_ir_file_id
        and child.language_pair == parent.language_pair
        and child.term_version_id == parent.term_version_id
        and child.term_snapshot_hash == parent.term_snapshot_hash
        and child.provider_call_budget == parent.provider_call_budget
        and child.max_attempts == parent.max_attempts
        and child.deterministic_batch_count == parent.deterministic_batch_count
        and child.split_level == parent.split_level + 1
        and child.item_count == len(child.item_ids)
        and child.char_count >= 0
    )


def _resolve_provider_call_budget(
    plans: Sequence[TranslationRootPlan],
    batches: Sequence[DocumentJobTranslationBatchRecord],
    explicit_budget: int | None,
) -> int | None:
    if explicit_budget is not None:
        return max(0, explicit_budget)
    values = {
        plan.provider_call_budget
        for plan in plans
        if plan.provider_call_budget > 0
    }
    if not values:
        values = {
            batch.provider_call_budget
            for batch in batches
            if batch.provider_call_budget > 0
        }
    if len(values) == 1:
        return values.pop()
    return None


def _retry_decision(
    batch: DocumentJobTranslationBatchRecord,
    *,
    used_budget: int,
    provider_call_budget: int | None,
    lease_expired: bool = False,
    respect_retryable: bool = True,
) -> tuple[bool, str, str]:
    if batch.attempt_count >= batch.max_attempts:
        return False, "attempts_exhausted", "翻译批次已耗尽最大 attempt 次数。"
    if provider_call_budget is not None and used_budget >= provider_call_budget:
        return False, "call_budget_exhausted", "本代 Provider 调用预算已耗尽。"
    if respect_retryable and not batch.retryable:
        if lease_expired:
            return False, "lease_exhausted", "翻译批次租约已耗尽，不能继续消费。"
        return False, batch.error_code or "translation_failed", "翻译批次已进入终态失败。"
    return True, "", ""


def _lease_expired(
    batch: DocumentJobTranslationBatchRecord,
    as_of: datetime,
) -> bool:
    return batch.lease_expires_at is not None and _normalise_datetime(batch.lease_expires_at) <= as_of


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _rows_for_failure(
    batches: Sequence[DocumentJobTranslationBatchRecord],
    *,
    terminal_ids: set[str],
    retrying_ids: set[str],
    stop_non_success: bool = False,
) -> tuple[TranslationBatchDispositionRow, ...]:
    stopping = bool(terminal_ids) or stop_non_success
    rows: list[TranslationBatchDispositionRow] = []
    for batch in batches:
        if batch.status == "split":
            disposition: TranslationBatchFailureDisposition = "superseded"
        elif batch.id in terminal_ids:
            disposition = "terminal"
        elif stopping and batch.status != "succeeded":
            disposition = "stopped"
        elif batch.id in retrying_ids:
            disposition = "retrying"
        else:
            disposition = "none"
        rows.append(
            TranslationBatchDispositionRow(
                batch_id=batch.id,
                is_effective_leaf=batch.status != "split",
                failure_disposition=disposition,
            )
        )
    return tuple(rows)

