---
doc_type: technical-plan
slug: frontend-workbench-implementation-plan
component: frontend-document-workbench
status: current
summary: 内部文档转换工作台的 Vue 前端实施计划，覆盖技术栈、路由、组件、状态、API、鉴权和分阶段开发。
tags: [frontend, technical-plan, vue, vite, element-plus, document-jobs]
last_reviewed: 2026-06-01
---

# 内部文档转换工作台前端实施计划

> 本文是前端实现的技术计划。它以 `document_jobs` 新链路为唯一业务入口，不接 legacy jobs 运维页面。

## 1. 技术栈建议

| 层级 | 选择 | 说明 |
|---|---|---|
| 构建工具 | Vite | 新建轻量前端工程 |
| 框架 | Vue 3 | 参考 `fastapiwebadmin` 的 Vue 技术路线 |
| 语言 | TypeScript | 固定 API 类型和页面状态 |
| UI 组件 | Element Plus | 适合内部工具和后台表格 |
| 状态管理 | Pinia | 保存登录态、当前用户和少量全局 UI 状态 |
| 路由 | Vue Router | `/login`、`/jobs`、`/jobs/:jobId` |
| HTTP client | Axios | 重新封装，适配本项目后端合同 |
| 图标 | Element Plus Icons 或 lucide-vue-next | 优先使用现成图标 |

### 1.1 fastapiwebadmin 参考边界

可以参考：

- Vite + Vue 3 + TypeScript 的工程组织。
- Element Plus 的后台表格、表单、卡片和状态组件用法。
- 登录页、侧边栏、顶部栏和内容区的布局思路。
- axios interceptor 的组织方式。

不直接复用：

- 动态菜单和后端控制路由。
- RBAC 菜单管理、角色管理、部门管理、字典管理。
- tagsView、多主题系统、Monaco、系统管理模块。
- 其 axios 的 `token` header 和 `{ code, msg, data }` 响应判断。

### 1.2 后端 envelope 决策

当前不改后端为统一 `code/data` envelope。原因：

- 后端已经使用标准 HTTP status 表达 401、403、409、413 等语义。
- 成功响应由 FastAPI `response_model` 直接描述，OpenAPI 更直观。
- 错误响应已经统一包含 `error_code`、`detail`、`error.message` 和 trace id。
- 文件下载、上传授权和临时 URL 不适合全局套同一种 envelope。

前端可以在 axios client 层做统一归一化，而不是要求后端改变所有响应合同。

## 2. 路由设计

| 路由 | 页面 | 鉴权 | 说明 |
|---|---|---|---|
| `/login` | `LoginPage` | 否 | 登录页 |
| `/jobs` | `JobsPage` | 是 | 任务工作台，第一屏 |
| `/jobs/:jobId` | `JobDetailPage` | 是 | 任务详情页 |
| `/:pathMatch(.*)*` | `NotFoundPage` | 否 | 可选，MVP 可简单跳回 `/jobs` |

路由守卫规则：

- 无 token 访问受保护路由时跳转 `/login`。
- 有 token 访问 `/login` 时跳转 `/jobs`。
- 页面刷新后优先调用 `/api/v1/auth/me` 校验 token。
- 401 时清理登录态并跳转 `/login`。

## 3. 页面结构

### 3.1 登录页

内容：

- 项目名称：内部文档转换工作台。
- 用户名输入。
- 密码输入。
- 登录按钮。
- 错误提示区域。

约束：

- 不做手机号登录、扫码登录。
- 不做注册和找回密码。
- 登录成功后进入 `/jobs`。

### 3.2 任务工作台

布局：

- 顶部：当前用户、刷新、退出登录。
- 主区上方：PDF 上传面板。
- 主区下方：任务列表。

任务列表列建议：

| 列 | 来源字段 | 说明 |
|---|---|---|
| 任务 ID | `id` | 可点击进入详情 |
| 模式 | `mode` | MVP 默认直接转 Word |
| 状态 | `status` | badge |
| 阶段 | `stage` | 阶段文案 |
| 进度 | `progress` | 进度条或数字 |
| 错误 | `error_code` | 仅失败时显示 |
| 创建时间 | `created_at` | 排序由后端默认处理 |
| 更新时间 | `updated_at` | 判断任务是否在推进 |
| 操作 | `id/status` | 查看、下载、重试 |

### 3.3 任务详情页

内容：

- 任务基础信息。
- 状态和阶段进度。
- 源文件和请求快照摘要。
- 错误详情。
- 操作区：刷新、下载、重试。
- 事件时间线。

轮询规则：

- `pending`、`queued`、`running` 时轮询详情和事件。
- `succeeded`、`failed`、`canceled` 时停止轮询。
- 页面隐藏或离开时停止轮询。

## 4. 目录结构建议

```text
frontend/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.ts
    App.vue
    api/
      client.ts
      auth.ts
      files.ts
      documentJobs.ts
      types.ts
    router/
      index.ts
    stores/
      auth.ts
    layouts/
      AppLayout.vue
    pages/
      LoginPage.vue
      JobsPage.vue
      JobDetailPage.vue
    components/
      PdfUploadPanel.vue
      JobTable.vue
      JobStatusBadge.vue
      JobProgress.vue
      JobActions.vue
      JobEventTimeline.vue
      ApiErrorAlert.vue
    utils/
      errors.ts
      format.ts
      upload.ts
    styles/
      main.scss
```

## 5. 组件拆分建议

| 组件 | 职责 | 备注 |
|---|---|---|
| `AppLayout` | 受保护页面布局 | 简化侧栏，只保留工作台导航 |
| `PdfUploadPanel` | 文件选择、基础校验、上传授权、上传内容、创建任务 | 内部状态较多，独立封装 |
| `JobTable` | 任务列表展示和分页 | 不承担 API 细节 |
| `JobStatusBadge` | 状态颜色和文案 | 避免各页重复映射 |
| `JobProgress` | 阶段和进度展示 | 详情页和列表可复用 |
| `JobActions` | 下载、重试、刷新 | 根据状态控制按钮 |
| `JobEventTimeline` | 事件流展示 | `level=error` 高亮 |
| `ApiErrorAlert` | 统一错误展示 | 展示 message、code、trace id |

## 6. 状态管理方案

### 6.1 Pinia 全局状态

`stores/auth.ts` 保存：

- `token`
- `user`
- `isAuthenticated`
- `login()`
- `logout()`
- `loadCurrentUser()`

持久化建议：

- token 存 `sessionStorage` 或 `localStorage`。
- MVP 可用 `localStorage` 简化刷新恢复。
- 退出登录时清理 token 和用户信息。

### 6.2 页面局部状态

- 上传进度、当前选择文件、上传错误：保留在 `PdfUploadPanel`。
- 列表分页、状态筛选：保留在 `JobsPage`。
- 详情轮询、事件加载：保留在 `JobDetailPage`。

### 6.3 服务端数据

MVP 可以直接用 Vue `ref` + API 调用管理。若后续页面增多，再引入 TanStack Query for Vue。

## 7. API 对接清单

### 7.1 Auth API

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/v1/auth/login` | 登录 |
| `GET` | `/api/v1/auth/me` | 获取当前用户 |

登录响应关键字段：

- `access_token`
- `expires_in`
- `role`
- `user_id`
- `username`
- `tenant_id`
- `company_id`

### 7.2 Files API

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/v1/files/upload-url` | 获取上传授权 |
| `PUT` | `/api/v1/files/{file_id}/content` 或返回的 `upload_url` | 上传 PDF 内容 |
| `GET` | `/api/v1/files/{file_id}` | 查询文件元数据 |

注意：

- `POST /files/upload-url` 使用本项目 API client。
- 真正上传内容时要按后端返回的 `upload_url`、`method`、`headers` 执行。
- 如果未来返回 S3 presigned URL，不应自动附带 Bearer token。

### 7.3 Document Jobs API

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/v1/document-jobs` | 创建任务 |
| `GET` | `/api/v1/document-jobs` | 任务列表 |
| `GET` | `/api/v1/document-jobs/{job_id}` | 任务详情 |
| `GET` | `/api/v1/document-jobs/{job_id}/events` | 任务事件 |
| `POST` | `/api/v1/document-jobs/{job_id}/retry` | 重试失败任务 |
| `GET` | `/api/v1/document-jobs/{job_id}/download-url` | 获取结果下载链接 |

MVP 创建任务请求：

```json
{
  "source_file_id": "file_xxx",
  "mode": "direct_pdf_to_word",
  "document_language": "auto"
}
```

英译中实验预留请求：

```json
{
  "source_file_id": "file_xxx",
  "mode": "en2zh_pdf_to_word",
  "document_language": "en",
  "debug_full_text": false
}
```

## 8. Axios client 设计

### 8.1 请求头

- 对本项目 API 自动添加 `Authorization: Bearer <token>`。
- 登录接口不要求 token。
- 外部上传 URL 不走默认 client，避免错误添加认证头。

### 8.2 成功响应

后端成功响应直接返回业务 schema。前端 API 函数直接返回 typed data：

```ts
const user = await authApi.me()
const jobs = await documentJobsApi.list({ page: 1, page_size: 20 })
```

### 8.3 错误归一化

前端统一归一化为：

```ts
type ApiClientError = {
  status?: number
  code?: string
  message: string
  traceId?: string
  raw: unknown
}
```

字段来源：

- `status`: HTTP status。
- `code`: `response.data.error_code` 或 `response.data.error.code`。
- `message`: `response.data.detail` 或 `response.data.error.message`。
- `traceId`: `response.data.error.trace_id`。

### 8.4 401 / 403 处理

- 401：清理登录态，跳转 `/login`。
- 403：展示无权限，不自动退出。
- `token_expired`：提示登录已过期。

## 9. 权限与鉴权处理

| 场景 | 前端行为 |
|---|---|
| 未登录访问受保护页 | 跳转 `/login` |
| token 过期 | 清理登录态，跳转 `/login` |
| operator 访问自己的任务 | 正常展示 |
| operator 访问无权限任务 | 展示 403 |
| admin 访问同 tenant/company 任务 | 按后端返回展示 |
| admin 配置管理 | MVP 不提供入口 |

前端不保存 `ADMIN_TOKEN`、`X-Jobs-Token` 或 `X-Admin-Token`。

## 10. 加载态、空态、错误态处理

| 区域 | 加载态 | 空态 | 错误态 |
|---|---|---|---|
| 登录 | 按钮 loading | 不适用 | 登录失败提示 |
| 上传 | 授权中、上传中、创建任务中 | 未选择文件 | 文件非法、上传失败、创建失败 |
| 任务列表 | 表格 loading | 暂无任务 | 加载失败，允许重试 |
| 任务详情 | 骨架屏或 loading | 不适用 | 404、403、网络错误 |
| 事件流 | loading | 暂无事件 | 加载失败，允许重试 |
| 下载 | 按钮 loading | 未完成时禁用 | 下载授权失败、任务未完成 |

## 11. 响应式与可访问性

- 桌面优先，兼容平板。
- 小屏下任务表格可切换为卡片式列表。
- 状态不可只用颜色表达，必须有文字。
- 上传控件支持键盘触发。
- 按钮禁用时通过 tooltip 或文案说明原因。
- 表单输入需要 label 和明确校验信息。
- 轮询不应导致焦点跳动或页面布局频繁重排。

## 12. 分阶段开发计划

### 阶段 1：工程骨架

目标：前端可启动并能路由到登录和空工作台。

任务：

- 创建 `frontend/` Vite Vue TS 工程。
- 安装 Element Plus、Pinia、Vue Router、Axios。
- 建立基础目录结构。
- 实现 `/login`、`/jobs`、`/jobs/:jobId` 静态页面。

验证：

- `npm run dev` 可启动。
- 三个路由可访问。
- `npm run build` 可通过。

### 阶段 2：鉴权和 API client

目标：打通登录态。

任务：

- 实现 `api/client.ts`。
- 实现 `api/auth.ts`。
- 实现 `stores/auth.ts`。
- 实现路由守卫。
- 处理 401、403 和后端错误结构。

验证：

- 正确账号能进入 `/jobs`。
- 错误密码展示后端错误。
- token 过期后回到 `/login`。

### 阶段 3：任务工作台

目标：用户能看到任务列表并刷新。

任务：

- 实现 `documentJobsApi.list()`。
- 实现 `JobTable`、`JobStatusBadge`。
- 实现分页和状态筛选。
- 实现空态和加载失败状态。

验证：

- `/jobs` 能展示后端任务列表。
- 空列表展示上传入口和空态。
- 加载失败可重试。

### 阶段 4：上传和创建任务

目标：打通 PDF 上传到任务创建。

任务：

- 实现 `filesApi.createUploadUrl()`。
- 实现上传内容工具函数。
- 实现 `documentJobsApi.create()`。
- 实现 `PdfUploadPanel`。
- 上传成功后跳转详情页。

验证：

- 合法 PDF 可创建 `direct_pdf_to_word` 任务。
- 非 PDF、超大小、上传失败不创建任务。
- 后端 400/413/409 错误能展示。

### 阶段 5：任务详情、轮询和事件

目标：用户能追踪长任务。

任务：

- 实现 `documentJobsApi.get()` 和 `listEvents()`。
- 实现 `JobProgress` 和 `JobEventTimeline`。
- 实现详情页轮询。
- 终态停止轮询。

验证：

- running 任务自动刷新。
- 事件流按时间展示。
- failed 任务显示失败阶段和错误。

### 阶段 6：下载和重试

目标：任务闭环完整。

任务：

- 实现 `documentJobsApi.createDownloadUrl()`。
- 实现 `documentJobsApi.retry()`。
- 实现 `JobActions`。
- 下载链接每次点击时重新获取。

验证：

- succeeded 任务可下载 Word。
- 未完成任务下载显示后端 conflict。
- failed 任务可重试或展示不可重试原因。

### 阶段 7：验收打磨

目标：达到内部可用。

任务：

- 补齐状态文案和错误码映射。
- 调整响应式布局。
- 补充最小 smoke 测试或手工验收清单。
- 预留英译中 feature flag，但默认关闭。

验证：

- 按前端需求文档验收标准逐项检查。
- 至少完成一次真实或测试后端的端到端流程。

## 13. 风险与验证方式

| 风险 | 影响 | 验证方式 | 处理建议 |
|---|---|---|---|
| 上传 URL 既可能是本地代理，也可能是 S3 presigned URL | 全局 axios 可能错误添加 token | 用返回的 `upload_url/method/headers` 做上传测试 | 上传函数单独实现，不复用默认 API client |
| 任务长时间停在 `running/parsing` | 用户误以为页面卡死 | 用 fake 或真实 MinerU pending 场景验证 | 展示事件和更新时间，提供手动刷新 |
| 下载 URL 过期 | 用户下载失败 | 等待过期后点击旧 URL 验证 | 每次点击下载都重新请求 URL |
| 错误码未产品化 | 用户看不懂失败原因 | 用 400/401/403/409/413/503 覆盖测试 | 建立错误码文案映射，保留原始 detail |
| 英译中提前暴露 | 用户误用实验能力 | feature flag 默认关闭 | 只保留代码结构和隐藏入口 |
| 前端照搬 fastapiwebadmin 请求合同 | 鉴权和错误处理不兼容 | 登录、401、文件上传联调 | 只借鉴结构，client 按本项目后端重写 |
| 后端接口缺少关键词搜索 | 列表任务多时筛选不足 | 用大量任务列表验证 | MVP 只做状态筛选，后续评估后端 `q` 参数 |

## 14. 最小验收清单

- 登录成功进入 `/jobs`。
- 错误账号密码展示错误。
- 未登录访问 `/jobs` 被重定向。
- 上传合法 PDF 后创建任务。
- 上传非法文件不创建任务。
- 任务列表刷新后仍能看到任务。
- 任务详情能展示事件。
- running 任务自动轮询。
- succeeded 任务能下载 Word。
- failed 任务显示错误并可尝试重试。
- token 过期后回到登录页。

## 15. V2.1 配置版本管理补充实施清单

> V1 任务工作台已完成后，V2.1 进入配置版本管理闭环：Template Profile -> Term Rule Set -> Translation Profile。

### 阶段 1：后端最小合同补齐

目标：先补齐前端工作流必须依赖的可追溯后端合同。

任务：

- 为 Template Version 发布流程持久化验证证据：`verification_job_id`、`verification_note`、`verified_by`、`verified_at`。
- 为 Template Version `publish` 增加必填 `publish_reason`，为 `set-default` 增加必填 `set_default_reason`。
- 新增 Term Rule Proposal 持久化模型和 API，支持 `pending_review`、`approved`、`rejected`。
- Term Rule Proposal 支持新增、编辑、禁用三类意图；编辑和禁用必须保存目标规则快照。
- Admin `approve` proposal 时原子合并到 Term Rule Set draft；合并失败时 proposal 不得进入 `approved`。

验证：

- Template 验证证据刷新页面后仍可查看。
- 未填写验证任务 ID、验证说明或发布原因时，Template Version 不能发布。
- 术语 proposal 刷新页面后仍保留状态、提交人、目标规则快照和审核结果。

### 阶段 2：配置中心和 Template Profile

目标：admin 能完成模板版本验证、发布和设默认；operator 只读可见。

任务：

- 新增静态导航：任务工作台、配置中心、术语建议。
- 新增配置中心待办汇总，只展示配置发布相关事项。
- 实现模板列表、模板详情、版本列表、模板文件下载。
- 实现上传 Template draft version。
- 在 Template Version 页面提供“创建验证任务”入口，仅 admin 可见。
- 发布 Template Version 前强制填写已成功的验证任务 ID 和验证说明。
- 发布和设默认拆成两个显式动作，不提供默认勾选的 publish+default 快捷操作。

验证：

- admin 能完成一次 `Template draft -> 验证任务 -> 发布 -> 设默认`。
- operator 能查看模板和版本，但看不到上传、发布、设默认和禁用操作。
- 普通 `/jobs` 上传不暴露指定 Template Version 选择。

### 阶段 3：术语 proposal 和 Term Rule Set 发布

目标：operator 能提交术语建议，admin 审核后合并到 draft 并发布规则集。

任务：

- 实现 `/term-proposals`，operator 默认“我的建议 + 新建建议”，admin 默认“待审核队列”。
- Operator 新建 proposal 使用轻量表单：变更意图、`source_term`、分类、分段展示建议、说明、可选来源。
- 分类下拉显示中文 `name`，提交 `category_id`。
- 实现有序分段编辑器，每段支持 `plain`、`subscript`、`superscript`。
- 编辑和禁用 proposal 必须选择现有规则；禁用只填写禁用原因，不允许修改 segments。
- Admin 审核页展示当前规则、提交时快照和提议变更；发现冲突时提示，不自动 rebase。
- Term Rule Set 发布页展示 draft 的 `rule_count`、`enabled_rule_count`、`snapshot_hash` 和本次已 approve proposals。

验证：

- operator 能提交一条 `VIN = V/plain + IN/subscript` proposal。
- admin 能 approve 该 proposal，并确认它合并到 Term Rule Set draft。
- admin 能发布 Term Rule Set，新规则进入默认版本。
- rejected proposal 必须填写拒绝原因。

### 阶段 4：Translation Profile 基础管理

目标：admin 能管理翻译配置版本，但不编辑 Prompt 正文。

任务：

- 实现 Translation Profile 列表、详情、draft 查看和基础字段编辑。
- 仅开放 `target_language`、`domain`、`prompt_version`、`model`、`max_pages_per_batch`、`max_chars_per_batch`。
- 实现 publish、set-default、rollback。
- 处理 MySQL resource service 未启用时的 `503` 不可用态。

验证：

- admin 能编辑 draft 并发布 Translation Profile。
- operator 只读可见。
- 页面不提供 Prompt 正文编辑入口。

### 阶段 5：V2.1 端到端验收

目标：证明配置版本管理闭环可追溯、可审核、可回滚。

任务：

- 执行 Template 端到端验收：admin 完成一次 `Template draft -> 验证任务 -> 发布 -> 设默认`。
- 执行术语端到端验收：operator 提交 `VIN = V/plain + IN/subscript` proposal，admin approve 并发布 Term Rule Set。
- 覆盖 403、409、503、表单缺失、冲突提示和刷新恢复。

验证：

- Template 验证证据、发布原因和设默认原因都能在后端追溯。
- Term proposal 的提交、审核、合并、发布全链路状态可追溯。
- operator 无法执行 admin-only 操作。
