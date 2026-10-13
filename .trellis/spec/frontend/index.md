# 前端开发规范

本规范描述当前 `md2word` Vue 3 + Element Plus 工作台的实现合同。修改壳层、共享视觉样式、响应式布局、滚动容器或弹层时，先阅读 [界面质量规范](./ui-quality-guidelines.md)；修改 Word 样式管理页时同时阅读 [Schema 驱动的模板样式编辑器合同](./schema-driven-template-style-editor.md)。

## 开发前检查

1. 确认实际滚动根、弹层挂载位置和组件 DOM 所有者，不在外层容器猜测性修补。
2. 优先复用 `frontend/src/styles/main.scss` 的 `--app-*` 令牌与共享类。
3. 响应式调整必须分别验证 `375/768/1024/1440px`，并至少覆盖一个深色主题样本。
4. 改变可见入口或弹层布局时，保留键盘可达性、关闭后的焦点返回和既有业务处理函数。
5. 修改任务模式/配置展示时阅读 [任务模式与 direct 资源合同](../backend/document-job-mode-contract.md)，共享五种名称和模式能力；direct 快照投影只读，动作仍消费后端 available actions。

## 规范索引

| 规范 | 覆盖范围 | 状态 |
|---|---|---|
| [界面质量规范](./ui-quality-guidelines.md) | 滚动条、移动端信息层级、抽屉滚动、Element Plus 弹层层级和卡片状态反馈 | 当前 |
| [Schema 驱动的模板样式编辑器合同](./schema-driven-template-style-editor.md) | 后端 schema 驱动、dirty patch、并发冲突、近似预览和 admin 权限 | 当前 |

## 质量检查

优先运行覆盖改动行为的最小测试，再执行完整前端门禁：

```bash
cd frontend && npm run test:unit
cd frontend && npm run build
cd frontend && npm run test:smoke -- --workers=1
```

构建中的第三方 `#__PURE__` 注释和大 chunk 警告属于当前已知基线；不得用屏蔽警告替代真实修复。
