---
doc_type: executable-backlog
status: ready-for-task-creation
last_reviewed: 2026-10-03
---

# Codex 可执行任务清单

## 1. 使用规则

- 每一项原则上对应一个 Trellis 子任务；
- API、DB、状态、跨模块任务必须有 `prd.md + design.md + implement.md`；
- 开始前先搜索当前实现，若已完成则转为验证/收口任务；
- 不跨任务顺手实现下一项；
- `Depends on` 未完成时不得提前合并依赖功能；
- 任务完成必须更新本清单状态或对应项目任务系统。

执行状态统一记录在 [任务 Manifest](codex-task-manifest.yaml)，本文件维护任务定义与依赖，不维护第二套状态。状态值为：

```text
todo | planning | in_progress | review | blocked | done | skipped_existing
```

实现与本地验证完成后只标记 `review`；人工验收后才能标记 `done` 或 `skipped_existing`。人工验收前 Trellis 子任务保持 `in_progress`，不 archive。

## 2. 总任务图

| ID | 任务 | Depends on | 主要模块 |
|---|---|---|---|
| DOC-001 | 合入文档包和索引 | - | docs/README |
| BAS-001 | 当前能力与测试基线核验 | DOC-001 | tests/scripts/docs |
| CON-101 | 产品模式和 UI 文案收口 | BAS-001 | translation modes/frontend |
| CON-102 | 执行阶段扩展 | BAS-001 | document_jobs |
| CON-103 | 质量/复核/交付状态模型 | CON-102 | models/repository/schema |
| CON-104 | 下载和发布可用性合同 | CON-103 | service/router/frontend |
| IR-201 | MinerUArtifactValidator | BAS-001 | document_ir |
| IR-202 | MarginArtifactNormalizer | IR-201 | document_ir |
| IR-203 | CrossPageParagraphMerger | IR-201 | document_ir |
| IR-204 | CaptionReconciler 增强 | IR-201 | document_ir |
| IR-205 | LogicalTableGroup 与 source spans | IR-201 | document_ir |
| IR-206 | Table Reference Asset | IR-205 | document_ir/files |
| IR-207 | ZK7044 最小回归样本 | IR-201 | fixtures/scripts |
| TAB-301 | CanonicalTableGrid 模型 | IR-205 | services/tables |
| TAB-302 | HTML Normalizer/Grid Builder | TAB-301 | services/tables |
| TAB-303 | Table Validator/Quality Flags | TAB-302 | tables/quality |
| TAB-304 | 大表保留合并关系 | TAB-302 | renderer |
| TAB-305 | 跨页逻辑表 Word 渲染 | TAB-304,IR-205 | renderer |
| TAB-306 | 空 HTML 内部占位和 blocked | TAB-303,CON-103 | renderer/quality |
| TAB-307 | 表格 evidence 聚合 | TAB-303,TAB-304 | quality |
| TAB-308 | 表格专项回归门禁 | TAB-304..307,IR-207 | tests/scripts |
| TR-401 | caption/footnote 翻译覆盖 | IR-204 | translation |
| TR-402 | ProtectedTokenCodec | BAS-001 | translation |
| TR-403 | TranslationIntegrityValidator | TR-402 | translation |
| TR-404 | TableContextBuilder | TAB-301 | translation/tables |
| TR-405 | 术语和目标语言后验检查 | TR-403 | translation/quality |
| TR-406 | 部分批次失败语义收口 | TR-403,CON-102 | translation/document_jobs |
| TR-407 | 四语言方向样本和门禁 | TR-401..406 | fixtures/scripts |
| RND-501 | RenderPlan 与 block evidence | IR-205,TAB-301 | renderer |
| RND-502 | 公式 OMML 和降级规则 | BAS-001 | renderer |
| RND-503 | 图片并排/caption 规则 | IR-204 | renderer |
| RND-504 | WordPreviewProvider | CON-103 | renderer/infra/files |
| RND-505 | PDF/IR/Word 页映射 | RND-501,RND-504 | quality/review |
| RND-506 | 页级 DOCX 质量检查 | RND-504,RND-505 | quality |
| QA-601 | translation QA 迁移为统一 review | CON-103 | document_jobs/frontend |
| QA-602 | Quality/Review API | QA-601,TAB-307,RND-506 | router/service |
| QA-603 | 三栏审核页面 | QA-602,RND-505 | frontend |
| QA-604 | 未复核/blocked 下载提示 | CON-104,QA-602 | frontend/API |
| QA-605 | PublicationRecord 和发布门禁 | QA-601,RND-504 | backend/db |
| QA-606 | 发布 UI 与审计 | QA-605 | frontend/audit |
| QA-607 | 审核发布 E2E | QA-603..606 | Playwright/API tests |
| REL-701 | Release check 和 Acceptance gate | TAB-308,TR-407,QA-607 | scripts/acceptance |
| REL-702 | 指标、告警和容量 | REL-701 | health/ops |
| REL-703 | 迁移和灰度启用 | REL-701 | deploy/migrations |
| REL-704 | Runbook、OpenAPI、最终签字 | REL-703 | docs/testing/deploy |

---

# 阶段 0：文档与基线

## DOC-001 合入文档包和索引

**目标**：将本包置入仓库，不覆盖已有事实文档。

**改动**：

- 新增 `docs/product|architecture|contracts|design|engineering|implementation|decisions`；
- 更新根 README 的文档索引；
- 标注 PRD 和实施计划权威性。

**验收**：

- 所有相对链接有效；
- 不删除现有 `docs/api|dev|testing|runbooks|deploy`；
- `git diff --check` 通过。

## BAS-001 当前能力与测试基线核验

**目标**：把 gap analysis 中“不确定”项变成事实。

**调查**：

- preview 是否已有；
- document publication 是否已有；
- caption/footnote 是否进入翻译；
- 跨页段落是否已有；
- 表格 reference asset 的现状；
- DB migration 机制。

**产物**：

- `docs/implementation/baseline-verification-<date>.md`；
- 当前测试命令和结果；
- 对 backlog 的 `SKIPPED_EXISTING` 或范围调整建议。

**验收**：不修改业务行为。

---

# 阶段 1：合同和状态

## CON-101 产品模式和 UI 文案收口

**目标**：产品层只显示“原文 PDF 转可编辑 Word”和四种翻译方向。

**主要文件**：

- `app/domains/translation/modes.py`
- `frontend/src/utils/format.ts`
- `frontend/src/components/PdfUploadPanel.vue`
- API types/tests/docs

**要求**：

- 保留历史 `zh2zh` alias→direct；
- UI/新文档不出现中译中；
- direct 模式隐藏翻译资源；
- direct 标注不调用 AI。

**验收**：前端 unit + mode backend tests。

## CON-102 执行阶段扩展

**目标**：增加 `translating`、`translation_validating`、`quality_checking`。

**要求**：

- direct 跳过翻译阶段；
- 旧记录/API 可读；
- stage events 正确；
- 失败阶段可定位；
- 前端状态文案同步。

**验证**：状态模型、execution 路径、OpenAPI、前端测试。

## CON-103 质量/复核/交付状态模型

**目标**：在 DocumentJob 中建立独立状态和持久化。

**字段**：

```text
quality_status
review_status
delivery_status
quality_summary
```

**要求**：

- 旧任务默认：quality pending/unavailable、review unreviewed、delivery internal_draft；
- 不从 translation QA 自动批准 direct；
- DB migration 可回滚；
- repository/schema/API 全链路。

## CON-104 下载和发布可用性合同

**目标**：后端权威返回 blocked/unreviewed 下载分类和 publish 禁用原因。

**验收场景**：

- blocked：download true + internal_only + warning；publish false；
- unreviewed：download true + warning；publish false；
- approved non-blocked：publish true（Admin）。

---

# 阶段 2：MinerU 与 IR

## IR-201 MinerUArtifactValidator

**目标**：在 converter 前验证 JSON、页、bbox、路径、HTML 和资产。

**主要文件**：

- `app/services/document_ir/mineru_package.py`
- 新 `artifact_validator.py`
- execution wiring

**要求**：

- 返回结构化 warnings/blockers；
- 包路径安全；
- `images/` 不算有效文件；
- 不做 PDF OCR 预检。

## IR-202 MarginArtifactNormalizer

**目标**：基于跨页重复+位置重新判定运行页眉页脚。

**样本**：ZK7044 型号标题、版本号 paragraph、一次性正文标题。

**要求**：

- 高置信度自动重分类；
- 不确定只标记；
- 不删除原始 source type metadata。

## IR-203 CrossPageParagraphMerger

**目标**：合并明显跨页断句，保留 source spans。

**规则**：结束标点、下一块类型、缩进、页面边界、列表编号。

**样本**：ZK7044 第 29–30、40–41 页。

## IR-204 CaptionReconciler 增强

**目标**：统一 image/chart/table caption 的拆分、编号和相邻对象绑定。

**要求**：

- 只在严格可判定时自动修复；
- 否则 `caption_binding_uncertain`；
- 图 5/6、图 24/25 回归。

## IR-205 LogicalTableGroup 与 source spans

**目标**：把页级 table fragments 表达为逻辑表格。

**产物**：

- `logical_group_id`；
- fragment page/bbox；
- continuation relation；
- repeated header hint。

## IR-206 Table Reference Asset

**目标**：把表格截图登记为 QA image asset，不作为默认渲染对象。

**要求**：

- source path/checksum/file ID；
- block metadata 引用；
- missing reference warning；
- review API 可授权展示。

## IR-207 ZK7044 最小回归样本

**目标**：从上传样本中沉淀非专有或允许使用的最小 MinerU fixture。

**要求**：

- 不提交完整客户/专有资料；
- 按页组最小化；
- manifest 写清风险和预期；
- runner 可离线执行。

---

# 阶段 3：表格

## TAB-301 CanonicalTableGrid 模型

**目标**：定义可序列化表格网格、cell 和 run。

**验收**：

- Pydantic/dataclass 模型；
- ID 稳定；
- raw HTML hash；
- cell span/run/quality；
- JSON roundtrip。

## TAB-302 HTML Normalizer/Grid Builder

**目标**：从 HTML 构建确定性占位网格。

**要求**：

- 不自动改技术内容；
- 处理 sup/sub/br/formula；
- span 冲突不覆盖；
- 保留 raw HTML；
- 单元测试覆盖异常。

## TAB-303 Table Validator/Quality Flags

**目标**：检测空 HTML、列数、span、数字/单位粘连、跨页不一致。

**要求**：

- 只标记不修改；
- blocker/warning 分级配置；
- 任务质量聚合可消费。

## TAB-304 大表保留合并关系

**目标**：替换当前超阈值“展开合并”的默认策略。

**主要文件**：`app/services/renderer/table_renderer.py`

**要求**：

- 使用 gridSpan/vMerge；
- 流式或分段降低内存；
- 大表仍保留 merge；
- 失败时明确失败/blocked，不截图。

## TAB-305 跨页逻辑表 Word 渲染

**目标**：多个 fragment 输出一个 Word Table。

**要求**：

- caption 一次；
- 重复表头；
- 自然分页；
- source fragment evidence；
- 表 10/表 24 回归。

## TAB-306 空 HTML 内部占位和 blocked

**目标**：实现冻结策略。

**行为**：

- 有 reference → 插图占位；
- 无 reference → source PDF+bbox 裁图；
- 明确非编辑；
- quality blocked；
- download enabled；
- publish disabled。

## TAB-307 表格 evidence 聚合

**目标**：生成 table-level report：结构、reference、Word shape、flags 和 source spans。

## TAB-308 表格专项回归门禁

**目标**：把 ZK7044/OPA228 表格加入脚本和 release gate。

**门禁**：HTML 存在→Word Table；大表 merge 保留；空 HTML blocked；blocked 不可发布。

---

# 阶段 4：翻译

## TR-401 Caption/Footnote 翻译覆盖

**目标**：显式抽取和回填 `captions/footnotes`。

**要求**：

- image/chart/table 都覆盖；
- ID 稳定；
- 结构字段不变；
- direct 不执行。

## TR-402 ProtectedTokenCodec

**目标**：编码/解码数字、单位、地址、位字段、信号、型号和公式。

**要求**：

- collision-safe；
- placeholder 唯一；
- roundtrip 100%；
- 不把普通词过度保护；
- 纯函数单测。

## TR-403 TranslationIntegrityValidator

**目标**：Provider 响应在回填前做确定性校验。

**检查**：ID、placeholder、数字、单位、地址、位字段、公式、型号。

**行为**：失败批次不回填，记录机器错误码。

## TR-404 TableContextBuilder

**目标**：为 table cell 提供 section/table/row/column context。

**要求**：

- context 不进入输出；
- 字符预算；
- 短文本优先；
- 基于 CanonicalGrid。

## TR-405 术语和目标语言后验检查

**目标**：mandatory term、forbidden term、目标语言和源语言残留 QA。

## TR-406 部分批次失败语义收口

**目标**：保证任一叶子批次最终失败时，不产生静默混合语言可交付件。

**要求**：

- 主任务失败或 blocked 的明确规则；
- partial artifact 只供 debug；
- generation 一致性；
- 事件和 UI 清晰。

## TR-407 四语言方向样本和门禁

**目标**：分别建立 `en2zh/ru2zh/zh2en/zh2ru` manifest、脚本和人工记录。

---

# 阶段 5：渲染与预览

## RND-501 RenderPlan 与 block evidence

**目标**：输出 section/block 渲染决策和 block→Word evidence。

## RND-502 公式 OMML 和降级规则

**目标**：统一 inline/block/table formula 渲染；无法转换时有明确 flag。

## RND-503 图片并排和 Caption

**目标**：基于 bbox 识别同一行图片组，以无边框布局表格渲染；caption 正确绑定。

## RND-504 WordPreviewProvider

**目标**：实现可替换 DOCX→PDF/页面图 provider。

**要求**：

- 超时和沙箱；
- 结果 Artifact；
- 可重试；
- 不与 DocumentIR 语义耦合。

## RND-505 PDF/IR/Word 页映射

**目标**：支持三栏同步定位。

**要求**：

- source spans；
- block ID；
- Word bookmark/evidence；
- preview page mapping；
- 映射失败可降级到最近页。

## RND-506 页级 DOCX 质量检查

**目标**：基于 preview 检测裁切、溢出、异常空白页、重叠和密度异常。

---

# 阶段 6：审核和发布

## QA-601 统一 Review 模型

**目标**：把 translation QA 兼容迁移成 direct/translation 共用 review。

**要求**：

- append-only ReviewRecord；
- 旧 API/字段兼容；
- result hash 变化失效；
- blocked 不能 approved。

## QA-602 Quality/Review API

**目标**：提供 quality、review、preview 查询和 review 更新。

## QA-603 三栏审核页面

**目标**：PDF、内容证据和 Word preview 同步，只读。

## QA-604 下载状态提示

**目标**：blocked/unreviewed 下载确认和醒目标识；不向 DOCX 强制加水印。

## QA-605 PublicationRecord 和发布门禁

**目标**：不可变发布记录、Admin-only、配置和文件快照。

**要求**：

- DB migration；
- publish 前置；
- 已发布文件不可覆盖；
- 新结果需新任务/generation。

## QA-606 发布 UI 与审计

**目标**：发布原因、前置检查、发布记录列表、最终下载入口。

## QA-607 审核发布 E2E

**场景**：

1. unreviewed translation 可下载不可发布；
2. blocked table 可下载不可批准；
3. approved warning 文档可发布；
4. 新结果使旧批准失效；
5. published 文件不可覆盖。

---

# 阶段 7：发布收口

## REL-701 Release Check 和 Acceptance Gate

扩展：

- schema current；
- preview provider readiness；
- quality/review/publish contract；
- table and translation gates；
- blocked publish negative test。

## REL-702 指标、告警和容量

增加 table/translation/preview/review/publish 指标及告警。

## REL-703 迁移和灰度启用

- migration 顺序；
- feature flags；
- 旧任务 backfill；
- rollback rehearsal；
- API/Worker 兼容窗口。

## REL-704 Runbook、OpenAPI、最终签字

- 更新 API 文档；
- 更新内部门户和后端 runbook；
- 更新 Acceptance Center；
- 线上真实任务验证；
- Admin signoff。

---

# 任务模板

每个 Trellis 子任务的 `implement.md` 至少包含：

```markdown
## Scope
- [ ] 明确修改模块
- [ ] 明确非目标

## Implementation
- [ ] 数据/模型
- [ ] 服务/算法
- [ ] API/前端（如适用）
- [ ] 兼容/迁移

## Tests
- [ ] 单元
- [ ] 集成
- [ ] 样本回归
- [ ] OpenAPI/前端

## Review Gates
- [ ] 不重复实现现有能力
- [ ] 不扩大产品范围
- [ ] blocked/unreviewed 规则未被削弱
- [ ] 文档和 Trellis Spec 更新

## Rollback
- [ ] 回滚点和数据兼容说明
```
