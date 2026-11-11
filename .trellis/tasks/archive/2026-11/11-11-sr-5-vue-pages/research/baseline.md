# 第 0 步基线（2026-11-11）

基线提交：`8365f380`（结构重构规划提交，前端源码与 `0c9a7923` 相同）。

## 命令结果

| 检查 | 结果 |
|---|---|
| `npm run test:unit` | 287 通过 |
| `npm run build` | 通过；仅已知的 `#__PURE__` 与大 chunk 警告 |
| `npx playwright test --workers=1`（smoke 全集） | 60 个用例：52 通过、8 失败 |

### smoke 基线失败（与本任务无关的既有问题）

1–4. `core-flow` · CON-102 详情展示 translating / translation_validating / quality_checking / future_document_stage：`.failure-summary` 命中 2 个元素（strict mode）。
5. `core-flow` · operations redesign screenshots：`tracing.stopChunk ENOENT`。原因是基线采集与 smoke 同时运行，共用并清理了 `frontend/test-results`；属于本次基线的并发干扰，回归时单独复核。
6. `core-flow` · operator can log in and inspect the document job workbench：`getByText("下载链接已生成")` 同时命中页面提示条和 ElMessage（strict mode），属于既有断言问题。
7. `core-flow` · admin can edit Word page styles and save a draft version。
8. `operations-cockpit` · command palette opens with Cmd/Ctrl+K…：命令面板对话框未出现。

## 视觉与 DOM 合同基线

采集工具：`frontend/tests/.sr5-capture/`（临时，不入库）。复用 `core-flow` 与 `incident-triage` 的 mock 前缀，固定时钟 `2026-06-20T04:05:00Z`，关闭过渡动画，对每个状态导出：

- 全页截图；
- `body` 下每个元素的路径、类名、`aria-label`、`role`、叶子文本、布局框（含滚动偏移）以及 36 项 computed style 与 `::before/::after`。

覆盖 375/768/1024/1440px 浅色 + 1440/375px 深色，共 6 个视口，状态如下：

| 页面 | 状态 |
|---|---|
| Jobs | 列表、勾选一行后的批量操作条、"更多筛选"弹层 |
| Incidents | 队列、勾选两行、批量重试确认框、`incident_job_id` 打开的诊断抽屉 |
| OpsDashboard | 初始、点击 "Preview real-send gates" 后 |
| FileRetention | 文件库标签页、"清理执行"标签页 |

确定性自检：同一份代码采集两次，逐元素对比 0 差异；人为改动一个属性后能被检出。基线文件约 106MB，存放在 `/tmp/sr5-capture/baseline`，不入库。

## 拆分完成后的回归结果

| 检查 | 结果 |
|---|---|
| `npm run test:unit` | 299 通过（基线 287 + 新增 12） |
| `npm run build` | 通过；警告与基线完全相同 |
| smoke 全集 `--workers=1` | 53 通过、7 失败；7 个失败全部属于基线既有失败（上表 1–4、6、7、8），无新增失败；基线第 5 项（并发干扰）本次通过 |
| 逐元素 DOM/样式/布局对比 | 4 个页面 × 11 个状态 × 6 个视口共 66 组，全部 0 差异（类名、`aria-label`、role、叶子文本、布局框、36 项 computed style 与伪元素一致） |
| 截图 | 66 张中 62 张字节一致；其余为渲染噪声（两次基线之间本身不同或仅 1 像素抗锯齿），以及 1 张全页截图的固定层时序问题，单独重采两次均与基线像素一致 |

行数：`JobsPage` 315、`IncidentTriagePage` 291、`FileRetentionPage` 347、`OpsDashboardPage` 322；新增组件/composable 最大 494 行（`JobsListPanel.vue`）。

产物体积（未压缩）：FileRetention CSS 4.3→11.1 kB、Ops CSS 6.6→16.0 kB（共享样式按 owner 复制）；四个页面 JS 合计增加约 55 kB（props 声明与组件边界）。
