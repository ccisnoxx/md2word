# TR-406 workflow reducer 合同

本文件记录 `app/domains/document_jobs/workflow.py` 中唯一的纯代次归约入口，供仓储原子操作、执行编排和批次 API 共同调用。它不写仓储、不调用 Provider、不推进主任务，也不把普通条件竞争解释为终态失败。

## 稳定入口

```python
reduce_translation_generation(
    *,
    job_id: str,
    job_status: str,
    job_stage: str,
    generation: int,
    expected_plans: Sequence[TranslationRootPlan],
    batches: Sequence[DocumentJobTranslationBatchRecord],
    provider_call_budget: int | None = None,
    as_of: datetime | None = None,
) -> TranslationGenerationSummary
```

`expected_plans` 必须由权威 source/config 计算，不能从现有批次记录反推。根计划包含根 ID、job/generation、source IR、语言/术语绑定、有序 item 分区、页码/字符计数、最大 attempt、确定性根数和本代调用预算。`batches` 是同一 job 的一致性快照；调用方在同一序列化边界取得它们。`provider_call_budget` 明确传入时优先，否则仅在全部根计划（或记录）共享同一个正预算值时复用该值；无法确定时不凭空判定预算耗尽。

`validate_translation_batch_tree(...)` 是同一文件中的窄纯校验入口，返回 `TranslationBatchTreeCheck`，供根计划安装和普通 reducer 共用。它只验证结构，不推导执行结论。

## 树校验

- 期望根集合与实际根 ID 必须完全相等；根的不可变字段必须逐项匹配权威计划。空计划只有在实际记录也为空时才是零单元。
- 根、子节点必须保持 job、generation、job retry、source IR、语言/术语绑定和预算身份。孤立子节点、缺根、多根、重复记录、重复 item 或未知 root 都返回 `translation_batch_tree_invalid`。
- `split` 父节点必须恰好有两个非空子节点，子节点 ID 必须是 `<parent>_s<level>_01/02`，两个有序 item 分区必须无交集且严格覆盖父项。未 split 的记录不得拥有子节点。
- `canceled` 叶子属于同代非法状态，返回 `translation_batch_state_invalid`；普通 claim/CAS 竞争不由 reducer 生成终态结论。

## 结论与优先级

结果 `outcome` 只使用：`not_started`、`running`、`retrying`、`validating`、`failed`、`completed`、`canceled`。结果同时包含有效叶子总数、成功/活动/可重试失败/终态失败计数、失败批次和安全原因，以及逐行 `is_effective_leaf` 与 `failure_disposition`。后者只使用：`none`、`retrying`、`terminal`、`stopped`、`superseded`。`split` 父项永远是 `superseded`，不进入叶子计数。

计数必须从同一次 reducer 产生的逐行 disposition 归类：终态失败或不可恢复的过期 running 是 `terminal` 并计入 `terminal_failed_leaf_count`；已有终态失败后，其他未终态失败叶子即使原记录 `retryable=true` 也改为 `stopped`，不能继续计入 retryable；合法活动叶子只有在行级仍为 `none/retrying` 时计入 active。原始记录字段不被回写或伪造。

判定顺序为：显式取消 → 已持久化 job 终态（failed/succeeded）→ 权威树校验 → 已过期 lease 的可恢复性/终态性 → 终态失败 → 同代重试 → 活动叶子 → 全部成功/验证阶段 → 零单元。终态 job 只投影主任务权威状态和行级描述，不用历史批次重新校验树，也不开展新工作；`job_status=failed` 时所有非成功、非 split 的历史批次均投影为 `stopped`（已有确切 terminal 行仍保留 `terminal`），避免 active/retryable 计数继续显示可消费工作；运行中 job 仍必须先通过权威 expected 根集合硬门。终态失败一旦存在，未终态兄弟是 `stopped`，不等待其完成；成功兄弟保留 `none`。`job_stage=translation_validating` 且全部有效叶子成功时返回 `validating`。

合法 `running` 叶子即使已经占用本代最后预算也保持 `running`，允许正在进行的调用完成；自动恢复中 `attempt_count>1` 的合法 running 叶子投影为 `retrying`。待消费 `pending/queued` 叶子在预算耗尽时返回 `failed/call_budget_exhausted`，避免永久 running。失败叶子按 `retryable`、`max_attempts` 和本代预算共同决定 `retrying` 或终态；原因码优先为 `attempts_exhausted`、`call_budget_exhausted`，否则使用批次安全错误码。运行中 claim 会将旧 `retryable` 清零，因此过期 lease 的恢复只按当前 attempt 与本代预算判断，仍有资源时为 `retrying`，耗尽时返回对应的 `attempts_exhausted` 或 `call_budget_exhausted`。

该合同只描述纯判定。仓储负责在同 job 锁/事务中执行完整根安装、claim 和条件写，execution 负责调用 reducer 后收口主任务，API 负责把 `TranslationGenerationSummary` 投影为响应；三者不得各自复制树、预算或停止规则。
