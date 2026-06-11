# md2word 前端开发计划：任务处置中心与契约防漂移

## 业务目标

前端本轮目标是把任务工作台从“能查看任务”提升到“能处置任务”：

- 第一轮：失败、停滞、冲突、不可重试、可取消、可归档、可下载这些状态在列表和详情页可读、可操作、可恢复。
- 第二轮：前端 API client、类型、mock、页面 smoke 与 OpenAPI 对齐，避免字段漂移造成页面回归。
- 不做 Word 交付质量、在线编辑、外部客户门户或大型状态管理重构。

## 页面 / 组件

- `JobsPage`：
  - 强化 failed job 摘要，展示 `failed_stage/error_code/error_message`。
  - 增加 running/stale 提示，显示最后刷新时间和后台刷新状态。
  - 行级动作加 pending 状态，防止 cancel/archive/clone/download/retry 重复点击。
  - 批量动作保留 partial failure 展示，并在 409/503 后刷新列表。
  - filtered empty 应给出“清除筛选/创建任务/查看归档”的可执行入口。
- `JobDetailPage`：
  - 首屏增加“任务处置面板”。
  - 面板展示 status、stage、progress、last updated、failed_stage、error_code、error_message、latest trace id、callback summary、关键文件可用性、`available_actions`。
  - running 且疑似停滞时，展示“最后事件时间/最后更新时间/可刷新或联系 admin”的提示。
  - events、files、callback summary 分别有局部 loading/error，不拖垮整页。
- `JobActions`：
  - 每个按钮基于对应 `available_actions` 控制 enabled。
  - disabled reason 必须可见，不能只放在浏览器 title。
  - 操作中按钮显示 pending 并锁定同一 job 的同类动作。
- `ApiErrorAlert`：
  - 继续展示 status、code、message、trace id。
  - 复制诊断信息包含 route、operation、job_id、status、code、trace id。

## 状态管理 / API Client / 类型定义

- 不新增全局 Pinia store。
- 页面局部状态负责：
  - list filters
  - auto refresh
  - per-row action pending
  - detail panel loading
  - local operation error
  - copied diagnostic state
- 可提取小 composable，但只在重复明显时做：
  - document job action pending
  - stale display
  - structured error copy payload
- `frontend/src/api/documentJobs.ts`：
  - 只访问 `/api/v1/document-jobs`。
  - 不新增旧 `/api/v1/jobs` wrapper。
  - 若后端新增 diagnosis projection，新增 typed wrapper/response。
- `frontend/src/api/types.ts`：
  - 补齐或校验 `available_actions`、failure fields、callback summary、structured error。
  - 类型命名与 OpenAPI 保持一致。
- mock：
  - smoke mock 必须覆盖 active/stale/failed/retryable/non-retryable/archived/canceled。
  - mock 中不可省略 `available_actions`。

## Loading / Error / Empty States

- Loading：
  - 首次列表加载、后台刷新、详情主信息加载、events/files/callback 局部加载要分开。
  - 后台刷新不得清空当前列表。
- Error：
  - 401 触发登录态处理。
  - 403 显示权限不足和可联系 admin 的提示。
  - 409 显示任务状态已变化，并自动刷新任务。
  - 503 显示运行时未就绪和系统状态入口。
  - timeout/network error 显示重试入口。
- Empty：
  - 无任务：引导创建任务。
  - 筛选无结果：引导清除筛选。
  - 无失败任务：不展示错误样式。
  - QA 或文件证据不可用：只读空态，不允许提交无效 PATCH。

## Mock 或 Contract First

- 接入顺序必须先更新 mock/type，再写页面依赖。
- contract check 要能发现：
  - OpenAPI 有字段但前端类型缺失。
  - smoke mock 缺少核心 action/failure 字段。
  - 前端 wrapper 指向旧 `/api/v1/jobs`。
- 不要求第一轮引入全量 OpenAPI codegen；可以先扩展 release check 做核心字段校验。

## 前端接入顺序

1. 对齐类型和 mock：补齐失败字段、`available_actions`、callback summary、structured error 场景。
2. 改 `JobActions`：按 action key 显示 disabled reason，增加 pending 防重复。
3. 改 `JobDetailPage`：新增任务处置面板，聚合现有 job/events/files/callback 信息。
4. 改 `JobsPage`：增强 failed/stale 摘要、行级 pending、partial failure 和 empty states。
5. 补 `ApiErrorAlert` 复制诊断 payload，确保 403/409/503 可读。
6. 扩展 smoke 和 unit tests。
7. 扩展 release contract check，保护第二轮防漂移目标。

## 单元测试 / E2E 或 Smoke Test

- Unit：
  - `normalizeApiErrorBody` nested error 优先和 legacy fallback。
  - action disabled reason 选择和展示。
  - stale display 不改变 job status。
  - diagnosis panel 对 failed/running/succeeded/canceled/archived 的展示。
- Smoke：
  - operator 进入任务列表，看到 active auto refresh。
  - failed job 列表摘要和详情处置面板可见。
  - retryable job 可以打开 retry；non-retryable job 显示 disabled reason。
  - cancel/archive/download 在 pending 时不可重复点击。
  - 409 后刷新任务并保留错误提示。
  - 503 显示 readiness blocker 和系统状态入口。

## 前端完成标准

- 用户无需打开浏览器控制台或后端日志即可理解失败任务。
- 详情首屏能回答：当前阶段、是否停滞、失败原因、trace id、可执行动作、禁用原因。
- 前端没有新增旧 `/api/v1/jobs` 依赖。
- 核心 mock 与 OpenAPI 字段一致。
- 关键页面状态都有 loading/error/empty 表达。

## 风险、回滚点、验证命令

- 风险：详情首屏信息过密。回滚点：只保留状态、失败、trace、动作四组信息，events/files 留在下方。
- 风险：pending 锁定过宽影响操作效率。回滚点：按 action + job_id 维度锁定，不锁全表。
- 风险：mock 场景维护成本上升。回滚点：保留核心 6 类任务状态 mock，非核心场景放 unit test。

验证命令：

```bash
cd frontend && npm run test:unit
cd frontend && npm run build
cd frontend && npm run test:smoke
```
