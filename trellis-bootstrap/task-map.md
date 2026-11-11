---
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文辅助/模板用途、原指令结构与Manifest定义的静态对照；仅追加治理字段和导语，未执行提示词、创建任务、修改状态或验收产品。原文字节、TR-406旧依赖差异及合并关系见 ../.trellis/tasks/11-10-documentation-evidence-governance/research/b4-preparation.md；45项实现证据沿用同目录manifest-reconciliation.md原范围。
---

# Trellis 子任务映射建议

本页是父子任务分组与slug建议模板；原目标、复选框、建议映射与验收条件供实际任务引用和确认，不证明当前已实施或验收，也不授权创建、启动、提交或归档任务。定义及 AC 见 [原任务清单](../docs/implementation/codex-task-backlog.md)，执行状态与依赖门以 [Manifest](../docs/implementation/codex-task-manifest.yaml) 为准；原模板字节保留。

| 父阶段 | 推荐子任务 Slug |
|---|---|
| 状态合同 | `document-job-quality-state-contract` |
| MinerU 验证 | `mineru-artifact-validator` |
| IR 规范化 | `document-ir-normalization` |
| 表格模型 | `canonical-table-grid` |
| 表格渲染 | `native-table-rendering` |
| 表格质量 | `table-quality-evidence` |
| 翻译 Token | `translation-protected-tokens` |
| 翻译上下文 | `translation-context-and-annotations` |
| 翻译门禁 | `translation-integrity-gate` |
| Word 预览 | `word-preview-provider` |
| 统一 QA | `unified-document-review` |
| 发布 | `document-publication` |
| 样本回归 | `datasheet-regression-matrix` |
| 上线 | `quality-rollout-and-gates` |

不要一次创建所有子任务并同时 `start`。按依赖顺序创建或规划，保持一个活跃实现任务。
