# TR-406：部分批次失败语义收口

> 规划修订 2，2026-10-22。用户已接受本规划并授权实施，状态为 in_progress；独立复审见 `planning-rereview.md`，授权和保护边界见 `implementation-authorization.md`。完成后停人工验收，不提交或 push。
> 阶段 R4（翻译完整性）；父任务 `10-12-datasheet-docx-delivery-quality`；建议分支 `md2word/TR-406`（只记录）。

## 目标与用户结果

任一有效叶子翻译批次最终失败时，任务必须明确失败，不产生静默混合语言的用户主 DOCX。Operator 能区分正在自动重试、已拆分、最终失败和被同代失败停止的批次；Admin 能通过安全事件和已有受控 debug 路径定位原因。

完整译文生成后产生的质量 `blocked` 草稿和翻译 `unreviewed` 草稿，继续允许内部下载，禁止批准或发布。本任务不把这些已有质量状态改成执行失败。

## 背景、真源与依赖

- 需求真源：`docs/product/prd.md` FR-006/015/016、`scope-and-decisions.md` PD-001/003/008/011–014/020；架构 ADR-001/002/003/007/008/010/012/014。
- 任务定义：`docs/implementation/codex-task-backlog.md:407`；目标行为：`docs/design/translation-design.md:252`；完整证据和读取清单见 `research/current-state.md`。
- TR-403=`done/implemented`，归档 `completed`，已人工接受，工作提交 `f46a3bcf148e6abc16a0011b6e7079d7f723130b` 在当前 HEAD 可达。
- CON-102=`done`，归档 `completed`，已人工接受；验收提交 `52810b61adef98ca424cdd8b2b677991dc222cce`、`4d3068260c7fe5b1dab2ef46bfeb83f8963e98dc` 不在当前 HEAD。依赖完成门通过；这不等于当前 checkout 已具备其阶段、原子 retry 和 first-valid-receipt。实施前必须准备兼容基线，本轮不合并。
- 当前 Worker 已整批验证、保存绑定 evidence，全部叶子成功后才 fan-in/apply；失败不会用原文补齐。新生成件已有 file_id 物理隔离。
- 已确认缺口：`execution.py:1546` 先等活动叶子，终态失败被延后；`:1315` 可再次领取不可重试 failed 批次；批次仓储仅按 status/generation 条件更新，同代旧 attempt 可写；split 中断树没有完整收口规则；页面将 retryable/split 统称“需关注”。
- revision 1 调查实测：37 项现有定向测试通过；fake 探针证明终态失败+活动兄弟仍 running、max_attempts=1 可执行 attempt 2、旧 attempt 更新被接受。独立规划审查另确认初始根计划安装幂等性、终态落库到主任务失败之间的消费入口两项 P2，见 `planning-review.md` 与 `research/review-decisions.md`。故存在增量，不建议 `skipped_existing`；本轮未重跑该历史基线。

## 范围与需求

### R1 终态与主任务

- `split` 是被替代的父节点，不是失败叶子，也不参与成功覆盖计数。其有效子树必须无重叠、无缺项地覆盖父项。
- 自动重试发生在同一 generation，只重试失败叶子；attempt、总调用预算和 lease 共同约束。不得因重复投递多调用 Provider。
- 一旦某叶子不可再重试，主任务立即 `failed/failed`，`failed_stage=translating`，顶层 `translation_failed`；无需等兄弟批次结束。队列中已有任务停止消费，正在外调的请求允许结束，但结果不得晋升。
- 已持久化的终态叶子或无效批次树，就是该代停止新工作的依据；即使父 job 尚为 running，后续 enqueue/claim 也必须拒绝新投递/领取。若终态叶子落库后、主任务失败前中断，重放该批次或排队兄弟时均须幂等收口主任务，不依赖另一次主任务 replay，不增加 Provider 调用或重复终态事件。
- fan-in 证据、覆盖或来源不合法在 `translation_validating` 明确失败；全部有效叶子通过才进入回填与原生渲染。空计划可走明确的零单元成功路径，损坏/不完整 split 树不能冒充空计划。
- 沿用既有超时、取消及异常处理；重放不能复活终态任务。

### R2 部分产物与权限

- 部分成功的 `translation_batch_result` 只是内部中间证据；同代最终失败后仅供诊断，不作为目标 IR、主 DOCX、下载结果或发布来源，不增加普通下载入口。
- 失败响应的部分内容不得保存为成功 batch result，不得用源文填补，不得自动转 direct。全文 debug 仅沿既有部署开关、Admin 显式启用、短 TTL、授权和审计路径；不新增全文出口或 ledger Artifact。
- 不为失败批次生成 partial DOCX，也不将 source IR 标成 translated。已完成/已发布历史件和审计不覆盖、不删改。
- 保留 tenant/company/owner/admin、到期、下载签名、路径安全、资源重选权限和后端 available actions；前端显示失败原因不能授予新动作。

### R3 generation 与 attempt

- 初始根计划每代只允许一次有效安装。并发初始化必须在同一权威边界重核 job/generation 和完整根集合；已有确定性 ID 不得被迟到初始化覆盖，不得重置 status、attempt、lease、结果指针或调用预算账本。部分根集合不得开始消费，恢复时明确失败，不静默补齐后当成完整安装。
- 本次消费的每个批次满足 `generation == job_retry_count == job.retry_count`，配置/源 IR 绑定准确；当前 attempt 和唯一 lease 身份决定谁可以提交成功、失败、split 或租约回收。
- 领取必须原子核对可运行状态、剩余 attempt 和全代调用预算并增加 attempt；重复投递、旧 lease、旧 attempt、旧 generation 不可写当前结果。
- 用户通过既有 retry 入口重试翻译失败时，retry_count 原子加一，从权威不可变 source IR 重新建本代批次。旧代成功译文不得通过改 generation 或重包 evidence 复用。
- `translation-design.md` 的“只处理失败批次”收窄为同代自动恢复；跨代用户 retry 不复用旧译文，符合 TR-403 现行 Spec。默认仍使用原配置快照，授权资源重选另按现有规则执行。
- 不在 TR-406 扩大 rendering/uploading 失败的恢复范围；TR-405 尚未实施的 QA 快照重译策略不作为已有能力或本任务交付物。

### R4 安全诊断与 UI

- 后端输出当前 generation 的权威结论、有效叶子计数、失败位置和安全原因；事件区分自动重试、拆分、终态失败及停止。拆分父节点不得使成功后仍显示任务失败。
- UI 消费该结论和 available actions，显示“自动重试中”“翻译失败，未生成可交付 Word”“其他批次已停止”等明确文案；不通过成功数、status=succeeded 或本地公式推导发布资格。
- 普通日志/事件/API 摘要不含原文、译文、Prompt、术语上下文、未经验证的返回 ID、凭据、对象路径或签名 URL。

## 非目标与必须保持的不变量

1. 一次只实现 TR-406；不提前实施 TR-401/404/405/407、QA、预览或发布任务。
2. 保持模块化单体；不引入微服务、Kafka、向量库、第二套转换流水线或队列重写。
3. 一个 DocumentJob 一个用户主 DOCX；其他语言 create/clone 新任务。
4. `direct_pdf_to_word` 零 AI Provider、翻译 Prompt、翻译术语集调用；不自动回退 direct。
5. MinerU 为唯一 PDF 解析入口；不增加 OCR 预检或多解析器路由。
6. HTML 可解析即输出 Word 原生表格；不默认截图替代。
7. 质量 blocked 和翻译 unreviewed 可内部下载，不可批准/发布；前端消费后端权威状态/available actions。
8. 不新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑/修表、批量任务或知识库。
9. 不为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
10. 不用源文填充失败 item 后标成功；旧 generation 不覆盖新 generation。
11. 不增加真实外部 Provider 测试、账号、部署操作或专有样本上传；不扩大存储保留政策治理。

## 验收条件

| ID | 可观察结果 |
|---|---|
| AC1 | 多根批次或拆分子树中任一叶子终态失败，即使兄弟 pending/queued/running，主任务也失败；零 apply、零新目标 IR、零主 DOCX/发布资格。 |
| AC2 | 截断父批次 split、子树全部成功可正常完成；自动重试后成功不误判终态；只调用失败叶子，不重复成功兄弟。 |
| AC3 | attempt 或全代调用预算耗尽、单 item 截断无法继续拆分、租约最终到期均有安全稳定原因；终态 failed 的重复投递为零新调用。 |
| AC4 | 同代旧 attempt 的成功/失败/split/lease 回收、双领取和预算最后名额争用均只有当前合法操作可落库；迟到处理不污染胜出记录、evidence 或字节。 |
| AC5 | 用户 retry 翻译失败原子换代，沿用准确源件和默认配置快照；新批次/evidence 同代，旧结果/旧 worker 不回填或覆盖，双 retry 不重复换代。 |
| AC6 | partial batch 只保留内部诊断身份；普通 files/download/QA/发布路径不能把其当主件；失败正文只在已授权 debug 中保存，并遵守到期和审计。 |
| AC7 | fan-in 缺证据、错来源/attempt/generation/hash、重复/缺失项或残缺 split 树均失败关闭；空单元明确成功；TR-403 专码不被压成 JSON 错误。 |
| AC8 | 事件与批次 API 区分 retrying/terminal/stopped，含正确代次、失败批次/原因、计数与 trace；重放不重复终态事件，不输出敏感正文。 |
| AC9 | UI 展示权威失败/自动重试/拆分结果，旧代异步响应不能覆盖新代；动作仍只来自后端；Operator/Admin 和未知旧字段可读。 |
| AC10 | direct 零翻译调用、一主件、HTML 原生表格、完整 blocked/unreviewed 草稿下载与批准/发布拒绝、已发布件不可变全部保持。 |
| AC11 | file/sqlite/MySQL 端口语义一致；真实 file/sqlite 交错测试通过，fake MySQL SQL/事务合同通过；真实 MySQL/InnoDB 与部署 FS 的写者启用门不得伪称已通过。 |
| AC12 | 同代双初始化：B 判空后暂停，A 安装并使一根成功、另一根运行，再恢复 B；已有 status/attempt/lease/result/预算账本完全不变，成功兄弟不重复调用。数据库完整安装或回滚；file 部分根写入后中断，恢复与批次消费均拒绝残缺集合，零新增 Provider/回填/主件。 |
| AC13 | 在终态叶子 CAS 后、job.failed 前故障中断，分别重放终态批次和排队兄弟：同代 enqueue/claim 拒绝新工作并完成 job failed 收口，零新增 Provider、零重复终态事件；普通 claim 竞争不误判失败，旧 generation 消息不修改新代。 |

## 评审与停止条件

三件套 revision 2 已通过独立架构复审并获用户接受，两项 P2 在规划层闭合，尚须由实现和候选验证提供证据。调查未发现无法消解的产品/冻结 ADR 冲突，fake/adapter 可覆盖范围内实现。实施完成后按 AC1–13 提交证据，停人工验收。

依赖状态退回、冻结合同冲突、必须破坏性迁移/覆盖发布件/删除审计、必须改变冻结任务模式/原生表格/下载发布规则，或必要安全授权缺失且不能用 fake/adapter 完成时停止。用户已授权激活本任务、先整合 CON-102 兼容验收基线，再按计划实施验证；提交、push、归档及生产写者启用仍未授权。
