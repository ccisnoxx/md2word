# Translation Term Set Management Implementation Record

本文件于 2026-06-04 做归档状态一致性修正。当前仓库已经完成本任务规划中的轻量 Translation Term Set 管理能力；下方记录实际落地范围、验证证据和残余缺口。

## Completed Scope

- 后端 expose Translation Term Set 管理 API，复用已有 service 能力。
- 前端提供 Admin-only 轻量管理页面，覆盖 list/detail/draft/import/export/publish/default/rollback。
- API 文档和 OpenAPI snapshot 已包含 Translation Term Set 管理合同。
- Targeted backend tests 已覆盖核心管理 API、错误状态和 job snapshot 不变量。
- 未触碰 pdf-mineru、翻译 provider、Word 生成主流程。
- 未实现真实删除、逐行术语 CRUD、完整 diff/冲突解决。

## Implemented Files

- `app/domains/translation/schemas.py`
- `app/domains/translation/sets_router.py`
- `app/domains/translation/term_set_version_service.py`
- `app/domains/translation/repository.py`
- `app/infrastructure/persistence/mysql/term_assets.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/translationTermSets.ts`
- `frontend/src/pages/TranslationTermSetPage.vue`
- `frontend/src/router/index.ts`
- `frontend/src/pages/SettingsHomePage.vue`
- `docs/api/translation-term-sets.md`
- `docs/api/openapi.json`
- `tests/test_fastapi_jobs_backend.py`

## Verified Behaviors

- `GET /api/v1/translation-term-sets` 可列出 set。
- `GET /api/v1/translation-term-sets/{set_id}` 可查看默认版本和 published versions。
- `GET /api/v1/translation-term-sets/{set_id}/draft` 可查看 draft、entries 和 validation。
- `POST /api/v1/translation-term-sets/{set_id}/import` 支持 `dedupe=reject` 和 `dedupe=keep_first`。
- `GET /api/v1/translation-term-sets/{set_id}/export` 返回 manifest 和 CSV 正文。
- `POST /api/v1/translation-term-sets/{set_id}/publish` 可发布 draft。
- `POST /api/v1/translation-term-sets/{set_id}/versions/{version}/set-default` 只允许 published version 成为默认。
- `POST /api/v1/translation-term-sets/{set_id}/rollback` 只切默认指针，不生成新版本。
- 非 MySQL resource service 返回 `503`。
- 缺失 set/version 返回 `404`。
- 非法 CSV、重复项默认拒绝、非法状态返回 `400`。
- rollback 不改变既有 job 的 `resource_snapshot.translation_term_set`。

## Test Evidence In Repository

- `tests/test_fastapi_jobs_backend.py::test_translation_term_set_version_service_draft_publish_default_rollback_and_archive`
- `tests/test_fastapi_jobs_backend.py::test_translation_term_set_version_service_blocks_errors_and_reports_warnings`
- `tests/test_fastapi_jobs_backend.py::test_translation_term_set_import_export_api_reports_duplicates_and_exports_manifest`
- `tests/test_fastapi_jobs_backend.py::test_translation_term_set_management_api_lists_draft_publishes_defaults_and_rolls_back`
- `tests/test_fastapi_jobs_backend.py::test_translation_term_set_management_api_returns_503_without_mysql_service`
- `tests/test_fastapi_jobs_backend.py::test_translation_term_set_rollback_changes_default_pointer_not_existing_jobs`

## Residual Gaps

- 前端 CSV 导入体验仍需要治理硬化：策略解释、重复项明细展示、CSV 校验失败提示。
- 默认版本切换和 rollback 确认文案还可以更明确地说明 job snapshot 边界。
- 完整 diff、冲突解决工作台、批量审核联动仍需后续独立任务承接。
- 逐条 Translation Term CRUD 仍明确不做。

## Follow-up

后续治理体验硬化由 `.trellis/tasks/06-04-translation-term-set-governance-hardening/` 承接。
