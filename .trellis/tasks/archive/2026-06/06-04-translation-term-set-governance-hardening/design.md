# Translation Term Set Governance Hardening Design

## Current Implementation

已实现能力：

- 前端：
  - `frontend/src/router/index.ts` 已有 Admin-only `/settings/translation-term-sets` route。
  - `frontend/src/pages/SettingsHomePage.vue` 已有“翻译术语集”入口。
  - `frontend/src/api/translationTermSets.ts` 已覆盖 list/detail/draft/import/export/publish/set-default/rollback。
  - `frontend/src/pages/TranslationTermSetPage.vue` 已有 set 列表、draft 摘要、validation 表、published versions、draft entries、CSV 导入、CSV 导出、发布、设默认、rollback。
- 后端：
  - `app/domains/translation/sets_router.py` 已暴露 list/detail/draft/import/export/publish/set-default/rollback。
  - `app/domains/translation/term_set_version_service.py` 已实现 draft、CSV import/export、publish、set-default、rollback、archive 内部能力。
  - `app/domains/translation/repository.py` 与 `app/infrastructure/persistence/mysql/term_assets.py` 已有 `list_sets()` 和版本读写端口。
  - `sets_router.py` 已将 service 缺失映射为 `503`，`FileNotFoundError` 映射 `404`，`ValueError` 映射 `400`。
- 文档和测试：
  - `docs/api/translation-term-sets.md` 与 `docs/api/openapi.json` 已包含 Translation Term Set 管理 API。
  - `tests/test_fastapi_jobs_backend.py` 已覆盖 import/export duplicate、management API、503、rollback 和 job snapshot 不变。

## Gaps

### Documentation Consistency

归档任务 `.trellis/tasks/archive/2026-06/06-04-translation-term-set-management/` 与实际实现不一致：

- `prd.md` 的所有 checkbox 仍未勾选，但代码、API 文档和测试显示大多数验收项已完成。
- `implement.md` 仍写着“当前任务仍处于 planning，未执行 task.py start 前不改产品代码”，这和实际已落地的前后端实现不一致。
- 需要将归档任务改成“完成记录 + 残余缺口”，避免 Phase 2 后续规划误判为未实现。

### Frontend Experience

当前 `TranslationTermSetPage.vue` 是可用的轻量页面，但治理体验不足：

- CSV 导入：
  - `dedupe` 只有 segmented 控件，没有解释 `reject` 与 `keep_first` 的后果。
  - `lastImportReport` 只在导入 dialog 中显示成功摘要，`loadAll()` 后仍关闭不了或无法沉淀为页面级结果。
  - `duplicates[]` 未以表格展示，Admin 无法快速定位哪些行被丢弃。
  - CSV 校验失败只走全局 `ApiErrorAlert`，没有把“未保存 draft”说清楚。
- CSV 导出：
  - 已支持 manifest + CSV 展示、复制和下载，但页面没有突出“默认导出”和“指定版本导出”的差异。
- 默认切换：
  - 已有确认，但没有说明只影响后续新 job 默认绑定，不改变已创建 job。
- rollback：
  - 文案已说明“不生成新版本”，但未说明“不删除/不修改历史版本，不改变既有 job snapshot”。
  - 当前默认版本仍显示 Rollback 按钮，容易制造无意义操作。
- 错误体验：
  - `503` 有页面级 unavailable alert。
  - `404`、`400`、CSV duplicate reject、CSV validation failure 仍主要依赖通用错误框，缺少针对本页面的 action hint。

### Backend / Contract

后端合同基本满足本轮目标，不建议重构。可考虑的小补强：

- 确认 API 测试覆盖 `400` 非法 CSV header、非法 status/priority/bool、非法 `dedupe` 和 rollback 到缺失 version 的 `404`。
- 如果测试已足够，不改后端代码。
- 不改变 `TranslationTermSetImportResponse` 或错误 envelope，继续使用 FastAPI 默认 `{"detail": ...}`。

### Data Model

不新增表和字段。继续使用：

- `translation_term_sets.default_version`
- `translation_term_sets.draft_version`
- `translation_term_versions.status`
- `translation_terms` rows for version entries
- job `resource_snapshot.translation_term_set`

默认版本切换和 rollback 都只更新 `translation_term_sets.default_version`。既有 job 的 `resource_snapshot` 必须保持不变。

## Proposed Scope

本任务推荐拆成一个小而聚焦的硬化切片：

1. 文档一致性修正：
   - 更新归档 `translation-term-set-management` PRD checkbox。
   - 更新归档 implement 状态为“实际完成 + 验证记录 + 残余缺口”。
2. 前端页面体验补强：
   - 在导入 dialog 中补 dedupe 策略说明。
   - 成功导入后展示 totals 和 duplicates 明细。
   - 失败时按 `status` 和 `message` 给本页面上下文提示。
   - 默认切换/rollback 确认文案补 job snapshot 边界。
   - 当前默认版本禁用 rollback。
3. API 文档小修：
   - 补充 CSV 校验失败时不保存无效 draft。
   - 补充默认切换/rollback 只影响后续默认绑定，不改变已有 job。
4. 最小测试：
   - 如前端只改文案和展示，运行 frontend build。
   - 如补后端边界测试，运行 targeted unittest。

## Explicit Non-goals

- 不做逐条 Translation Term CRUD。
- 不做 Translation Term Set archive/delete UI 或真实文件删除。
- 不做完整 diff、冲突解决、批量审核联动。
- 不引入新的 error envelope 或后端错误框架。
- 不改 job 创建、retry、stage runtime 的 Translation Term Set 绑定逻辑。
- 不运行 pdf-mineru 解析、翻译 provider 或 Word 生成主流程。

## Risk Notes

- `rollback()` 目前复用 `set_default_version()`，可能同时写入 `translation_term_set.set_default` 和 `translation_term_set.rollback` audit event。当前测试只要求存在 rollback，不阻塞本任务；如要调整 audit 语义，应另行评估是否影响审计历史。
- 前端页面缺少组件测试，硬化验证主要依赖 typecheck/build 和人工浏览确认。
- 归档文档修正会触碰 archived task，但只修正 Trellis 状态记录，不代表重新打开旧任务实现。
