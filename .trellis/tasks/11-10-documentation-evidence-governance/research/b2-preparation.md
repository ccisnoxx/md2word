# B2 只读准备与用途核对

日期：2026-11-10。21 份 B2 全文与 backlog 45 项原始 AC 已阅读；本记录先形成于只读准备阶段。主会话随后明确 B1 独立复核通过，允许按原 design revision 1 开始 B2。

本批不运行应用测试、构建、发布聚合器或生产验证；未检查全机会话。Git 历史只读取相关提交、路径、任务和验收对象，不把历史报告的 passed 当成本轮实跑。

## 21 份资料的用途判断

| 相对路径 | 建议生命周期 | 保留的原字段 | 正文核对范围 | 实施前 SHA-256 |
|---|---|---|---|---|
| `docs/architecture/business-architecture.md` | active | doc_type=business-architecture, status=target, last_reviewed=2026-10-03 | 业务能力、角色和价值流是目标边界；不能把能力地图当作现有全链实现。 | `615e5fab8070ae88e5c2ea5de235b8301aeed5b6a0589b8d35904fec0a5a358c` |
| `docs/architecture/domain-model.md` | active | doc_type=domain-model, status=target, last_reviewed=2026-10-03 | 聚合、不变量和模型为目标合同；示例字段与实际模型不逐项等同。 | `a988ea1e062e612bf00dfee7f93792b5a92dcd47c0d3a66042d0d0775f2c963e` |
| `docs/architecture/system-architecture.md` | active | doc_type=system-architecture, status=target-with-current-baseline, baseline_commit=e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8, last_reviewed=2026-10-03 | 目标模块边界与历史当前拓扑混排；保留 e51e6ccd 与 2026-11-06 局部复核，不给全篇换新基线。 | `55197878ae79849b183169773d088e05d52eef01fd2d938040ea30ae85e086cf` |
| `docs/architecture/technology-stack.md` | active | doc_type=technology-stack, status=current-and-target, last_reviewed=2026-10-03 | 技术约束仍维护；表内旧版本说明不证明当前安装版本，实际依赖入口是 requirements/锁与 frontend package 文件。 | `50eb3aca562b356abb44bd3d5a004c7f2d6cc0e732badbaf6c380b9299b5e2b1` |
| `docs/architecture/workflows-and-state-machines.md` | active | doc_type=workflow-spec, status=target, last_reviewed=2026-10-03 | 执行/质量/复核/交付目标状态机与已有 TR-406 合同；不据文本宣布环境门已过。 | `3b334b856c26104e44c58ac0a38efb27a15272e7cd3d61417c534c6ce064def1` |
| `docs/contracts/document-ir-contract.md` | active | doc_type=data-contract, status=target-compatible-extension, last_reviewed=2026-10-03 | v2 兼容扩展合同；保留当前结构示例与 IR-204 回执专项语义，具体当前实现另见对账。 | `eb2018c1115934055af49de1b7f09ca4c446405b2c053a6295cb5433fee230b7` |
| `docs/contracts/mineru-artifact-contract.md` | active | doc_type=data-contract, status=target, last_reviewed=2026-10-03 | 输入、资源、路径与规范化的目标边界，不是所有生产输入已验证的报告。 | `0cd875f26ff1a6c70e375a6fd3845a8e385ef87839788dc388979d9485a3c20b` |
| `docs/decisions/architecture-decisions.md` | active | doc_type=architecture-decision-index, status=accepted, last_reviewed=2026-10-03 | ADR-001 至 ADR-016 为已接受决策；accepted 不表示其所有目标能力已交付。 | `4943945bad2e7ff863b6c2876076295f727df769575080bdf3b4e59430b94a65` |
| `docs/design/docx-rendering-template-design.md` | active | doc_type=technical-design, status=target, last_reviewed=2026-10-03 | 目标渲染设计及已写入的 RND-502/503 合同；保留细节，Word/部署预览未验边界不能丢。 | `59219e54d620823a76f65d2de47a258099bfca05ba810607afb81f47576a5076` |
| `docs/design/quality-review-release-design.md` | active | doc_type=technical-design, status=target, last_reviewed=2026-10-03 | 质量、统一复核、三栏和发布的目标设计；后端局部存在不等于全部前端/端到端完成。 | `c24d15b40c854c140b0d07c170f54bd56ea10b47fa04a1268305f58e09dee4a1` |
| `docs/design/table-processing-design.md` | active | doc_type=technical-design, status=target, last_reviewed=2026-10-03 | 目标表格设计；第2节当前基线/主要差距是历史调查，不凭旧行号重复实现当前已有 grid。 | `58e9affde65acb831f2baae92828761bdfc37fe4006d1f66d0edacde333e79f8` |
| `docs/design/translation-design.md` | active | doc_type=technical-design, status=target, last_reviewed=2026-10-21 | 翻译目标与 TR-402/403/406 局部合同；其他任务需区分历史接受与当前集成，不能用历史功能提交代替当前调用核对。 | `98277216808ca4c2e88172ab69d0df8e9627638d17619e68f39848a7090356e1` |
| `docs/engineering/security-observability-operations.md` | active | doc_type=non-functional-design, status=target, last_reviewed=2026-10-03 | 安全、运维、指标和部署目标要求；不声明本批完成权限或线上安全验收。 | `b1c80ba109fb35bdf8d10c24d694065852ca6b14aeb36feff9e171df5c240649` |
| `docs/engineering/testing-acceptance-strategy.md` | active | doc_type=testing-strategy, status=target, last_reviewed=2026-10-03 | 分层验收策略和目标样本方案；不是本次检查清单，translation-core 等建议命令须先核实实际支持。 | `caf99ecab2b997b11c53701f8c054fc77545c3b038afbeb3b21ee275e4154de7` |
| `docs/implementation/baseline-verification-2026-10-12.md` | historical | doc_type=baseline-verification, status=accepted, baseline_commit=fcea60ff8c131edff7fd5ba360e1bf4e37ec4227 | 2026-10-12 BAS-001 已接受历史报告，绑定 fcea60ff 基线；运行命令/结果/哈希保持。 | `47af9edc0598b5535f107b7e22290efc8a2c5e3045036887f02245994a8e2d47` |
| `docs/implementation/codex-execution-guide.md` | active | doc_type=ai-development-guide, status=executable, last_reviewed=2026-10-03 | 复杂任务执行指引与模板；按当前 AGENTS/实际任务选择必要检查，不自动扩成全仓测试或提交授权。 | `19c667bb69add23f9deac54b2b009f7ba7345466a17eab9c3151adc4225bdc7a` |
| `docs/implementation/codex-task-backlog.md` | active | doc_type=executable-backlog, status=ready-for-task-creation, last_reviewed=2026-10-03 | 45项原始目标/AC与依赖定义；执行状态仍只由 Manifest记录，文档迁移不改 AC。 | `da1cc364e4fe566cb86689d661ea3061905a563abbcc5c271600c120a24278bf` |
| `docs/implementation/implementation-plan.md` | active | doc_type=implementation-plan, status=executable, last_reviewed=2026-10-03 | 七阶段目标、出口和回滚建议；不把建议flag当作已安装配置，不自动触发阶段门禁。 | `71b80babbb8a2fb7c9505ae1d946fca8d52c507f4aa72354be6cdfcc07e4e4a0` |
| `docs/implementation/rollout-and-migration.md` | active | doc_type=rollout-plan, status=target, last_reviewed=2026-10-03 | 迁移与启用目标及 CON-103 专项文字；建议flag不证明存在或启用，实际迁移需对应任务/部署证据。 | `8409d5af09eab1b76a6b0fcd64c2ed5e369937a6a436433c1f13abc67d29be91` |
| `docs/product/prd.md` | active | doc_type=product-requirements, status=scope-frozen, baseline_commit=e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8, last_reviewed=2026-10-03 | 冻结产品需求与验收边界；FR列表描述目标，不声明所有功能已上线。 | `76448a78bf4df68583ea00b900cf62f0b8e1e4a6e433d9439767313322fb8e39` |
| `docs/product/scope-and-decisions.md` | active | doc_type=product-decision-record, status=scope-frozen, last_reviewed=2026-10-03 | 冻结范围与 PD-001 至 PD-020 决策；维护其约束，不扩展产品范围。 | `818c564ee37712acfa92694e35aaa97dfe3b5c56ce233441671439d4ca6aae92` |

21 份文档均无已确认的维护责任人，owner 保持 null。目标用途核对不等于全篇实现认证，拟将 last_verified_commit 全部保留 null；verification_scope 逐份写明目标/历史性质和本任务相对证据。

## 对账中必须区分的事实

- 当前源码已有阶段、状态、表格网格、逻辑组、参考图、原生 table 计划、预览、页映射、复核和后端发布入口；只据存在无法满足整项 AC。B1 已核验的不变入口复用其内容身份。
- 当前 checkout 不含多数精确任务目录，但相关 Git 对象中能读取任务及验收记录。原业务提交不在 HEAD 祖先链上，也不能单独证明功能未集成；需分别比较当前文件和历史对象。
- 具体集成差异线索：历史 IR-202 的 margin_artifact_normalizer.py、TR-405 的 post_validation.py、TAB-308 的 table_regression_gate.py、TR-407 的四方向夹具、QA-603 的 DocumentReviewPage.vue 在当前路径不存在；配合当前调用路径对账，不能从目录缺失推定全部功能未实现。
- 当前翻译显式抽取只调用 text/list/html，回填也只分这三类字段；历史 TR-401 已接受声明与当前 annotation 覆盖需要重新对齐。当前表格 context 是 B06 默认关闭的输入专用上下文，不自动等于原 TR-404 全目标。
- 当前 JobPublicationPanel 只有发布资格/禁用原因展示，无点击处理；下载动作会生成并打开链接后显示 warning。历史 QA-604/606 的接受与当前界面集成需分开。
- BAS-001 的旧缺口、测试次数、机器和版本均保留原报告范围；不能将它的未实现结论直接套到本次源码。

## 后续记录

45 项对账写入本任务 `research/manifest-reconciliation.md`，每行给原 AC 锚点、当前入口、历史记录与具体未决项。B2 实施结果和候选内容身份写入 `research/b2-implementation.md`；不改任何产品执行状态。
