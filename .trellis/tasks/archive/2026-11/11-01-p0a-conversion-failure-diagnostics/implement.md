# P0a 实施计划

## 1. 有序任务

1. 后端投影：新增 `app/domains/document_jobs/failure_diagnostic.py` 与 `DocumentJobFailureDiagnosticResponse`；`DocumentJobResponse`、`DocumentJobIncidentDiagnosticResponse` 增加可空字段（AC1–AC4）。
2. 接线：详情路由失败任务读取事件并填充；异常中心 `get_diagnostics` 用全量事件填充（AC1–AC3）。
3. 分类：`_classify_failure` 增加错误码优先映射（AC5）。
4. 前端：类型、`utils/failureDiagnostic.ts`、详情页失败摘要、异常中心抽屉（AC6）。
5. OpenAPI：用 `python scripts/ops/export_openapi.py` 更新 `docs/api/openapi.json`（AC7）。

## 2. 计划修改文件

- `app/domains/document_jobs/failure_diagnostic.py`（新）
- `app/domains/document_jobs/schemas.py`、`router.py`、`incidents.py`
- `tests/test_document_job_failure_diagnostic.py`（新）
- `frontend/src/api/types.ts`、`frontend/src/utils/failureDiagnostic.ts`（新）及其测试、`frontend/src/pages/JobDetailPage.vue`、`frontend/src/pages/IncidentTriagePage.vue`
- `docs/api/openapi.json`

## 3. 定向测试

- 投影单测：页级、文档级、旧代事件、缺 `retry_count`、可转换报告、非失败任务、多 blocker 去重排序、截断标志、非法类型收窄。
- API：真实应用 + 失败任务夹具，断言详情与诊断接口字段；列表接口为 `null`；翻译模式 `document_ir_failed` 归 `conversion_failed`；`missing_image_asset` 消息不归 `artifact_missing`。
- 既有：`tests.test_fastapi_jobs_backend` 中异常中心用例、`tests.test_document_job_execution_stages` 新阶段投影用例、`tests.test_document_job_delivery_state_api`、`tests.test_openapi_export`。
- 前端：`vitest` 跑新增 util 测试与 incidents 相关测试，`npm run build`（vue-tsc）。

## 4. 验证边界

- 不跑全仓回归与 Playwright smoke；页面改动为既有卡片内文本行，用单测与类型构建覆盖，未做浏览器视觉核对时如实说明。
- 不涉及 Word 输出，不跑 renderer 专项。

## 5. 回滚点

每步独立可回退；无数据迁移。

## 6. 实施结果与验证（2026-11-01 北京时间）

- 新增：`tests.test_document_job_failure_diagnostic` 8 例通过（含真实 eager Worker：WebP 图片在第 3、5 页触发 `invalid_image_asset`，及缺 content_list 的文档级失败）；`frontend/src/utils/failureDiagnostic.test.ts` 4 例通过；`npm run build`（vue-tsc + vite）通过。
- 既有：fastapi 异常中心队列/批量重试/完整性门禁 3 例通过。`test_document_job_delivery_state_api`、`test_document_job_download_availability_api`、`test_document_job_execution_stages`、`test_saved_views` 共 14 失败/21 错误，与基线 `90ebb407` 失败集合逐条一致（`_build_image_loader` 签名、原子发布端口、默认质量摘要等历史夹具），未处理。
- 前端全量单测：基线 14 失败/211 通过，改后 14 失败/215 通过；14 例均为 `jobRequestRaces.test.ts` 缺 `loadReviewBlocks` 等桩的既有问题。
- AC7 偏差：`docs/api/openapi.json` 在基线已过期（如 `DocumentCurrentReviewResponse` 未导出），整体再生成会混入约 3 万行无关差异；本任务未更新快照，需单独任务处理。
- 未做浏览器视觉核对与 Playwright smoke。
