# Translation Term Set Management

## Goal

补齐 Admin 侧 Translation Term Set 轻量管理入口，让管理员能围绕现有 `en2zh` 翻译术语集完成版本查看、CSV 导入/导出、draft 发布、默认版本切换和 rollback。

本任务已完成轻量管理入口和 API 合同落地。本文件于 2026-06-04 做状态一致性修正，避免 archived task 与当前实现不一致。

## Requirements

- 管理对象限定为路线图中的 Translation Term Set，不扩展到完整术语规则 CRUD 工作台。
- 后端复用现有 `TranslationTermSetVersionService` 的 draft、publish、set-default、rollback、import/export 能力；只补必要 API 包装和响应模型。
- 前端新增 Admin-only 配置中心页面，和现有 `TermRuleSetPage` / `TranslationProfilesPage` 保持同类交互风格。
- CSV 是本阶段唯一批量编辑入口：支持导入到 draft、查看导入校验/去重报告、导出默认或指定版本 CSV。
- 版本管理只做查看、发布 draft、设默认、rollback；不做真实文件删除，不做 Translation Term 条目逐行 CRUD，不做复杂 diff / 冲突解决工作台。
- 非 MySQL resource service 部署必须清晰显示不可用，后端保持 `503` 能力门控。
- 不触碰 pdf-mineru 解析、翻译 provider 调用、Word 生成主流程，不重跑主流程。
- API 行为保持向后兼容：现有 import/export 路径和响应不破坏。

## Acceptance Criteria

- [x] Admin 可以从配置中心进入“翻译术语集”页面；Operator 不看到该入口且不能访问 admin-only route。
- [x] 页面可以列出 Translation Term Set，查看选中 set 的默认版本、draft 摘要、校验 warnings/errors 和 published versions。
- [x] Admin 可以把 CSV 导入 draft；重复项按 `reject` / `keep_first` 策略返回明确结果，错误不保存无效 draft。
- [x] Admin 可以导出当前默认或指定版本 CSV，导出结果包含 manifest 和 CSV 正文。
- [x] Admin 可以发布 draft、设默认版本、rollback 到已发布版本；rollback 只切默认指针，不生成新版本。
- [x] 后端在 MySQL resource service 不可用时返回 `503`，缺失 set/version 返回 `404`，非法状态或 CSV 返回 `400`。
- [x] 不新增真实删除、文件清理、术语逐行 CRUD、完整 diff/冲突解决、pdf-mineru/翻译/Word 主流程调用。
- [x] 最小验证通过：后端 targeted unittest 覆盖新增管理 API，前端 typecheck/build 通过或明确记录未运行原因。

## Completion Notes

- 前端入口、route、API wrapper 和管理页已落在 `frontend/src/pages/TranslationTermSetPage.vue`、`frontend/src/api/translationTermSets.ts`、`frontend/src/router/index.ts` 和 `frontend/src/pages/SettingsHomePage.vue`。
- 后端 list/detail/draft/import/export/publish/set-default/rollback 已落在 `app/domains/translation/sets_router.py`，核心语义复用 `TranslationTermSetVersionService`。
- `docs/api/translation-term-sets.md` 和 `docs/api/openapi.json` 已记录对应 API 合同。
- `tests/test_fastapi_jobs_backend.py` 已覆盖 Translation Term Set 管理 API、CSV duplicate import/export、`503` 能力门控、rollback 默认指针，以及 rollback 不改变既有 job resource snapshot。
- 当前仍未覆盖完整 diff、冲突解决工作台、批量审核联动和逐条 Translation Term CRUD；这些不是本 archived task 的完成条件。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- 父路线图里该子任务属于 later task：`翻译术语集列表、详情、导入导出、版本、默认、回滚`。
