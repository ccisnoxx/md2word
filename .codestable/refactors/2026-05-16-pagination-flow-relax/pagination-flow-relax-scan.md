---
doc_type: refactor-scan
refactor: 2026-05-16-pagination-flow-relax
status: user-reviewed
scope: "`page_layout_runtime.py` 中按源页强制分页的页面编排链，以及真实样例 `CWQ2P690T-visual-check.docx` 的分页回归问题"
summary: 发现 3 条优化点，结构 2 / 可维护性 1 / 性能 0
---

# pagination-flow-relax scan

## 总览

- 扫描范围：`page_layout_runtime.py`、`text_rendering.py`、真实样例 `CWQ2P690T-visual-check.docx`
- 发现 3 条优化点：结构 2 / 可维护性 1 / 性能 0
- 按风险：低 1 / 中 2 / 高 0
- 建议先做：#1 #2 #3
- 建议慎做 / 后做：无
- 前置检查 7 条全过：✓

## 条目

### #1 去掉“每个源页必起新 section”的默认规则 ✓

- **位置**：`page_layout_runtime.py` 中 `prepare_document_section()` / `build_document()`
- **分类**：结构
- **现状**：除第一页外，每个源页都会 `add_section(NEW_PAGE)`，把 MinerU 源页直接当成 Word 的硬分页边界
- **问题**：后续内容无法回流填补上一页剩余空白；真实样例第 40/41/42 页都有明显页底大空白
- **建议**：把“源页”降级为内容切片，不再天然等于 Word 页边界；仅在必要条件命中时再新建 section
- **建议映射的方法**：M-L3-07
- **风险**：中（会改变整份文档的分页模型，需要保住横竖版切换和页眉页脚逻辑）
- **验证**：AI 自证（真实样例重新生成并目视检查 40/41/42 页）
- **范围**：约 2 文件 / 80 行

### #2 把新分页条件收敛成单点策略函数 ✓

- **位置**：`page_layout_runtime.py`
- **分类**：结构
- **现状**：当前 section 创建逻辑分散在编排主循环和 `prepare_document_section()` 里，没有“什么时候必须换页/换 section”的单点规则
- **问题**：后续继续调分页时很容易引入新的局部补丁，难以判断行为边界
- **建议**：新增单点策略函数，明确只有三类情况触发新 section：首个渲染页、横竖版切换、启用 MinerU 页眉页脚覆盖且需要页级独立 header/footer
- **建议映射的方法**：M-L2-01
- **风险**：中（需要保证默认模板页眉页脚模式仍连续流排）
- **验证**：AI 自证（页面编排 characterization tests + 真实样例）
- **范围**：约 2 文件 / 40 行

### #3 保留长表显式分页，不让它被流式正文吞掉 ✓

- **位置**：`table_long_renderer.py`、`page_layout_runtime.py`
- **分类**：可维护性
- **现状**：长表续页依赖 `WD_BREAK.PAGE` 显式分页；正文页大空白问题来自 section 级分页，不是长表续页逻辑
- **问题**：如果修分页时顺手改掉长表显式分页，会把两个问题混在一起
- **建议**：本次只改正文/页面编排的分页模型，保留长表续页现状不动
- **建议映射的方法**：M-L1-01
- **风险**：低（范围守护）
- **验证**：AI 自证（附录长表页仍能正常续页）
- **范围**：约 1 文件 / 0-10 行
