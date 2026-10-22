# TR-406 前端验证记录

日期：2026-10-22

## 实际命令

1. `npm run test:unit -- src/utils/translationBatches.test.ts src/api/documentJobs.test.ts`：通过，2 个文件、8 个测试。
2. `npm run test:unit`：通过，31 个文件、152 个测试。
3. `npm run build`：通过；包含 `vue-tsc --noEmit` 和 Vite 构建。保留现有第三方 `#__PURE__` 注释及大 chunk 警告。
4. `npm run test:smoke -- tests/smoke/core-flow.spec.ts --grep '翻译批次' --workers=1 --output=/tmp/md2word-tr406-smoke-results-20261022-v2`：通过，1 个 mock API smoke。

## 浏览器证据

Smoke 使用现有 Chrome 项目和 Vite `3010`，未启动后端、未调用真实 Provider。测试覆盖 operator/admin、375/768/1024/1440 viewport、1024 深色主题、刷新按钮键盘焦点，以及自动重试、终态失败、split 成功和旧 generation 响应保护。

截图目录：

`/tmp/md2word-tr406-smoke-results-20261022-v2/core-flow-TR-406：翻译批次展示自动重试、终态失败、拆分成功与旧代响应保护-chrome/`

其中包含：

- `translation-batches-operator-mobile.png`
- `translation-batches-operator-tablet.png`
- `translation-batches-operator-laptop.png`
- `translation-batches-operator-desktop.png`
- `translation-batches-admin-mobile.png`
- `translation-batches-admin-tablet.png`
- `translation-batches-admin-laptop.png`
- `translation-batches-admin-desktop.png`

## 未验证项

真实后端 API、MySQL/SQLite/file adapter、真实 Provider、线上部署文件锁和发布/下载写者未在本轮前端验证中运行；这些由后端及部署门禁分别负责。本文件不把 mock API 可用性当作线上合同已验证。

## 文案修正补充

随后将完成态批次提示改为面向操作人员的“所有翻译批次已完成；可用的下载和发布操作请以任务页面提示为准。”，未改变状态、动作或布局。补跑定向 unit：`npm run test:unit -- src/utils/translationBatches.test.ts src/api/documentJobs.test.ts`，8 个测试通过；本次仅文案修正，未重新生成 smoke 截图。
