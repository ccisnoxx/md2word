---
doc_type: refactor-design
refactor: 2026-05-16-page-layout-split
status: approved
scope: 在不改页面编排行为、主模块导出和测试 patch 点的前提下，把页面编排链从 `mineru_to_docx.py` 拆出到独立模块
summary: 先抽页面编排模块，再保留主模块兼容导出，最后同步更新共享测试 helper 的模块重载入口
---

# page-layout-split refactor design

## 1. 本次范围

- 从 scan 勾选了 #1 #2 #3
- 明确不做的：输入适配规则、页面修补逻辑、配置解析、文本渲染、表格渲染本身
- 预估总工作量 / 总风险档位：中等工作量 / 中风险

## 2. 前置依赖

- 继续使用现有 characterization tests，不新增测试文件
- 共享 helper 已经处理 `tempfile.tempdir`，本轮只补 page-layout 子模块清理

## 3. 执行顺序

- 步骤 1：抽出页面编排运行时模块
- 引用方法：M-L2-04 Move Function
- 具体操作：新建 `page_layout_runtime.py`，迁移 `build_document`、TOC 判定、单双栏布局、视觉块分发等页面编排函数
- 退出信号：页面编排逻辑不再在主文件中本地定义
- 验证责任：AI 自证
- 回滚：删除新模块并恢复主文件原实现

- 步骤 2：主文件保留兼容导出与运行时绑定
- 引用方法：M-L1-01 Parallel Change
- 具体操作：`mineru_to_docx.py` 直接从新模块导出页面编排函数；新模块内部通过 `bind_runtime()` 回看主模块可 patch 符号
- 退出信号：现有页面编排 characterization tests 能继续 patch `mineru_to_docx` 顶层函数
- 验证责任：AI 自证
- 回滚：恢复原导出来源

- 步骤 3：共享 helper 同步清理 page-layout 子模块缓存
- 引用方法：M-L2-01 Extract Function
- 具体操作：在 `_load_module()` 的模块清理列表中加入 `page_layout_runtime`
- 退出信号：全量 characterization tests 在单进程内反复重载模块仍稳定
- 验证责任：AI 自证
- 回滚：移除 helper 中新增的模块名

## 4. 风险与看点

- 页面编排链跨表格渲染和文本渲染两个方向调用，运行时绑定必须覆盖 `render_toc_page`、`render_page_body`、`render_one_col_region`、`render_two_col_region` 等关键节点
- `render_visual_block` 是页面编排和表格渲染的连接点，这次只迁移位置，不改调用顺序和降级策略
- `build_document` 通过 `create_document`、`clear_document_body`、`clone_first_section_layout` 等主模块符号完成骨架装配，必须继续允许现有测试 patch 这些入口
