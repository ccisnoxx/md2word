# MinerU 回调测试夹具修复（4 个既有用例）

## 状态、优先级与授权

- 独立任务，P2，`completed`，`parent=null`；关联 B03 验收遗留；按本轮授权将通过证据回填 B03，不归档。
- 本轮授权：用户已确认此最小方案，允许四个目标用例的局部配置与断言位置修复，并仅运行计划中的四个用例。
- 不引入 CI、不跑全量测试、不提交/推送，不启动生产服务或增加 MySQL/Redis 环境。

## 问题与目标

四个既有用例把 `single_tenant_public` 与 `eager` Worker、默认 `file` 元数据组合。公开模式属于 `production_like`，创建任务的就绪检查正确返回 503 / `document_jobs_not_ready`，包含 `document_jobs_worker_backend_eager_in_production` 和 `document_jobs_metadata_store_not_mysql`。随后直接读取 `job_id` 导致 KeyError，真正回调断言没有执行。

目标是让隔离夹具匹配其回调行为测试职责，恢复原有验签、入队、去重和取消合同的有效执行。`internal` 与公开模式共用回调 URL 和 checksum 校验；生产就绪策略不在本次变更范围。

## 范围

确认后仅修改 `tests/test_fastapi_jobs_backend.py` 中以下四个方法：

| 方法（省略 test_document_job_ 前缀） | 必须保留并通过的断言 |
|---|---|
| invalid_callback_checksum_leaves_no_callback_message | 创建 201；错误 checksum 返回 403；回调消息总数为 0；任务仍为 running/parsing |
| mineru_callback_queues_before_worker_completes_parse | 回调 200；Worker 前 pending=1、可重放数=1、下载为空，任务 running/parsing；Worker 后 succeeded/completed、processed=1，下载指定结果 URL；原摘要与 metrics 断言保留 |
| mineru_callback_dedupes_duplicate_delivery_before_worker | 两次回调均 200，仅一条 pending/可重放消息；重复执行保持 succeeded，processed=1、下载仅一次 |
| worker_ignores_queued_callback_after_cancel | 回调及取消均 200；执行后 canceled/canceled、ignored=1，未下载 |

保留现有 fake MinerU、真实测试 renderer、仓储、队列、artifact 后端和回调内容。禁止修改共享 `build_test_runtime` 默认值、业务代码、生产就绪检查、回调安全检查及其他测试；不得删除断言、skip/expectedFailure 或用成功替身掩盖错误。

## 验收

1. 四个方法明确采用 `public_deployment_mode="internal"`，每个创建 201 断言移至读取 `job_id` 之前，移除原位置的重复断言。
2. 上表原有合同断言全部实际执行通过；只运行 `implement.md` 列出的四个定向用例。
3. 最终差异仅涉及四个方法及本任务记录；既有 B03 和其他工作区改动保持不变。
4. 记录实际结果、未验证边界及中文注释审阅情况；不得将本任务结果宣称为公开部署或全量回归验收。

## 规划阶段证据

四个未修改测试均返回相同 503，4 tests / 4 errors；观察器只记录响应，不替换配置、返回值或业务行为。详见 `research/root-cause.md`、`research/failure-observation.json` 和 `.log`。这是故障定位，尚非修复通过证据。

## 实施验收结果

用户确认后已按最小方案完成四个局部配置及创建断言前移，原有 55 条断言保留。四个定向用例一次运行全部通过（1.021s，exit 0），独立检查无范围内问题。任务现为 completed，已回填 B03，未提交、推送或归档；完整证据见 implementation-validation.md。
