# Checker 复核记录

## Findings (fixed)

无。候选无需二次修改；本次 checker 仅新增本任务证据及本记录。

## Findings (not fixed)

未发现本次候选范围内的正确性或合同缺陷。完整 stderr 保留三项既有 Starlette 弃用警告（TestClient/httpx 与 HTTP 状态常量），与本次四处配置及断言位置调整无关；未修改依赖或业务代码。

## 范围与断言复核

- `tests/test_fastapi_jobs_backend.py` 差异为 8 additions / 8 deletions，仅四个目标方法。每个方法将 `single_tenant_public` 改为 `internal`，将原创建 201 断言移至首次读取 `job_id` 之前，并删除原位置断言。
- 对照 HEAD 的 AST 断言多重集完全相同：checksum 6 条、入队 28 条、去重 11 条、取消 10 条，共 55 条。没有删除、弱化、skip 或 expectedFailure。
- checksum、URL guard、队列、真实 renderer、共享 fixture、业务代码和生产 readiness 均未由本任务修改。读取真实 callback router/guard 确认两种部署模式共用 checksum 校验。
- `research/workspace-baseline.json` 所列 29 个既有路径的 SHA-256 / 删除状态全部保持，包含 B03 与其他既有任务记录；详见 `validation/static-review.json`。
- 已审阅四个方法的注释、docstring 与开发者可见文本：触及范围无需要翻译的注释或 docstring；没有新增说明显然行为的注释，没有增加日志或异常文案。测试合同字面量保持原样。
- 无新增生产合同或架构约定；不需要修改共享 Spec、模板、OpenAPI 或配置默认值。夹具责任及根因已由本任务 prd/design/research 记录。

## Verification

- Lint：未运行，按本轮明确授权限制。
- TypeCheck：未运行，按本轮明确授权限制。
- Tests：通过。严格按 implement.md 的四个 selector 运行一次，未添加其他 selector；`Ran 4 tests in 1.021s`，`OK`，退出码 0。

| 用例 | 结果 | 实际覆盖 |
|---|---|---|
| invalid_callback_checksum_leaves_no_callback_message | PASS | 创建 201；错误 checksum 403；无消息；running/parsing |
| mineru_callback_queues_before_worker_completes_parse | PASS | pending/可重放各 1；Worker 前不下载；后 succeeded/completed、processed=1；摘要、metrics 与结果 URL |
| mineru_callback_dedupes_duplicate_delivery_before_worker | PASS | 两次回调成功但仅一条消息；重复 Worker 保持 succeeded；processed=1、仅一次下载 |
| worker_ignores_queued_callback_after_cancel | PASS | 回调及取消成功；Worker/最终任务 canceled；ignored=1；不下载 |

实际命令见 `validation/targeted-tests.command.txt`；完整原始 stdout/stderr 分别见 `validation/targeted-tests.stdout.log` 与 `validation/targeted-tests.stderr.log`；退出码、开始/结束时间及测试源码 SHA-256 见 `validation/targeted-tests.result.json`，另存独立 `targeted-tests.exit-code.txt`。

本次没有运行整个测试文件、其他测试、lint/typecheck、build、CI 或聚合发布脚本；没有 commit/push/archive/add_session，也没有修改任务状态。没有验证公开部署、真实 MinerU、MySQL/Redis/Celery、线上服务、全量回归或 B03 整体验收；四例通过仅证明本次隔离回调合同恢复有效执行。
