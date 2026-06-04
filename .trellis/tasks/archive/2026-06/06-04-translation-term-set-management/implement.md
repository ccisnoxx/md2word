# Translation Term Set Management Implementation Plan

本文件是后续实现清单。当前任务仍处于 `planning`，未执行 `task.py start` 前不改产品代码。

## Success Criteria

- 后端 expose Translation Term Set 管理 API，复用已有 service 能力。
- 前端提供 Admin-only 轻量管理页面，覆盖 list/detail/draft/import/export/publish/default/rollback。
- 不触碰 pdf-mineru、翻译、Word 生成主流程。
- 不实现真实删除、逐行术语 CRUD、完整 diff/冲突解决。

## Ordered Steps

1. Backend contracts
   - 在 `app/domains/translation/schemas.py` 添加 Translation Term Set list/detail/draft/version/entry/publish/rollback schema。
   - 验证点：schema 字段和 `models.py` / service dataclass 一一对应，不返回未定义 ad hoc dict。

2. Backend service/repository read support
   - 在 `TranslationTermRepositoryProtocol` 增加必要只读方法，优先 `list_sets()`。
   - 在 `MysqlTranslationTermRepository` 实现对应查询。
   - 在 `TranslationTermSetVersionService` 添加 `list_sets()` / `get_set_detail()` 响应组装。
   - 验证点：不改数据库表结构，不复制 publish/default/rollback 规则。

3. Backend router
   - 在 `app/domains/translation/sets_router.py` 增加 list/detail/draft/publish/set-default/rollback。
   - 继续使用 `_require_translation_term_set_version_service`、`not_found_http_exception`、`bad_request_http_exception`。
   - 验证点：能力门控 `503`、业务错误 `400`、缺失资源 `404`、mutation admin-only。

4. Backend tests
   - 扩展 `tests/test_fastapi_jobs_backend.py` 的 translation term set API 测试。
   - 如 fake MySQL 查询缺失，最小更新 `tests/test_database_job_repository.py`。
   - 验证命令：
     `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`

5. Frontend API contracts
   - 在 `frontend/src/api/types.ts` 添加 Translation Term Set 类型。
   - 新建 `frontend/src/api/translationTermSets.ts`。
   - 验证点：frontend 类型名和后端 response model 对齐。

6. Frontend page and routing
   - 新建 `frontend/src/pages/TranslationTermSetPage.vue`。
   - 更新 `frontend/src/router/index.ts`，新增 `/settings/translation-term-sets` admin-only route。
   - 更新 `frontend/src/pages/SettingsHomePage.vue` 增加入口卡片。
   - 验证点：页面不提供逐行 CRUD 和 archive/delete 操作。

7. API docs / OpenAPI
   - 更新 `docs/api/translation-term-sets.md`。
   - 如 API schema 变化导致 snapshot 过期，运行：
     `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`

8. Frontend verification
   - 运行 `npm --prefix frontend run build`。
   - 若 build 受本任务外环境阻塞，记录阻塞和残余风险。

## Review Gates

- Gate 1: 开始实现前，由用户确认 PRD/design/implement 范围。
- Gate 2: 后端 API + tests 完成后，再进入前端页面。
- Gate 3: 前后端验证通过后，检查是否需要更新 Trellis spec；没有新稳定约定则不更新。

## Rollback Points

- 后端 API 出现合同风险时，可保留 import/export 现状，回退新增 list/detail/publish/default/rollback 路由。
- 前端页面出现范围膨胀时，可只保留入口和只读详情，延后导入/发布动作。
- OpenAPI 更新失败时，不合并 API 变化，先恢复 docs/snapshot 一致性。
