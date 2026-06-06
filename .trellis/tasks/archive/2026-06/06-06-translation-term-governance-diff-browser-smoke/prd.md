# Translation Term Governance Diff Browser Smoke

## Goal

为已实现的 Translation Term Set governance diff/preflight/proposal compatibility 页面做一次浏览器级 smoke 规划，验证真实前端渲染能覆盖核心治理状态，而不重新实现 diff 功能。

## Requirements

- 本任务只覆盖 `TranslationTermSetPage` 的浏览器/front-end smoke。
- 数据来源优先使用浏览器侧 mock API 或测试 fixture；不依赖真实 MySQL、真实后端状态或人工导入 CSV。
- smoke 场景必须覆盖：
  - Translation Term Set 页面能加载。
  - diff summary 显示 added / removed / changed / unchanged。
  - diff row 显示 changed fields、before、after。
  - preflight non-blocked 状态。
  - preflight blocked 状态和 blocking reasons。
  - proposal compatibility compatible / warning / conflict 三类行。
  - 从 proposal 审核页 deep-link 到治理页时，页面能显示 proposal context，并能返回审核页。
- 如果 smoke 发现 UI 问题，只允许记录并另开小修复任务；不要在 smoke 任务内扩大成新功能。
- 不做逐条 Translation Term CRUD，不做 automatic rebase，不做新批量 mutation。
- 不运行 pdf-mineru 解析、真实翻译 provider 或 Word 生成主流程。

## Acceptance Criteria

- [x] browser smoke 能在 mocked/fixture API 下打开 `settings/translation-term-sets`。
- [x] smoke 能验证 diff summary 与至少一条 changed diff row。
- [x] smoke 能验证 preflight blocked 与 non-blocked 两种状态的文案。
- [x] smoke 能验证 proposal compatibility 三类状态和 finding codes。
- [x] smoke 能验证 proposal deep-link context banner 和返回 proposal review 的链接。
- [x] smoke 过程不调用真实解析、翻译、Word 生成主流程。
- [x] 未发现需要开小修复的 UI bug，未在本任务中扩大功能。

## Notes

- 本任务当前仅拆 planning；review 后再 `task.py start` 执行 smoke。
