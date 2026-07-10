# 界面质量规范

## 滚动容器合同

滚动条样式只添加到实际承载 `overflow` 的元素，不使用全局 `*::-webkit-scrollbar`，也不通过 `overflow: hidden` 掩盖溢出。

- `app-scrollbar-transient`：侧栏、保存视图条、短横向操作条。滑块默认透明，在 `hover` 或 `focus-within` 时显示。
- `app-scrollbar-persistent`：抽屉正文、长表格、配置列表、命令面板和长代码块。始终显示低对比度细滑块。
- `app-technical-block`：现有技术内容容器，行为与 persistent 一致。
- 颜色和尺寸统一读取 `main.scss` 的 `--app-scrollbar-*` 令牌；浅色、深色必须提供同名令牌。
- 工具类只能改变滚动条外观，不改变滚动方向、滚动位置、滚轮、触摸或键盘行为。

```html
<!-- 错误：样式加在不滚动的卡片外壳。 -->
<section class="app-scrollbar-persistent">
  <div class="table-wrap">...</div>
</section>

<!-- 正确：样式加在声明 overflow-x: auto 的实际滚动根。 -->
<div class="table-wrap app-scrollbar-persistent">...</div>
```

## Scoped 样式与子组件 DOM

父组件通过 class prop 或 slot 把类名传给子组件创建的 DOM 时，父组件的 scoped CSS 必须使用 `:deep(...)` 命中该元素。普通 `.class-name` 会被编译为带父组件 scope 属性的选择器，无法匹配只带子组件 scope 属性的 DOM。

```vue
<!-- WorkbenchDrawerSurface 创建 qa-review-body 元素。 -->
<WorkbenchDrawerSurface body-class="qa-review-body" />

<style scoped>
/* 错误：不会命中子组件拥有的 DOM。 */
.qa-review-body { overflow-y: auto; }

/* 正确：明确穿透到子组件创建的滚动根。 */
:deep(.qa-review-body) { overflow-y: auto; }
</style>
```

验证时必须读取浏览器 computed style 和 `scrollHeight/clientHeight`，不能只凭源码类名判断滚动合同已经生效。

## 移动端壳层与抽屉

- `<=640px` 顶栏优先显示导航、当前页面标题、搜索、主题和用户菜单；模块名、面包屑和桌面平铺账号操作可以隐藏。
- 修改密码和退出必须复用桌面现有处理函数，不建立第二份认证状态；关闭密码对话框后焦点返回原触发器。
- 短视口抽屉只保留一个纵向滚动根。移动端正文若并入抽屉根，应设置为 `overflow: visible`，避免双滚动。
- 吸底操作栏必须位于抽屉滚动上下文内，使用不透明背景、边界和 `env(safe-area-inset-bottom)`；最后一项表单内容不得被遮挡。
- 桌面抽屉继续使用可滚动正文和固定 footer，不能用移动端重排破坏高频操作密度。

## Element Plus 弹层层级

Element Plus 会在运行时为 dialog、dropdown、select popper 分配递增 `z-index`。禁止用 `!important` 给所有 `.el-popper` 或 `.el-picker-panel` 写死静态层级，否则对话框内选项即使可见，也可能落到遮罩或对话框内容下方而无法点击。

允许统一边框、背景、阴影等视觉属性；层级只在明确拥有独立产品合同的覆盖层上设置，例如命令面板或通知。嵌套 select/dropdown 必须以真实点击 smoke 验证，不能只断言选项可见。

## 状态与卡片反馈

- 只有运行中状态允许持续动画，并遵守 `prefers-reduced-motion`。
- 成功、警告和阻断必须同时包含文字语义以及图标、形状或边界，不依赖颜色单独表达。
- 禁用卡片不得通过整卡 `opacity` 降低标题、说明和原因的可读性。
- 静态指标卡、筛选卡和内容面板不提供 hover 抬升；只有真实按钮、链接或 `role="button"` 卡片提供 hover/focus 反馈。
- 基础面板优先使用 `--app-shadow-subtle`；强阴影保留给 dialog、drawer、command palette 等覆盖层。

## 必要测试

- 样式合同单元测试：令牌、显式工具类、代表性滚动根、静态卡片与禁用卡片规则。
- 响应式 smoke：`375/768/1024/1440px` 无页面级横向溢出，移动端标题可辨识。
- 行为 smoke：移动用户菜单的改密/退出、弹层关闭焦点返回、QA 抽屉单滚动根、操作栏不遮挡表单。
- 主题样本：至少一个深色壳层、表格和抽屉样本；新增令牌必须同时验证浅色和深色定义。
