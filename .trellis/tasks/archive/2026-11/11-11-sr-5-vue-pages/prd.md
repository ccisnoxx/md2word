# 拆分大型 Vue 页面组件

父任务：`11-11-structure-refactor`（对应用户需求第 5 项）。不依赖其他子任务，可以并行推进。

## 目标

参照已有的 `frontend/src/features/job-detail/` 拆分方式（展示面板组件 + `useXxx` composable 管理数据和动作），把超过 2000 行的页面拆成"页面壳 + 区块组件 + composable"，页面行为和 DOM 合同保持不变。

## 范围

第一批（本任务）：

| 页面 | 行数 | 路由 | smoke 覆盖 |
|---|---|---|---|
| `OpsDashboardPage.vue` | 3004（script 1456、template 1197） | system-status 下 | `user-auth`、`core-flow`、`governance-workbench` 中的相关用例 |
| `FileRetentionPage.vue` | 2329 | system-status 下 | 同上（实施第 0 步核实） |
| `JobsPage.vue` | 2106 | `/jobs` | `core-flow`、`workbench-table-preferences`、`accessibility-responsive-gate` |
| `IncidentTriagePage.vue` | 2059 | `/incidents` | `incident-triage` |

第二批（不在本任务范围内，需要用户另行确认）：`TermProposalsPage`（1974）、`TranslationQaQueuePage`（1612）、`TranslationTermSetPage`（1452）、`WordPageStyleDetailPage`（1275）、`AcceptanceCenterPage`（1190）、`TranslationProfilesPage`（1105）。

## 需求

1. 每个页面在 `frontend/src/features/<kebab-page>/` 下建立：区块组件（按页面现有的 `<section aria-label>` / 对话框边界拆分）和 composable（按数据 owner 拆分，一个数据源只有一个 owner）。
2. 页面文件只保留：路由/权限相关逻辑、composable 的组装、区块组件的布局与事件连线。
3. 父子组件之间通过 props 向下传数据、通过 emits 向上传事件；不为拆分页面而新增 Pinia store；API 调用继续通过 `src/api/*`。
4. 样式跟随 DOM 所有者迁移；父组件通过 class prop 传给子组件 DOM 的类，按 ui-quality 规范使用 `:deep(...)`。

## 约束

- 用户可见行为、文案、`aria-label`、smoke 依赖的选择器、URL query 同步、键盘可达性和焦点返回保持不变。
- 不修改共享组件（`src/components/*`）的接口；确实需要修改时，单独说明并先确认。
- 不修改后端，不新增依赖。

## 验收标准

- [ ] 4 个页面文件每个不超过约 400 行；新增的每个组件/composable 不超过约 500 行。
- [ ] `npm run test:unit`、`npm run build` 通过（已知的 `#__PURE__` 和大 chunk 警告除外）。
- [ ] smoke 通过：`core-flow`、`incident-triage`、`workbench-table-preferences`、`accessibility-responsive-gate`、`governance-workbench`、`user-auth`（`--workers=1`）。
- [ ] 按前端规范在 375/768/1024/1440px 宽度下，以及至少一个深色主题样本中，对 4 个页面做截图抽查，没有布局回退。
- [ ] 为每个新 composable 中的非平凡状态逻辑补充或迁移单元测试（只覆盖已有页面行为，不为了覆盖率写测试）。
