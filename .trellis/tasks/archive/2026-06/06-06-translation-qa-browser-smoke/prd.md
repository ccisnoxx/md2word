# Translation QA Browser Smoke

## Goal

为 Phase 3 Translation QA 页面做一次浏览器级 smoke 验证，覆盖现有 QA 页面加载、segment 展开、术语 trace、AI call-level evidence、debug archive 缺失提示和 direct job 不误导显示 QA。

本任务只做前端/browser 验证和必要的小修复，不运行 `pdf-mineru` 解析、翻译 provider 或 Word 生成主流程。

## Requirements

- 使用 mock API 或前端测试 fixture 构造 smoke 数据，优先避免真实后端任务执行。
- 覆盖 `en2zh_pdf_to_word` 可用 QA 任务：
  - 页面能加载任务摘要和 QA 复核表单。
  - 片段表能显示 evidence status 和术语命中数。
  - 展开片段能看到匹配的术语 trace。
  - AI calls 显示为任务级 metadata-only / call-level evidence，不伪装成片段级证据。
- 覆盖 debug archive 缺失或不可用状态：
  - 源文/AI 译文对照缺失提示清楚。
  - 不把缺失 debug archive 误报为页面失败。
- 覆盖 direct job 或 unsupported mode：
  - QA 页面提示不适用。
  - 不展示误导性的翻译 QA 证据。
- 如果 smoke 发现 UI 问题，只做小修复；不扩大到新功能。

## Acceptance Criteria

- [x] smoke 数据源明确，不依赖 PDF 解析、翻译 provider 或 Word 生成。
- [x] browser/front-end smoke 能验证可用 QA 任务的 segment trace 展开。
- [x] smoke 能验证 debug archive 缺失提示。
- [x] smoke 能验证 unsupported direct job 不误导。
- [x] 如有 UI 小修复，记录具体修复和验证结果。
- [x] 验证结果写入 `implement.md`。

## Non-goals

- 不新增后端 API。
- 不新增持久化 QA 状态能力。
- 不做浏览器自动化框架的大规模引入。
- 不做段落级保存、自动评分、proposal CRUD 或列表筛选改造。
