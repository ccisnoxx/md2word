# 翻译批次生命周期与原子边界

## 1. 范围与触发

修改 DocumentJob 翻译根计划、split、同代自动恢复、attempt/lease、批次仓储、失败收口或 translation-batches API 时适用。完整性证据仍由 [Validator 合同](translation-integrity-validator.md) 拥有，主件 receipt 与物理文件身份仍由 [数据库合同](database-guidelines.md) 拥有，质量/下载/发布资格沿用 [模式与阶段合同](document-job-mode-contract.md)。

- `document_jobs/workflow.py` 唯一拥有树校验与纯 generation reducer。
- `repository.py` 与三个 metadata adapter 拥有同 job 原子操作和一致快照。
- `execution.py` 负责锁外 I/O、权威计划构造、调用原子端口和幂等 finalizer。
- `service.py` 负责用户 retry、授权及 API 投影；前端只消费结论和 available actions。

## 2. 签名

纯判定的实际入口：

```python
reduce_translation_generation(
    *, job_id: str, job_status: str, job_stage: str, generation: int,
    expected_plans: Sequence[TranslationRootPlan],
    batches: Sequence[DocumentJobTranslationBatchRecord],
    provider_call_budget: int | None = None,
    as_of: datetime | None = None,
) -> TranslationGenerationSummary

validate_translation_batch_tree(
    *, job_id: str, generation: int,
    expected_plans: Sequence[TranslationRootPlan],
    batches: Sequence[DocumentJobTranslationBatchRecord],
) -> TranslationBatchTreeCheck
```

仓储的窄端口由 `DocumentJobTranslationBatchRepositoryProtocol` 定义：

- `ensure_translation_batch_roots(job_id, *, generation, expected_plans)`：完整根集合一次安装或返回原现态。
- `get_translation_batch_snapshot(job_id, *, generation=None)`：同一边界读取 job 和该代批次。
- `enqueue_translation_batch(...)` / `claim_translation_batch(...)`：显式接收 expected generation、attempt、调用预算和权威 expected plans；claim 另接唯一 lease 与起止时间。
- `update_translation_batch_if_current(...)`：运行期提交接收 expected generation、attempt、lease、job 状态/阶段与 expected plans。
- `release_translation_batch_lease(...)` / `split_translation_batch(...)`：显式接收 expected generation、attempt、lease 和 expected plans；前者比较观察到的到期 lease，后者原子登记父状态和两个孩子。

这些方法返回记录或 `None` 表达条件竞争；根/子树不一致抛 `TranslationBatchTreeInvalidError`。真实存储异常不转换成竞争。旧有无条件更新只用于已有内部管理/测试准备，运行期消费必须走相应条件端口。

## 3. 数据与状态合同

- expected plans 在锁外由已验证的不可变 source/config 计算，包含确定性根身份、代次、源件、语言/术语绑定、有序 item 分区及规划预算。不能从现存根列表反推期望集合。
- 完整根集合是安装单位。已有 ID 不得通过 create/upsert 重置 status、attempt、lease、result 或累计调用账本；已 split 的根仍保留原计划身份。非空残缺集合失败，不补根后继续。
- split 必须有两个确定性孩子，parent/root/source/config/generation 一致，按顺序无重叠、无缺项地覆盖父 items。split 父不是有效叶子，只有权威零单元计划可走空成功。
- enqueue、claim、success/failure/split 和 lease 回收在同 job 序列化点核对当前代、完整树及已持久化停止结论。不能只看父 job 仍为 running；停止后不再新领取或晋升在途结果。
- claim 在锁内核剩余 attempt 和全代 `sum(attempt_count)` 预算，再增加 attempt 并写唯一 lease。过期 running 的恢复只看剩余 attempt/预算，不能依赖 claim 已清零的 retryable；failed 记录仍受 retryable 约束。
- file 复用稳定 job.lock 和单文件原子替换，不承诺多文件事务；残缺安装/split 在恢复时失败关闭。sqlite 使用同连接 BEGIN IMMEDIATE；MySQL 固定同连接 job→batch 锁序；事务/锁内不做 Provider、对象存储或审计外调。
- 持久化终态后立即调用 finalizer，不等待兄弟。若在 batch 终态与 job.failed 之间中断，终态自身或排队兄弟的重放都须在停止拒绝后锁外收口；只有成功推进主任务的执行者记终态事件。普通合法 claim 竞争和旧代不误记失败。
- 用户 retry 由既有原子入口换代，从权威 source 重建全部批次；只有同代自动恢复复用成功兄弟。不重包旧译文，不复制 source 来冒充同代，不覆盖历史主件。

`GET /api/v1/document-jobs/{job_id}/translation-batches` 先做等价 get_job 可见性校验，再从同一 job/batch 快照投影 generation、execution 和行级字段。execution 为 nullable，outcome 为 `not_started/running/retrying/validating/failed/completed/canceled`，包含五项叶子计数、nullable 失败批次/安全原因及 partial_artifacts_debug_only。每行新增 is_effective_leaf 和 failure_disposition（none/retrying/terminal/stopped/superseded）。direct 的 execution=null，不加载翻译资源；旧 API 缺字段时 UI 标明结论不可用，不自行推断发布资格。异步响应须绑定 job、请求轮次和当前 generation。

## 4. 校验与错误矩阵

| 条件 | 结果 |
|---|---|
| 缺根、多根、不可变绑定不一致、残缺/重复/孤立 split | `translation_batch_tree_invalid`，主任务 `translating/translation_failed`。 |
| running job 下非法 canceled 等有效叶子 | `translation_batch_state_invalid`，明确失败。 |
| attempt / 全代调用预算 / 最终租约不可恢复 | 稳定的 `attempts_exhausted` / `call_budget_exhausted` / `lease_exhausted` 诊断，不新增调用。 |
| 旧 generation/attempt/lease 或普通条件竞争 | 不写胜出记录；旧代不推进新代，普通竞争不生成失败。 |
| 同代停止拒绝 enqueue/claim/结果提交 | 锁外幂等 finalizer，无新 Provider 或结果晋升。 |
| fan-in 缺项/额外项 | `translation_validating/translation_fan_in_mismatch`。 |
| evidence/来源/字节/hash 不符 | 保留 TR-403 专码，`translation_validating/translation_failed`。 |
| 真正仓储/Artifact I/O | 沿真实阶段的 `oss_failed`，不得伪装成 Provider/JSON 错误。 |

普通事件和新摘要只含固定安全文本、代次/attempt/计数和本地权威身份；不输出外部异常正文、源文/译文、Prompt、对象路径或签名 URL。每次真实 Provider 调用只审计一次。

## 5. 正常、缺省与非法场景

- 正常：一根截断 split 后两子成功，所有有效叶子通过，再 fan-in/apply 一次并由原 receipt 选主件。
- 缺省：direct 不参与翻译；历史 job 终态只投影权威结论，不因缺批次或旧诊断重判失败，也不补写“已重新验证”。
- 非法：迟到初始化覆盖已成功根；半棵树被当成零单元；一个叶子终败时仍领取兄弟；旧 attempt 回流替换 evidence；partial result 被提升为目标 IR/DOCX 或普通下载来源。

## 6. 必要测试

- `tests.test_translation_batch_workflow`：终态优先、split 覆盖、预算与真实 retryable=False 的过期 claim、自动恢复在途 outcome、安全计数和行级语义。
- `tests.test_translation_batch_repository`：真实 file/sqlite 双初始化 barrier、两独立连接/消费者、最后预算、旧 attempt/lease、完整根/父孩子事务回滚、file 中断残树，以及 fake MySQL 同连接锁序/rollback。
- `tests.test_translation_batch_failure_semantics`：真实执行器和 fake Provider 的终败优先、AC12 消费前拒绝残根、AC13 terminal CAS 故障窗口两类消息重放、普通竞争/换代对照、零主件/零新调用/零重复终态事件；公开样本与合成表格的成功/失败对照。
- 保留 TR-403 evidence、真实字节与 checksum 保护、CON-102 receipt、CON-103/104 下载/复核/资格、direct 零翻译和前端旧代响应回归。

fake MySQL 不证明 InnoDB 并发或断连。真实 MySQL、部署文件系统跨进程锁、旧 Worker 排空和 Word 人工证据仍是生产启用门；不得混跑忽略新 attempt 条件的旧写者，无 backfill 或历史发布件覆盖。

## 7. 错误与正确做法

错误：调用者先 list 判空，再逐条 upsert 根；只按 batch.status 领取；claim 返回 None 就直接返回；部分成功结果先回填后检查剩余叶子。

正确：锁外从权威 source/config 计算 expected plans，同 job 边界一次安装/核验完整集合；所有运行期条件操作核当前代、树、停止结论和 attempt/lease。拒绝后区分普通竞争、旧代和同代停止，最后一种锁外幂等收口。全部叶子及完整性通过后一次回填，部分结果只保留既有受控诊断身份。
