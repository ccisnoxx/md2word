# 前端开发规范

本规范描述当前 `md2word` Vue 3 + Element Plus 工作台的实现合同。修改壳层、共享视觉样式、响应式布局、滚动容器或弹层时，先阅读 [界面质量规范](./ui-quality-guidelines.md)；修改 Word 样式管理页时同时阅读 [Schema 驱动的模板样式编辑器合同](./schema-driven-template-style-editor.md)。

## 开发前检查

1. 确认实际滚动根、弹层挂载位置和组件 DOM 所有者，不在外层容器猜测性修补。
2. 优先复用 `frontend/src/styles/main.scss` 的 `--app-*` 令牌与共享类。
3. 响应式调整必须分别验证 `375/768/1024/1440px`，并至少覆盖一个深色主题样本。
4. 改变可见入口或弹层布局时，保留键盘可达性、关闭后的焦点返回和既有业务处理函数。
5. 修改任务模式/配置、下载风险或发布资格展示时阅读 [任务模式与 direct 资源合同](../backend/document-job-mode-contract.md)，共享五种名称和模式能力；direct 快照投影只读，动作消费后端 available actions。`publish.eligible` 只表示核心资格，不能替代 `enabled` 或在前端重算；下载提示消费当次签发的分类/warning，旧合同缺失不能推断可交付。

## 规范索引

| 规范 | 覆盖范围 | 状态 |
|---|---|---|
| [界面质量规范](./ui-quality-guidelines.md) | 滚动条、移动端信息层级、抽屉滚动、Element Plus 弹层层级和卡片状态反馈 | 当前 |
| [Schema 驱动的模板样式编辑器合同](./schema-driven-template-style-editor.md) | 后端 schema 驱动、dirty patch、并发冲突、近似预览和 admin 权限 | 当前 |

## 大型页面拆分约定

参照 `frontend/src/features/job-detail/`、`jobs/`、`incidents/`、`file-retention/`、`ops-dashboard/`：

- 页面壳只组装 composable 并连线区块组件；区块组件用 `defineProps` 接收状态与处理函数，ref 级双向绑定用 `defineModel`，类型取 `UnwrapRef<ReturnType<typeof useXxx>["key"]>`。reactive 表单对象可作为 prop 传入并由子组件修改字段。
- 每个数据源只有一个 owner composable；跨 owner 只通过注入的回调或 `Pick<>` 只读依赖，不直接写对方状态。URL query 同步与请求竞态防护必须留在同一个 owner 中。
- 拆分不新增包装元素：区块组件的根就是原 `section`/`div`；嵌套子区块用具名插槽由页面放入，避免多层 props 透传。
- 样式跟随 DOM owner 迁移：一条规则中的类（忽略 `:deep()` 内部与组件生成的 `el-*` 类）出现在哪个组件模板里就放进哪个组件，多处使用则各自复制，保持原书写顺序。`.parent .el-button` 这类规则要归属到包含 `.parent` 的组件，否则会丢失对组件根元素的覆盖。
- 验证以浏览器 computed style 与布局框逐元素对比为准，截图作为辅助；`vue-tsc` 不报告模板闭合错误和"对 prop 使用 v-model"，需由 build 或 SFC 编译检查兜底。

## 质量检查

优先运行覆盖改动行为的最小测试，再执行完整前端门禁：

```bash
cd frontend && npm run test:unit
cd frontend && npm run build
cd frontend && npm run test:smoke -- --workers=1
```

构建中的第三方 `#__PURE__` 注释和大 chunk 警告属于当前已知基线；不得用屏蔽警告替代真实修复。
