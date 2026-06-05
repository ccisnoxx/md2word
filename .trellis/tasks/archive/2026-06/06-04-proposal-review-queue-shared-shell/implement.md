# Proposal Review Queue Shared Shell Implementation Plan

## Gate

本 child task 已执行 `task.py start` 并进入实现阶段。

shared-shell 的前端实现和 smoke 验证已完成；后续不在本 child task 中继续扩展
bulk action 或治理页联动。

## Target Files

1. `frontend/src/pages/TermProposalsPage.vue`
2. `frontend/src/components/TermProposalTable.vue`
3. `frontend/src/components/TranslationTermProposalTable.vue`

## Step Plan

### 1. Refine route and tab helpers in `TermProposalsPage.vue`

- 补齐 `review` 到 `initialActiveTab()` / `applyRouteProposalContext()` 的支持
- 新增 tab helper：
  - `isTermFormTab`
  - `isTranslationFormTab`
  - `isTermQueueTab`
  - `isTranslationQueueTab`
  - `fallbackTabFor`
- 保留现有 form context query 写入逻辑，不改字段名

完成标准：

- `tab=review` 可以稳定打开 term review
- `tab=translation-review` 行为保持不变
- `tab=new` / `tab=translation-new` 不受影响

### 2. Introduce stable per-domain selection ids

- 在页面层新增：
  - `selectedTermProposalId`
  - `selectedTranslationProposalId`
  - `focusNotice`
- 保留现有：
  - `selectedProposal`
  - `selectedTranslationProposal`
- 点击表格行时同时更新对象和 id

完成标准：

- 页面拥有“当前详情对象”和“可恢复的稳定 id”两层状态
- 同 domain 刷新后可恢复当前选中项

### 3. Refactor queue loading into load + resolve-focus

- 保留 `loadActiveTab()` 作为入口，但将其拆成两个阶段：
  - 列表加载
  - focus 解析与恢复
- 解析顺序固定为：
  - route `proposal_id`
  - remembered selected id
- 只对 `review` / `translation-review` 执行 fallback
- 每次 route 解析最多允许一次 fallback

完成标准：

- `proposal_id` 存在且目标在当前列表中时，自动选中
- `proposal_id` 存在但目标不在 review 队列时，自动切到 `all` / `translation-all`
- fallback 后仍不可见时，detail panel 清空并展示 `focusNotice`

### 4. Add selected-row contract to both table components

- 为 `TermProposalTable.vue` 增加 `selectedId` prop
- 为 `TranslationTermProposalTable.vue` 增加 `selectedId` prop
- 用统一 class 高亮选中行
- 保持原有 `@select` 事件不变

完成标准：

- 详情面板对应的行在列表里始终有视觉反馈
- 不引入 checkbox 或多选逻辑

### 5. Wire tables back into page template

- `mine` / `review` / `all` 三个 term table 都传入 `selectedId`
- `translation-mine` / `translation-review` / `translation-all` 三个 translation table 都传入 `selectedId`
- `focusNotice` 只在 queue 场景显示，不污染 form 场景

完成标准：

- 任一 queue 中点选 proposal 后，列表和 detail panel 同步
- 刷新后同步仍成立

### 6. Non-regression pass

- 确认任务详情页进入 proposal form 的 query 上下文不变
- 确认来源任务链接仍跳到 `job-detail`
- 确认 approve / reject / approve-and-publish 按钮状态逻辑不变

## Minimal Verification

1. `cd frontend && npm run build`
2. 手工 smoke
   - `tab=review` + pending term rule proposal
   - `tab=review` + non-pending term rule proposal
   - `tab=translation-review` + pending translation proposal
   - `tab=translation-review` + non-pending translation proposal
   - 任一 queue 手动点选后刷新
   - `tab=new` / `tab=translation-new` 来源任务上下文回归

## Explicitly Out Of Scope

- backend endpoint 变更
- batch toolbar / bulk mutation
- review page 到治理页的 CTA
- Translation / Term Rule domain-specific conflict UI
- router 层 query 同步重构

## Review Notes

- 不新增 backend endpoint
- 不新增 batch action
- 不引入泛化 queue framework
- 实现顺序必须先做 shared shell，再做两个 domain child task

## Implementation Result

已实现：

- `TermProposalsPage.vue`
  - 支持 `tab=review` / `tab=translation-review` 的 route deep-link。
  - 支持 `proposal_id` 定位当前 proposal。
  - 支持 `review -> all` 与 `translation-review -> translation-all` 的单次 fallback。
  - 支持刷新后根据 remembered selected id 恢复选中行和 detail panel。
  - 增加 `focusNotice`，用于说明 deep-link fallback 或未命中。
- `TermProposalTable.vue`
  - 新增 `selectedId` prop。
  - 根据 `selectedId` 高亮当前选中行。
- `TranslationTermProposalTable.vue`
  - 新增 `selectedId` prop。
  - 根据 `selectedId` 高亮当前选中行。

明确未做：

- 未新增 backend endpoint。
- 未引入多选、batch toolbar 或 bulk mutation。
- 未增加 review page 到治理页的 CTA。

## Verification Result

已执行：

- `cd frontend && npm run build`
  - 通过。
- 真实浏览器 smoke：
  - 使用 Vite dev server + Playwright CLI。
  - 因本机 `.env` 指向 `JOBS_REPOSITORY_BACKEND=mysql`，当前 Python 环境缺 `PyMySQL` 且本机
    `127.0.0.1:3306` 无 MySQL 服务，真实后端 proposal API 无法启动。
  - smoke 改用真实浏览器 + 前端 API mock，验证本 child task 负责的 shared-shell 交互闭环。

通过的 smoke 场景：

- `tab=review&proposal_id=tr-smoke-pending` 自动选中 Term Rule 待审核 proposal。
- 点击“刷新”后，选中行和 detail panel 保持。
- `tab=review&proposal_id=tr-smoke-rejected` 自动回退到 `all` 并选中目标 proposal。
- `tab=translation-review&proposal_id=tt-smoke-pending` 自动选中 Translation 待审核 proposal。
- `tab=translation-review&proposal_id=tt-smoke-rejected` 自动回退到 `translation-all` 并选中目标 proposal。
- `tab=new` 来源任务上下文正确渲染。
- `tab=translation-new` 来源任务上下文正确渲染。
- 浏览器 console error 为 `0`。

残余风险：

- 本轮没有验证真实 MySQL-backed proposal API 与浏览器的端到端联调；该验证需要可用 MySQL
  服务和 `PyMySQL` 依赖。
