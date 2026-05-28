---
doc_type: dev-guide
slug: backend-pdf-online-completion-change-summary
component: backend-change-summary
status: current
summary: 总结本轮 PDF 在线链路从 callback 停在 parsed 演进到自动完成 completed 的行为变化，以及已拍板的产品/API 选择。
tags: [backend, change-summary, jobs, pdf, mineru]
last_reviewed: 2026-05-28
---

# PDF 在线链路行为变更摘要

## 这轮改了什么

当前 `md2word` 后端的 PDF 在线链路，已经从：

```text
submit_to_mineru -> callback -> parsed/failed
```

演进为：

```text
submit_to_mineru -> callback -> 恢复 parsed_result_package -> 后处理 conversion -> completed/failed
```

这意味着：

- callback 命中 `done + full_zip_url` 后，不再只是把 job 停在 `parsed`
- 服务会自动继续走后处理链
- 正常情况下，外部更常看到 `completed`

## 对外可观察的具体变化

### 1. callback 成功后的最终状态变化

旧行为：

- callback 成功后，job 通常停在 `parsed`

新行为：

- callback 成功后，job 会自动继续推进
- 最终通常进入 `completed`
- 如果恢复结果 zip 或后处理 conversion 失败，则进入 `failed`

### 2. 新增本地 artifact

新增 artifact：

- `parsed_result_package`

对应合同：

- alias: `parsed-result-package`
- 本地逻辑路径：`input/parsed-result.zip`
- 含义：远端 MinerU 结果 zip 的本地恢复副本

### 3. 事件流变长

callback 成功时，当前典型事件顺序会变成：

1. `mineru_callback_received`
2. `mineru_callback_processed`
3. `stage_enqueued` for `convert_parsed_result`
4. `parsed_result_conversion_started`
5. `parsed_result_package_recovered`
6. `job_completed`

如果下载或后处理失败，则会在后半程改为：

- `job_failed`

### 4. `parsed` 的语义变化

`parsed` 仍保留，但现在更像：

- 内部生命周期里程碑
- 表示“远端结果已确认可用”

而不再表示：

- callback 成功后会稳定停留在该状态供外部长期观察

## 对调用方的影响

### 对前端 / 脚本调用方

需要更新的假设：

- 不要再把“callback 成功后 status 一定是 `parsed`”当作稳定合同
- callback 成功后，轮询时通常会直接看到：
  - `queued`
  - `converting`
  - `completed`

仍然可继续依赖的东西：

- `mineru_result_zip_url` 仍会持久化
- `events` 仍可用于解释完整执行轨迹
- `result` / `download/result` 仍是最终 DOCX 交付入口

### 对本地运维 / 联调

现在应把 PDF 在线链路视为：

- 可以完整走到 `completed`

而不只是：

- 验证 callback 成功后任务能进入 `parsed`

## 已落地的内部架构变化

这轮变化背后的关键结构收口包括：

- `JobRecord` 引入 `lifecycle_status + execution_status`
- `source_pdf_context` 成为 `source_pdf` workflow 的内部上下文边界
- `JobStageService` 依赖 `JobStageWorkflowRepositoryProtocol`
- `WorkflowEventIntent -> workflow_events.py -> JobEvent` 成为主事件落盘路径
- `convert_parsed_result` 成为新的 stage
- `MinerUClient` 新增 `download_result_zip()`，明确承担远端结果下载职责

## 已拍板的两个产品/API 决策

决策存档见 [.codestable/compound/2026-05-28-decision-pdf-online-api-contract.md](/Users/sc/PycharmProjects/md2word/.codestable/compound/2026-05-28-decision-pdf-online-api-contract.md)。

### 决策 1：`parsed_result_package` 的对外定位

当前状态：

- 内部 artifact 合同已经存在
- `files` 列表里已经能看到 `parsed_result_package`
- `download/{artifact_alias}` 也已经支持 `parsed-result-package`

选项：

- 选项 A：完全隐藏，只作为内部文件使用
- 选项 B：作为受支持的中间 artifact 暴露，但不作为默认交付物
- 选项 C：提升为和 `result.docx` 同等重要的主交付物

拍板结论：

- 采用选项 B
- `parsed_result_package` 是正式支持的中间 artifact
- 调用方可以通过 `download/parsed-result-package` 下载它，用于排障、复现或回溯
- `result` / `result_docx` 仍是默认交付物，产品语义上不把 `parsed_result_package` 提升到同等优先级

### 决策 2：`parsed` 的对外状态语义

当前状态：

- 对外 schema 仍保留 `parsed`
- 内部生命周期里也保留 `parsed`
- 但正常自动链路下它通常只短暂停留

选项：

- 选项 A：短期保留为对外可观察状态，但明确它是瞬时里程碑
- 选项 B：立即从对外 schema 移除，只保留内部 lifecycle
- 选项 C：恢复为 callback 成功后的稳定停留态

拍板结论：

- 采用选项 A
- `parsed` 继续保留在对外 status 枚举中
- 它表示“MinerU 结果已确认可用”这个里程碑
- 调用方不得依赖它作为 callback 成功后的稳定停留态
- 后续若要移除或淡化它，应作为单独的 API 版本兼容议题处理

## 建议的下一步

如果转入发布/收尾节奏，建议顺序是：

1. 用这份摘要对齐团队内外认知
2. 用 Jobs API 文档作为调用方联调入口
3. 如果需要，再补一份更面向调用方的 release note 或迁移提示
