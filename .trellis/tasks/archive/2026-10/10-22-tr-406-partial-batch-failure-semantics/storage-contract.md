# TR-406 批次仓储合同

本文件是 `repository.py` 与 file/sqlite/MySQL adapter 的窄端口说明。权威
`expected_plans` 由 execution 在锁外从 source/config 计算并传入；仓储绝不从
已有批次列表自证根集合，也不在锁内读取 source、对象存储、Provider 或写审计。

## 端口

```python
ensure_translation_batch_roots(
    job_id: str, *, generation: int,
    expected_plans: Sequence[TranslationRootPlan],
) -> list[DocumentJobTranslationBatchRecord]

get_translation_batch_snapshot(
    job_id: str, *, generation: int | None = None,
) -> tuple[DocumentJobRecord, list[DocumentJobTranslationBatchRecord]]

enqueue_translation_batch(
    batch_id: str, *, expected_generation: int,
    expected_attempt_count: int, provider_call_budget: int,
    expected_plans: Sequence[TranslationRootPlan],
) -> DocumentJobTranslationBatchRecord | None

claim_translation_batch(
    batch_id: str, *, expected_generation: int,
    expected_attempt_count: int, lease_owner: str,
    leased_at: datetime, lease_expires_at: datetime,
    provider_call_budget: int,
    expected_plans: Sequence[TranslationRootPlan],
) -> DocumentJobTranslationBatchRecord | None

update_translation_batch_if_current(
    batch_id: str, *, allowed_statuses: set[str],
    expected_generation: int,
    expected_attempt_count: int | None = None,
    expected_lease_owner: str | None = None,
    expected_job_id: str | None = None,
    expected_job_status: set[str] | None = None,
    expected_job_stages: set[str] | None = None,
    expected_plans: Sequence[TranslationRootPlan] | None = None,
    **patch: Any,
) -> DocumentJobTranslationBatchRecord | None

release_translation_batch_lease(
    batch_id: str, *, expected_generation: int,
    expected_attempt_count: int, expected_lease_owner: str,
    now: datetime, expected_plans: Sequence[TranslationRootPlan],
    **patch: Any,
) -> DocumentJobTranslationBatchRecord | None

split_translation_batch(
    batch_id: str, *, expected_generation: int,
    expected_attempt_count: int, expected_lease_owner: str,
    expected_plans: Sequence[TranslationRootPlan],
    children: Sequence[DocumentJobTranslationBatchRecord],
) -> tuple[
    DocumentJobTranslationBatchRecord,
    tuple[DocumentJobTranslationBatchRecord, ...],
] | None
```

`None` 表示普通条件竞争、旧 attempt/lease、旧 generation、任务已换代或消费
停止；批次或任务不存在继续抛 `FileNotFoundError`，JSON/SQL/锁等真实存储错误
继续抛出。根集合或 split 树不一致抛 `TranslationBatchTreeInvalidError`，其
稳定 code 为 `translation_batch_tree_invalid`，由 execution 在锁外推进失败收口。

## 线性化与停止闸门

- file 在 `document_jobs/<job_id>/job.lock` 内完成读、核验和写；JSON 文件由
  backend 的临时文件替换。部分根安装或 split 中断留下的残树下次以权威计划
  核验为 `translation_batch_tree_invalid`，不补根、不覆盖已有可变状态。
- sqlite 在同一连接 `BEGIN IMMEDIATE` 后按 job 当前 payload 和当前代批次快照
  核验、写入；异常由连接上下文 rollback。
- MySQL 需要先在事务外短读批次归属 `job_id`；真正写事务在同一连接固定先
  `document_jobs ... FOR UPDATE`，再以 `... FOR UPDATE` 当前读批次和全代列表并写入。
  这样不会在默认 RR 下先建立旧一致性读视图，也不会把 batch 锁置于 job 锁之前。
  commit/rollback 由 backend 上下文负责。三类 adapter 不在事务中做外部 I/O。

`ensure_translation_batch_roots` 空集合只在权威计划和实际集合都为空时成立；空
实际集合且有计划时一次写入全部根。已有完整集合只返回原始记录，保留 status、
attempt、lease、result 和账本字段。缺根、多根、不可变计划不一致均停止，不以
确定性 ID upsert 修补。

`claim_translation_batch` 在同一线性化点核对父 job 的 generation、`running`/
`translating` 阶段、完整根树，并在同一锁内调用 workflow 的唯一 reducer；reducer
归约为 failed/completed/canceled 时拒绝新的 enqueue/claim。随后再核对候选 status、
expected attempt、max attempts 和全代 `sum(attempt_count) < provider_call_budget`，然后递增 attempt
并写入唯一 lease_owner。`update_translation_batch_if_current` 传入
`expected_plans` 时执行同一根树和终态停止核验；queued、success、failure、split
等结果入口必须传入该参数，终态兄弟一旦落库，旧兄弟的条件写返回 `None`，由
execution 在锁外调用幂等 finalizer。只要锁内 reducer 已归约为任一终态，结果晋升
一律返回 `None`；不能按 `reason_code` 放行兄弟结果，因为锁外摘要到条件写之间兄弟
可能刚刚终败。合法的最后预算在途结果仅在 reducer 仍为 `running`/`retrying`（没有
待消费 leaf 触发终态）时晋升；lease 已过期或 attempt 已耗尽的旧结果仍返回 `None`。

`release_translation_batch_lease` 和 `split_translation_batch` 都必须接收锁外计算的
`expected_plans`，在同一 job 锁/事务中核对完整根树和同代终态停止结论，再接受当前
attempt/lease 条件。前者会复用 reducer，但允许当前已过期 lease 的自身回收，以便
attempt 尚有余量时恢复或在耗尽时落下诊断；后者在非幂等 split 前拒绝 reducer 终态，再登记
两个确定性子节点。数据库整次回滚，file 中断由下一次树核验失败关闭。子节点已有不同
不可变内容时抛树错误，不能覆盖。

