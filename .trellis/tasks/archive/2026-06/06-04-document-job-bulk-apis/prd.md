# Document job bulk APIs

## Goal

为 document_jobs 工作台补齐轻量批量操作后端合同，让前端不再为批量重试、归档和取消逐个直连单任务 API，同时保持所有任务生命周期语义复用现有单任务逻辑。

本子任务只覆盖批量 API 和现有任务列表页面的最小调用适配，不触碰 pdf-mineru 解析、翻译、Word 生成主流程，不做真实文件删除，不扩展术语规则 CRUD 工作台。

## Requirements

- 新增后端批量操作接口：
  - 批量重试 failed document_jobs。
  - 批量归档 succeeded / failed / canceled document_jobs。
  - 批量取消 pending / queued / running document_jobs。
- 每个批量接口必须按 job_id 返回逐项结果，支持部分成功；单个任务失败不能阻断后续任务。
- 每个成功项必须复用现有单任务 service 逻辑，保持现有状态检查、权限检查、事件写入、audit 写入和取消/归档语义。
- 批量重试请求最多只复用现有 `DocumentJobRetryRequest` 支持的字段，不新增配置治理能力。
- 批量归档仍只是隐藏终态任务，不能删除源文件、结果文件、debug/log 文件或事件。
- 批量取消仍只是把任务标记为 `canceled` 并停止后续处理语义，不能承诺强制中断已进入外部服务的长耗时阶段。
- 前端只做现有 `JobsPage` 批量重试/批量归档调用切换；不新增页面，不新增完整批量取消 UI。
- 验证过程中不得启动 eager Worker 去重跑 pdf-mineru / 翻译 / Word 主流程。

## Non-goals

- 不实现路线图之外的新功能。
- 不做真实文件删除、文件管理页、保留策略执行或存储清理。
- 不做完整术语规则 CRUD 工作台。
- 不改变单任务 `retry` / `cancel` / `archive` API 的既有合同。
- 不改变 document_jobs 持久化模型和主流程执行状态机。

## Acceptance Criteria

- [ ] `POST /api/v1/document-jobs/bulk-retry` 接受 job_id 列表和现有 retry 选项，返回逐项成功/失败结果。
- [ ] `POST /api/v1/document-jobs/bulk-archive` 接受 job_id 列表，返回逐项成功/失败结果，成功项保留文件和事件。
- [ ] `POST /api/v1/document-jobs/bulk-cancel` 接受 job_id 列表，返回逐项成功/失败结果，成功项使用现有取消语义。
- [ ] 批量接口对空列表、超出上限、重复 job_id 给出明确 `400 invalid_request`。
- [ ] 部分成功场景返回 `200`，每个失败项包含 `job_id`、`status_code`、`error_code`、`detail`，每个成功项包含最新 job 摘要。
- [ ] 成功项写入现有 `document_job.retry` / `document_job.archive` / `document_job.cancel` audit event，事件 trail 与单任务 API 一致。
- [ ] Operator/Admin 可见性与单任务 API 一致，跨租户/跨公司/不可见任务不得被批量修改。
- [ ] `JobsPage` 现有批量重试和批量归档按钮行为保持不变，但调用新 bulk API。
- [ ] API 文档和 OpenAPI 快照更新。
- [ ] 最小验证使用 targeted backend tests，不重跑主流程；如改前端 API/types，运行最小 typecheck 或说明无法运行原因。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
