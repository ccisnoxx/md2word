# Term rule workbench

## Goal

为 Admin 提供一个轻量术语规则检查台，用来浏览当前术语规则、按分类/启用状态/关键词定位规则，并用现有模拟接口验证输入文本会如何被术语规则渲染。

本子任务是 `term-rule-workbench` 的最小可交付切片，不实现路线图 Phase 2 中的完整术语规则 CRUD、导入导出、版本 diff 或规则集发布治理扩展；不触碰 pdf-mineru 解析、翻译、生成 Word 主流程。

## Requirements

- 在配置中心为 Admin 暴露“术语规则检查”入口。
- 新增一个 Admin-only 术语规则检查页面，或等价的独立检查区；优先保持配置中心和现有 `TermRuleSetPage` 的治理职责清晰。
- 页面必须复用现有后端能力：
  - `GET /api/v1/term-rule-categories`
  - `GET /api/v1/term-rules`
  - `GET /api/v1/term-rules/{rule_id}`，仅在详情需要时使用
  - `POST /api/v1/term-rules/simulate`
- 页面至少支持：
  - 分类概览：分类名称、启用状态、规则总数、启用规则数。
  - 规则筛选：分类、启用状态、关键词。
  - 规则列表：source term、分类、scope、priority、enabled、segments 预览。
  - 规则详情：显示 segments、custom markdown/html、notes 等只读信息。
  - 规则模拟：输入文本，展示 original、markdown preview、html preview 字符串结果。
- 规则模拟结果不得使用不受控 `v-html` 直接渲染用户输入派生 HTML；先以文本/代码形式展示。
- 保留现有 proposal 审核、规则集 draft/publish/default/rollback 流程，不改变已有后端语义。
- 改动保持小而聚焦，优先复用已有 Vue/Element Plus 页面结构、`TermPreview` 组件和 `termRulesApi` 包装。

## Non-goals

- 不做完整术语规则 CRUD 工作台。
- 不新增、修改、启停或删除规则/分类。
- 不做真实文件删除。
- 不做术语规则导入、导出、同步文件入口。
- 不做 Term Rule Set 版本 diff、冲突分析、发布前校验扩展。
- 不新增后端 API、持久化字段或权限模型。
- 不重跑 pdf-mineru 解析、翻译或 Word 生成主流程。

## Acceptance Criteria

- [x] Admin 在配置中心能进入术语规则检查页面；Operator 不能从导航或直连路由进入。
- [x] 页面加载后显示分类概览和规则列表；后端 503/错误时复用现有错误展示方式。
- [x] 分类、启用状态、关键词筛选会调用现有规则查询接口，并能清除筛选回到默认列表。
- [x] 规则列表展示 `source_term`、分类、scope、priority、enabled 和 segments 预览；点击规则可查看只读详情。
- [x] 模拟区输入文本后调用 `POST /api/v1/term-rules/simulate`，展示 original、markdown preview、html preview 字符串。
- [x] 页面没有新增/编辑/删除/导入/导出/发布按钮，不扩大为完整 CRUD 工作台。
- [x] 后端 API 契约和主流程代码不变；不运行 pdf-mineru 主流程。
- [x] 最小验证通过：`cd frontend && npm run build`，以及 `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-workbench`。

## Notes

- Parent roadmap: `.trellis/tasks/06-03-product-roadmap`.
- Existing frontend has no dedicated Trellis frontend spec; use local Vue/Element Plus patterns from existing pages/components.
- If implementation discovers simulate API wrapper/types are missing, add only the minimal frontend wrapper and TypeScript contracts needed for this page.
