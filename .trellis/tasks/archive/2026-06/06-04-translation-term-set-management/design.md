# Translation Term Set Management Design

## Current State

后端已有 `app/domains/translation/sets_router.py`，但只暴露：

- `POST /api/v1/translation-term-sets/{set_id}/import`
- `GET /api/v1/translation-term-sets/{set_id}/export`

`TranslationTermSetVersionService` 已具备内部能力：

- `get_draft`
- `update_draft`
- `import_csv_text`
- `export_csv`
- `publish_draft`
- `set_default_version`
- `rollback`
- `archive`（本任务不暴露）

前端已有 `TermRuleSetPage` 和 `TranslationProfilesPage` 两个相近配置治理页面，但没有 Translation Term Set API wrapper、TypeScript contract、route 或配置中心入口。

## Scope

本任务实现一个轻量 Admin 管理面，不做完整术语规则 CRUD 工作台，也不做 Translation Term 条目逐行编辑。CSV import 是唯一 draft 修改入口。

包括：

- Translation Term Set list/detail/draft API。
- publish draft、set-default、rollback API。
- 保留并接入已有 import/export API。
- 前端新增 `TranslationTermSetPage`，展示 set、draft、版本、导入导出动作。
- 配置中心新增入口，router 新增 admin-only route。
- 后端 API 文档和 OpenAPI snapshot 随合同变化更新。

不包括：

- 不暴露 service 的 `archive`。
- 不做真实文件删除或存储清理。
- 不做逐行新增、修改、禁用、删除 Translation Term UI。
- 不做 term rule CRUD 工作台。
- 不做 diff、批量审核、复杂冲突解决。
- 不调用或重跑 pdf-mineru、翻译 provider、Word 生成流程。

## Backend API Changes

在现有 `/api/v1/translation-term-sets` 下补齐：

| Method | Path | Purpose | Access |
|---|---|---|---|
| `GET` | `/translation-term-sets` | 列出可管理 set | mirror existing config read endpoints |
| `GET` | `/translation-term-sets/{set_id}` | set detail + versions | mirror existing config read endpoints |
| `GET` | `/translation-term-sets/{set_id}/draft` | draft 摘要、entries、validation | mirror existing config read endpoints |
| `POST` | `/translation-term-sets/{set_id}/publish` | 发布 draft | admin actor |
| `POST` | `/translation-term-sets/{set_id}/versions/{version}/set-default` | 切默认版本 | admin actor |
| `POST` | `/translation-term-sets/{set_id}/rollback` | rollback 默认指针 | admin actor |

现有接口保持：

| Method | Path | Current Behavior |
|---|---|---|
| `POST` | `/translation-term-sets/{set_id}/import` | CSV 导入 draft/seed |
| `GET` | `/translation-term-sets/{set_id}/export` | 导出默认或指定版本 CSV |

新增/扩展 schema：

- `TranslationTermEntryResponse`
- `TranslationTermSetListItemResponse`
- `TranslationTermSetListResponse`
- `TranslationTermSetVersionResponse`
- `TranslationTermSetDetailResponse`
- `TranslationTermSetDraftResponse`
- `TranslationTermSetPublishRequest`
- `TranslationTermSetRollbackRequest`

错误语义沿用现有后端规范：

- `503`：`translation_term_set_version_service` 不可用。
- `404`：set 或 version 不存在。
- `400`：CSV、draft、set-default、rollback 业务校验失败。
- `403`：admin-only mutation 缺少权限。

## Backend Service / Persistence Impact

优先复用已有 service 逻辑，避免新增第二套版本规则。

最小后端实现建议：

- 在 `TranslationTermSetVersionService` 增加只读响应组装方法：
  - `list_sets`
  - `get_set_detail`
  - `get_version_entries` 若页面需要指定版本 entries，可先不暴露，导出 CSV 已满足版本查看。
- 在 `TranslationTermRepositoryProtocol` 和 MySQL adapter 增加 `list_sets()`，让 list API 不硬编码 `en2zh`。
- 若测试 fake MySQL adapter 缺少该方法，在 `tests/test_database_job_repository.py` 的 fake cursor 中补最小查询支持。
- 不改 `translation_terms` 表结构，不新增 migration。

## Frontend Page Changes

新增：

- `frontend/src/api/translationTermSets.ts`
- `frontend/src/pages/TranslationTermSetPage.vue`

更新：

- `frontend/src/api/types.ts`
- `frontend/src/router/index.ts`
- `frontend/src/pages/SettingsHomePage.vue`

页面结构：

- 顶部标题、刷新按钮、`503` unavailable alert。
- Set 列表/选择区：显示 `set_id`、`language_pair`、默认版本、版本数。
- Draft 区：显示 base version、term count、snapshot hash、validation warnings/errors；提供 CSV 导入入口。
- Versions 表：显示 version、默认、status、term_count、snapshot_hash、published_at、release_note；提供 export、set-default、rollback。
- Export dialog：展示 manifest 和 CSV 正文，允许用户复制/下载浏览器侧文本文件；不触发后端文件删除或文件管理。

交互约束：

- 仅 Admin route 可见。
- 发布前要求 release note。
- set-default 禁用当前默认版本。
- rollback 必须确认文案说明“只切默认指针，不生成新版本”。
- 导入默认 `target=draft`、`dedupe=reject`，可切 `keep_first`。

## Validation Plan

后端：

- 扩展 `tests/test_fastapi_jobs_backend.py`，使用 fake MySQL runtime 验证 list/detail/draft/publish/set-default/rollback。
- 复用已有 import/export API 测试，不触发 document job 主流程。
- 用项目 conda interpreter 运行 targeted unittest。

前端：

- 运行 `npm --prefix frontend run build` 做 typecheck + Vite build。

文档：

- 更新 `docs/api/translation-term-sets.md`。
- 如 OpenAPI snapshot 受影响，使用项目 conda interpreter 运行 `scripts/ops/export_openapi.py`。
