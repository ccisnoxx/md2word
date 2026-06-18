# md2word frontend SaaS UI main flow

## Goal

完成 md2word 前端主链路的第一轮产品化 SaaS UI 改造，让 `/jobs`、`/jobs/new`、`/jobs/:id` 在视觉层级、页面壳层、表格、表单、状态反馈和动作区上呈现为同一个成熟的内部 SaaS 产品。改造方向参考 Stripe / Linear 的精致、克制、专业表达，但不引入新 UI 库、不替换 Element Plus，并保持现有业务行为不变。

## What I Already Know

- 产品栈是 Vue 3 + Element Plus + SCSS，前端脚本位于 `frontend/package.json`。
- 本轮范围限定在主链路：`AppLayout`、`JobsPage`、`JobTable`、`JobCreatePage`、`PdfUploadPanel`、`JobDetailPage`、`JobActions`、`JobStatusBadge`、`JobProgress`。
- 第一轮不碰设置、术语、系统状态深层页面；这些页面只通过全局壳层和共享 token 被动获得基础一致性。
- 现有 `frontend/src/styles/main.scss` 只有少量全局规则，`JobsPage.vue`、`PdfUploadPanel.vue`、`JobDetailPage.vue` 内存在较多局部颜色、间距、圆角、边框和阴影值。
- 现有主链路业务已经包含筛选、批量操作、上传、配置摘要、创建任务、详情诊断、轮询、下载、重试、克隆、取消、归档、删除等行为，本任务不改变这些语义。
- 现有 smoke 测试 `frontend/tests/smoke/core-flow.spec.ts` 覆盖 `/jobs`、`/jobs/new`、`/jobs/:id` 相关核心行为，可作为 UI 改造后的行为回归基线。

## Requirements

- 建立项目自己的视觉层：
  - 在现有 SCSS 体系内统一颜色、间距、圆角、边框、阴影、字体层级等 design tokens。
  - token 需要能覆盖 Element Plus 组件外壳、主链路自定义模块和状态反馈，不新增 UI 库。
  - 视觉基调采用克制专业的 SaaS 风格：浅色为主、低饱和中性色、清晰蓝色主操作、少量语义色，避免大面积渐变、装饰性背景和过度营销化布局。

- 统一产品壳层：
  - `AppLayout` 统一导航、用户区、面包屑、页面宽度和主内容 padding。
  - 保留现有路由、权限过滤、登出、面包屑和移动端导航行为。
  - 页面容器需要支持主链路的列表页、创建页和详情页，不让各页面各自定义冲突的最大宽度与背景。

- 统一主链路页面模板：
  - `/jobs`、`/jobs/new`、`/jobs/:id` 使用一致的页面标题区、辅助说明、工具栏、内容面板、表格、表单和状态反馈样式。
  - 标题区应该是工作台式信息架构，不做 landing-page hero。
  - 工具栏、筛选区、批量操作条、空状态、提示条和下载链接提示需要在密度、边框、间距、按钮层级上统一。

- 改造 `/jobs` 列表体验：
  - 保留现有搜索、状态筛选、QA 筛选、高级筛选、快捷筛选、筛选 chip、批量操作、状态汇总、自动刷新提示和空状态。
  - `JobTable` 表头、行高、固定操作列、状态与进度列、异常列、分页区需要与整体 token 对齐。
  - 表格在窄屏不产生破坏性横向溢出；必要时保持可滚动表格容器。

- 改造 `/jobs/new` 创建体验：
  - 保留 `PdfUploadPanel` 的文件校验、单文件上传、模式选择、配置摘要、管理员配置、P0 readiness 阻断、提交状态和创建成功跳转。
  - 上传面板、步骤条、配置摘要、管理员配置区和 footer 操作需要与主链路面板样式一致。
  - 创建页宽度保持聚焦，不强行拉满到列表页宽度。

- 改造 `/jobs/:id` 详情体验：
  - 保留详情页现有 tabs、任务处置、概览、诊断、上下文、文件、事件、重试/克隆弹窗、轮询和所有动作可用性逻辑。
  - `JobActions` 在详情标题区保持清晰的主次动作层级，不能因视觉改造改变可点击条件、tooltip 原因或 loading 状态。
  - `JobStatusBadge` 和 `JobProgress` 使用统一状态色、标签密度、进度条高度和文本层级。

- 保持业务行为不变：
  - 不修改 API payload、路由定义、权限检查、store、上传流程、轮询流程、可用动作判断、错误归一化或后端契约。
  - 不新增静默 fallback，不隐藏错误，不把后端返回的可用性判断改为前端推断。

## Acceptance Criteria

- [ ] `frontend/src/styles/main.scss` 或等价样式入口提供统一 design tokens，主链路不再主要依赖页面内重复硬编码颜色、阴影、圆角和间距。
- [ ] `AppLayout` 的导航、面包屑、页面宽度、主内容 padding 和移动端布局统一，且现有导航权限过滤和登出行为不变。
- [ ] `/jobs` 的标题区、指标区、筛选工具栏、批量操作条、状态提示、空状态、表格和分页视觉一致，且现有筛选、批量操作、刷新、下载入口行为不变。
- [ ] `/jobs/new` 的标题区与上传面板符合统一模板，且 PDF 校验、上传授权、文件上传、任务创建、配置摘要和创建成功跳转行为不变。
- [ ] `/jobs/:id` 的标题区、动作区、任务处置、tabs、概览、诊断、上下文、文件和事件区视觉统一，且现有轮询、下载、重试、克隆、取消、归档、删除行为不变。
- [ ] `JobStatusBadge` 与 `JobProgress` 的状态表达统一且可读，仍正确映射 succeeded、failed、running、canceled 等现有状态。
- [ ] 第一轮改造不触及设置、术语、系统状态深层页面的页面级重设计。
- [ ] 移动端约 375px、平板约 768px、桌面约 1024px/1440px 下主链路没有明显文字重叠、按钮挤压、不可读表单或破坏性横向滚动。
- [ ] 运行 `npm run build` 通过；如涉及 smoke 风险，补充运行 `npm run test:smoke` 或至少与用户说明未运行原因。

## Definition of Done

- PRD 经用户确认后，再运行 `task.py start` 进入实现阶段。
- 实现前读取相关前端文件和 Trellis 规范。
- 代码改造范围保持在主链路 UI 与样式组织，不做无关功能、接口或数据层改动。
- 最小验证优先运行 `cd frontend && npm run build`。
- 若 smoke 测试环境可用，优先运行与主链路相关的 `frontend` smoke；如跳过，最终说明原因和剩余风险。
- 最终说明哪些样式 token、页面模板或组件文档/注释被更新；如果只是样式重组且无需新增注释，也明确说明。

## Technical Approach

推荐方向：在现有 Element Plus 基础上建立“项目视觉 token + 主链路模板类 + 组件局部收敛”的轻量视觉层。

- Design tokens:
  - 在全局样式入口定义语义 token，例如 surface、surface-muted、border、text、muted、primary、success、warning、danger、radius、shadow、content-width、spacing。
  - 以中性灰蓝为基础，使用克制蓝色作为主操作，保留 Element Plus 语义色但让主链路显示更一致。
  - 避免一页一个变量命名空间造成第二套视觉系统；页面级变量只保留少量必要 override。

- Layout shell:
  - 收敛 `AppLayout` 的 sticky header、nav active、breadcrumb shell、content shell 和响应式规则。
  - 页面主体使用统一内容宽度；创建页通过局部 modifier 使用更窄聚焦宽度。

- Page template:
  - 抽象为可复用 CSS 类，而非新增 Vue 抽象组件，降低第一轮风险。
  - 使用统一的 page header、panel、toolbar、section header、summary card、empty state、inline alert spacing。
  - 保持 Element Plus 组件，主要通过 SCSS token 和 `:deep()` 做边界内定制。

- Component cleanup:
  - `JobsPage` 优先删除/替换局部 `--jobs-*` token 中与全局重复的部分。
  - `PdfUploadPanel` 和 `JobDetailPage` 的硬编码颜色、边框、阴影、半径改为全局 token。
  - `JobActions`、`JobStatusBadge`、`JobProgress` 统一密度和状态表达，但不改变 props、events 和可用性逻辑。

## Decision (ADR-lite)

**Context**: 当前前端已经使用 Vue 3、Element Plus 和 SCSS，主链路业务完整，但视觉层散落在页面 scoped style 中，导致 `/jobs`、`/jobs/new`、`/jobs/:id` 的成熟度和一致性不足。

**Decision**: 第一轮采用“保留 Element Plus + 建立项目 SCSS tokens + 收敛主链路页面模板”的方式，不引入新 UI 库，不做组件库替换，不做业务逻辑重构。

**Consequences**: 改造风险较低，能快速统一主链路 SaaS 质感；代价是第一轮仍会有少量 `:deep()` 和页面局部样式，后续如继续产品化，可再评估抽取正式布局/面板组件。

## Out of Scope

- 不引入新 UI 库，不替换 Element Plus。
- 不重做登录页、设置页、模板配置、术语规则、术语建议、翻译 QA 队列、系统状态、运维深层页。
- 不改变 API、路由、权限、上传、轮询、任务动作、错误处理、下载链接、后端 readiness 或数据模型。
- 不新增暗色模式专项设计；保留现有 `prefers-color-scheme` 兼容即可，不把 dark mode 作为第一轮验收重点。
- 不做品牌营销页、插画系统、图表体系、复杂动效、主题切换器或白标能力。
- 不做端到端重写、状态管理重构或测试框架调整。

## Technical Notes

- Inspected files:
  - `frontend/src/layouts/AppLayout.vue`
  - `frontend/src/pages/JobsPage.vue`
  - `frontend/src/components/JobTable.vue`
  - `frontend/src/pages/JobCreatePage.vue`
  - `frontend/src/components/PdfUploadPanel.vue`
  - `frontend/src/pages/JobDetailPage.vue`
  - `frontend/src/components/JobActions.vue`
  - `frontend/src/components/JobStatusBadge.vue`
  - `frontend/src/components/JobProgress.vue`
  - `frontend/src/styles/main.scss`
  - `frontend/src/router/index.ts`
  - `frontend/tests/smoke/core-flow.spec.ts`
  - `frontend/package.json`
- Relevant scripts:
  - `cd frontend && npm run build`
  - `cd frontend && npm run test:smoke`
- Existing project specs currently expose `backend` and general thinking guides only; implementation should still read Trellis context before code and use frontend files as the authoritative local convention.
- UI research notes:
  - `ui-ux-pro-max` default design-system result skewed vibrant/immersive, which conflicts with the requested Stripe / Linear direction, so it is not adopted.
  - More relevant search results support Swiss/Minimal SaaS patterns: strict grid, clear hierarchy, high contrast, limited accent colors, restrained effects, responsive tables/forms, visible focus and submit feedback.

## Open Questions

- 请确认本 PRD 是否可以作为第一轮实现依据。推荐直接确认当前范围：先统一主链路视觉层和页面模板，不扩大到其它模块；实现后用 `npm run build` 做最小验证，并视情况补 smoke。
