# Frontend SaaS UI Second Round QA And Settings

## Goal

完成 md2word 前端产品化第二轮：把翻译 QA 队列、任务级翻译 QA 结果页、配置中心主要入口页接入第一轮已经建立的 Stripe / Linear 型内部 SaaS 视觉层，让这些页面在标题区、内容面板、表格、表单、状态反馈和操作栏上与 `/jobs` 主链路保持一致，同时保持现有业务行为不变。

## What I Already Know

- 第一轮主链路任务已归档：`.trellis/tasks/archive/2026-06/06-18-frontend-saas-main-flow-ui/`。
- 第一轮实现 commit `c56793a0` 只集中在主链路 UI、`AppLayout` 和 `frontend/src/styles/main.scss`，未观察到 API/store/router/backend 合同改动。
- 第一轮已建立 `--app-*` semantic tokens 和页面 shell 类：`app-page`、`app-page-shell`、`app-page-header`、`app-panel`、`page-title`、`page-description` 等。
- 本轮推荐范围来自用户确认方向：
  - `TranslationQaQueuePage`
  - `TranslationResultQaPage`
  - `SettingsHomePage`
  - 配置中心主要入口页相关入口/总览组件
- `ConfigTodoSummary` 直接服务于 `SettingsHomePage` 的配置中心入口体验，应纳入本轮范围。
- 本轮不引入新 UI 库，不替换 Element Plus，不改变业务行为。
- 第一层验证优先使用 `cd frontend && npm run build`。
- 不执行 `npx playwright install chromium`，不因 Playwright Chromium 下载失败判定任务失败。
- 如必须跑 Playwright smoke，只能复用本机已有 Chrome/Chromium；若本机浏览器不可用，则跳过 smoke 并说明原因。

## Round 1 Acceptance And Residual Issues

验收结论：第一轮主链路 UI 改造可作为第二轮视觉基线继续复用。

证据：

- `frontend/src/styles/main.scss` 已提供统一 design tokens 和页面 shell 类。
- `/jobs`、`/jobs/new`、`/jobs/:id` 已使用共享 shell/token 体系。
- `JobStatusBadge`、`JobProgress`、`JobActions`、`JobTable`、`PdfUploadPanel` 已使用共享状态色、边框、密度或文本 token。
- `cd frontend && npm run build` 已通过。

遗留问题：

- `TranslationQaQueuePage`、`TranslationResultQaPage`、`SettingsHomePage`、`ConfigTodoSummary` 仍主要使用页面局部 `.page-heading`、`.metric-card`、`.section-header`、card/grid/action 样式和硬编码颜色。
- 第二轮页面虽继承了第一轮 `AppLayout`，但页面内部标题区、面板、表格、表单、状态反馈和操作栏还没有与主链路统一。
- 本地 headless Chrome 在本轮验收时无法启动；Playwright smoke 未跑到页面断言。第二轮实现后仍应先跑 build，再按环境能力尝试 smoke 或浏览器手工验证。

完整验收记录见 `research/round1-acceptance-and-second-round-context.md`。

## Requirements

### Shared Visual Layer

- 复用第一轮 `frontend/src/styles/main.scss` 中的 `--app-*` token 和页面 shell 类。
- 页面级样式优先替换为 `var(--app-*)`，减少 `#111827`、`#667085`、`#d9e2ec`、`#ffffff`、`#2563eb` 等硬编码重复。
- 如目标页之间重复出现 metric card、entry card、table shell、form shell、action strip、status note 等模式，可在 `main.scss` 中新增少量通用 CSS helper。
- 不新增 UI 库，不替换 Element Plus，不引入新的图标库；继续使用 Element Plus icons。
- 保持浅色、克制、中性、工作台式 SaaS 视觉，不做 landing hero、大面积渐变、装饰背景或营销式卡片堆叠。

### Translation QA Queue

- `TranslationQaQueuePage` 使用统一页面结构：`app-page`、`app-page-shell`、`app-page-header`、`app-panel`、`page-title`、`page-description`。
- 统一队列标题区、刷新操作、指标卡、筛选工具栏、错误状态、表格、证据标签、操作列和分页区的密度、边框、间距、按钮层级。
- 保留现有行为：
  - `documentJobsApi.list` 查询参数与响应处理。
  - `translation_qa_status`、`status`、`sort`、`include_archived`、`q`、`page` 的路由查询同步。
  - QA 状态摘要、筛选、分页、刷新、进入复核、进入任务详情。
  - `from=translation-qa` 返回上下文。
- 窄屏下筛选栏、表格和操作列不能出现文字重叠或破坏性横向溢出；表格可保持受控横向滚动。

### Translation Result QA

- `TranslationResultQaPage` 使用统一页面标题区和操作栏，明确返回 QA 队列、任务详情、提交翻译术语建议、刷新等动作层级。
- 统一任务信息面板、复核结论表单、不可用/只读提示、指标卡、证据文件、片段对照、展开 trace card、术语命中和 AI 调用摘要的 panel/table/form 样式。
- 保留现有行为：
  - 并行读取 `documentJobsApi.get` 和 `documentJobsApi.getTranslationQa`。
  - `qa.available` 控制只读状态，不改为前端猜测。
  - `saveQa` 的 payload、成功/错误反馈、保存后刷新逻辑不变。
  - 从 QA 队列返回时保留原查询参数。
  - 提交翻译术语建议的路由 query 和资源版本观测逻辑不变。
  - 不展示、不生成新的全文 prompt/response；继续只展示现有 metadata 和可用证据。
- 表格密集区要保持可扫描：片段对照、术语 trace、AI call table 在移动端不挤压正文或按钮。

### Settings Entry Page

- `SettingsHomePage` 作为配置中心主要入口页接入统一页面 shell 和 token。
- `ConfigTodoSummary` 作为入口页总览组件纳入本轮视觉统一。
- 统一配置工作台标题区、管理员状态、运行门禁总览、Word 配置入口、发布门禁处理队列、配置组卡片、指标格、finding 列表和入口按钮。
- 保留现有行为：
  - `configSummaryApi.get("overview")`、`configSummaryApi.getGroup(groupId, "full")` 调用不变。
  - `CACHE_TTL_MS` 缓存策略和后台刷新行为不变。
  - `RoleGate` 显示规则不变。
  - release gate route mapping、severity/status tag mapping、deferred group detail 加载逻辑不变。
  - Word 模板、Word 页面样式、配置组详情入口路由不变。
- 仅改主要入口页和入口页直接渲染的总览组件；不进入模板详情、Word 页面样式详情、术语规则、翻译 profile、翻译术语集等深层详情页重设计。

### Behavior Preservation

- 不修改 API payload、API client、router route definitions、权限检查、Pinia store、上传流程、轮询流程、后端 action availability、错误归一化或后端契约。
- 不新增静默 fallback，不隐藏错误，不把后端可用性判断改为前端推断。
- 不改变已有测试语义；如测试需要调整，应只因可访问文本/结构变化导致，且必须保持业务断言不弱化。

## Acceptance Criteria

- [ ] `TranslationQaQueuePage` 使用第一轮页面 shell/token 体系，标题区、指标区、筛选栏、表格、证据标签、操作列和分页视觉与 `/jobs` 主链路一致。
- [ ] `TranslationQaQueuePage` 的查询参数同步、筛选、分页、刷新、QA 队列返回上下文和跳转行为不变。
- [ ] `TranslationResultQaPage` 使用统一标题区、操作栏、面板、表单、表格和状态反馈样式，QA 证据视图更接近主链路 SaaS 视觉。
- [ ] `TranslationResultQaPage` 的只读判断、保存复核 payload、保存后刷新、返回队列、任务详情和术语建议跳转行为不变。
- [ ] `SettingsHomePage` 和 `ConfigTodoSummary` 使用共享 token/panel/entry-card/metric-card 风格，配置中心入口页与主链路视觉一致。
- [ ] `SettingsHomePage` 的 summary 缓存、后台刷新、deferred group detail 加载、release gate 路由、RoleGate 和配置入口路由行为不变。
- [ ] 本轮不重设计系统状态、运维 dashboard、文件保留、所有配置详情页、术语工作台、术语建议页。
- [ ] 目标页面在约 375px、768px、1024px、1440px 下没有明显文字重叠、按钮挤压、不可读表单或破坏性横向滚动；表格密集区允许受控横向滚动。
- [ ] `cd frontend && npm run build` 通过。
- [ ] 如本机浏览器可用，使用已有 Chrome/Chromium 或可用浏览器工具做视觉/交互 smoke；如不可用，明确记录浏览器启动失败原因和替代验证。

## Definition Of Done

- 本 PRD 经用户确认后，再运行 `task.py start .trellis/tasks/06-18-frontend-saas-qa-settings-ui` 进入实现阶段。
- 实现前读取 `.trellis/spec/frontend/index.md`、`.trellis/spec/frontend/ui-system-guidelines.md` 和本 PRD。
- 代码改造范围保持在第二轮目标页、入口页直接组件和必要共享 SCSS helper。
- 最小验证优先运行 `cd frontend && npm run build`。
- 不执行 `npx playwright install chromium`。
- 若 smoke 使用本机 Chrome/Chromium 失败，不下载新浏览器，并在结果中记录失败原因、替代验证和剩余风险。
- 最终说明是否新增或更新注释/文档；样式重组无新增业务注释时也明确说明。

## Technical Approach

推荐方案：复用第一轮 token + CSS shell/helper 的轻量收敛方式，不抽新 UI 库，不先抽大型 Vue layout 组件。

- Shared CSS:
  - 保留 `--app-*` 为唯一视觉 token 来源。
  - 视重复程度补充通用 helper，例如 metric card、entry card、table panel、action strip、status note，但避免建立第二套页面命名体系。
  - 优先让目标页使用 `app-page`、`app-page-shell`、`app-page-header`、`app-panel`、`page-title`、`page-description`、`section-title`、`section-subtitle`、`toolbar`。

- QA Queue:
  - 将 `.page-heading` 收敛为 `app-page-header`。
  - 将 queue panel 和 metric cards 接入 shared panel/token。
  - 对筛选 toolbar 和表格容器补响应式宽度控制。

- QA Result:
  - 将顶部 `section-header` 升级为页面标题区，并把 action toolbar 放在统一操作区。
  - 将复核结论表单和证据面板统一为 `app-panel` 风格。
  - 对 trace cards、metric cards、nested tables 用 token 替换硬编码色值。

- Settings Entry:
  - 将 `SettingsHomePage` 标题、运行门禁、Word 配置入口、发布门禁和配置组统一为 shared panel/entry/card 模式。
  - 将 `ConfigTodoSummary` 的 metric items 和 alert spacing 与主页面一致。
  - 保持入口信息密度，不做营销式首页。

## Research References

- `research/round1-acceptance-and-second-round-context.md` — 第一轮验收证据、浏览器验证限制、第二轮目标页现状和 UI 研究取舍。

## Out Of Scope

- 不引入新 UI 库，不替换 Element Plus。
- 不深改系统状态、运维 dashboard、audit、file retention 页面。
- 不重设计所有配置详情页，包括模板详情、Word 页面样式详情、术语规则、翻译 profile、翻译术语集等。
- 不修改后端、API client、权限模型、路由表语义、store、上传、轮询、错误归一化或数据模型。
- 不新增暗色模式专项设计；只保持 token 层兼容。
- 不做图表体系、复杂动效、主题切换、白标能力或页面信息架构重写。

## Open Questions

- 请确认本 PRD 是否可以作为第二轮实现依据。推荐确认当前范围：只做 Translation QA 队列、Translation QA 结果页、SettingsHomePage 与 ConfigTodoSummary 的视觉产品化，不扩大到系统状态或配置详情页。
