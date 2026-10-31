# 只读复核位置提示最小适配

## 目标与授权

在任务详情展示源 PDF 页码、块 ID 和受控复核建议，复用 main 的题注裁决与 GET review/blocks。用户已在上一轮最终审查和执行建议后明确授权：从最新 main 新建独立 worktree，创建最小 Trellis 任务，完成规划并实施，只运行两个新增直接回归模块。

基线 main 44fd4ad82f62347f28553c09da5a84e1ac8a1c58；参考归档 archive/refine-word-generation-rules-20261031（c9b1e6a9）。外置 approved-review.json 保存已审查范围。本任务承接该批准，无待决产品问题，不重复要求批准同一范围。

## 已确认事实

- CaptionReconciler 已产生 uncertain/rebound；review_content.py:_block 未把这些事实列为块提示。
- 现有 GET /api/v1/document-jobs/{job_id}/review/blocks 提供 source、content_snapshot、source_spans、flags、total 和 next_cursor；前端尚未消费。
- 旧 review_issues 生产字段不在 main；旧 manual_review 自由 flag 会影响 main 未知风险统计。不能搬入旧 collector、renderer evidence 或 metadata 透传。

## 范围

五份源码：app/domains/document_jobs/review_content.py、frontend/src/api/types.ts、frontend/src/api/documentJobs.ts、frontend/src/utils/format.ts、frontend/src/pages/JobDetailPage.vue。

两份新增直接回归：tests/test_document_job_review_hints.py、frontend/src/pages/documentJobReviewHints.test.ts。必要 Spec 只改 .trellis/spec/backend/word-generation-rules.md；任务记录仅本目录六份文件。

## 验收

| ID | 可观察行为 |
|---|---|
| AC1 | 主源块 uncertain 显示受控 warning，rebound 显示信息提示；普通块和派生副本不误报，不改变题注归属或可见内容 |
| AC2 | 页面展示源 PDF 页码、块 ID、固定中文建议与已加载位置数量；内部页索引加一，未知页明确未知，不能称为 Word 实际页码 |
| AC3 | 分页有界且绑定同一 content_snapshot；任务/代数/IR/结果变化、旧响应或旧 finally 不得覆盖新状态；错误/不可用不冒充无风险 |
| AC4 | 只读 UI 不写 quality_flags 或 blocking_quality_flags，不修改质量/审核/交付/发布状态；所有动作仍由后端 available_actions 决定 |
| AC5 | v2 来源 owner、坏 v2 不回退、render_result 输出绑定、receipt 及历史请求幂等行为不变；不向历史 evidence 增加必填字段 |
| AC6 | 仅运行两份新增模块，无旧测试、lint/typecheck/build、smoke、CI 或线上操作；相同成功输入复用，不重复检查 |
| AC7 | 原有八个工作区及其索引和未提交内容保留，历史11测试/2文档维护不导入；实施轮不提交；本提交轮仅保存本批14路径为一个本地提交，不推送/合并/删分支/自动归档 |

## 排除

annotation 翻译、表图重叠检测与裁剪、语义重分类、正式复核提交 UI、发布动作、新的后端路由/schema/DB、renderer/worker、默认资源、本地 .review.json、旧测试维护及完整 smoke 均不在范围。

## 本次本地提交授权

用户已明确授权当前独立worktree的14个路径创建一个本地提交，包含五份源码、两份新增直接回归、一份必要Spec及六份任务记录。本轮不再运行测试或配置CI，复用源码/依赖输入未变的后端9/9、前端39/39结果；其他八工作区及全部未提交内容、历史11测试与2文档维护继续保留。
