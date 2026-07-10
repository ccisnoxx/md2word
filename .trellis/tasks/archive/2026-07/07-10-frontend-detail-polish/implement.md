# 前端页面细节优化实施计划

## Scope

先完成全站细节审计并冻结 P0/P1 清单，再实施共享可用性修复；P0/P1 门禁通过后才进入 P2 视觉收敛。全过程不新增前端依赖，不修改后端合同。

## Checklist

### 1. 完成审计与范围冻结

- [x] 从 `frontend/src/router/index.ts` 建立五类页面族审计矩阵。
- [x] 复用现有 smoke mock 和截图用例采集 `375/768/1024/1440px` 证据；确认固定遮罩的 `fullPage` 截图不直接作为缺陷证据。
- [x] 补充深色主题的壳层、表格、抽屉代表样本（在 P0/P1 门禁统一采集，避免重复启动浏览器）。
- [x] 更新 `research/ui-detail-audit.md`，为每项 P0/P1 记录复现证据、所有者和验证方式。
- [x] 冻结 P0/P1 清单；没有证据的纯主观项不进入第一阶段。

### 2. 统一滚动容器

- [x] 在 `frontend/src/styles/main.scss` 增加浅色/深色滚动条令牌。
- [x] 实现 `app-scrollbar-transient` 与 `app-scrollbar-persistent`，覆盖 Firefox 和 Chromium/Safari。
- [x] 逐一分类审计发现的滚动根；把工具类加在真实滚动元素上，不改变现有 `overflow` 合同。
- [x] 验证侧栏、保存视图条、长表格、命令面板、配置列表和抽屉正文的滚轮、触摸、键盘与焦点行为。
- [x] 为关键容器补最小样式合同断言。

### 3. 修复移动端顶栏

- [x] 在 `AppLayout.vue` 增加移动端用户 dropdown，复用现有修改密码与退出处理函数。
- [x] 桌面继续显示用户身份、修改密码和退出；移动端只显示紧凑用户菜单触发器。
- [x] 调整顶栏 flex/grid 约束，保证页面标题获得可辨识宽度；按断点隐藏模块名和面包屑。
- [x] 保持密码 dialog 的焦点返回，分别覆盖桌面按钮和移动端用户菜单触发器。
- [x] 更新现有 smoke：验证 `375px` 标题、用户菜单、修改密码、退出和导航焦点返回。

### 4. 修复移动端 QA 复核抽屉

- [x] 保持桌面 `header / body / footer` 三段布局不变。
- [x] 移动端把抽屉根设为唯一纵向滚动根，正文和 footer 回归文档流。
- [x] 隐藏移动端快捷键提示，把三个操作整理为不遮挡内容的紧凑吸底栏。
- [x] 处理 `100dvh`、底部安全区和短视口边界；软键盘沿用浏览器 `dvh` 收缩行为。
- [x] 新增 `375x812px` 断言：单滚动根、表单可达、三个操作在滚动后可达、最后一项不被 sticky 栏遮挡。

### 5. P0/P1 门禁

- [x] 运行相关单元测试、构建和目标 smoke。
- [x] 对比桌面/移动端截图，确认桌面行为无回归。
- [x] 浅色/深色各验证一次顶栏、滚动容器和 QA 抽屉。
- [x] 扫描 diff，确认没有全局隐藏滚动条、页面裁切、重复用户状态或第二套表单状态。
- [x] P0/P1 门禁通过后进入 P2。

### 6. 收敛 P2 视觉细节

- [x] 调整共享类，规范基础面板、交互卡片、覆盖层的阴影层级。
- [x] 移除静态指标卡的误导性 hover；保留交互卡片的 focus/hover。
- [x] 保持现有文字、状态点/边框和色彩组合；确认只有运行中状态使用轻量动画。
- [x] 移除整卡禁用透明度，保证说明和不可用原因可读。
- [x] 将移动顶栏、QA footer 等已验证间距收敛到现有空间令牌；未做无证据的全站批量替换。
- [x] 保留全局 `prefers-reduced-motion` 合同，并通过深色代表样本验证新增规则。

### 7. 最终验证与审查

- [x] 运行全部前端单元测试和构建。
- [x] 运行受影响的 Playwright smoke；若耗时允许，再运行完整 smoke 套件。
- [x] 复查 `375/768/1024/1440px` 代表截图和浅色/深色样本。
- [x] 按 PRD AC1-AC8 逐项核对。
- [x] 检查注释、TSDoc、可见中文文本和测试描述与最终行为一致。

## 最终验证证据

- `npm run test:unit`：30 个测试文件、120 项测试全部通过。
- `npm run build`：类型检查和生产构建通过；仅保留第三方 `#__PURE__` 注释与现有大 chunk 警告。
- `npm run test:smoke -- --workers=1`：Chrome 项目 44 项 smoke 全部通过，覆盖统一四视口、深色 laptop 样本、移动用户菜单和 QA 抽屉纵向可达性。
- `git diff --check`：通过；Playwright 生成的截图、trace 和 `.last-run.json` 已从工作变更中清理。

## Validation Commands

优先执行：

```bash
cd frontend && npm run test:unit
cd frontend && npm run build
cd frontend && npm run test:smoke -- --workers=1 --grep "shell|navigation|password|translation QA|responsive|overflow"
```

截图与已知页面族回归：

```bash
cd frontend && npm run test:smoke -- --workers=1 --grep "operations redesign renders verified desktop, tablet, and mobile screenshots|acceptance center renders without page overflow|term rule draft dialog stays reachable"
```

最终条件允许时：

```bash
cd frontend && npm run test:smoke
```

## Risk Files And Rollback Points

- `frontend/src/styles/main.scss`：全局令牌和共享类，任何宽泛选择器都可能跨页面回归；滚动条与 P2 视觉变更分开提交/审查。
- `frontend/src/layouts/AppLayout.vue`：认证入口、顶栏、dialog 焦点与响应式壳层；移动端菜单不能复制退出或密码状态。
- `frontend/src/components/TranslationQaReviewPanel.vue`：高频复核表单和短视口布局；桌面与移动端门禁必须分别通过。
- `frontend/src/components/WorkbenchDrawerSurface.vue`：只有 QA 需求无法在现有合同内表达时才修改；若修改，必须验证其他 drawer 使用方。
- `frontend/tests/smoke/core-flow.spec.ts` 与 `accessibility-responsive-gate.spec.ts`：避免只更新截图而缺少行为断言。

回滚顺序：先回滚 P2，再按“QA 抽屉 -> 移动顶栏 -> 滚动条工具类”逆序回滚。不得用 feature flag、旧样式兼容分支或全局 `overflow: hidden` 掩盖问题。

## Review Gate Before Start

- PRD、design 和 implement 已由用户审阅；
- 全站审计矩阵与首批 P0/P1 所有者明确；
- 滚动条分级、移动顶栏信息层级、QA 单滚动方案和状态反馈规则不再存在未决项；
- P0/P1 与 P2 之间的验证门禁明确；
- 任务启动后先执行 Checklist 1，不直接跳到样式修改。
