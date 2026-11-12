# 实施计划

工作目录 `frontend/`。

## 检查清单

- [ ] 0. 基线：`npm run test:unit`、`npm run build`、相关 smoke 各运行一次并记录结果；收集 4 个页面的 smoke 选择器清单；在 4 种宽度和深色主题下截图保存到 `validation/baseline/`；逐页写 `research/<page>.md` 定稿拆分边界。
- [ ] 1. `JobsPage`（风险最高，涉及 query 同步和请求竞态）：先抽 composable，再抽区块组件。检查：`test:unit`（含 `jobRequestRaces.test.ts`）、build、`core-flow`、`workbench-table-preferences`。提交。
- [ ] 2. `IncidentTriagePage`。检查：test:unit、build、`incident-triage`。提交。
- [ ] 3. `FileRetentionPage`。检查：test:unit、build、相关 smoke。提交。
- [ ] 4. `OpsDashboardPage`。检查：test:unit、build、相关 smoke。提交。
- [ ] 5. 全量回归：smoke 全集（`--workers=1`）；4 种宽度 + 深色主题截图并与基线对比；`wc -l` 确认行数上限；如有新约定，更新 `.trellis/spec/frontend/index.md`；运行 `trellis-check`。

## 审查关口

每个页面拆完后对照 smoke 选择器清单逐项确认；截图有差异时先找到原因再继续，不累积差异。

## 回滚点

每个页面一次提交，互相独立。
