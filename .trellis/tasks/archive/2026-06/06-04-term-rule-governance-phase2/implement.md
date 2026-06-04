# Term Rule Governance Phase 2 Implementation Plan

## Gate

本 parent task 当前只处于 planning。不要运行 `python3 ./.trellis/scripts/task.py start 06-04-term-rule-governance-phase2`，不要修改应用代码，不要运行 pdf-mineru / 翻译 / Word 生成主流程。

实现前需要用户 review 并确认 child task 拆分。确认后为每个 child task 单独创建 Trellis task，并在 child task 内完成实现、验证和归档。

## Parent Checklist

1. [x] 创建 parent task `term-rule-governance-phase2`。
2. [x] 写 PRD 草案。
3. [x] 写 design 草案。
4. [x] 写 implement 草案。
5. [x] 用户 review parent planning。
6. [x] 创建并启动首个 child task。
7. [x] 完成 Child 3 `term-rule-governance-ui` 实现验证，并运行 `task.py finish` 收尾当前任务指针。
8. [x] 创建、规划并启动 Child 4 `term-rule-proposal-boundary-conflicts`。
9. [x] 完成 Child 4 实现验证，并运行 `task.py finish` 收尾当前任务指针。
10. [x] 完成 parent 最终集成验收，结论写入 `acceptance.md`。

## Child Task Map

### Child 1: `term-rule-draft-crud-contract`

目标：提供 draft 内结构化规则 CRUD contract。

预期文件范围：

- `app/domains/term_rules/sets_router.py`
- `app/domains/term_rules/schemas.py`
- `app/domains/term_rules/versioning_service.py`
- `tests/test_fastapi_jobs_backend.py`
- `docs/api/term-rule-sets.md`
- `docs/api/openapi.json`

验收：

- Admin 可以对 draft 规则新增、编辑、启停、移除。
- 写操作只改变 draft，不改变 live runtime YAML。
- Legacy `/api/v1/term-rules` 写保护保持不变。
- 重复 `source_term`、分类缺失、非法 segment 有明确错误。

验证：

- `python -m unittest tests.test_fastapi_jobs_backend -k term_rule_set`
- `python -m unittest tests.test_openapi_export`

### Child 2: `term-rule-set-diff-preflight`

目标：补 draft diff 和发布前校验。

预期文件范围：

- `app/domains/term_rules/versioning_service.py`
- `app/domains/term_rules/schemas.py`
- `app/domains/term_rules/sets_router.py`
- `tests/test_fastapi_jobs_backend.py`
- `docs/api/term-rule-sets.md`
- `docs/api/openapi.json`

验收：

- API 返回 draft vs default/published diff。
- API 返回 preflight report。
- Blocking finding 阻止 publish。
- Warning 可展示但不破坏现有 publish 兼容路径。

验证：

- `python -m unittest tests.test_fastapi_jobs_backend -k term_rule_set`
- `python -m unittest tests.test_openapi_export`

### Child 3: `term-rule-governance-ui`

目标：把结构化 CRUD、diff、preflight 接入 Admin 治理页面。

状态：实现和验证已完成；已运行 `python3 ./.trellis/scripts/task.py finish` 清理当前任务指针。

预期文件范围：

- `frontend/src/pages/TermRuleSetPage.vue`
- `frontend/src/api/termRuleSets.ts`
- `frontend/src/api/types.ts`
- `frontend/src/components/TermSegmentEditor.vue`，仅在需要小修时触碰
- `frontend/src/pages/TermRuleWorkbenchPage.vue`，仅允许加跳转或说明，不允许加入编辑能力

验收：

- Admin 能在 `TermRuleSetPage` 编辑 draft 规则。
- Admin 能查看 diff 和 preflight。
- Publish 前展示校验结果；blocking errors 禁用发布。
- `TermRuleWorkbenchPage` 仍无新增/编辑/删除/导入/导出/发布按钮。
- `cd frontend && npm run build` 通过。

验证：

- `cd frontend && npm run build`
- 可选：用本地 mocked API 做页面 smoke。

### Child 4: `term-rule-proposal-boundary-conflicts`

目标：梳理 proposal 审核与 Admin 直接治理边界，并补结构化冲突提示。

状态：实现和验证已完成；已运行 `python3 ./.trellis/scripts/task.py finish` 清理当前任务指针。

预期文件范围：

- `app/domains/term_rules/proposals_router.py`
- `app/domains/term_rules/proposals_service.py`
- `app/domains/term_rules/schemas.py`
- `frontend/src/pages/TermProposalsPage.vue`
- `frontend/src/api/types.ts`
- `docs/api/term-rules.md`
- `docs/api/openapi.json`
- `tests/test_fastapi_jobs_backend.py`

验收：

- stale target rule approve 返回结构化 `409`。
- 前端稳定展示 `conflicts[]`，不依赖自由文本。
- Proposal 状态仍保持 pending_review。
- 不实现自动 rebase 或批量审核。

验证：

- `python -m unittest tests.test_fastapi_jobs_backend -k term_rule_proposal`
- `cd frontend && npm run build`
- `python -m unittest tests.test_openapi_export`

## Recommended Order

1. 先做 `term-rule-draft-crud-contract`，建立结构化写入 contract。
2. 再做 `term-rule-set-diff-preflight`，作为发布安全门。
3. 然后做 `term-rule-governance-ui`，前端只消费已稳定 contract。
4. 最后做 `term-rule-proposal-boundary-conflicts`，收口 proposal 和治理边界；如果 UI 需要结构化冲突，也可提前到 Child 2 后做。

## Review Gates

每个 child task 启动前都需要确认：

- 是否仍保持 `TermRuleWorkbenchPage` 只读。
- 是否只操作 draft，不直写 live runtime store。
- 是否不运行 pdf-mineru / 翻译 / Word 主流程。
- 是否有最小可观察验证命令。
- 是否有明确 rollback 点。

## Rollback Points

- Child 1 后：保留旧 `PUT /draft/rules` YAML 兜底，移除结构化 CRUD endpoints 即可回退。
- Child 2 后：publish 仍可回到现有校验路径，隐藏 diff/preflight endpoints 即可。
- Child 3 后：隐藏新 UI 分区，保留旧 `TermRuleSetPage`。
- Child 4 后：前端兼容旧自由文本 `409`，后端结构化响应可独立回退。

## Validation Scope

不要运行：

- pdf-mineru 解析。
- 翻译。
- Word 生成主流程。
- 真实文件删除或清理。

应该运行：

- 直接相关 backend unit/API tests。
- OpenAPI snapshot check。
- Frontend build。
- Trellis task validate。
