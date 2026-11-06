# B05 第 3、4 步最终独立复核

复核日期：2026-11-06。复核范围为当前工作区候选 diff 与先前 P1/P2/P3 的处置；只读产品源码，仅写本报告。不运行新增测试、不访问外部服务、不提交。

## Findings (fixed)

- **P1：健康计数字段删除导致前端读取异常，已由主会话修复。**
  - `app/api/v1/routers/health_schemas.py:43` 保留 `jobs`、`stage_messages` 两个字典字段；`app/services/health_service.py:446` 明确返回两个空字典，不再读取旧仓储。
  - 这保持 `SystemStatusPage.vue:422、426` 和 `OpsDashboardPage.vue:2628` 的索引访问合同。正式 `document_jobs` 和 callback 计数继续来自正式仓储。
  - `stage_dispatcher` 仍已移除；现有前端仅在文本展示中通过 `checkValue` / `stringCheck` 处理缺值，不存在相同的索引异常。
- **P2：真实告警夹具误换许可码，已由主会话修复。**
  - `tests/test_fastapi_jobs_backend.py:244` 新增 `build_pilot_alert_response()`，通过合成 `HealthOpsAlertItem` 提供原固定许可码；真实 pilot 测试恢复 `stage_spool_failed_messages_present` 请求和 allowlist，并在健康响应边界注入该合成告警。
  - `app/domains/ops/real_alert_delivery.py` 相对 HEAD 无改动，固定许可、active-alert、确认、限流及审计规则没有放宽。
  - `docs/api/ops.md:290` 明确说明正式健康服务不再产生旧告警，active-alert 门禁无法满足，合成安全测试不证明正式发送可用；迁移到 callback 告警需要另行授权。
- **P3：异常处理规范引用已删服务，已由文档 owner 修复。**
  - `.trellis/spec/backend/error-handling.md:209` 已改为正式 `document_jobs` execution 与 `_failure_policy.py` 的失败处理职责；不再将 `JobStageService._handle_stage_failure()` 描述为当前路径。

## Findings (not fixed)

最终定向复核未发现新的可操作缺陷。以下是明确保留的范围边界，不作为新增阻塞：

- 历史真实 Slack pilot 的旧告警没有正式 active 目标；当前保留原发送许可规则，未迁移、未扩大发送范围。
- `DocumentJobFailureDiagnosticResponse.source_page_count` 和 `page_count_basis` 的既有 OpenAPI 快照漂移未补。主会话的 `openapi-baseline-drift.log` 记录在 HEAD 隔离基线复现这两个字段；本复核只读取该证据，未重新执行基线或导出。

## Verification

- **快照结构复核：通过。** 独立解析并比较 HEAD 与工作区 `docs/api/openapi.json`：全部 `paths` 内容完全一致；无 schema 新增或删除；仅 `HealthMetricsResponse`、`HealthOpsAlertItem`、`HealthOpsAlertSummary` 内容改变；其他 components 完全一致，顶层只有 components 改变。
- **健康旧读取核对：通过。** 当前 `HealthService` 无旧 `job_repository`、`stage_message_store`、`stage_dispatcher` 依赖和旧消息查询；两个兼容计数字段直接返回空字典。
- **事件与 schema：复用前轮静态证据。** 三种后端 `JobEventRepository` 类 AST 与 HEAD 一致；SQLite/MySQL CREATE 仅删除 `jobs`、`job_files`、`stage_messages`，其余 CREATE 不变。
- **Tests：复用主会话已执行结果。** `compatibility-tests.log` 显示 8 项定向测试全部通过，涵盖真实 pilot 权限、固定目标和确认、kill switch、注入 provider 与去重、限流、能力报告及健康空计数字段。本复核没有再次运行测试。
- **Lint / TypeCheck：本复核未运行。** 按委派不重复执行验证；不将只读差异检查表述为 lint 或类型检查通过。
- **代码修改：无。** 本轮仅新增任务报告；产品注释与开发者文本的新增、同步由实现方完成。
