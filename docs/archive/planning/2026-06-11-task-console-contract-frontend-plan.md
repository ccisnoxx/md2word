# md2word 前端开发计划：任务控制台与契约收敛

## 业务目标

前端第一轮目标是把任务工作台做成 operator 可独立使用的闭环：

- 创建任务前看得懂配置/readiness 状态。
- 任务列表能持续展示 active、failed、stale 和可执行动作。
- 错误展示稳定包含 code/message/trace id。
- API 类型、mock 和后端 OpenAPI 不继续漂移。

## 页面 / 组件

- `PdfUploadPanel.vue`：
  - 展示 config-summary loading/error。
  - readiness blocker 使用中文说明。
  - 配置不可用或 P0 not ready 时禁用创建。
  - 上传失败、创建失败均保留可重试状态。
- `JobsPage.vue`：
  - 支持 `status_group=active` 快捷筛选。
  - 展示 last refreshed、active auto refresh、stale 提示。
  - failed job 显示 `failed_stage/error_code/error_message` 摘要。
  - action conflict 后自动刷新列表且保留错误提示。
- `JobActions.vue`：
  - 禁用按钮的 `disabled_reason` 显式可见，不只依赖 title。
- `JobDetailPage.vue`：
  - 活跃任务轮询降噪：job/events 高频，files/callback 降频或按 tab 刷新。

## 状态管理 / API Client / 类型定义

- 不新增全局 Pinia store；列表刷新、stale、last refreshed 用页面局部状态。
- `documentJobsApi` 只访问 `/api/v1/document-jobs`，不引入旧 `/api/v1/jobs`。
- `DocumentJobListParams` 增加 `status_group?: "active"`。
- `DocumentJobListResponse` 兼容 `filtered_summary` 和 `translation_qa_summary` 缺省。
- `normalizeApiErrorBody` 优先读取 nested `error.*`，再 fallback legacy 字段。

## Loading / Error / Empty States

- 创建页：
  - `configLoading`、`uploading`、`creating`、`blocked`、`retryable failure` 分开。
- 列表页：
  - 初次 loading、后台刷新、filtered empty、stale、bulk partial failure 分开。
- 详情页：
  - events/files/callback 独立 loading/error，避免一个接口失败拖垮整页。
- 错误：
  - 展示 code、message、status、trace id；trace id 可复制。

## 前端接入顺序

1. 修 `normalizeApiErrorBody` 优先级并补 unit test。
2. 接入 readiness blocker 中文映射和创建失败兜底。
3. Jobs 列表 active refresh、stale、failed summary。
4. Job action disabled reason 显式化。
5. JobDetail 轮询降噪。
6. 补 OpenAPI/type/mock contract check。
7. 清理旧 `/api/v1/jobs` 文档引用和 smoke mock 漂移。

## 测试

- Unit：
  - nested `error.*` 优先。
  - legacy `error_code/detail` fallback。
  - trace id/request id 优先级。
- Smoke：
  - operator 登录后进入 Jobs。
  - active 快捷筛选走 `status_group=active`。
  - download conflict 后显示 409 并刷新列表。
  - config-summary 503 时不能创建任务。
  - QA queue 兼容 `translation_qa_status=all`。

## 验证命令

```bash
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```

