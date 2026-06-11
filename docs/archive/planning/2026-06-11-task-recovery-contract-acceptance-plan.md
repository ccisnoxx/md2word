# md2word 联调验收计划：任务处置中心与契约防漂移

## 业务目标

验收目标是证明两件事：

1. 失败/停滞任务处置中心真实解决 operator/admin 的任务可见性和下一步操作问题。
2. 前后端契约防漂移机制能阻止核心 Document Jobs 合同被 OpenAPI、前端类型、mock 或 release check 悄悄破坏。

本验收不覆盖 Word 交付质量专项，不读取外部调试项目，不要求真实 S3 delete、provider cancellation 或 scheduler execute。

## API Contract 验收

- OpenAPI 中必须存在 Document Jobs 主链路 endpoint。
- OpenAPI 中不得出现公开 `/api/v1/jobs`。
- `DocumentJobResponse` 或其 list/detail response 必须包含：
  - `id`
  - `status`
  - `stage`
  - `progress`
  - `failed_stage`
  - `error_code`
  - `error_message`
  - `available_actions`
  - `updated_at`
- `available_actions` 每个 action 必须能表达：
  - `enabled`
  - `disabled_reason`
  - 是否 retryable 或 action-specific metadata（如现有 schema 支持）
- 结构化错误必须能表达 code、message、status、trace id，并兼容 legacy 字段。

## 数据模型 / 状态流验收

- active job：列表能通过 `status_group=active` 查到，详情显示运行阶段和刷新状态。
- stale running job：页面提示停滞，但后端状态仍保持 running，不发生隐式状态迁移。
- failed retryable job：展示失败阶段、错误码、错误消息、trace id，可执行 retry。
- failed non-retryable job：retry 禁用并显示后端 disabled reason。
- canceled job：不能 download result，不能 cancel，按后端 actions 显示 archive/clone 等允许动作。
- archived job：默认列表隐藏，include archived 或归档筛选可见，unarchive 按 action 控制。
- file expired/missing：clone/download 禁用原因可见，不误报为 Word 生成失败。

## 权限 / 错误模型验收

- operator 不能读取或操作无权限 job/file，返回 403，页面显示权限错误和 trace id。
- admin 可进入系统状态和运维视图，但危险动作仍 gated。
- 409 场景：
  - 用户对已变化状态的任务执行动作时返回冲突。
  - 前端展示冲突并刷新 job/list。
- 503 场景：
  - runtime/readiness 不满足时创建或动作返回 503。
  - 前端展示运行时不可用，并给出系统状态入口。
- trace id：
  - API 错误体、日志和前端复制诊断中可以关联。

## 后端接口完成标准

- `tests.test_openapi_export` 证明 OpenAPI 暴露面正确。
- backend tests 证明：
  - `available_actions` 在 list/detail/command 后一致。
  - failed/stale/callback summary 可支撑诊断。
  - 权限和错误码符合 403/409/503 语义。
  - create readiness gate 不创建注定失败的 job。
- `scripts/ops/check_release.py` 证明：
  - OpenAPI snapshot、核心前端合同、smoke mock 字段一致。
  - 旧 `/api/v1/jobs` 没有回流为公开 endpoint。

## 前端接入验收

- 页面验收：
  - `/jobs` 展示 active、failed、stale、archived 筛选和摘要。
  - `/jobs/:jobId` 首屏展示任务处置面板。
  - `JobActions` 禁用原因可见。
  - `ApiErrorAlert` 可复制诊断。
- 状态验收：
  - 初次加载、后台刷新、局部 events/files/callback loading 分开。
  - 403/409/503/timeout 都有不同提示。
  - empty state 有可执行下一步。
- API client 验收：
  - 不存在新增 `/api/v1/jobs` 调用。
  - document-jobs wrapper 与类型覆盖页面所需字段。

## 单元测试 / 集成测试 / E2E 或 Smoke Test

- 后端单元/集成：
  - document job action matrix。
  - failed job diagnosis fields。
  - callback summary。
  - permissions。
  - readiness gate。
  - OpenAPI export。
- 前端 unit：
  - error normalize。
  - action disabled reason。
  - diagnosis panel state rendering。
  - stale display。
  - copy diagnostic payload。
- Smoke：
  - operator core flow。
  - active auto refresh。
  - failed diagnosis。
  - retry/cancel/archive disabled reason。
  - 409 conflict refresh。
  - 503 readiness blocker。
  - admin system status link。

## Mock 或 Contract First

- smoke mock 必须先于页面验收补齐。
- mock 至少包含：
  - active job
  - stale running job
  - failed retryable job
  - failed non-retryable job
  - archived job
  - callback pending/failed
  - result file available
  - source file expired
  - 403/409/503 structured error
- release check 必须读取或静态验证 mock 中的核心字段，不能只验证页面能启动。

## 端到端验收脚本

手动或自动 smoke 应覆盖：

1. operator 登录进入 `/jobs`。
2. 切换 active 筛选，看到 running job 和刷新状态。
3. 打开 failed job，确认首屏看到 failed stage、error code、trace id、callback summary、可执行动作。
4. 对 retryable failed job 触发 retry 入口。
5. 对 non-retryable failed job 确认 retry disabled reason。
6. 模拟 409，确认页面刷新并显示冲突。
7. 模拟 503，确认页面显示 readiness blocker 和系统状态入口。
8. admin 登录查看 system status，不触发真实危险动作。

## 风险、回滚点、验证命令

- 风险：真实后端数据与 mock 差异。回滚点：以 OpenAPI 和后端 tests 为准更新 mock，不在页面补 silent fallback。
- 风险：前端把 stale 当作终态。回滚点：stale 只作为提示，不影响 status/action。
- 风险：release check 阻塞过多。回滚点：只保留旧 jobs 禁止和核心字段 hard gate，其他检查暂时 warning。
- 风险：任务处置误导用户以为 Word 质量异常。回滚点：失败说明按 stage/error_code 展示，不把 renderer 质量作为默认结论。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
cd frontend && npm run test:unit
cd frontend && npm run build
cd frontend && npm run test:smoke
```
