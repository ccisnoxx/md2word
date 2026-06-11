# md2word 前端开发计划：任务处置闭环与契约护栏

## 业务目标

前端目标是把现有任务列表和任务详情补成 operator 可连续使用的处置工作台。

- 用户能从列表快速识别 active、failed、stale、succeeded、archived。
- 用户进入详情后能看到状态、阶段、错误、trace、文件、callback、可执行动作。
- 禁用动作必须解释原因，且原因可见、可聚焦，不只依赖 hover tooltip。
- 错误诊断可复制，便于转交 admin/运维。
- 前端 types、API client、mock 与后端 OpenAPI 保持一致。

本轮不做营销页，不新增全局复杂状态，不改 Word 质量链路。

## 页面 / 组件

### JobsPage

- 保留筛选上下文：从筛选后的列表进入详情，再返回时保留 query。
- failed 摘要：展示 failed stage、error code、简短 message、更新时间。
- stale 提示：基于 `updated_at` 和当前时间标记长期未更新任务，提供详情入口。
- active refresh：只对 active 视图或活跃任务做后台刷新，避免全页闪烁。
- 409/部分失败：动作冲突后保留错误提示并刷新相关任务。

### JobDetailPage

- 首屏任务处置区展示：
  - status/stage/progress。
  - failed stage/code/message。
  - updated_at/stale hint。
  - trace/request id。
  - files/callback/events 摘要。
  - available actions 和 disabled reasons。
- events/files/callback 独立 loading/error/empty，未加载不得显示成“暂无数据”。
- failed 帮助文案必须跟随 `available_actions.retry.enabled`，不能默认提示可重试。

### JobActions / JobTable

- 行操作和详情操作都从 `available_actions` 渲染。
- disabled reason 直接展示在菜单项或动作说明中，兼容键盘和触屏。
- tooltip 可保留，但不能是唯一信息载体。

### ApiErrorAlert

- 复制诊断增加：
  - route
  - operation
  - job_id
  - status
  - code
  - message
  - trace_id/request_id
  - updated_at
- 503 readiness blocker 显示下一步；operator 无 admin 权限时提示联系 admin。

## 状态管理 / API Client / 类型定义

状态管理：

- 不新增全局 Pinia store。
- 列表刷新、return query、stale 判断、局部 loading 保持页面局部状态。

API client：

- `documentJobsApi` 只访问 `/api/v1/document-jobs`。
- 不新增或复活 `/api/v1/jobs` client。
- command API 遇到 409 后触发调用方刷新。

类型定义：

- `DocumentJob`、`DocumentJobActionAvailability`、`DocumentJobFile`、error body 与 OpenAPI 对齐。
- 修正 smoke mock 中旧字段名，例如旧 storage/file 字段不能继续伪装成当前合同。
- 对 optional 后端增强字段做安全降级。

## Loading / Error / Empty States

- 初次 loading：用页面级 skeleton 或 loading 状态。
- 后台刷新：保留现有数据，显示 subtle refreshing。
- 真实空态：提供创建任务或清除筛选入口。
- 筛选空态：提供清除筛选、查看全部。
- 局部错误：events/files/callback 单独显示，不拖垮详情页。
- 权限错误：说明当前角色不可执行，避免不可达链接。

## Mock / Contract First

- smoke mock 必须以 OpenAPI/types 为准，不允许页面私造字段。
- MVP mock 场景：
  - active job
  - failed job
  - stale-like running job
  - succeeded job with downloadable file
  - archived job
  - 403 forbidden
  - 409 conflict
  - 503 readiness blocker
- release check 中增加或保留核心字段扫描，防止 mock 回到旧 `/api/v1/jobs` 或旧 file 字段。

## 前端接入顺序

1. 修错误归一化和诊断复制。
2. 修 `available_actions` 文案一致性、disabled reason 可见性。
3. 修任务列表 return query、failed/stale 连续处置入口。
4. 修详情 events/files/callback 的局部 loading/error/empty。
5. 修 smoke mock/type 漂移。
6. 接后端新增兼容字段或 recovery preview 链接。
7. 补 unit/smoke，再跑 build。

## 测试计划

Unit：

- nested `error.*` 优先，legacy fallback。
- diagnostic copy 字段完整。
- available_actions retry disabled 时不提示“可重试”。
- disabled reason 可见。
- return query 保留。
- stale 判断。

Smoke：

- operator 登录进入任务列表。
- failed job 进入详情看到诊断。
- disabled action 可见原因。
- 409 conflict 后刷新并显示错误。
- 503 blocker 禁止创建并显示下一步。
- forbidden admin route 说明权限不足。

## 风险、回滚点、验证命令

风险：

- 任务详情首屏信息过多。
- 自动刷新影响用户阅读错误。
- mock 与 OpenAPI 再次漂移。

回滚点：

- 自动刷新可关闭。
- 新诊断复制字段可降级为现有字段。
- recovery preview 链接可在后端未完成时隐藏。

验证命令：

```bash
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```
