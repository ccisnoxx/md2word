# TR-406 执行计划

> 修订 2，2026-10-22。用户已接受本修订并授权先整合 CON-102、再实施验证；独立复审见 planning-rereview.md。任务已激活；勾选项和实施报告记录实际执行结果，历史规划基线仍见 planning-validation.md。完成后停人工验收，不提交或 push。

## 1. 实施前门禁与顺序

1. [x] 重新执行 pwd/status，保存原有 1428 个路径哈希和未提交差异；读取本任务三件套与 context。记录用户接受与实施授权，仅将 TR-406 激活为 in_progress，不推进其他任务状态。
2. [x] 在工作树整合已验收 CON-102（52810b6/4d30682）与 TR-403（f46a3bc）合同；阶段/receipt 39 项、相关 API 4 项与完整性/模式/翻译 38 项通过，保留编码/evidence/脱敏/唯一物理路径及 stage/原子 retry/receipt。见 dependency-integration.md，未产生提交。
3. [x] 按用户追加授权整合 CON-103/104 已验收实现及 CON-103 原有 schema bootstrap；48 项定向合同与84项相关回归通过，复用质量/available actions owner，无 TR-406 额外 DDL、无生产连接。TR-404/405 未在本工作区实施，本轮共享文件由已明确分工的 TR-406 workers 拥有；宽回归更新前失败选择器记录在 dependency-con103104-integration.md，候选稳定后定向确认。
4. [x] 固定验收基线测试选择器及样本路径，执行已有窄基线；精确入口与真实结果见 research/verification-navigation.md、quality-validation.md 和 sample-validation.md。按已取得的实施授权，先激活本子任务再整合依赖，避免在 planning 状态改业务；实施分支 codex/tr-406-partial-batch-failure-semantics，不修改其他任务分支/状态。

## 2. 有序实现清单

### A. 合同与最小状态归属（AC1–3/7–9/12–13）

- [x] 在 workflow.py 实现共用的 typed generation reducer：对照权威确定性 plans 核根/子树完整性、有效叶子、剩余 attempt/预算、终态优先、全部成功/零单元边界；execution/service 和 enqueue/claim 停止闸门不各自复制规则。
- [x] 明确 API execution 摘要与逐行 disposition，采用 design 第 5 节字段，复用原 status/stage，不新增执行状态或数据库字段。
- [x] 终态错误归 translating；fan-in 错误归 translation_validating；保留 CON-102 I/O 与 TR-403 专码，普通事件采用固定中文安全文本。

### B. 仓储、根计划与 attempt（AC3–5/11–13）

- [x] 先实现本代完整根计划安装/核验的窄端口：锁外算权威 plans，锁内重核 job/generation/现有根；完整既存计划只返回权威现态，create 禁止 upsert 重置 status/attempt/lease/result。sqlite/MySQL 同事务安装完整集合或回滚，file 部分根中断按计划检测并失败关闭，不补缺根，不新增持久标记或事务日志（AC12）。
- [x] 把初始化、重放/恢复及批次消息入口接到完整根计划核验；安装完成前不得 enqueue/claim。覆盖 B 判空暂停、A 已成功/运行、B 恢复的真实 barrier 交错，以及 file 部分写和数据库 rollback；不能只验证单条 create 加锁。
- [x] 扩展现有批次条件写端口，核对预期 attempt/lease 和父 job 当前代；新增必要的原子领取与一致快照能力。enqueue/claim 在同一锁/事务确认完整根集合且当前代无停止结论，再核状态、attempt、预算后递增，写唯一 lease_owner。
- [x] file/sqlite/MySQL 均复用 CON-102 同 job 序列化点，锁顺序 job→batch；覆盖 enqueue/claim/success/failure/split/lease 回收及所有实际调用的更新入口，不留下绕写路径。不在锁内调用 Provider、对象存储或写外部审计。
- [x] split 写入置于同 job 锁/事务；file 中断的残缺树在恢复时失败关闭，不引入多文件事务框架。保存冲突与真实存储异常的不同含义。
- [x] 审查失败/取消/旧代与 claim/完成的交错，确保旧 operation 不能污染本代；已有 CON-102 原子用户 retry/receipt 不重写。

### C. 编排、partial 与恢复（AC1–8/13）

- [x] finalizer 在活动叶子之前处理终态失败；本次立即推进 job failed 并停止新领取。既有在途请求只保留真实调用审计，当前代已失败时禁止结果晋升。
- [x] 以已持久化 terminal/tree-invalid 为 enqueue/claim/结果晋升的停止依据，不只检查 job.failed；同代停止闸门拒绝后释放锁并调用幂等 finalizer。终态批次自身重放和排队兄弟均须触发收口；普通竞争不误判失败，旧 generation 不修改新代（AC13）。
- [x] 在 terminal batch CAS 后、job 更新前故障注入，分别重放终态自身和排队兄弟，断言零新 Provider/完整失败收口，再次重放零重复终态事件；增加竞争换代对照，不依赖额外主任务 replay。
- [x] 全部成功才 translation_validating/fan-in/apply；保留完整性重核、逐项覆盖、一次 apply、唯一主件。残缺树/全 split/非法 canceled 叶子不能卡住或冒充零单元。
- [x] 自动重试仅同代失败叶子；终态 failed 重复投递零调用；预算耗尽不可新领取，已领取合法结果可完成。
- [x] 用户 retry 翻译失败由既有原子端口换代，从已验证不可变 source 重建本代全部批次，默认原快照；不复用旧译文，不改 rendering/uploading 失败的已有恢复策略。
- [x] partial 不注册目标 IR/主 DOCX，不增下载入口；只沿原安全 debug 路径留全文。证明 source 下载不会被误标为目标文档，普通 batch file_id 不能绕过 allowlist。
- [x] 只在成功条件状态变更后记录终态事件；payload 带本代/本 attempt 和安全原因，不因重放重复记终态，不输出 Provider 原异常正文。

### D. API 和 UI（AC8–10）

- [x] GET translation-batches 使用同一授权快照生成 execution/leaf/disposition；direct execution=null，旧字段兼容，未知旧记录可读。
- [x] 更新 schemas/router、前端 types/utils/JobDetailPage；明确“自动重试中”“最终失败，无可交付 Word”“其他批次停止”。有效叶子进度与历史 split 父项分开；发布/下载/retry 动作只消费后端。
- [x] 防旧代、旧 job、旧请求的异步响应覆盖当前页面；响应与 job generation 不一致时不显示为当前结论。
- [x] 生成并校验 OpenAPI，不手改 JSON，不借 UI 修改权限或失败语义。

## 3. 计划修改文件及条件边界

| 文件 | 计划用途 |
|---|---|
| app/domains/document_jobs/{workflow,repository,execution}.py | 唯一 reducer、根计划一次性安装/核验、窄原子端口/快照、enqueue/claim停止闸门及同代重放收口、attempt条件、split/预算/恢复。 |
| app/domains/document_jobs/{models,service,schemas,router}.py | 复用模型字段及中文合同说明、翻译失败 retry/source 校验、权威 DTO/权限投影；models 不新增持久字段。 |
| app/infrastructure/persistence/{file,sqlite,mysql}/document_jobs.py | 根计划完整安装与已有ID不可覆盖、同job锁/事务、带停止闸门的原子领取/提交、一致快照；不改schema。 |
| frontend/src/api/types.ts | additive DTO。 |
| frontend/src/utils/translationBatches.ts 与 .test.ts | 使用权威结论/有效叶子，展示语义及兼容。 |
| frontend/src/pages/JobDetailPage.vue | 提示/失败原因、available actions、异步 generation 保护。 |
| tests/test_translation_batch_failure_semantics.py（计划新增） | 主任务/真实 adapter/fake Provider 失败矩阵与竞态回归。 |
| tests/test_translation_integrity_execution.py | 现有完整性、迟到 generation/字节回归，必要时增 attempt 交错。 |
| tests/test_fastapi_jobs_backend.py、tests/test_database_job_repository.py | API/权限/下载/序列化/事务合同；以整合后现有测试为基础增量。 |
| tests/test_document_job_execution_stages.py（CON-102 基线已有） | translating/fan-in/receipt 和失败阶段恢复，不在当前缺文件时另建第二份。 |
| frontend/src/api/documentJobs.test.ts、frontend/tests/smoke/core-flow.spec.ts | DTO/失败提示/权威动作/旧响应 UI 定向测试；不重做页面布局。 |
| docs/api/document-jobs.md、docs/api/openapi.json | API 说明和生成快照。 |
| docs/design/translation-design.md、docs/architecture/workflows-and-state-machines.md | 终态规则、同代自动 retry 与跨代用户 retry、debug 边界。 |
| .trellis/spec/backend/{translation-integrity-validator,database-guidelines,error-handling}.md | 新批次生命周期/条件写/错误合同，纠正旧 ir_converting 失败说明；必要时以短专文链接，避免复制整个设计。 |

`app/domains/translation/**` 的同步全部成功才 apply、Codec/Validator/Provider/audit 已有能力优先不改。只有整合或真实测试证明调用方必须传递安全 attempt 关联时才局部调整 audit；不得借此实施 TR-404/405。files 服务唯一物理身份已存在，优先测试，不再改 key；除用户追加授权整合的 CON-103 原有 schema bootstrap 外，TR-406 对 DB schema、配置、队列适配器和本地转换脚本没有额外增量；新的必要变更仍须先更新设计/范围后评审。

## 4. 定向测试矩阵

| 场景 | 必须断言 / 对应 AC |
|---|---|
| 两根/拆分后一个成功、一个终败，另有 active | 真实 finalizer 导致 failed/translating/translation_failed；apply=0，目标 IR/主 DOCX=0；队列后续零新调用（AC1）。 |
| retry 成功、split 两子成功 | 只重试失败叶子，父项不算失败，不重复成功兄弟；最终内容完整、技术 Token/表格 DOM 不变（AC2/7）。 |
| 预算最后一个名额、attempt 上限、单 item 截断、过期 lease | 定向 barrier 交错，不能超领；确定终态原因；重复消息零额外 Provider（AC3/4）。 |
| 两个 attempt 交错、双领取、旧 lease 回收、取消/失败/retry 后回流 | 真实 file/sqlite 事务/锁下当前尝试获胜；旧成功/失败/split 不能覆盖；真实读取 winner/历史字节与 checksum（AC4/5）。 |
| 双初始化：B 判空暂停，A 安装且一根成功/一根运行，B 恢复 | 已有status/attempt/lease/result/全代预算账本逐项不变，成功兄弟零重调；sqlite/MySQL完整根集合原子提交或回滚，不能用逐条加锁代替（AC12）。 |
| file 初始根集合只写一部分后中断；随后重放初始化/消费 | 以不可变source/config重算expected plans识别缺根，明确translation_batch_tree_invalid，主任务失败；不补根、不消费部分计划，零Provider/回填/主件（AC12）。 |
| terminal batch CAS后、job.failed前中断；终态自身与排队兄弟分别重放 | 同代快照停止闸门先拒绝enqueue/claim，再幂等finalizer；零新增Provider、job失败、重复重放零重复终态事件；普通claim竞争与旧代消息对照不误伤当前代（AC13）。 |
| split 中间写/进程中断、孤立/重复孩子、全 split、无 items | 完整树才成功；残缺恢复明确失败不无尽 running；只有经抽取证明零项才空计划成功（AC7/11）。 |
| 翻译失败用户 retry、授权术语重选、并发双 retry | generation/retry_count/job_retry_count 一致；source ID/字节不变；新证据绑定新代；旧译文不重新包装；沿原权限拒绝（AC5）。 |
| 默认/授权 debug、显式 partial file_id、源 IR/QA latest 候选 | 默认无失败正文 Artifact，受控 debug TTL/审计不变；batch partial 不可当主件下载或审核发布；无正文泄漏（AC6/8）。 |
| API/UI 当前代、旧响应和 split 最终成功 | 权威 summary、明确失败/停止原因、旧代响应不覆盖、available_actions 生效；不自行推导发布（AC8/9）。 |
| direct、完整 blocked/unreviewed、receipt 与 published | direct 零翻译加载/调用；有效 HTML 仍 Word Table；完整草稿内部下载允许且批准/发布拒绝；唯一主件/不可变（AC10）。 |
| MySQL 与 sqlite/file 合同 | 同连接事务、锁顺序、预算原子核对、JSON 往返及回滚；fake 只证明 SQL/合同，真实 MySQL/部署 FS 另保留启用门（AC11）。 |

按真实正式 converter 读取公开最小 OPA228 MinerU fixture：`tests/fixtures/component_pdf_samples/samples/texas-instruments/op-amp/ti-opamp-opa228-p1-smoke/mineru/component_content_list_v2.json`，用 fake Provider 控制失败。该样本不能代表所有表格风险，另用合成含表格/单位/多 item 的 MinerU ZIP 走真实 converter→batch→fan-in→renderer；成功对照断言 w:tbl、合并/结构、目标文本，失败对照断言无主件。不得以有 Provider 调用即成功代替验收。

## 5. 验证命令与回归门禁

下列为执行计划入口；实际执行的命令、选择器、通过数量和已确认的原始基线失败见 quality-validation.md，不将计划入口视为已通过：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_failure_semantics
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_integrity_execution tests.test_document_ir_translation tests.test_generated_artifact_identity tests.test_document_job_modes
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_execution_stages tests.test_database_job_repository tests.test_openapi_export
.venv/bin/python scripts/ops/export_openapi.py
.venv/bin/python scripts/ops/export_openapi.py --check
.venv/bin/python scripts/ops/check_release.py
```

FastAPI 巨型模块只选本任务/既有失败、split、retry、权限、下载和已接受 blocked/unreviewed/publication 相关用例；实施基线核实完整类名/选择器后记录，不盲跑全模块。新增测试写完并将原探针固化后再集中验证，失败先诊断再重跑。

前端先 `npm run test:unit -- src/utils/translationBatches.test.ts src/api/documentJobs.test.ts`（工作目录 frontend），随后项目要求的 `npm run test:unit`、`npm run build`；对 core-flow.spec.ts 新增带“翻译批次”名称的 mock API smoke，运行 `npm run test:smoke -- tests/smoke/core-flow.spec.ts --grep '翻译批次' --workers=1`。浏览器证据覆盖自动 retry、终败、split 成功、旧响应、两角色、主要 viewport 与键盘；实际 mock smoke 已运行，角色、viewport、键盘及截图证据见 frontend-validation.md。

复用已安装样本门禁：component regression、direct phase2-core matrix；先核 `--help` 和 SAMPLE_SETS，再采用实际可用筛选。当前没有 translation-core，不能写成已运行；四方向正式样本建设属于 TR-407。本任务以四种 mode 的 fake 状态负例和公开/合成样本证明编排合同，不新增真实 Provider 测试。

业务候选稳定后必须 Trellis check，并针对三 adapter 原子性、跨代回流、partial 下载和主件不可变做独立只读风险复核。真实 MySQL/InnoDB 并发/rollback/断连及部署 FS 跨进程锁是上线写者启用门；本地/fake 不代替线上证据。没有本次部署授权时记录 pending，不擅自连接 VPS、开生产写者或运行真实外调。线上 Golden/Word 人工证据与本地 fake 分列。

## 6. 文档、回滚点与完成定义

- [x] 更新本任务验收映射、目标翻译设计/API/状态机/相关 Spec；实施总结和最终复审已冻结；代码注释、docstring、日志/错误和触及文档按中文规则检查，不翻译机器字段或测试合同字面量。
- [x] 检查精确 diff/status，不混入现存 backlog、manifest 其他任务、父任务既存更改或并行候选；context 路径可解析，task.py validate 通过。
- [x] 回滚点 A：实现前已固定 HEAD、index、dirty 文件和兼容基线；保留工作树候选，本轮未执行业务回滚。
- [ ] 回滚点 B（部署门，未执行）：部署前暂停翻译并排空旧 Worker；若新 attempt 合同不兼容，维持暂停，不让旧写者接管新活跃代。本轮未获部署授权。
- [ ] 回滚点 C（部署门，未执行）：已生成证据/receipt/审计/发布件不删不覆；不执行 DDL down/backfill 回滚。只回到仍执行 generation/attempt/完整性门的兼容版本，不能恢复无验证回填。CON-103 已验收 bootstrap 的整合已另获授权，本轮没有生产执行。
- [x] PRD AC1–13 均有本地证据，尤其 AC12 双初始化/部分安装和 AC13 终态窗口两类重放；定向/回归/前端/OpenAPI通过，未验线上项和风险明确，三件套/Spec current；实现与独立复审完成，停用户人工验收；提交计划待后续明确要求，不自行提交、push、归档或启动其他任务。

本轮实施的完成定义：revision 2 已接受，CON-102/103/104 已验收依赖按授权整合；AC1–13 的本地候选、验证、独立复审和验收映射可审查。历史规划的37项基线不冒充本轮结果；TR-406 保持 in_progress，最终检查通过后停人工验收，不提交、push、归档或运行会话 bookkeeping。真实环境与人工门分列保留。

最终交付：implementation-summary.md、acceptance-evidence.md、quality-validation.md、implementation-review-final.md。核心/兼容126项通过，前端152项及build/smoke通过；2项已复现的旧数据库callback失败与真实环境门明确分列。原332个非任务dirty文件、原index和6项既存删除保护检查通过。
