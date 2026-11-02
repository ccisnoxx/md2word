# C1+C2：验证阶段整页降级与依赖闭包

父任务：`11-02-partial-success-page-degradation`（决策 D1、D2'、D3–D6 见父任务 PRD 与 `research/d2-cost-analysis.md`）。

## 目标

无法解析的表格 HTML、P0-4 回退失败的正文图片，不再让整份文档失败：所在页（及与其相互依赖的页）以原 PDF 整页图像保留，前置一段可见提示；其余页面照常可编辑；任务成功但质量 `blocked`、交付 `internal_draft`。

## 范围

1. 可降级错误：`invalid_table_html`、P0-4 回退失败的 `missing_image_asset`/`invalid_image_asset`，且该块有页码。
2. 依赖闭包：试算逻辑表格组，跨越降级页的组把所有页都纳入降级；组内含验证器合并回执（续页占位）时放弃降级，按原错误整体失败。
3. 阈值：降级页数超过页面总数一半，或任一降级页无法栅格化、源 PDF/栅格器不可用、错误无页码、已有其他中止错误时，所有推迟的错误恢复为中止并整体失败（输出与现状一致）。
4. IR 替换：降级页的全部块（含页眉页脚、派生块）从 IR 移除，替换为提示段落与整页图像块；`metadata.degraded_pages` 记录页码、原因码、问题指针、移除的源块数量与类型计数、源指针、图像资产与源 PDF sha256。
5. 来源对账：`build_source_integrity` 扣除降级源块，排除合成块；对账输出保持 `ir_main_block_count == expected_source_block_count` 语义。
6. 整页栅格化：新增 Poppler 整页栅格器（144 DPI PNG），生产装配。
7. 质量：降级原因问题以非中止 blocker 留在验证报告，`quality_status` 为 `blocked`，交付保持 `internal_draft`。
8. 提示文案：`第 N 页因 {原因码} 无法转换，已按原 PDF 页面图像保留，本页不可编辑。`

## 非目标

- `validate()` 阶段的块结构错误、渲染阶段降级（C3）、展示与翻译适配（C4）。

## 验收条件

- AC1：单页表格 HTML 无法解析的文档转换成功，该页为提示 + 整页图像，其他页内容保留；验证报告保留非中止 blocker。
- AC2：跨页表格组涉及降级页时组内所有页降级；涉及合并回执时整体失败。
- AC3：超过阈值、无栅格器、无源 PDF、栅格失败、错误无页码、存在其他中止错误时整体失败，诊断与现状一致。
- AC4：IR 校验、来源对账、逻辑表格组校验、渲染与渲染证据均通过；端到端任务成功，`quality_status=blocked`、`delivery_status=internal_draft`，批准被拒。
- AC5：不触发降级的文档行为与基线一致。
