# md2word Codex 逐任务提示词

本目录为 `docs/implementation/codex-task-backlog.md` 中全部 45 个任务提供可直接复制给 Codex 的独立提示词。

## 使用方式

每个任务文件包含：

1. 分支准备命令；
2. 规划会话提示词；
3. 计划批准后的实施会话提示词；
4. 人工验收后的收尾提示词。

由于仓库 `AGENTS.md` 和 Trellis 工作流要求复杂任务先完成 `prd.md`、`design.md`、`implement.md`，默认一个任务使用两个 Codex 会话：先规划，再实现。轻量文档任务仍可按仓库规则在同一会话内完成，但不要绕过 manifest、依赖和验收门禁。

## 状态约定

`docs/implementation/codex-task-manifest.yaml` 是机器可读的执行状态清单：

```text
todo → planning → in_progress → review → done
                                  ↘ blocked
review → skipped_existing（仅现有能力已完整满足且人工接受时）
```

- 实施会话只能把任务推进到 `review`；
- 人工验收后才能改为 `done` 或 `skipped_existing`；
- Trellis 子任务在人工验收前保持 `in_progress`，不得 archive；
- 每次只允许一个冲突范围的实现任务处于 `in_progress`。

## 父任务

父任务 slug：`datasheet-docx-delivery-quality`。

若尚未创建，请先参考 [`00-parent-task-bootstrap.md`](./00-parent-task-bootstrap.md)。

## 任务索引

| 任务 | 标题 | 阶段 | 依赖 | 建议分支 |
|---|---|---|---|---|
| [DOC-001](./DOC-001.md) | 合入文档包和索引 | R0 | 无 | `md2word/DOC-001` |
| [BAS-001](./BAS-001.md) | 当前能力与测试基线核验 | R0 | DOC-001 | `md2word/BAS-001` |
| [CON-101](./CON-101.md) | 产品模式和 UI 文案收口 | R1 | BAS-001 | `md2word/CON-101` |
| [CON-102](./CON-102.md) | 执行阶段扩展 | R1 | BAS-001 | `md2word/CON-102` |
| [CON-103](./CON-103.md) | 质量/复核/交付状态模型 | R1 | CON-102 | `md2word/CON-103` |
| [CON-104](./CON-104.md) | 下载和发布可用性合同 | R1 | CON-103 | `md2word/CON-104` |
| [IR-201](./IR-201.md) | MinerUArtifactValidator | R2 | BAS-001 | `md2word/IR-201` |
| [IR-202](./IR-202.md) | MarginArtifactNormalizer | R2 | IR-201 | `md2word/IR-202` |
| [IR-203](./IR-203.md) | CrossPageParagraphMerger | R2 | IR-201 | `md2word/IR-203` |
| [IR-204](./IR-204.md) | CaptionReconciler 增强 | R2 | IR-201 | `md2word/IR-204` |
| [IR-205](./IR-205.md) | LogicalTableGroup 与 source spans | R2 | IR-201 | `md2word/IR-205` |
| [IR-206](./IR-206.md) | Table Reference Asset | R2 | IR-205 | `md2word/IR-206` |
| [IR-207](./IR-207.md) | ZK7044 最小回归样本 | R2 | IR-201 | `md2word/IR-207` |
| [TAB-301](./TAB-301.md) | CanonicalTableGrid 模型 | R3 | IR-205 | `md2word/TAB-301` |
| [TAB-302](./TAB-302.md) | HTML Normalizer/Grid Builder | R3 | TAB-301 | `md2word/TAB-302` |
| [TAB-303](./TAB-303.md) | Table Validator/Quality Flags | R3 | TAB-302 | `md2word/TAB-303` |
| [TAB-304](./TAB-304.md) | 大表保留合并关系 | R3 | TAB-302 | `md2word/TAB-304` |
| [TAB-305](./TAB-305.md) | 跨页逻辑表 Word 渲染 | R3 | TAB-304、IR-205 | `md2word/TAB-305` |
| [TAB-306](./TAB-306.md) | 空 HTML 内部占位和 blocked | R3 | TAB-303、CON-103 | `md2word/TAB-306` |
| [TAB-307](./TAB-307.md) | 表格 evidence 聚合 | R3 | TAB-303、TAB-304 | `md2word/TAB-307` |
| [TAB-308](./TAB-308.md) | 表格专项回归门禁 | R3 | TAB-304、TAB-305、TAB-306、TAB-307、IR-207 | `md2word/TAB-308` |
| [TR-401](./TR-401.md) | Caption/Footnote 翻译覆盖 | R4 | IR-204 | `md2word/TR-401` |
| [TR-402](./TR-402.md) | ProtectedTokenCodec | R4 | BAS-001 | `md2word/TR-402` |
| [TR-403](./TR-403.md) | TranslationIntegrityValidator | R4 | TR-402 | `md2word/TR-403` |
| [TR-404](./TR-404.md) | TableContextBuilder | R4 | TAB-301 | `md2word/TR-404` |
| [TR-405](./TR-405.md) | 术语和目标语言后验检查 | R4 | TR-403 | `md2word/TR-405` |
| [TR-406](./TR-406.md) | 部分批次失败语义收口 | R4 | TR-403、CON-102 | `md2word/TR-406` |
| [TR-407](./TR-407.md) | 四语言方向样本和门禁 | R4 | TR-401、TR-402、TR-403、TR-404、TR-405、TR-406 | `md2word/TR-407` |
| [RND-501](./RND-501.md) | RenderPlan 与 block evidence | R5 | IR-205、TAB-301 | `md2word/RND-501` |
| [RND-502](./RND-502.md) | 公式 OMML 和降级规则 | R5 | BAS-001 | `md2word/RND-502` |
| [RND-503](./RND-503.md) | 图片并排和 Caption | R5 | IR-204 | `md2word/RND-503` |
| [RND-504](./RND-504.md) | WordPreviewProvider | R5 | CON-103 | `md2word/RND-504` |
| [RND-505](./RND-505.md) | PDF/IR/Word 页映射 | R5 | RND-501、RND-504 | `md2word/RND-505` |
| [RND-506](./RND-506.md) | 页级 DOCX 质量检查 | R5 | RND-504、RND-505 | `md2word/RND-506` |
| [QA-601](./QA-601.md) | 统一 Review 模型 | R6 | CON-103 | `md2word/QA-601` |
| [QA-602](./QA-602.md) | Quality/Review API | R6 | QA-601、TAB-307、RND-506 | `md2word/QA-602` |
| [QA-603](./QA-603.md) | 三栏审核页面 | R6 | QA-602、RND-505 | `md2word/QA-603` |
| [QA-604](./QA-604.md) | 下载状态提示 | R6 | CON-104、QA-602 | `md2word/QA-604` |
| [QA-605](./QA-605.md) | PublicationRecord 和发布门禁 | R6 | QA-601、RND-504 | `md2word/QA-605` |
| [QA-606](./QA-606.md) | 发布 UI 与审计 | R6 | QA-605 | `md2word/QA-606` |
| [QA-607](./QA-607.md) | 审核发布 E2E | R6 | QA-603、QA-604、QA-605、QA-606 | `md2word/QA-607` |
| [REL-701](./REL-701.md) | Release check 和 Acceptance gate | R7 | TAB-308、TR-407、QA-607 | `md2word/REL-701` |
| [REL-702](./REL-702.md) | 指标、告警和容量 | R7 | REL-701 | `md2word/REL-702` |
| [REL-703](./REL-703.md) | 迁移和灰度启用 | R7 | REL-701 | `md2word/REL-703` |
| [REL-704](./REL-704.md) | Runbook、OpenAPI、最终签字 | R7 | REL-703 | `md2word/REL-704` |
