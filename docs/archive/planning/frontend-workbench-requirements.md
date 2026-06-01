---
doc_type: prd
slug: frontend-workbench-requirements
component: frontend-document-workbench
status: current
summary: 内部文档转换工作台的前端需求基线，覆盖页面、流程、MVP 范围、状态和验收标准。
tags: [frontend, requirements, workbench, document-jobs, vue]
last_reviewed: 2026-06-01
---

# 内部文档转换工作台前端需求文档

> 本文是前端开工前的需求基线。已确认第一版只做内部文档转换工作台，不做完整后台管理系统。

## 1. 项目背景

### 1.1 已知事实

- 后端已提供内部账号登录、PDF 上传授权、文件内容上传、`document_jobs` 创建、查询、事件查询、重试和下载授权接口。
- 第一版前端只面向 `operator` 和 `admin`。
- 第一版核心路径是：上传 PDF -> 创建 `document_job` -> 查看进度和事件 -> 失败重试 -> 下载 Word。
- 第一版不接 legacy `/api/v1/jobs` 运维页面，不做模板管理、术语管理、翻译配置管理。
- 首个验收版本只默认开放 `direct_pdf_to_word`，不默认开放 `en2zh_pdf_to_word`。

### 1.2 推断

- 内部用户需要一个可恢复的异步任务工作台，而不是一次性上传页。
- 用户经常需要刷新页面、离开后回来查看任务、同时处理多份 PDF。
- 失败原因、任务事件和下载入口比通用 dashboard 统计卡片更重要。

### 1.3 建议

- 第一屏设计为任务工作台：上传入口 + 任务列表。
- 任务详情页承载进度、阶段、事件流、错误、重试和下载。
- 英译中实验能力在前端代码结构中预留，但通过 feature flag 默认隐藏。

## 2. 目标用户

| 用户类型 | 角色 | 优先级 | 核心诉求 |
|---|---|---:|---|
| 内部文档交付人员 | `operator` | P0 | 上传 PDF，等待生成 Word，下载结果并线下校对 |
| 内部技术运营人员 | `operator` / `admin` | P0 | 查看任务进度、失败原因和事件，触发可重试任务 |
| 配置管理员 | `admin` | P1/P2 | 后续管理模板、术语和翻译配置；第一版不覆盖 |

## 3. 核心使用场景

1. 内部用户登录后进入任务工作台。
2. 用户上传电子元器件数据手册或规格书 PDF。
3. 系统完成 PDF 类型、大小、页数等后端校验。
4. 前端创建 `direct_pdf_to_word` 文档任务。
5. 用户查看任务列表中的状态、阶段、进度和更新时间。
6. 用户进入详情页查看阶段事件和失败原因。
7. 任务成功后用户获取临时下载链接并下载 Word。
8. 任务失败且后端允许时，用户触发重试。

## 4. 页面清单

| 页面 | 路由 | 目标 | 主要内容 |
|---|---|---|---|
| 登录页 | `/login` | 获取内部账号 JWT | 用户名、密码、登录错误 |
| 任务工作台 | `/jobs` | 第一屏和主操作页 | 上传入口、任务列表、状态筛选、刷新、空态 |
| 任务详情页 | `/jobs/:jobId` | 查看单个任务全貌 | 状态概览、进度、事件流、错误、重试、下载 |

## 5. 用户流程

### 5.1 登录流程

1. 用户访问任意受保护页面。
2. 未登录时跳转 `/login`。
3. 用户提交用户名和密码。
4. 前端调用 `POST /api/v1/auth/login`。
5. 成功后保存 `access_token` 和用户信息，跳转 `/jobs`。
6. 失败时展示后端返回的 `detail` / `error_code`。

### 5.2 上传并创建任务

1. 用户在 `/jobs` 选择一个 PDF。
2. 前端做基础校验：文件后缀、MIME、大小。
3. 前端调用 `POST /api/v1/files/upload-url` 获取上传授权。
4. 前端按后端返回的 `upload_url`、`method`、`headers` 上传文件内容。
5. 上传成功后调用 `POST /api/v1/document-jobs`。
6. 首个验收版本请求体固定使用 `mode=direct_pdf_to_word`。
7. 创建成功后跳转 `/jobs/:jobId`。

### 5.3 任务查询和下载

1. `/jobs` 分页查询 `GET /api/v1/document-jobs`。
2. `/jobs/:jobId` 查询 `GET /api/v1/document-jobs/{job_id}` 和事件接口。
3. `pending`、`queued`、`running` 状态下轮询详情和事件。
4. `succeeded/completed` 后显示下载按钮。
5. 点击下载时调用 `GET /api/v1/document-jobs/{job_id}/download-url`，再打开或下载返回的临时 URL。

### 5.4 失败和重试

1. 任务进入 `failed` 时展示 `failed_stage`、`error_code`、`error_message`。
2. 显示重试入口。
3. 前端调用 `POST /api/v1/document-jobs/{job_id}/retry`。
4. 若后端返回 409，展示不可重试原因，不在前端自行判断根因。

## 6. MVP 范围

| 功能 | 是否进入 MVP | 说明 |
|---|---|---|
| 内部账号登录 | 是 | JWT 登录，支持 token 过期处理 |
| PDF 上传 | 是 | 单文件 PDF 上传，不做批量 |
| 创建直接转 Word 任务 | 是 | 固定 `direct_pdf_to_word` |
| 任务列表 | 是 | 分页、状态筛选、刷新 |
| 任务详情 | 是 | 状态、阶段、进度、事件、错误 |
| 下载 Word | 是 | 每次点击重新获取临时下载 URL |
| 失败重试 | 是 | 按后端规则执行 |
| 英译中实验入口 | 预留但默认隐藏 | 代码结构预留，不进入首个验收默认 UI |
| 模板管理 | 否 | 后续 admin 模块 |
| 术语管理 | 否 | 后续 admin 模块 |
| 翻译配置管理 | 否 | 后续 admin 模块 |
| legacy jobs 运维 | 否 | 不接 `/api/v1/jobs` 运维动作 |

## 7. 功能需求

| ID | 功能 | 主流程 | 异常场景 | 优先级 | 验收标准 |
|---|---|---|---|---:|---|
| FR-001 | 登录 | 用户名密码换取 JWT | 密码错误、账号禁用、鉴权未配置 | P0 | 成功后进入 `/jobs`，失败展示明确错误 |
| FR-002 | 登录态恢复 | 刷新页面后读取本地 token 并调用 `/auth/me` | token 过期、token 无效 | P0 | 401 后清理登录态并返回登录页 |
| FR-003 | PDF 上传授权 | 选择 PDF 后获取上传 URL | 非 PDF、超大小、未登录 | P0 | 授权成功后拿到 `file_id` |
| FR-004 | PDF 内容上传 | 按授权 URL 上传文件内容 | 上传失败、后端校验页数失败、网络超时 | P0 | 上传成功后文件状态为 uploaded |
| FR-005 | 创建任务 | 使用 `source_file_id` 创建 `document_job` | 文件未上传完成、文件已被任务绑定、模板不可用 | P0 | 返回 `job_id` 并进入详情页 |
| FR-006 | 任务列表 | 展示可见任务、状态、阶段、进度、更新时间 | 列表为空、加载失败 | P0 | 用户能回到历史任务 |
| FR-007 | 任务详情 | 展示单任务状态、事件、错误和操作 | 无权限、任务不存在 | P0 | 用户能看清任务当前卡在哪个阶段 |
| FR-008 | 下载结果 | 成功任务获取临时下载 URL | 任务未完成、下载授权失败、链接过期 | P0 | 成功下载生成 Word |
| FR-009 | 重试失败任务 | 失败任务触发 retry | 不可重试、重试次数达上限 | P0 | 后端允许时任务重新推进 |
| FR-010 | 英译中实验预留 | feature flag 打开后可选择 `en2zh_pdf_to_word` | provider 未配置、翻译失败 | P1 | 默认关闭，不影响 P0 验收 |

## 8. 状态覆盖要求

### 8.1 页面状态

- 登录页：初始、提交中、登录失败、鉴权服务未配置。
- 任务工作台：加载中、空列表、加载失败、分页、筛选后为空。
- 任务详情：加载中、任务不存在、无权限、轮询中、终态。

### 8.2 上传状态

- 未选择文件。
- 文件类型不合法。
- 文件过大。
- 获取上传授权中。
- 上传中。
- 上传失败。
- 创建任务中。
- 创建任务失败。
- 创建任务成功。

### 8.3 任务状态

| `status` | 前端含义 |
|---|---|
| `pending` | 已创建，等待投递 |
| `queued` | 已入队，等待 Worker |
| `running` | Worker 正在处理 |
| `succeeded` | 已成功完成，可下载 |
| `failed` | 处理失败，可查看原因 |
| `canceled` | 已取消 |

### 8.4 任务阶段

| `stage` | 前端含义 |
|---|---|
| `uploaded` | 源文件已上传或任务已创建 |
| `parsing` | PDF 正在解析 |
| `parsed` | 解析结果已就绪 |
| `ir_converting` | 正在转换 DocumentIR，英译中实验模式也在此阶段翻译 |
| `rendering` | 正在生成 Word |
| `uploading` | 正在保存生成结果 |
| `completed` | 已完成 |
| `failed` | 已失败 |
| `canceled` | 已取消 |

### 8.5 错误展示

- 优先展示 `detail` 或 `error.message`。
- 同时保留 `error_code`、HTTP status 和 trace id 供排障。
- 未知错误不吞掉原始信息，展示通用提示并允许重试。

## 9. 非目标

- 不做完整后台管理系统。
- 不引入动态菜单、RBAC 菜单管理、tagsView、多主题系统、Monaco。
- 不做模板管理、术语管理、翻译配置管理。
- 不做 legacy `/api/v1/jobs` 任务和运维页面。
- 不做在线 Word 校对、段落级编辑、差异对比。
- 不做批量上传。
- 不改后端为统一 `code/data` envelope；前端在 client 层归一化错误和数据。
- 不承诺英译中实验模式默认稳定可用。

## 10. 验收标准

1. operator 能登录并进入 `/jobs`。
2. 未登录访问 `/jobs` 或 `/jobs/:jobId` 会跳转 `/login`。
3. 用户能上传一个合法 PDF 并创建 `direct_pdf_to_word` 任务。
4. 上传非法文件或超限文件不会创建任务，并展示明确错误。
5. `/jobs` 能展示当前用户可见任务，刷新页面后历史任务仍可进入。
6. `/jobs/:jobId` 能展示任务状态、阶段、进度和事件。
7. `running` 任务详情会自动轮询，终态后停止轮询。
8. 成功任务可下载 Word。
9. 失败任务展示 `failed_stage`、`error_code` 和 `error_message`。
10. 失败任务可按后端规则重试；不可重试时展示后端返回原因。
11. token 过期后清理登录态并回到登录页。

## 11. Open Questions

| 问题 | 影响 | 建议 |
|---|---|---|
| 是否需要任务关键词搜索 | 当前 `document-jobs` 列表没有 `q` 参数 | MVP 暂不做搜索，只做状态筛选 |
| 是否需要展示源 PDF 页数 | 文件 metadata 可能有 `page_count`，但任务列表不直接包含文件详情 | 详情页后续可按 `source_file_id` 补查文件 |
| 英译中实验入口如何开启 | 影响 feature flag 来源和权限 | 建议先用前端环境变量隐藏，后续结合 health 或后端配置 |
| 是否需要前端取消任务 | 当前 `document-jobs` 未提供 cancel API | MVP 不做 |
| 是否需要批量上传 | 影响上传队列和错误聚合 | MVP 不做，等单任务体验稳定后再评估 |

## 12. 参考边界

- 可以参考 `rebort-hub/fastapiwebadmin` 的 Vue 3 工程骨架和后台布局风格。
- 不直接复用其动态路由、RBAC、系统管理模块和 axios 响应合同。
- 前端请求封装应适配本项目当前 HTTP status + OpenAPI schema + `error_code/detail` 的后端合同。
