# Trellis 子任务映射建议

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
