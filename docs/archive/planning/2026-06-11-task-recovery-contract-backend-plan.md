# md2word 后端开发计划：任务处置中心与契约防漂移

## 业务目标

后端本轮目标是为任务处置页面提供稳定、可解释、可测试的服务端合同：

- 第一轮：让失败、停滞、不可重试、可取消、可归档、可下载等状态通过 Document Jobs API 清晰表达。
- 第二轮：让 OpenAPI、schema、release check 和前端 mock/type 不再围绕核心任务字段漂移。
- 不改 Word renderer、DocumentIR 质量、MinerU 解析策略或外部调试项目。

## API Contract

- `GET /api/v1/document-jobs`：
  - 返回 list item 时必须包含 `available_actions`。
  - 保持 `summary`、`filtered_summary`、`translation_qa_summary` 兼容。
  - `status_group=active` 继续表示 `pending/queued/running`。
- `GET /api/v1/document-jobs/{job_id}`：
  - 返回完整任务详情、失败字段、资源摘要、`available_actions`。
  - 详情页所需诊断优先从现有字段、events、files、callback summary 取得。
- `GET /api/v1/document-jobs/{job_id}/events`：
  - 保持事件按时间返回，错误事件必须保留 trace 关联信息。
- `GET /api/v1/document-jobs/{job_id}/callback-summary`：
  - 用于显示 callback pending、failed、ignored、processed 等排障信息。
- 命令接口：
  - retry/cancel/archive/unarchive/clone/download-url 都必须返回或刷新后可获得一致 `available_actions`。
  - 409 状态冲突后前端可刷新获得最新 job 状态。

## 数据模型 / 状态流

- 不新增任务表，不做 migration。
- `DocumentJobRecord` 继续作为任务状态、阶段、失败字段和归档字段的源。
- `DocumentJobEventRecord` 继续承载阶段变化、错误、命令和恢复动作的审计线索。
- `DocumentJobCallbackMessage` 继续承载 MinerU callback spool；本轮只消费 summary，不改变 spool 语义。
- `available_actions` 由 service 根据当前 job、文件可用性、权限、归档状态、retry_count、错误可重试性生成。
- 停滞状态只作为只读诊断：
  - running 且 `updated_at` 超过既有 stale threshold 时前端提示。
  - 后端 health/metrics 继续暴露 stale/timeout 指标。
  - 不因前端查看而改变 job 状态。

## 权限 / 错误模型

- 保持现有租户、公司、创建者和角色权限边界。
- operator 只能处理自己有权限的 job/file；admin 可跨范围查看和处理。
- 所有命令接口必须做后端强校验，不能依赖前端禁用态。
- 错误响应保持统一结构：
  - nested `error.code/message/status_code/trace_id`
  - legacy `detail/error_code/trace_id`
- 细化任务处置可见错误时，必须保持错误码稳定，message 面向用户可读，内部异常留在日志。

## Schema / Migration

- MVP schema 变更策略：
  - 优先不新增字段。
  - 如新增只读 diagnosis projection，字段必须是可派生、不可写、向后兼容。
  - projection 字段命名应面向页面诊断，例如 latest error trace、callback counters、stale hint；不得复制完整 event log。
- 不做 DB migration。
- 不索引 JSON payload，不引入 read model。
- 多 worker 原子 claim、callback claim、storage reconciliation、payload version migration 进入后续可靠性专项，不混入本轮。

## Service / API / 异步任务 / 文件处理 / 存储

- Service：
  - 收口任务动作判断和 disabled reason。
  - 提供任务处置所需的只读汇总。
  - 避免 router、worker、frontend 重复实现可重试/可取消/可归档规则。
- API：
  - Router 保持 thin，只处理鉴权、参数校验、HTTPException/ApiError 映射。
  - OpenAPI snapshot 必须反映核心 response 字段。
- 异步任务：
  - 不改 `DocumentJobExecutionService` 的核心阶段推进。
  - 不改 MinerU callback 成功/失败语义。
  - 不新增自动 replay/poll scheduler。
- 文件处理：
  - clone/download 的可用性仍由源文件和结果文件 metadata 决定。
  - 文件过期、缺失、不可下载应体现在 action disabled reason 或诊断提示中。
- 存储：
  - 不开启真实物理删除。
  - 不改变 artifact storage provider。
  - orphan object 清理和 metadata/object 事务一致性列为后续风险。

## 单元测试 / 集成测试

- Unit 或 backend tests 覆盖：
  - list/detail response 始终包含 `available_actions`。
  - failed job 暴露 `failed_stage/error_code/error_message`。
  - retryable 与 non-retryable failed job 的 disabled reason。
  - canceled、archived、active job 的 action matrix。
  - source file expired/missing 时 clone 禁用。
  - 409 状态冲突、403 权限不足、503 readiness 不可用。
  - callback summary 可用于诊断展示。
- OpenAPI 测试：
  - `/api/v1/jobs` 不暴露。
  - document-jobs 核心字段存在。
  - 命令接口 response schema 不丢失 action 或错误字段。
- Release check：
  - 增加核心字段静态检查：`available_actions`、`failed_stage`、`error_code`、`error_message`、callback summary、structured error。

## 后端接口完成标准

- 后端不需要前端硬编码业务规则即可说明每个 job 的动作可用性。
- 失败或停滞任务能通过 API response + events + callback summary 形成完整诊断信息。
- OpenAPI、docs、release check 对核心字段一致。
- 旧 `/api/v1/jobs` 不作为公开合同回流。
- 不新增 silent fallback，不吞 trace id，不泄露敏感 URL/token。

## 风险、回滚点、验证命令

- 风险：诊断 projection 过早固化。回滚点：删除 projection，只保留现有字段和 events/callback summary。
- 风险：错误 taxonomy 扩大影响现有测试。回滚点：保留旧 error_code，新增更细字段只做可选展示。
- 风险：release check 过严。回滚点：新检查先作为 warning，再升级 hard gate。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```
