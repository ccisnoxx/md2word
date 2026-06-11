# md2word 后端开发计划：任务处置闭环与契约护栏

## 业务目标

后端目标是提供稳定、可解释、可验收的任务处置合同，让前端只负责展示和交互，不重复推断业务规则。

- `DocumentJobResponse` 成为任务处置页面的可信数据源。
- `available_actions` 成为所有操作按钮的唯一可用性依据。
- failed/stale/readiness/recovery 相关信息能被 operator/admin 理解和转交。
- OpenAPI、schema、错误体与前端类型和 mock 保持一致。

本轮不改 Word 生成链路，不访问外部调试项目，不把 Word 质量作为 P0。

## API Contract

### Document Jobs

- `POST /api/v1/document-jobs`
  - ready 时创建任务并返回完整 `DocumentJobCreateResponse`。
  - required 且 not ready 时返回 `503 document_jobs_not_ready`，不创建注定卡住的 job。
- `GET /api/v1/document-jobs`
  - 保留现有筛选、分页、排序、include archived。
  - 活跃任务视图优先支持 `status_group=active` 或已有等价合同。
  - summary 不应受分页影响；filtered summary 应与当前筛选一致。
- `GET /api/v1/document-jobs/{job_id}`
  - 返回完整 `available_actions`、错误摘要、阶段、进度、更新时间。
- 命令接口
  - retry/clone/cancel/archive/unarchive/download-url 均由服务端 action policy 判定。
  - 不可执行返回结构化 409 或 403，不让前端猜测。

### Recovery / Ops

- recovery preview 是只读接口，不改变任务、文件、队列、audit。
- execute 必须保留 admin 权限、reason/confirmation、audit。
- 本轮 MVP 可以只把 preview 信息接入任务处置入口，不要求新增 execute 能力。

## 数据模型 / 状态流

- 不新增状态，不做破坏性 migration。
- `pending/queued/running` 为 active。
- `succeeded/failed/canceled` 为 terminal。
- `archived_at` 继续作为正交归档字段。
- 建议在 `document_jobs.workflow` 或同等模块收口：
  - active/terminal 状态组。
  - cancel/retry/clone/archive/unarchive/download 的 action policy。
  - disabled reason 的标准枚举或标准文案来源。
- stale 不优先落库；如后端需要表达，只做只读 projection。

## Schema / Migration / Service

Schema：

- 确认 `DocumentJobResponse.available_actions` 在所有任务返回路径都存在。
- 确认 `DocumentFileResponse` 字段与 OpenAPI、前端 types 一致，避免旧字段继续进入 mock。
- 错误 response 保留 legacy 兼容，同时稳定 nested `error.*`。

Migration：

- MVP 无 migration。
- 若发现诊断字段必须持久化，需单独评估 migration、backfill、兼容策略；不默认加入本轮。

Service：

- `DocumentJobService` 继续负责 create/query/action/response projection。
- action policy 从散落判断中小范围收口，但不重写整个状态机。
- readiness gate 保持在创建入口，避免创建不可执行任务。
- callback summary、files summary、event summary 尽量通过既有查询组合，不增加重型同步逻辑。

异步任务：

- 不修改 MinerU、DocumentIR、Word 生成阶段。
- 不做多 worker claim 重构。
- 对 callback 丢失或 running stale 的处置，本轮只提供可见性和 recovery preview 入口。

文件处理 / 存储：

- 上传继续走 files upload authorization 与 content upload。
- 结果文件继续走 document job files 和 download-url。
- 不新增任务级删除；真实 S3 delete 仍保持 deferred/gated。

## 权限 / 错误模型

- operator 只能操作自己有权限的 job。
- admin 可访问 ops/recovery/system status。
- 403：权限不足。
- 409：当前状态不允许动作、动作冲突、文件不可下载等。
- 503：readiness blocker。
- 500：保留 trace/request id，不吞错。
- 所有错误响应必须可被前端归一化为 `status/code/message/trace_id`。

## 后端接口完成标准

- OpenAPI snapshot 与实现一致。
- `/api/v1/jobs` 不作为公开 v1 主合同出现。
- 所有任务对象响应都包含 `available_actions`。
- disabled reason 对 retry/cancel/archive/unarchive/download 至少覆盖常见不可执行状态。
- readiness blocker create 不创建 job。
- recovery preview 无副作用，有测试证明。

## 测试计划

Unit / integration：

- active/terminal/action policy。
- list/detail/create/action response 均含 `available_actions`。
- failed job 诊断字段返回。
- status conflict 返回 409 structured error。
- operator/admin 权限。
- readiness ready/unready。
- recovery preview no-side-effect。

Contract：

- OpenAPI export。
- `DocumentJobResponse`、`DocumentFileResponse`、error schema 核心字段检查。
- release check 覆盖前端依赖字段。

## 风险、回滚点、验证命令

风险：

- action policy 收口过大引发行为变化。
- disabled reason 文案成为第二套业务规则。
- readiness 判断误伤开发环境。

回滚点：

- policy 收口按 action 分批提交。
- 新诊断字段保持 optional。
- readiness gate 保持 required flag 保护。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
```

说明：后端主门禁以 `check_release.py` 内置 targeted unittest 为准；整套 `tests.test_fastapi_jobs_backend` 仍包含 legacy `/api/v1/jobs` 历史断言，不作为本轮必过门禁。
