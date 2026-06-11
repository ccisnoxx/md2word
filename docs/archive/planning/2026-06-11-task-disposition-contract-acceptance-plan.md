# md2word 联调验收计划：任务处置闭环与契约护栏

## 验收目标

证明本轮交付满足两个目标：

- 任务处置闭环：operator/admin 能从页面完成“看状态、看原因、看动作、看下一步、复制诊断”。
- 最小契约护栏：后端 schema/OpenAPI、前端 types/API client、smoke mock、文档口径一致。

验收不覆盖 Word 格式质量专项。若发现 Word 交付异常，只记录为独立风险，后续按专项调试。

## 验收前置

- 后端接口完成标准已满足。
- 前端 build/unit/smoke 可运行。
- OpenAPI snapshot 已更新。
- smoke mock 使用当前 `/api/v1/document-jobs` 和 `/api/v1/files` 合同。
- README/runbook/API/testing 文档不把 legacy `/api/v1/jobs` 当主入口。

## 后端接口完成标准

- `POST /api/v1/document-jobs`
  - ready 时创建成功。
  - required 且 not ready 时返回 `503 document_jobs_not_ready`。
  - not ready 时不创建 job。
- `GET /api/v1/document-jobs`
  - 支持当前工作台所需筛选。
  - active/failed/succeeded/archived 场景返回可展示摘要。
  - summary 与分页、筛选语义一致。
- `GET /api/v1/document-jobs/{job_id}`
  - 返回状态、阶段、进度、错误、更新时间、`available_actions`。
- command APIs
  - 按服务端 action policy 判断。
  - 不可执行动作返回 409 或 403 structured error。
- recovery preview
  - 无副作用。
  - execute 不在 MVP 必需范围内；若暴露，必须有 admin/reason/audit。

## 前端接入验收顺序

1. API client/types 与 OpenAPI 对齐。
2. smoke mock 改为当前合同字段。
3. `ApiErrorAlert` 与错误归一化单测通过。
4. `JobActions`/`JobTable` disabled reason 可见。
5. `JobsPage` return query、failed/stale 入口可用。
6. `JobDetailPage` 局部 loading/error/empty 可区分。
7. 运行 build/unit/smoke。

## 端到端验收场景

### Operator Core

1. operator 登录。
2. 进入 `/jobs`。
3. 查看 active/failed/succeeded 列表状态。
4. 进入一个任务详情。
5. 查看 events/files/callback 摘要。
6. 对允许的动作执行操作。
7. 成功任务可生成 download-url。

通过标准：

- 页面不依赖 legacy `/api/v1/jobs`。
- 操作按钮与后端 `available_actions` 一致。
- 错误和成功反馈清晰。

### Failed / Stale

1. 列表展示 failed stage/code/message。
2. 从 failed 筛选进入详情，再返回保留筛选。
3. stale-like running 任务显示更新时间和详情入口。
4. retry 不可用时显示 disabled reason，不提示“可重试”。

通过标准：

- 用户能判断问题位置和下一步。
- 诊断复制包含 route/operation/job/status/code/message/trace。

### Readiness Blocker

1. 后端 required 且 worker/MinerU 等 not ready。
2. 创建页显示 blocker。
3. 直接调用 create 返回 `document_jobs_not_ready`。
4. operator 页面说明需要 admin 处理；admin 页面可进入系统状态或 ops。

通过标准：

- 不创建注定卡住的 pending job。
- 503 错误结构化，前端展示下一步。

### Conflict / Permission

1. 对不可执行动作返回 409。
2. 前端展示冲突原因并刷新任务。
3. operator 访问 admin-only 入口返回 403。

通过标准：

- 用户不会基于旧状态继续操作。
- 权限错误不给不可达操作路径。

### Contract

1. OpenAPI 不公开 legacy `/api/v1/jobs` 主合同。
2. 前端 smoke mock 字段与 `frontend/src/api/types.ts` 一致。
3. release check 能拦住核心字段漂移。

通过标准：

- 后端 tests、OpenAPI tests、release check、前端 build/unit/smoke 全部通过。

## 单元测试 / 集成测试 / E2E 或 Smoke

后端：

- `tests.test_fastapi_jobs_backend`
- `tests.test_openapi_export`
- action policy、permission、readiness、recovery preview、structured error。

前端：

- error normalization。
- diagnostic copy。
- available_actions/disabled reason。
- return query。
- loading/error/empty state。

Smoke：

- operator jobs flow。
- failed/stale detail flow。
- readiness blocker。
- 409 conflict。
- 403 forbidden。

## 风险、回滚点、验证命令

风险：

- 验收环境没有真实 worker/MinerU，导致只能验证 blocker 和 mock flow。
- release check 增加后初期可能误报。
- 页面处置信息过密，需要再做 UX 收敛。

回滚点：

- contract check 先核心字段、后扩展字段。
- 自动刷新可关闭。
- 新诊断字段 optional。
- recovery preview 链接可隐藏。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```

说明：后端主门禁以 `check_release.py` 内置 targeted unittest 为准；整套 `tests.test_fastapi_jobs_backend` 仍包含 legacy `/api/v1/jobs` 历史断言，不作为本轮必过门禁。
