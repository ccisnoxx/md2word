---
doc_type: integration-acceptance
slug: md2word-fe-be-integration-acceptance
component: md2word-internal-portal
status: current
summary: md2word 前后端联调计划和验收口径，覆盖 mock/contract-first、接口完成标准、前端接入顺序和端到端验收。
tags: [testing, integration, frontend, backend, acceptance, document-jobs]
last_reviewed: 2026-06-10
---

# md2word 前后端联调计划与验收口径

## 1. 联调原则

本联调计划服务内部工作台成熟化，不把真实 PDF/MinerU/翻译/Word 主流程作为每次页面迭代的前置条件。

分层验收：

| 层级 | 目标 | 必跑程度 |
| --- | --- | --- |
| Contract-first | 锁定 API 请求/响应、权限、错误码、状态流。 | 每次合同变化必跑。 |
| Backend tests | 证明服务层和 API 行为稳定。 | 每次后端变化必跑相关测试。 |
| Frontend build/smoke | 证明页面可加载、角色边界和状态展示正确。 | 每次前端变化必跑 build，关键页面跑 smoke。 |
| Controlled E2E | 证明真实上传、建任务、事件、下载闭环可用。 | 发布或专项验收跑，不随普通页面迭代自动跑。 |

禁止在普通联调中隐式执行：

- 真实 MinerU 解析。
- 真实 LLM 翻译。
- Word 主流程回归。
- 真实 Slack/webhook 发送。
- 真实 S3 删除。
- 自动 cleanup scheduler execute。

## 2. Mock 或 Contract First

### 2.1 合同来源

权威顺序：

1. 后端 Pydantic schema。
2. `docs/api/openapi.json`。
3. `docs/api/*.md`。
4. 前端 `frontend/src/api/types.ts`。
5. mock 数据。

如果出现不一致，以后端 schema 和 OpenAPI 为准，并同步文档和前端类型。

### 2.2 Mock 数据集

前端 smoke 至少准备以下 mock：

| 数据集 | 覆盖 |
| --- | --- |
| `operator-empty` | operator 登录、空任务列表、无 admin 导航。 |
| `operator-active-jobs` | pending/queued/running 任务、cancel 可用。 |
| `operator-failed-job` | failed 任务、retry/clone/archive、失败诊断和事件。 |
| `operator-succeeded-job` | succeeded 任务、download-url、文件列表。 |
| `operator-en2zh-qa` | translation QA 队列、QA 详情、PATCH 保存。 |
| `admin-config-summary` | admin 可选 published versions。 |
| `admin-system-status` | readiness ok/watch/blocker、metrics、ops gate。 |
| `admin-file-retention` | retention preview、cleanup plan、confirmation 文案。 |

### 2.3 Mock 响应规则

- `available_actions` 必须覆盖启用和禁用两类。
- 错误响应必须包含 `error_code`、`error.message` 和 `trace_id`。
- QA mock 必须覆盖：
  - supported `en2zh_pdf_to_word`
  - unsupported `direct_pdf_to_word`
  - artifact missing
  - debug archive disabled/expired
- 文件 mock 不包含真实本地路径、bucket secret 或长期 URL。

## 3. 后端接口完成标准

一个后端接口达到“可给前端接入”的条件：

1. 路由和 schema 已实现。
2. OpenAPI snapshot 已更新且测试通过。
3. API 文档说明请求、响应、权限、错误码和副作用。
4. 成功路径有 targeted test。
5. 403/404/409/422 或该接口相关错误至少覆盖关键分支。
6. 写动作记录 audit 或任务事件；只读动作不产生副作用。
7. 不暴露 secret、全文正文、prompt body、provider response body 或本地绝对路径。

推荐验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

发布前聚合：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

## 4. 前端接入顺序

### 4.1 第一批：任务工作台

接入顺序：

1. `GET /document-jobs/config-summary`
2. `POST /files/upload-url`
3. `PUT /files/{file_id}/content`
4. `POST /document-jobs`
5. `GET /document-jobs`
6. `GET /document-jobs/{job_id}`
7. `GET /document-jobs/{job_id}/events`
8. `GET /document-jobs/{job_id}/files`
9. `GET /document-jobs/{job_id}/download-url`

验收：

- operator 默认配置可建任务。
- admin 可选择 published 配置。
- 任务列表和详情展示同一份状态语义。
- 文件下载不缓存短期 URL。

### 4.2 第二批：任务动作

接入顺序：

1. 单任务 retry。
2. 单任务 clone。
3. 单任务 cancel。
4. archive/unarchive。
5. bulk retry/cancel/archive。

验收：

- 按 `available_actions` 禁用按钮。
- 409 显示后端原因。
- 批量动作显示成功/失败数量。
- clone 后跳转新任务，源任务不变。

### 4.3 第三批：翻译 QA 与提案

接入顺序：

1. `/translation-qa` 队列读取任务列表筛选。
2. `GET /document-jobs/{job_id}/translation-qa`。
3. `PATCH /document-jobs/{job_id}/translation-qa`。
4. 术语规则提案和翻译术语提案 deep link。

验收：

- Direct job 不进入 QA 队列。
- QA 详情能区分证据不可用原因。
- PATCH 后列表和详情 QA 状态一致。
- 提案保留 source job/file/version 上下文。

### 4.4 第四批：admin 配置和运维页面

接入顺序：

1. `/settings` 入口。
2. 模板、术语规则集、翻译配置、翻译术语集治理页。
3. `/system-status` readiness/metrics。
4. `/system-status/audit-events`。
5. `/system-status/file-retention`。
6. `/system-status/ops-dashboard`。

验收：

- operator 路由守卫和后端 API 都拒绝 admin-only 能力。
- 配置写动作都有 reason/audit。
- 文件清理必须 preview -> reason -> confirmation。
- ops real integration 默认 gated/deferred。

## 5. 端到端验收

### 5.1 Mock E2E 验收

Mock smoke 通过标准：

- `/login` 加载无控制台错误。
- operator：
  - 能进入 `/jobs`。
  - 看不到 `/settings` 和 `/system-status` 导航。
  - 能看到任务列表、详情、文件、事件、QA 入口。
  - admin-only 配置选择不可见。
- admin：
  - 能进入 `/settings`、`/system-status`、审计、文件保留。
  - 能看到配置 summary options。
  - 危险动作必须出现 confirmation 文案。
- 错误：
  - 401 会回登录。
  - 403 说明角色无权限。
  - 409 说明状态冲突。
  - 503 指向 readiness/配置排查。

### 5.2 后端集成验收

后端验收通过标准：

- OpenAPI snapshot current。
- targeted backend tests 通过。
- API 文档与 schema 一致。
- 所有写动作的 audit/event 行为明确。
- 所有只读接口无副作用。

### 5.3 真实 P0 主链路验收

真实链路只在明确验收窗口执行，使用：

- [docs/testing/pdf-to-word-p0-integration-guide.md](./pdf-to-word-p0-integration-guide.md)
- [docs/testing/pdf-to-word-golden-sample-acceptance-report.md](./pdf-to-word-golden-sample-acceptance-report.md)

最小真实验收步骤：

1. 登录。
2. 获取上传授权。
3. 上传 PDF 内容。
4. 创建 `direct_pdf_to_word` 任务。
5. 查询任务详情和事件。
6. 获取 `download-url`。
7. 下载并打开 Word。

真实验收不自动表示页面全部通过；页面仍需独立 mock smoke 和 build。

### 5.4 翻译 QA 真实验收

`en2zh_pdf_to_word` 仍按实验能力验收：

- 仅在翻译 provider 配置明确可用时执行。
- debug archive 是否启用要提前确认。
- 验收记录必须区分：
  - 翻译任务是否成功。
  - QA evidence 是否可读取。
  - 人工质量是否通过。

## 6. 阻断条件

出现以下任一情况，不进入真实 E2E：

- `/health/ready` 有未解释 blocker。
- Worker 未启动或 queue/broker 不可用。
- `AUTH_JWT_SECRET_KEY` 或内部用户配置缺失。
- `MINERU_API_TOKEN` 缺失但要跑真实 MinerU。
- artifact storage 不可写或 download-url 失败。
- OpenAPI 与前端类型明显不一致。
- 前端 build 失败。

## 7. 验收记录模板

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| OpenAPI snapshot |  |  |
| Backend targeted tests |  |  |
| Frontend build |  |  |
| Mock smoke `/jobs` |  |  |
| Mock smoke `/jobs/:jobId` |  |  |
| Mock smoke translation QA |  |  |
| Mock smoke admin settings/status |  |  |
| Operator permission boundary |  |  |
| Admin permission boundary |  |  |
| Real P0 upload/create/status/download |  |  |
| Real Word opens |  |  |
| Translation QA evidence |  |  |
| Known residual risks |  |  |

## 8. 通过口径

本阶段“联调通过”要求：

- Contract、backend tests、frontend build、mock smoke 均通过。
- 真实 P0 验收如果本轮执行，必须单独记录样本、环境、任务 ID、下载结果和人工判断。
- 未执行真实 P0 时，最终报告必须明确说明“未重跑 PDF/MinerU/翻译/Word 主流程”。
- 不允许用 mock smoke 代替真实 Word 质量验收。

## 9. 2026-06-10 执行记录

本轮执行范围：按四份成熟化设计文档检查并验证当前实现，不重跑真实 PDF/MinerU/翻译/Word 主流程。

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| OpenAPI snapshot | 通过 | `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`，3 tests passed；`scripts/ops/check_release.py` 报告 OpenAPI current，`changed: False`。 |
| Backend targeted tests | 通过 | `tests.test_fastapi_jobs_backend` 中 document job list/filter、available actions、clone、retry、cancel、archive、bulk、translation QA 等 13 个定向用例通过；`scripts/ops/check_release.py` 额外跑 28 个 targeted tests 通过。 |
| Frontend build | 通过 | `npm --prefix frontend run build` 通过；仅有 Rollup pure annotation 和 chunk size 警告。 |
| Mock smoke `/login` | 通过 | Vite 指向本地 mock API；页面可加载，仅 favicon 404。 |
| Mock smoke `/jobs` | 通过 | `auth/me`、`document-jobs/config-summary`、`document-jobs` 均返回 200；任务列表、上传区、批量动作可渲染。 |
| Mock smoke `/jobs/:jobId` | 通过 | job detail、events、files 均返回 200；详情页状态、动作、文件、事件和配置快照可渲染。 |
| Mock smoke translation QA | 通过 | QA queue 和 QA detail 均可加载；证据不可用原因、段落对比、空 term/AI call 状态可渲染。 |
| Mock smoke admin settings/status | 通过 | `/settings` 所需 templates、template versions、translation profiles、profile draft、term proposals 均返回 200；`/system-status` 的 readiness/metrics 均返回 200；无控制台错误。 |
| Operator permission boundary | 通过 | operator token 访问 `/settings` 被路由守卫重定向到 `/jobs`；`auth/me`、`config-summary`、`document-jobs` 均返回 200；无控制台错误。 |
| Admin permission boundary | 通过 | admin token 可访问 `/settings` 和 `/system-status`；配置概览与状态页接口均返回 200。 |
| Real P0 upload/create/status/download | 未执行 | 按本轮约束未重跑真实上传、解析、翻译或 Word 生成链路。 |
| Real Word opens | 未执行 | 按本轮约束未生成或打开新的 Word 产物。 |
| Translation QA evidence | Mock 通过，真实未执行 | mock QA evidence 页可渲染；未创建新的真实 `en2zh_pdf_to_word` 任务。 |
| Known residual risks | 保留 | mock smoke 不覆盖真实 provider、真实 artifact 读取、真实 Word 质量、长耗时任务和生产对象存储权限。 |
