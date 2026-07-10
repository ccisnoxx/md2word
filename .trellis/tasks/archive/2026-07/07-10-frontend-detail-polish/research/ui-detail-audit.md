# 前端细节审计基线

## 审计范围

本轮以现有路由、共享壳层、全局样式、核心工作台截图、验收中心截图和规则弹窗截图为证据，按以下页面族审查：

- 登录与访问控制入口；
- 处理队列与任务详情；
- 翻译 QA、术语提案和术语治理；
- 配置、模板和页面样式；
- 系统状态、运维、验收、审计、用户与文件保留。

审计结论用于排序和规划，不以“自动化用例通过”替代视觉与交互判断。

## 页面族审计矩阵

| 页面族 | 路由/组件证据 | 自动化证据 | 结论 |
|---|---|---|---|
| 登录与访问控制 | `/login`、`/forbidden`、`LoginPage.vue`、`ForbiddenPage.vue` | `core-flow.spec.ts`、`user-auth.spec.ts` | 登录页四视口截图无页面级横向溢出；本轮没有新增 P0/P1，保留为 P2 间距/阴影样本。 |
| 处理队列与任务详情 | `/cockpit`、`/jobs`、`/incidents`、`/jobs/new`、`/jobs/:jobId` | `operations-cockpit.spec.ts`、`core-flow.spec.ts`、`incident-triage.spec.ts`、`accessibility-responsive-gate.spec.ts` | 桌面/平板/移动基础层级与横向溢出门禁已覆盖；移动顶栏挤压为共享 P1。 |
| 质量治理 | `/translation-qa`、任务 QA 详情、提案、规则、术语集与发布 | `core-flow.spec.ts`、`governance-workbench.spec.ts`、`term-rule-set-dialog.spec.ts` | QA 抽屉短视口纵向不可达为 P0；规则弹窗已有独立滚动与 footer 可达断言，`fullPage` 截图失真不单独立项。 |
| 配置发布 | `/settings`、模板、页面样式、翻译配置、AI/MinerU 配置 | `core-flow.spec.ts`、`governance-workbench.spec.ts`、`long-tail-admin-convergence.spec.ts`、相关单元测试 | 固定宽 dialog 已被 `main.scss:1421` 的移动端全局宽度合同约束；当前无新增 P0/P1，滚动根纳入共享 P1。 |
| 系统运维 | 系统状态、运维看板、验收、审计、用户、文件保留 | `core-flow.spec.ts`、`acceptance-center.spec.ts`、`long-tail-admin-convergence.spec.ts`、`user-auth.spec.ts` | 主要路由和移动端 drawer/dialog 可达已有覆盖；验收卡片整卡透明度归入 P2，不提升为可用性缺陷。 |

源码横向扫描同时覆盖：固定/粘性定位、`100vh`、大 `min-width`、全部 dialog/drawer、滚动根、整卡透明度、直接阴影和响应式断点。已有全局合同能够解释的固定宽度不重复增加兼容分支。

## 已验证问题

### P0：移动端 QA 复核操作不可稳定到达

- 证据：`core-flow.spec.ts` 的 `ops-qa-drawer-mobile.png` 显示 `375x812px` 下 footer 占据大部分视口，正文、表单和操作区竞争同一高度。
- 根因边界：`TranslationQaReviewPanel.vue:776` 的 footer 在移动端仍包含三列表单、快捷键提示、三项操作和复核元信息；现有门禁只检查抽屉宽度不超过视口，没有检查 footer 高度、纵向可达性和遮挡。
- 目标：移动端改为单一纵向内容滚动，底部只保留紧凑吸底操作栏；桌面交互不变。

### P1：移动端顶栏页面上下文被操作区挤压

- 证据：任务工作台、翻译 QA、验收中心的 `375px` 截图中，模块与页面标题只剩一两个汉字或省略片段。
- 根因边界：`AppLayout.vue:48` 同时平铺搜索、主题、用户、修改密码和退出；`AppLayout.vue:511` 只压缩文字，没有改变信息层级。
- 目标：移动端保留导航、当前页面标题、搜索、主题和用户菜单，将修改密码、退出收拢到用户菜单。

### P1：滚动容器缺少统一视觉和交互合同

- 证据：`frontend/src/` 至少 21 个文件声明 `overflow: auto`、`overflow-x: auto` 或 `overflow-y: auto`，没有任何 `scrollbar-width`、`scrollbar-color` 或 `::-webkit-scrollbar` 规则。
- 直接示例：`AppSidebar.vue:253` 的导航区域仅声明 `overflow-y: auto`，外观完全由操作系统与浏览器默认值决定。
- 目标：侧栏和短操作条采用按交互显现的细滚动条；长表格、抽屉正文和配置列表采用始终可见的低对比度细滚动条。

## P2 候选问题

- 禁用或不可用状态存在对整个卡片应用透明度的做法，例如 `AcceptanceCenterPage.vue:1042` 使用 `opacity: 0.78`，会同时削弱标题、说明与状态信息的可读性。
- 局部页面与组件仍存在较多直接阴影值、渐变和固定像素间距；后续应先归并到现有令牌和共享组件，再判断是否调整视觉强度。
- 横向操作条虽然具备原生滚动能力，但部分移动端截图只呈现被截断的末项，缺少明确的滚动提示或边缘反馈。
- 深色主题目前只有主题工具单元测试，没有主要页面族的浏览器级视觉或对比回归证据。

## P0/P1 冻结清单

第一阶段实现以下已验证问题：

1. **P0：移动端翻译 QA 抽屉纵向可达性**
   - 所有者：`TranslationQaReviewPanel.vue`，必要时联动 `TranslationQaQueuePage.vue`。
   - 验证：`375x812px` 单滚动根、表单/操作可达、无 sticky 遮挡，桌面布局不变。
2. **P1：移动端顶栏页面上下文与用户操作层级**
   - 所有者：`AppLayout.vue`。
   - 验证：`375px` 页面标题可辨识，移动用户菜单可打开改密/退出，焦点返回正确，桌面入口不变。
3. **P1：滚动容器共享视觉合同**
   - 所有者：`main.scss` 和各真实滚动根。
   - 验证：transient/persistent 分类明确，Firefox/Chromium 规则齐全，原生滚动行为不变。
4. **P1：对话框内下拉层被全局 z-index 压到遮罩下方**
   - 证据：完整 smoke 中“上标”选项可见但点击被 `.rule-form-grid` 截获；`main.scss` 用 `!important` 把所有 `.el-popper` 固定为低于 dialog 的静态层级。
   - 所有者：`main.scss`。
   - 验证：移除错误的静态 z-index 覆盖，继续让 Element Plus 运行时管理嵌套弹层；上标选择用例通过。

其他发现保持 P2 或观察项，不在第一阶段追加无证据的页面重构。

## 实施后证据

- 移动端顶栏截图已显示完整“任务工作台”“翻译 QA”“验收中心”标题，操作区收敛为搜索、主题和用户菜单。
- QA drawer 在桌面恢复独立正文滚动与固定表单 footer；`375x812px` 下由抽屉根单独滚动，表单和三个操作可到达，快捷键提示隐藏。
- `1280px` 深色样本已覆盖壳层、任务表格和 QA drawer；令牌与内容对比保持可辨识。
- P2 仅调整共享基础面板阴影、静态卡片 hover 和验收禁用卡片透明度，没有扩大到未验证页面重构。

## 验证结果与剩余缺口

- 核心工作台截图覆盖 `375/768/1024/1440px`，其中 `1024px` 使用深色主题，代表壳层、表格和 QA drawer；页面级横向溢出门禁通过。
- 新增断言覆盖移动端标题最小可见宽度、用户菜单改密/退出、对话框焦点返回、QA 单滚动根、吸底栏不遮挡备注和三个操作可达。
- 样式合同单元测试覆盖浅色/深色滚动条令牌、transient/persistent 分类、静态卡片 hover 和禁用卡片可读性。
- 全量 Chrome smoke 共 44 项全部通过；Firefox/Safari 未纳入当前 Playwright 项目，滚动条兼容通过标准属性和 WebKit 选择器源码合同约束，仍属于浏览器视觉层面的剩余风险。
- 规则弹窗保留 `fullPage: true` 的既有截图限制，但实际 select 选项点击和三种视口的操作可达已通过行为 smoke，不再依赖长截图单独定性。
