# 既有任务与整改重叠

基线与日期同 `audit-matrix.md`。本轮只读任务登记和相关 PRD/Spec，结合当前源码定位；没有重写其他任务状态，也没有把 archived/done 直接当成本地集成或生产验收。

| 现有工作 | 当前登记/证据 | 本计划处理 |
|---|---|---|
| Datasheet DOCX 交付质量父任务 | `.trellis/tasks/10-12-datasheet-docx-delivery-quality/prd.md:1`；task.json 仍 planning | 本任务独立作为审查规划，不接管产品父任务，不自动认定全部验收。 |
| BAS-001 能力基线 | `docs/implementation/codex-task-manifest.yaml:24` 记录 done；2026-10-12 旧基线 | 本轮是 79f20cef 审查核实，不重跑 BAS-001 或原发布检查；旧报告保留时间边界。 |
| TR-402 / TR-403 | `.trellis/tasks/archive/2026-10/10-21-tr-402-protected-token-codec/task.json:1`、`.trellis/tasks/archive/2026-10/10-21-tr-403-translation-integrity-validator/task.json:1`；登记 completed，当前 codec/validator/translator 调用可见 | 不重新实现 Token/Validator；B01 修正“尚未接入”状态文字。 |
| TR-406 批次失败语义 | `.trellis/tasks/archive/2026-10/10-22-tr-406-partial-batch-failure-semantics/task.json:1`；当前 Spec 明确 attempt/lease/原子根树与失败收口 | B04/B05 保留其状态 owner；测试存在不等于真实 MySQL 验收。 |
| TR-404 TableContextBuilder | `docs/implementation/codex-task-manifest.yaml:300`：todo、trellis_task_path=null；`docs/implementation/codex-task-backlog.md:390` 已列上下文/预算/CanonicalGrid | B06 对接该既有待办；本轮不创建重复子任务、不改 manifest。 |
| 公式字面最小适配 | `.trellis/tasks/10-31-formula-literal-minimal/prd.md:1`；登记 in_progress | B02/B06 不顺带改公式规则。 |
| MinerU 根唯一性与标题 | `.trellis/tasks/10-31-mineru-root-heading-minimal/prd.md:1`；登记 in_progress | A04 复用当前实现，不因 task 状态重做。 |
| 复核位置提示 / 模板 seed 历史 | `.trellis/tasks/11-01-review-hints-minimal/prd.md:1`、`.trellis/tasks/11-01-template-seed-history-minimal/prd.md:1`；均 in_progress | B07 不覆盖这些产品语义或重构对应无关页面。 |
| 页面降级相关四项 | `.trellis/tasks/11-02-render-degradation-coverage/prd.md:1`、`.trellis/tasks/11-02-degraded-page-isolation/prd.md:1`、`.trellis/tasks/11-02-source-page-counts/prd.md:1`、`.trellis/tasks/11-02-poppler-readiness-degradation-policy/prd.md:1`；均 in_progress，部分 AC 已勾选 | 当前实现作为兼容基线。B04 需保留降级尝试、独占页、页数统计、Poppler readiness 和 direct/翻译差异；不自动结案。 |

## 已知历史文字与当前源码差异

- backend directory Spec 曾将 runtime_runner 描述为 legacy /jobs backing path；当前主 router 与 OpenAPI 测试已明确不公开旧 /jobs，但 main 仍装配 stage_service，独立 StageWorker 入口仍存在。B01 更新描述，B05 另核运行消费者。
- gap 文档自身已有旧 baseline 标识及“先验证当前实现”的提示。需要精确更新或标注引用关系，不将整个历史文档无条件删除或归档。
- 11-02 降级任务的未闭合条目不是本任务授权的缺陷修复。未来试点若遇到失败，先区分本次回归与已有问题，不借重构顺带处理。

## 后续立项规则

本任务交付核实与路线图，不创建 B01–B11 子任务。将来只为用户选定的批次新建任务，或继续已有 TR-404；先重新检查当前 commit 与并行修改，再写该批次自己的 PRD/design/implement。候选批次不等于实施授权，不存在自动沿阶段执行的承诺。

## 2026-11-06 B03 后续进展同步

以上为原始审查与既有任务盘点时点。B03 后经用户独立批准实施，四个既有回调夹具另经批准修复；现两个任务均为 completed（本地实现和批准定向验收完成），未提交、推送或归档。A05 的初始缺口已完成本地修复验收；换代并发/真实生产证据边界仍保留。详见 [总计划进度](../progress.md) 与 [B03 逐项对账](../../11-06-mineru-download-boundary/acceptance-reconciliation.md)。本轮只同步记录，未运行测试，未改变其他既有任务及产品 manifest。
