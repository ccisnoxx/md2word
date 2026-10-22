# TR-406 技术设计

> 修订 2，2026-10-22，已通过独立架构复审并获用户接受，进入实施。规划基线为 `md2word/TR-403@596a2de7ed29edb7fdb378d91c17bda09b7f1066`；实施分支为 `codex/tr-406-partial-batch-failure-semantics`。两项 P2 的处理映射见 `research/review-decisions.md`，复审见 `planning-rereview.md`，本轮授权见 `implementation-authorization.md`。

## 1. 真实基线与差距

`research/current-state.md` 保存文件锚点、反例和实际测试结果。当前链路为源 IR → 当前 generation 根批次 → Provider/完整性验证 → 成功 batch Artifact → 全叶子 fan-in → 一次 apply → 目标 IR/原生 DOCX。同步 translate 也在所有批次通过后一次 apply，不能重复建设。

| 已有能力 | 需补的行为 |
|---|---|
| split、attempt、总调用预算、租约、批次事件 | 当前 finalizer 先等活动叶子，终态失败不能立即收口；pending 领取也未在原子边界验证预算。 |
| 状态/generation 条件写 | failed 入口忽略 retryable/max_attempts；同代旧 attempt 可覆盖新尝试。file/sqlite/MySQL 当前批次实现不能称为原子 CAS。 |
| split 父节点写入后创建孩子 | 中断可能留下残缺树；只按 status!=split 取叶子不足以证明子树覆盖。 |
| 初始化先 list 判空、后逐条 create/upsert | 缺少本代完整根计划的一次性安装；迟到初始化可能重置运行记录与预算账本；单条加锁不足以解决。 |
| TR-403 完整性证据及 file_id 物理隔离 | 应保持，不放宽代次/哈希校验来复用旧译文。 |
| 任务批次 API、错误行、需关注统计 | 缺后端权威自动重试/终态/停止投影，统计包含 split 父项。 |
| CON-102 验收实现 | 不在当前 HEAD；其 translating/translation_validating、主任务锁、原子 retry、receipt 必须与 TR-403 正确整合。 |

不能根据 manifest done 推断当前源码拥有依赖。实施前准备包含已接受 CON-102 与 TR-403 的兼容 checkout；质量/下载合同沿用 CON-103/104 的 owner，不在 TR-406 重建。实施调查确认当前 checkout 同样缺少 CON-103/104，用户已追加授权整合这两项已验收实现及 CON-103 原有 schema bootstrap，再完成全部验收，详见 `implementation-authorization.md`。这只增加依赖基线整合，不授权 TR-406 新设计 DDL 或生产操作。真实 MySQL/InnoDB/部署文件锁启用门仍 pending。

## 2. owner 与目标边界

保持当前模块化单体，使用现有队列、资源快照、三类 metadata adapter 与 Artifact Storage，不新增依赖或配置开关。

| 责任 | owner |
|---|---|
| 批次树和 generation 结论的纯计算 | `document_jobs/workflow.py`：新增仅用于本合同的 typed reducer，execution/service 共用。验证实际 split 树和有效叶子，计算 retrying/terminal/stopped，不创建通用图框架。 |
| 执行与推进、失败事件、Provider 结果消费 | `document_jobs/execution.py`：调用快照/条件写入；终态优先、失败关闭；保留 TR-403 共享准备/Validator。 |
| 根计划一次性安装、原子领取、attempt 提交、同代一致快照 | `document_jobs/repository.py` 与 file/sqlite/MySQL `document_jobs.py`；复用 CON-102 的同 job 序列化点；禁止 create/upsert 重置已有批次。 |
| 用户 retry、权限、可下载文件 | `document_jobs/service.py`：保留原子 retry 和原权限；翻译失败的新代从权威 source 重新建批。 |
| API 与 UI | schemas/router 只投影，前端只消费权威结论及 available actions，不建立发布公式。 |
| Token、恢复、证据、对象不可变 | 复用 TR-403 的 translation integrity 与 files owner；本任务不复制其算法或存储路径。 |

## 3. 状态机和数据流

```text
ir_converting 保存 source IR
→ translating：本代完整根计划一次性安装/核验 → pending/queued
→ 同 job 锁内确认本代无停止结论 → claim → running
  ├─ 通过完整性 → succeeded（仅内部 batch result）
  ├─ 截断且可拆分/预算可用 → split → 两个子节点
  ├─ 可再试 → failed(retryable=true) → queued/running（同代 attempt+1）
  └─ 不可再试 / 残缺树 / 预算耗尽 → 叶子终态失败
       → 主任务 failed，failed_stage=translating，translation_failed
       → 禁止后续领取/结果晋升/回填/目标 IR/DOCX
全部有效叶子 succeeded
→ translation_validating：重核 source/binding/hash/ID/coverage
→ 一次 apply → 当前目标 IR → rendering/quality_checking/uploading
→ CON-102 唯一 receipt → 主 DOCX
```

判定顺序固定为：核对 job 当前代/状态 → 识别明确取消或超时 → 校验批次树 → 已存在终态失败优先 → 自动恢复/等待活动叶子 → 全部成功 → fan-in。`retryable=true` 只是记录当时意图，实际剩余 attempt 与全代预算也必须满足；预算已耗尽且失败叶子无法重试时立即终态。已在途且合法占用预算的请求可完成，但不得再新领取。pending 没有可用预算且没有已存在终态原因时，也要显式失败，不无限等待。

所有 batch 均无可运行/成功路径的异常状态（例如 running job 下孤立 canceled 叶子）显式失败；不得长期返回 running。沿用既有 Worker/recovery 入口和总 timeout，不新增扫描调度系统；没有新投递时不承诺新增主动监控能力。

“立即失败”表示持久化终态叶子后本次收口立即推进，不等待同代兄弟；该持久化终态本身已是本代停止新工作的依据，不等到 job.failed 才禁止领取。若进程恰在两步间中断，终态批次自身或排队兄弟的消费入口都须先检查停止结论、调用同代幂等 finalizer 后返回；不依赖另一次主任务 replay，也不宣称跨 job/batch/event exactly-once 事务。普通 claim 竞争和过时消息不自动视作新失败，具体拒绝路径见 3.2。

### 3.1 树、split 和覆盖

只从本代根节点遍历；未 split 的节点是有效叶子，split 父节点必须有两个确定性子节点，且 parent/root/source/config/generation 一致，item IDs 严格分区覆盖父项，无空组、重复或遗漏。全根还须在 fan-in 与权威 source 的有序 items 对账，不能只核对计数。

split 的状态变更和孩子登记使用同一 job 锁/事务，避免并发消费者看到正在写入的半棵树。MySQL/sqlite 在事务内提交；file adapter 只承诺同 job 排他与各文件原子替换，不假装多文件事务。file 中断留下的不完整 split 在恢复时明确 `translation_batch_tree_invalid` → 主任务失败，保留已写证据，用户可新代 retry；不静默补原文、不盲目续用部分孩子，也不新增事务日志系统。真正的零单元由权威 source 抽取/计划证明；“只有 split 父节点”不能走空计划成功。

### 3.1.1 初始根计划的一次性安装（P2-1）

在既有批次仓储 owner 增加“确保本代完整根计划已安装”的窄操作，取代调用者先 list 判空、再逐条 create/upsert 的竞态；不是为每次 create 分别加锁。唯一安装单位为 job_id + generation 的完整确定性根集合，不新增安装标记、持久字段或事务日志。

1. 锁外读取并按 TR-403 验证权威 source/config，计算本代确定性 plans；预期根 ID 和不可变计划字段来自该计算，不能从现有记录自证完整性。expected plans 绑定准确 source file/checksum、快照与 generation；不在锁内做 source/Provider/对象 I/O。
2. 同 job 锁/事务内重读父 job 与当前代全部批次，核对预期 generation 和合法阶段。过时或终态调用不再安装、不推进状态，返回当前权威现态；不能用旧计划修改新代。当前合法代有既存停止结论时先拒绝新安装/消费，并走 3.2 的收口。
3. 当前代全部批次记录为空时，只有真实 plans 非空才一次安装完整根集合；安装完成并核验前不得 enqueue/claim。sqlite/MySQL 使用同一连接事务，出错全部回滚；file 使用整次安装的同 job 锁和各文件原子替换，完整写完前不投递。
4. 当前已有根时，比较根 ID 集合及不可变计划字段：job/generation/job_retry_count、root/parent、源件与语言/术语绑定、item 有序分区/计数、规划预算；允许根已 split，其后代另按树规则核验。完整且一致则返回包含原 status、attempt、lease、result 的权威现态，不能写回新构造的 pending/attempt=0，也不比较或重置运行时间等可变字段。`create_translation_batch` 对已有确定性 ID 不得再用 upsert 覆盖；任何在用创建入口都服从本合同。
5. 非空但缺根、多根或不可变字段不一致，均为 `translation_batch_tree_invalid` 停止结论，不补缺根、不覆盖现存记录。file 安装中断后的恢复按同一确定性期望根集合识别残缺，保留证据并使主任务失败。重放/恢复及批次消费在 enqueue/claim 前必须经过完整根集合核验，不能只在最终 fan-in 才发现缺根。

只有权威 source 确认零 items 且 plans/根集合均为空时走原零单元路径；残缺安装不等同零单元。迟到初始化在 A 已成功一根、另一根运行时只能观察权威现态，不得减小累计 attempt 或更换结果指针。本合同以 AC12 的双初始化 barrier、数据库回滚和 file 部分写入中断验收；不能把未增加 Provider 调用的简单重复 create 当作完整验证。

### 3.2 原子领取和 attempt 隔离

扩展窄批次端口，不提供通用条件 DSL：

- 原子 claim：同 job 锁/事务中核对父 job 为本代 running/translating、完整根计划、当前代快照无 terminal/tree-invalid 等停止结论，然后核对可运行批次、预期 attempt、失败的 retryable、max_attempts 和全代 attempt 总预算，才递增 attempt 并写 running/唯一 lease_owner。enqueue 使用同一停止闸门；既有排队消息不能凭父 job 仍 running 绕过。现有常量 `translation_batch_worker` 改为本次 claim 的唯一 lease 身份，不新增持久字段、heartbeat 或配置。
- queued、success、failure、split、lease 回收等条件写入补充预期 attempt/lease，且在同一序列化点核对父 job/generation 和合法阶段。success/failure/split 只能由当前 running claim 提交；回收要比较观察到的 lease 身份/到期状态；过期但已被新 attempt 接管的记录不再修改。
- 领取与终态更新不得仅把 Python 中的 read→check→upsert 命名为 CAS。file 复用 CON-102 的 `job.lock`/`record_lock`，sqlite 使用 `BEGIN IMMEDIATE`，MySQL 固定 job→batch 锁顺序并在同一连接事务核验预算/更新；禁止在锁内进行 Provider、对象 I/O 或事件外调。
- 批次快照读取在同一 job 序列化边界取得 job 与当前代全部 batch，供 reducer 和 API 使用，避免先读旧 job 再拼新代列表。新增快照端口用于一致性，不是字段转发包装。所有运行期 batch 写入口（含 unconditional updater 的在用路径）必须服从同一锁，不能留绕过入口。
- 普通竞争沿 record/None 风格，调用方读取权威现态；若同代已出现停止结论，释放锁后调用幂等 finalizer 再返回，不直接结束。该检查也覆盖不可重试终态批次自身的重复消息以及 enqueue 拒绝路径，不能把停止原因与普通竞争混成同一种直接返回。若只是另一个合法 claim 获胜则不误记失败；若 generation 已变化或 job 已终态则不修改新代、不复活旧代。真正存储错误仍显式抛出并按阶段映射，不能当成竞争失败吞掉。

同代持久化停止结论出现后，不再允许新 enqueue/claim 或成功结果晋升；不能只以 job.failed 为门。检查停止结论和领取的线性化点均在现有同 job 锁内；这里不承诺强制取消终态前已合法领取的在途请求，也不在锁内调用 Provider。其他已在途批次的持久 status 可保留“最后一次运行观察”，诊断投影为 stopped；不把其伪装为用户 canceled 或改写已有成功证据。实际已经发出的请求保留一次真实调用审计，不能选为当前主件。

终态叶子成功落库后立即进入 finalizer；若在其间中断，下一条终态自身或兄弟消息须按上述闸门触发同代收口。finalizer 使用预期 generation 的原子 job 更新，只有成功推进 job 终态的执行者写对应 stage_failed；重复收口观察现态，不重复终态事件。AC13 在 batch CAS 与 job 更新之间故障注入，并分别验证两种消息重放，包含另一次重放和并发换代对照。不新增扫描器或跨域事务，存储/审计错误仍保持可见。

### 3.3 generation、用户 retry 与并行任务

批次消费必须 `batch.generation == batch.job_retry_count == job.retry_count`，source/config/evidence 和 attempt 均由权威记录构造。沿用 TR-403 的严格类型、真实字节 checksum/size 和 file_id 唯一 key。

自动 retry 不变 generation，成功兄弟不重调 Provider。用户 retry 翻译失败由 CON-102 原子 retry 端口唯一换代，默认原快照；先验证 job 权威 source 指针、归属、role、IR 来源与真实字节，再从该源建立全部新代批次。不复制同字节 source 来冒充新代，不重包旧译文/evidence。源文件的创建代次可以早于消费代次。已授权资源重选仍先解析资源，再以预期旧代提交新快照；并发 retry 冲突沿既有 409。

本任务只明确翻译失败的恢复，不重写 rendering/quality_checking/uploading 已有恢复策略。TR-405 revision 2 尚待批准的有 QA 快照重译设计不是本任务基线；若随后落地，交叉文件整合时保持其强约束，不退回旧代 report/译文复用。TR-404/405 与本任务可能同写 execution/service/translator，实施前固定已接受基线并协调文件所有权，禁止互相覆盖或顺手实施相邻需求。

## 4. partial Artifact、权限与安全

成功 batch result 含恢复译文和 evidence，是正常中间输入；只在全部当前叶子通过时才可消费。主任务最终失败后保留其身份用于内部诊断，不改 file_type，不提升 job.document_ir_file_id/result_file_id，不生成 partial 目标 IR 或 DOCX。未通过 Validator 的响应没有成功 batch result；默认仅安全摘要审计，全文仅走现有 Admin 开启的 ai_debug_archive。ledger 保持内存。

任务 files/download allowlist 当前不含 translation_batch_result；本任务维持排除，并回归验证显式 file_id 下载、QA/latest fallback 和现有管理文件入口不会把它提升为主件。debug 不新增可见性，沿现有 owner/admin、签名、TTL、审计与受控文件规则；不把“debug only”解释为允许向普通日志暴露文本。source PDF/source IR 的已有合法下载保持，不能显示为翻译成果。

质量 blocked 与翻译 unreviewed 的完整 DOCX 仍沿 CON-103/104 内部下载/批准发布拒绝合同。本任务没有新的 review/publication endpoint，不修改发布资格计算。一个 job 只由现有 receipt 选出一个主 DOCX；历史主件、发布记录、资源快照和审计不可变。

## 5. 模型、API 与 UI

不新增执行 status、stage 或 batch status；使用 CON-102 的真实阶段。复用现有 attempt_count/lease_owner/generation/job_retry_count，不新增 DB 字段。

`GET /api/v1/document-jobs/{job_id}/translation-batches` additive 扩展：

- 列表新增 nullable `execution`，旧客户端可忽略；字段为 `outcome`（not_started/running/retrying/validating/failed/completed/canceled）、`leaf_count/succeeded_leaf_count/active_leaf_count/retryable_failed_leaf_count/terminal_failed_leaf_count`、nullable `failure_batch_id/reason_code/reason_message` 和 `partial_artifacts_debug_only`。generation 沿用列表现有字段，不再存第二份。job 终态优先；retrying 表示有待执行的可重试失败叶子或自动恢复尝试在途，普通首次执行为 running；不能仅因历史 split 父项存在就报失败。
- 每行 additive `is_effective_leaf`、`failure_disposition`（none/retrying/terminal/stopped/superseded）；split 父项为 superseded，主任务失败后的非终态兄弟为 stopped。旧字段保留，原 result_file_id 仍只是中间文件标识，无下载授权含义。
- summary/reducer 只消费同一授权快照，必须先按 get_job 等价规则校验可见性，再读取；direct 返回 execution=null，不加载翻译资源。旧记录可读，但不能伪造“已重新校验”。不新增 endpoint、请求参数或 ApiError 枚举。

`JobDetailPage.vue` 和 `utils/translationBatches.ts` 以新字段呈现有效叶子进度/失败提示；旧 API 缺 execution 时保留现有诊断并标“详细结论不可用”，不自行推断终态或发布资格。异步批次请求绑定 job_id/请求轮次，并比较 response.generation 与已显示 job.retry_count；旧响应不覆盖新代。保留键盘、重试按钮 disabled reason、原页面布局与未知状态 raw fallback。更新 api/types.ts，避免临时强转。

OpenAPI 由 `scripts/ops/export_openapi.py` 生成 `docs/api/openapi.json`；同步 `docs/api/document-jobs.md`。常规事件复用 translation_batch_*、stage_failed/retry_requested，不新增事件种类；payload 带实际 generation、attempt、root/parent、terminal/retrying/stopped 原因、计数与 trace，绝不写未经验证的 ID 或外部异常全文。

## 6. 错误映射与可观测性

| 场景 | failed_stage / 顶层错误 | 安全原因 |
|---|---|---|
| Provider/完整性叶子最终失败 | translating / translation_failed | 原 batch 专码；attempts_exhausted、call_budget_exhausted、lease_exhausted 等区分。 |
| split 树损坏或非法叶子状态 | translating / translation_failed | translation_batch_tree_invalid / translation_batch_state_invalid。 |
| fan-in ID 缺失/额外 | translation_validating / translation_fan_in_mismatch | 仅计数、权威批次身份。 |
| fan-in 完整性/来源/代次/证据失败 | translation_validating / translation_failed | TR-403 现行专码与安全摘要。 |
| 实际 Artifact/仓储 I/O 失败 | 实际阶段 / oss_failed（沿 CON-102） | 固定安全文本；不把 I/O 伪装为 Provider 或 JSON 错误。 |
| 旧 generation/attempt、重复消息 | 不改当前 job | 条件写被拒绝；不记假成功或新 Provider 调用。 |
| 主任务取消、超时、未预期异常 | 保留当前合同 | canceled、document_job_timeout、document_job_unexpected_error，不复活任务。 |

批次完整性失败仍按原有有限尝试预算处理，不新增“自动修复”模型；只有真实疑似截断可 split，Token 错误不能冒充截断。业务 QA warning/blocked 不属于 Provider terminal failure，TR-405 若已落地须保持这一区分。审计自身失败保持可见，不捕获后补一份伪失败调用日志。

## 7. 数据库、兼容、迁移、部署与回滚

- TR-406 批次合同不新增表/列/索引、DDL、backfill、历史批次重写或已发布文件迁移。经用户追加授权，依赖基线整合可带入 CON-103 已验收的 schema bootstrap 与原有兼容行为；不在此基础上再新增迁移设计，不连接生产数据库。DTO 和事件是 additive；内部 lease_owner 已是字符串，唯一值可直接往返。批次部分改变的是条件更新事务语义，三 adapter 必须一起验证。
- 活跃旧批次由部署窗口接管：暂停翻译入队，排空旧 Worker/旧活跃代，再同步部署 API/Worker。无唯一 lease 的旧 running 批次只能在其旧租约到期后按新 claim 创建新 attempt，不能拿新身份接收旧回流；缺 TR-403 evidence 的活跃旧结果继续拒绝。历史完成件只读不重跑。
- 不让忽略 attempt 条件的旧 Worker 与新写者混跑。真实 MySQL/InnoDB 和部署文件系统锁的既有门禁仍须满足后才启用生产写者；本轮 fake/本地测试不代表通过。
- 回滚先暂停翻译与相关恢复执行，保留队列身份、所有 Artifact/receipt/审计/快照；只回到仍能保持当前 generation/attempt 和完整性门的兼容版本，否则维持停执行待修复。不删历史数据、不回退无校验回填，不回退 direct，不覆盖发布件。
- 没有尚待选择的外部系统；实现和定向验证可用现有 fake/adapter。真实 Provider 测试明确范围外；线上部署、专有样本和 Word 人工签字不冒充本任务规划证据。
