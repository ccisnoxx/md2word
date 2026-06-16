# md2word 前端开发计划：产品成熟化

## 业务目标

前端第一轮目标是让工作台在权限、配置、错误和危险动作上更成熟：

- operator/admin 能清楚知道什么可做、为什么不可做、失败后如何转交诊断。
- 配置版本选择不依赖展示 label，和后端 canonical contract 一致。
- QA 不可用时不展示可提交的编辑态。
- 运维/文件清理危险动作有一致的前端门禁提示。

第二轮目标是提升长期维护性：

- 页面状态拆分更清楚。
- API/types/mock 与 OpenAPI 有覆盖清单。
- 关键体验场景有 smoke 或 unit 保护。

## API Contract

- `documentJobsApi` 继续只访问 `/api/v1/document-jobs`。
- `filesApi` 继续走 `/api/v1/files`，上传创建任务时不传 `job_id`。
- Config summary option 使用：
  - `resource_id`
  - `version`
  - `label`
  - 可派生稳定 key，但不把 `label` 当业务值。
- `available_actions` 仍是动作展示依据。
- Ops recovery wrapper 需要清楚区分 preview 和 execute。

## 数据模型 / 状态流

- 页面本地状态继续保存：
  - 上传 step。
  - 列表 query/filter。
  - active refresh/stale。
  - dialog form。
- 不新增大型全局 Pinia store。
- 抽小型 helper/composable：
  - config option encode/decode。
  - API error diagnostic copy。
  - dangerous confirmation completeness。
  - document job action disabled reason。

## 权限 / 错误模型

- 路由权限继续使用后端返回 permissions；fallback 仅保留兼容旧响应。
- 避免新增 `hasPermission([...])` 的歧义用法，多个权限需显式判断 all/any。
- `ApiErrorAlert` 展示并复制：
  - status
  - code
  - message
  - trace_id/request_id
- 403/409/503 分别使用权限不足、状态冲突、运行时未就绪文案。

## 页面 / 组件

- `PdfUploadPanel.vue`
  - 使用稳定 config option key。
  - 不传 `job_id`。
  - readiness blocker 继续阻止创建。
- `JobDetailPage.vue`
  - retry/clone dialog 使用稳定 config option key。
  - 文件、事件、callback 逐步拆为局部 loading/error。
- `TranslationResultQaPage.vue`
  - `qa.available=false` 时复核表单只读或隐藏保存按钮。
  - `saveQa` 前增加 guard。
- `SettingsHomePage.vue`
  - release gate route mapping 使用明确 code -> route 规则。
  - `translation_term` 不被错误映射到 term rule sets。
- `FileRetentionPage.vue`
  - 物理删除确认按钮禁用条件与 cleanup run 对齐。
  - 缺 reason/confirmation 时显示缺失项。
- `ApiErrorAlert.vue`
  - 增加复制诊断信息按钮。
- `JobTable.vue`
  - 第二轮将 disabled reason 从 `title` 升级为可聚焦 tooltip/行内说明。

## 状态管理 / API Client / 类型定义

- 增加 config option helper，保证 create/clone/template validation 共用。
- 前端 type 继续手写维护，但第一轮建立覆盖表：
  - OpenAPI endpoint。
  - wrapper。
  - type。
  - page/component。
  - mock/smoke。
  - status: implemented/deferred/deprecated/no-ui。
- 第二轮评估 OpenAPI type generation 或 release diff checker。

## Loading / Error / Empty States

- 创建页：
  - config loading/error。
  - upload/create failed 可重试。
  - P0 readiness blocked。
- 列表页：
  - 初次 loading。
  - 后台刷新。
  - filtered empty。
  - stale/failed summary。
- 详情页：
  - job load error 不等同于 files/events/callback 局部错误。
- QA：
  - unavailable/unsupported mode/artifact missing/debug expired 都是只读状态。
- Ops/File retention：
  - preview、execute、fake、real 清楚区分。

## 单元测试 / E2E 或 Smoke

- Unit:
  - config option key encode/decode。
  - release gate routing。
  - QA unavailable guard。
  - diagnostic copy payload。
  - dangerous confirmation completeness。
- Smoke:
  - operator core flow。
  - config-summary 503 blocker。
  - QA unavailable readonly。
  - failed job action conflict。
  - admin file-retention dangerous confirm disabled/enabled。
  - admin ops preview vs execute labels。

## Mock 或 Contract First

- Mock 字段以后端 OpenAPI 和 Pydantic schema 为准。
- Smoke mock 至少覆盖：
  - `available_actions`
  - `config-summary.options`
  - `translation_qa.available=false`
  - structured 403/409/503
  - file retention preview hash / confirmation phrase
  - ops recovery preview/execute safety flags

## 前端接入顺序

1. 新增 config option key helper 并接入 create/clone/template validation。
2. 修 QA unavailable 只读 guard。
3. 修 release gate route mapping。
4. 补危险确认禁用态。
5. 增加 `ApiErrorAlert` 诊断复制。
6. 建立 OpenAPI -> frontend coverage 表。
7. 第二轮拆任务详情局部 loading/error。
8. 第二轮补 disabled reason 可聚焦展示和移动端/键盘 smoke。

## 风险、回滚点、验证命令

- Config option key 改动可能影响 mock；回滚点是 helper 兼容 label 和 `resource_id@version`，但提交 payload 只用 canonical 字段。
- QA unavailable guard 可能改变用户已有操作习惯；回滚点是保留说明和任务详情入口，不允许保存。
- File retention 禁用态只是前端体验，后端强校验必须保留。

验证命令：

```bash
cd frontend && npm run build
cd frontend && npm run test:unit
cd frontend && npm run test:smoke
```
