# Frontend Workbench Closeout Fastforward Note

## Context

- Date: 2026-06-03
- Mode: fastforward
- Source requirement: `docs/archive/planning/frontend-workbench-requirements.md`
- Scope: front-end internal PDF -> Word workbench closeout for `/jobs`, `/jobs/:jobId`, login/auth failure handling, and shared API error display.

## Implemented

- 收敛主导航为 `任务工作台`，隐藏配置中心和术语建议的主路径入口。
- 上传入口降级为默认 `direct_pdf_to_word` 单文件创建任务，不再暴露 admin 术语资产版本选择。
- 任务列表保留查看、下载、重试入口；移除取消、归档操作；失败任务重试统一进入详情页带上下文确认。
- 任务详情页移除术语建议、取消、归档、admin 资源选择等扩展流程，保留刷新、下载、重试。
- 任务详情页强化失败解释，展示 `failed_stage`、`error_code`、`error_message`、最近错误事件和 `trace_id`。
- 任务详情页新增 long-running/timeout 提示、成功任务下载提示，并把请求快照折叠为次级排障信息。
- 下载动作显示后端返回的临时链接过期时间。
- 登录守卫在 token 失效或用户加载失败时带 `auth` query 跳转登录页，登录页展示重新登录提示。
- `ApiErrorAlert` 新增 401/403/409/503/timeout 的 operator/admin 处置提示。

## Files

- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/router/index.ts`
- `frontend/src/pages/LoginPage.vue`
- `frontend/src/pages/JobsPage.vue`
- `frontend/src/pages/JobDetailPage.vue`
- `frontend/src/components/PdfUploadPanel.vue`
- `frontend/src/components/JobActions.vue`
- `frontend/src/components/JobTable.vue`
- `frontend/src/components/ApiErrorAlert.vue`

## Verification

- `npm run build` in `frontend/`: passed. Observed existing Vite/Rollup warnings for third-party pure annotations and chunk size; no type or build failures.
- `npm run preview` + Playwright CLI smoke:
  - Opening `http://127.0.0.1:4173/jobs` redirects to `http://127.0.0.1:4173/login?redirect=/jobs`.
  - Login page renders username/password form and workbench copy.
  - Opening `http://127.0.0.1:4173/login?auth=token_expired` renders `登录已过期，请重新登录。`.
  - Only console entry observed was `favicon.ico` 404, unrelated to the workbench flow.

## Residual Notes

- No backend business logic changed.
- Config and proposal pages still exist as direct routes; they are no longer exposed from the main workbench navigation.
