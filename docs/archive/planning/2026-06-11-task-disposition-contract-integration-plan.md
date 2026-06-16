# md2word 总计划：任务处置闭环与最小契约防漂移护栏

## 背景与业务目标

本轮选择“任务处置闭环 + 最小契约防漂移护栏”作为下一阶段正式方向。目标不是重做任务系统，也不是提升 Word 渲染质量，而是在现有 Files + Document Jobs 主链路上，让 operator/admin 能稳定完成：

- 看清任务现在处于什么状态、哪个阶段、是否停滞、是否失败。
- 看清能执行哪些动作、为什么某些动作不可用、下一步应该去哪里处理。
- 在失败、冲突、readiness blocker、权限不足时，拿到可复制、可转交的诊断信息。
- 保证后端 OpenAPI/schema、前端 API client/types、smoke mock、文档入口不继续漂移。

Word 交付质量按当前稳定能力处理。本轮不改 Word renderer、导出质量、外部 `md2word_main` 调试链路；只有出现明确当前回归证据时，才作为风险备注进入后续专项。

## 范围与非范围

范围：

- Document Jobs 任务列表、任务详情、任务动作、错误表达、readiness blocker、诊断复制。
- `/api/v1/document-jobs`、`/api/v1/files`、`/api/v1/health/ready`、ops recovery preview 的最小协同。
- OpenAPI、前端类型、API client、smoke mock、release check 的核心契约护栏。
- 相关 README/runbook/API/testing 文档口径更新。

非范围：

- 不恢复 legacy `/api/v1/jobs` 为公开主合同。
- 不做大规模状态机或任务模型重构。
- 不做多 worker 原子 claim、真实 S3 delete、provider cancellation、scheduler execute。
- 不把补文档本身作为用户功能；文档更新作为交付 DoD。

## API Contract

主合同仍是 Files + Document Jobs：

- `POST /api/v1/files/upload-url`
- `PUT /api/v1/files/{file_id}/content`
- `POST /api/v1/document-jobs`
- `GET /api/v1/document-jobs`
- `GET /api/v1/document-jobs/{job_id}`
- `GET /api/v1/document-jobs/{job_id}/events`
- `GET /api/v1/document-jobs/{job_id}/files`
- `POST /api/v1/document-jobs/{job_id}/download-url`
- `POST /api/v1/document-jobs/{job_id}/retry`
- `POST /api/v1/document-jobs/{job_id}/clone`
- `POST /api/v1/document-jobs/{job_id}/cancel`
- `POST /api/v1/document-jobs/{job_id}/archive`
- `POST /api/v1/document-jobs/{job_id}/unarchive`

合同要求：

- 所有返回任务对象的接口必须包含 `available_actions`。
- 前端不得根据 `status` 自行推断动作是否可执行，只能消费 `available_actions.{action}.enabled/reason`。
- `GET /document-jobs` 列表继续支持现有筛选；如已有 `status_group=active`，前端使用它表达处理中视图；如未满足处置需求，后端只做兼容增强。
- 诊断信息优先复用现有字段：`status`、`stage`、`progress`、`failed_stage`、`error_code`、`error_message`、`updated_at`、`trace_id/request_id`、`callback summary`、`files`。
- 如需要新增诊断 projection，必须是向后兼容的可选字段，不破坏旧响应。
- 错误体前端读取优先级：nested `error.code/error.message/error.trace_id` > legacy `error_code/detail/trace_id` > HTTP status fallback。

## 数据模型 / 状态流

任务状态保持现状：

- 活跃态：`pending`、`queued`、`running`
- 终态：`succeeded`、`failed`、`canceled`
- 归档态：由 `archived_at` 正交表达，不新增 `archived` status。

处置状态表达：

- failed：展示 `failed_stage`、`error_code`、`error_message`、最后更新时间、trace/request id。
- stale：优先由前端用 `updated_at` 与当前时间推导；后端如已有更可靠信号，可作为只读字段暴露。
- recovery：只读 preview 与执行动作分离；preview 不改变 job、queue、files、audit。
- download：继续走短期 `download-url`，不暴露长期对象地址。

状态流约束：

- cancel 仅对后端允许的活跃任务开放。
- retry/clone/archive/unarchive/download 均以后端 `available_actions` 为准。
- 409 conflict 触发前端刷新当前 job/list，避免用户继续基于旧状态操作。

## 权限 / 错误模型

角色：

- operator：查看和处置自己有权限的任务，创建任务，下载授权结果。
- admin：查看系统状态、ops、跨用户任务、恢复动作和配置治理。

错误：

- 403：显示权限不足；如下一步需要 admin，文案直接说明，不给 operator 不可达链接。
- 409：显示动作冲突原因，保留 trace/request id，并刷新 job/list。
- 503：显示 readiness blocker、影响范围、下一步入口；operator 无 admin 权限时提示联系 admin。
- timeout/network：显示可重试提示和诊断复制。
- 所有可转交错误都应支持复制诊断，至少包含 `route`、`operation`、`job_id`、`status`、`code`、`message`、`trace_id/request_id`、`updated_at`。

## 前后端协作顺序

1. 后端确认核心 response schema、错误结构、`available_actions` 完整性。
2. 前端同步 types/API client/mock，修正已发现的旧字段漂移。
3. 前端先接错误归一化、诊断复制、disabled reason 显示。
4. 后端补齐必要的只读诊断 projection 或 recovery preview 合同。
5. 前端接列表连续处置、详情局部 loading/error/empty、readiness 下一步。
6. 统一 release check：OpenAPI、后端 targeted tests、前端 build/unit/smoke、核心 mock contract。
7. 最后同步 API docs、runbook、testing acceptance。

## 测试与验收

后端：

- schema/action policy/permission/error/readiness/recovery preview 单元或集成测试。
- OpenAPI snapshot 和 `/api/v1/jobs` 不公开断言。

前端：

- error normalize、diagnostic copy、available_actions 文案、disabled reason、return query、loading/error/empty 单测。
- operator jobs smoke、failed/stale detail flow、409 conflict、503 blocker、forbidden admin route smoke。

联调：

- mock-first 覆盖 active、failed、stale-like running、succeeded、403、409、503。
- real backend smoke 至少覆盖登录、列表、详情、download-url conflict/readiness blocker 中的关键路径。

## 风险、回滚点与验证命令

风险：

- 页面信息过密，导致处置中心变成运维看板。
- action 文案与后端可执行状态不一致。
- smoke mock/type 与 OpenAPI 再次漂移。
- readiness 文案给出 operator 不可达的 admin 链接。

回滚点：

- 自动刷新可单独关闭。
- 新增诊断 projection 为可选字段，可前端降级。
- release check 的新增契约检查先覆盖核心字段，误报时可降为 warning。
- recovery execute 不进入本轮 MVP；preview 保持只读。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```

说明：后端主门禁以 `check_release.py` 内置 targeted unittest 为准；整套 `tests.test_fastapi_jobs_backend` 仍包含 legacy `/api/v1/jobs` 历史断言，不作为本轮必过门禁。
