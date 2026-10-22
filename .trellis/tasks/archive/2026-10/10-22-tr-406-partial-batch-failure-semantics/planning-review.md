# TR-406 revision 1 独立架构规划审查

> 历史审查记录：下述问题位置均为 revision 1 当时的行号，不能当作修订后文档的现行位置。revision 2 已按用户指示处理两项 P2，最新映射见文末及 `research/review-decisions.md`；本记录不表示 revision 2 已独立复审。

日期：2026-10-22。对象：revision 1 的 prd.md、design.md、implement.md。

审查方式：全新 architect，fork_turns=none，不继承主会话历史；只读核对三件套、相关 Spec/产品合同、当前实现/测试代码及 CON-102 验收提交。子代理报告由主会话整理落盘，主会话已核对下述规划锚点、初始化链路及失败/claim 路径，并接受两项问题。未修订三件套，未授权实施。

审计 ID：`20261022T021032Z-tr-406-revision1-fresh-architect-review-3ca8901c`。

## 结论

revision 1 暂不宜通过实施准入评审。确认两项 P2 规划缺口，无确认 P1；补足窄合同和定向验收后再评审。现有整体模块边界、失败产品语义与状态 owner 可以保留，无须新持久字段、事务框架或队列重写。

这里的确认问题是规划合同未闭合，不把现有代码尚未实现新设计本身当成规划缺陷，也不声称已经运行未来候选的并发测试。

## P2-1 初始根计划缺少一次性安装和不可覆盖合同

**规划位置：**`design.md:60`、`design.md:69`、`implement.md:23`。

设计明确 split 父子登记同事务、运行期 batch 写者共享 job 锁，却未定义初始根计划的“重新检查不存在→安装完整计划”边界，也未约定 create 遇到已有确定性 ID 时保留权威现态而非覆盖。仅对单条 create 加同一锁并不能解决迟到初始化。

**触发交错：**同代至少两根批次，初始化 A、B 都先读到空列表。A 安装并开始消费，一根已成功、另一根运行中，job 仍 running/translating。B 随后取锁，以早先构造的 pending/attempt_count=0 记录逐条 create；若沿原 create/upsert 语义，会重置现有状态、attempt/lease/result 指针。

**影响：**成功兄弟可能重复调用 Provider，attempt 总和被低估并绕过 max_attempts/全代预算，已选结果指针丢失。file_id 物理隔离保护旧字节，无法保护执行账本。

**代码证据：**

- `app/domains/document_jobs/execution.py:1072` 先 list 判空，`:1144` 逐条 create。
- `app/infrastructure/persistence/file/document_jobs.py:246` create 直接写记录。
- `app/infrastructure/persistence/sqlite/document_jobs.py:401`、`app/infrastructure/persistence/mysql/document_jobs.py:421` 的 upsert 冲突覆盖。
- architect 对照 CON-102 验收提交 `4d30682`，同一初始化仍为先 list、后逐条 create；单纯整合依赖不解决该规划缺口。

**最小修订建议：**在现有批次仓储 owner 内定义初始化本代计划的窄操作。锁外基于不可变 source/config 计算；锁内重核 job/generation/已有计划，已有计划返回权威现态，禁止覆盖 status、attempt、lease、result。数据库同事务安装完整根集合；file 中断留下部分根集合时，恢复按确定性计划检测并失败关闭。

**补充验收：**双初始化 barrier：B 判空后暂停，A 完成一根并领取另一根，再恢复 B；断言已有批次记录、预算账本、结果身份均不变，成功兄弟不重复调用。

## P2-2 终态叶子落库到 job.failed 之间缺少消费入口闸门

**规划位置：**`design.md:54`、`:66`、`:70`；关联 `prd.md:28`、`implement.md:68`。

终态优先的 finalizer 已明确，不需要重做。缺口是设计接受“先持久化终态叶子、再推进主任务”的中断窗口，但 claim 前提只列父 job、当前 batch、attempt/retryable/预算，没有要求同一锁内拒绝已有终态叶子的 generation；冲突路径还规定读取现态后停止，没有要求终态 batch 消息重放触发同代收口。

**触发交错：**A 把叶子写为不可重试 failed，在 finalizer 前中断，父 job 仍 running/translating。排队兄弟 C 此后消费，按当前列举的 claim 前提仍可领取并调用 Provider。若重放 A 本身，claim 被拒绝便返回，也不推进主任务失败。CON-102 主任务 recovery 可在另外一次 replay 时收口，但不能保证已经到达的 batch 消息先收口再停止。

**影响：**已知终态之后仍可能新调用 Provider，主任务可能继续显示 running，直到兄弟结束或额外 recovery。这不属于“不新增主动扫描器”的已接受限制，因为该交错已有消费消息到达。

**代码证据：**

- `app/domains/document_jobs/execution.py:1176`–`:1178`，claim 拒绝后直接返回。
- 同文件 `:1388` 批次失败写入、`:1408` 事件、`:1427` finalizer 是分步执行。
- architect 对照 CON-102 验收提交 `4d30682`，batch 入口也保持 claim 拒绝直接返回，主任务 `_ensure_translation_batches_and_enqueue` 才调用 finalizer。

**最小修订建议：**将持久化终态叶子明确为本代停止新工作的依据。claim/enqueue 在现有 job 锁内用当前代快照检查 terminal/tree-invalid 等停止结论；拒绝后走同代幂等 finalizer 再返回。终态 batch 重复投递也走该收口路径，不承诺 job/batch/event 跨表 exactly-once。

**补充验收：**在 terminal batch CAS 后、job 更新前故障中断；分别重放终态 batch 和排队兄弟，断言 job 失败收口、Provider 调用数不增加、终态事件不重复。

## 五项重点的其余判断

| 重点 | 判断 |
|---|---|
| 依赖基线整合 | HEAD=596a2de7；TR-403 可达，CON-102 两验收提交不可达，与规划一致。实施门保留 stage/原子 retry/receipt 及 TR-403 编码/evidence/脱敏/物理身份。除上述初始化缺口，无新增确认整合冲突。 |
| attempt/lease | 唯一 lease、预期 attempt/lease、回收时比较原 lease/到期、job→batch 锁序、同连接事务及可见存储异常已有明确设计；方向可保留。 |
| 终态收口 | 活动兄弟不得延后失败、残缺 split 失败关闭、非法 canceled 叶子及真实零单元均覆盖；新增问题为两步窗口的入口闸门。 |
| partial Artifact | 成功中间证据与失败正文、下载 allowlist/显式 file_id/QA latest/source IR、debug 授权/TTL/审计及唯一主件历史不可变已纳入设计验收，无新增确认缺陷。 |
| 跨代 retry | 自动同代只重试失败叶子，用户原子换代从权威 source 重建；source 创建代可早于消费代，旧译文禁止重包。与 TR-403 Spec 一致，未扩大 rendering/uploading 恢复。 |

## 证据边界和工作区保护

- 子代理 completed 后、主会话保存此报告前，对派发前 1425 个 tracked/untracked 路径检查：无文件字节变化、无新增路径、HEAD 未变。三件套哈希与派发前一致；这为仓库只读行为提供核验，不仅依赖子代理自报。
- 本轮开始父任务六个文件已处于删除状态，未恢复、覆盖或把旧研究记录当成当前现场。
- 没有运行业务测试或未来候选竞态测试，也未重跑上轮37项基线；无真实 Provider、MySQL/InnoDB、部署 FS、浏览器或 Word 证据。兼容基线尚未组成，生产写者启用门保持。
- 主会话仅新增此审查报告和仓库外持久审计记录；三件套保持 revision 1，task/manifest 状态不变，不 start、commit、push。
- 审计工具仅将 reviewer/critical_reviewer 标为 independent_review；本轮按用户指定采用全新 architect，工具的独立实现复核计数为0，不影响本轮架构审查的上下文隔离事实。审计“验收通过”仅表示本次审查交付被主会话接受，不表示规划或实现获批。

## revision 2 处理记录（2026-10-22）

用户已确认上述两项 P2，并授权仅将规划修订至 revision 2。旧审查结论和已关闭审计 Bundle 保留，不以修订稿替换历史证据。

| 问题 | revision 2 的规划处理 | 验收映射 | 当前状态 |
|---|---|---|---|
| P2-1 初始计划安装幂等性 | design 3.1.1 固化完整根集合安装、锁内重核、已有ID不可覆盖、file残缺检测；implement B先实现并接全部入口。 | PRD R3/AC12：双初始化barrier、预算/结果身份不变、数据库rollback与file部分安装中断。 | 已在规划层处理，待人工审核/独立复审/实现验证。 |
| P2-2 终态失败窗口 | design 3/3.2以持久化停止结论约束enqueue/claim；同代拒绝走幂等finalizer，普通竞争/旧代另行处理。 | PRD R1/AC13：terminal CAS后中断，重放终态自身/兄弟，零新增调用、完整失败收口、重复事件防止及换代对照。 | 已在规划层处理，待人工审核/独立复审/实现验证。 |

本轮未派发新的审查子代理，没有业务实现或新业务测试证据。任务仍planning，revision 2三件套和最小context待人工评审；不start、提交或push。
