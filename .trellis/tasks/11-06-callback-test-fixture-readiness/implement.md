# 实施与定向验收计划

用户已明确确认最新最小方案，以下实施与四例定向验收已完成；当前 completed，证据已回填 B03，未提交/推送或归档。

## 确认后步骤

1. 核对本任务文档和工作区基线，保持 B03 及其他既有改动。
2. 仅在四个目标方法中把 public_deployment_mode 改为 internal；将已有创建 201 断言前移至 job_id 读取前，删除原位置重复断言。
3. 核对 checksum、消息、状态、下载次数和监控摘要断言未削弱；审阅触及范围注释。
4. 一次性运行下列四个方法；成功后不因收尾重复测试。不运行整个测试文件、其他模块、聚合发布脚本、CI、build 或全量测试。

```bash
.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_invalid_callback_checksum_leaves_no_callback_message \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_queues_before_worker_completes_parse \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_dedupes_duplicate_delivery_before_worker \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_ignores_queued_callback_after_cancel
```

5. 若失败先定位。仅修正本任务实际引入的局部错误并重跑受影响用例；如需要改变计划范围，保留失败证据并先请求确认。
6. 检查精确 diff、git status、任务文档及 context 引用；记录结果。测试通过可进入 review，不执行 commit/push、archive、add_session 等可能产生提交的命令。

## 完成标准

四个用例均通过，原有行为断言全部保留且运行；代码改动仅限四个方法；本任务记录完整。保留未执行公开部署、真实外部依赖和全量回归的证据边界。B03 的独立状态不由本任务自动改写。

## 规划阶段记录

仅运行未修改的四个测试并观察创建响应：4 tests / 4 errors，均在 job_id 处失败，503 原因一致。未实施或验证候选修复。规划检查见 planning-validation.md。

## 实施结果

步骤 1–6 已完成，四例仅运行一次且全部通过；原行为断言完整保留，29 个既有工作区路径保持不变。没有扩大变更或测试范围。详见 implementation-validation.md 与 checker-report.md。
