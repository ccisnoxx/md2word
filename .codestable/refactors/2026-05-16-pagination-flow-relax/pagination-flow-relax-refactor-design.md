---
doc_type: refactor-design
refactor: 2026-05-16-pagination-flow-relax
status: approved
scope: 在不改输入解析、文本渲染和长表续页逻辑的前提下，把正文分页从“按源页硬分页”改成“按条件分页”
summary: 去掉默认 `NEW_PAGE` section 创建，改为条件式新 section；让普通正文内容可以连续流式回填上一页空白
---

# pagination-flow-relax refactor design

## 1. 本次范围

- 从 scan 勾选了 #1 #2 #3
- 明确不做的：输入适配、页面修补、配置解析、长表续页算法、表格渲染本身
- 预估总工作量 / 总风险档位：中等工作量 / 中风险

## 2. 目标行为

- 普通正文页不再因为“源页号变化”而天然另起新页
- 只有以下条件才创建新 section：
  - 首个渲染页
  - 页面方向变化（portrait / landscape 切换）
  - `use_mineru_header_footer=True` 且当前页需要独立 header/footer/page number
- 长表续页仍然沿用 `table_long_renderer.py` 里的显式分页

## 3. 执行顺序

- 步骤 1：抽出分页决策函数
- 引用方法：M-L2-01 Extract Function
- 具体操作：在 `page_layout_runtime.py` 增加单点 section 决策函数，例如 `should_start_new_section(...)`
- 退出信号：页面编排不再直接写死“非第一页就 NEW_PAGE”
- 验证责任：AI 自证
- 回滚：恢复当前 section 创建逻辑

- 步骤 2：把 `build_document` / `prepare_document_section` 改为条件分页
- 引用方法：M-L3-07 Single Responsibility Split
- 具体操作：将“文档内容渲染”和“是否创建 section”分离；默认连续流排，必要时才新建 section
- 退出信号：真实样例第 40/41/42 页的页底大空白明显收敛
- 验证责任：AI 自证 + HUMAN 目视
- 回滚：恢复按源页分页

- 步骤 3：回归长表与目录页
- 引用方法：M-L1-01 Parallel Change
- 具体操作：确认目录页续页、长表续页、横竖版切换页不被本次流式正文策略破坏
- 退出信号：长表页和目录页仍正常
- 验证责任：AI 自证 + HUMAN 目视
- 回滚：保留新策略函数，恢复旧分页条件

## 4. 风险与看点

- 如果 `use_mineru_header_footer=True` 时仍取消页级 section，页眉页脚会串页
- 如果 landscape 页面不单独起 section，页面方向会错
- 真实样例中的 40/41/42 页是本轮最关键的验收锚点

## 5. 最小验证

- `python3 -m py_compile ...`
- 全量 characterization tests
- 真实样例重新生成 [CWQ2P690T-visual-check.docx](/Users/sc/MinerU/md2word_file/out_file/CWQ2P690T-visual-check.docx)
- 目视检查：封面、目录、20 页、40/41/42 页、146 页附录长表
