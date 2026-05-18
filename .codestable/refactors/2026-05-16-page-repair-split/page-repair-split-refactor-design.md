---
doc_type: refactor-design
refactor: 2026-05-16-page-repair-split
status: approved
scope: 在不改页面修补行为、主模块导出和测试 patch 点的前提下，把页面修补链从 `input_adapter_runtime.py` 再独立成单独模块
summary: 先抽页面修补模块，再调整主模块与输入适配模块的兼容导出，最后同步更新共享测试 helper 的模块重载入口
---

# page-repair-split refactor design

## 1. 本次范围

- 从 scan 勾选了 #1 #2 #3
- 明确不做的：输入 JSON 解析规则、配置解析、文本渲染、页面编排和表格渲染
- 预估总工作量 / 总风险档位：中等工作量 / 中风险

## 2. 前置依赖

- 继续使用现有 characterization tests，不新增测试文件
- `tempfile.tempdir` 兼容入口已经在共享 helper 中就位，本轮只补 page-repair 子模块清理

## 3. 执行顺序

- 步骤 1：抽出页面修补运行时模块
- 引用方法：M-L2-04 Move Function
- 具体操作：新建 `page_repair_runtime.py`，迁移 `repair_and_sort_pages`、`attach_table_continuations`、`merge_page_with_middle`、`find_best_visual_match` 等函数
- 退出信号：页面修补逻辑不再在 `input_adapter_runtime.py` 中本地定义
- 验证责任：AI 自证
- 回滚：删除新模块并恢复 `input_adapter_runtime.py` 原实现

- 步骤 2：更新主模块与输入适配模块的兼容导出
- 引用方法：M-L1-01 Parallel Change
- 具体操作：`mineru_to_docx.py` 直接从新模块导出页面修补链符号；`input_adapter_runtime.py` 复用新模块导出，继续维持 `load_pages()` 调用面
- 退出信号：现有测试仍能从 `mineru_to_docx` 顶层直接访问页面修补函数
- 验证责任：AI 自证
- 回滚：恢复原导出来源

- 步骤 3：共享 helper 同步清理 page-repair 子模块缓存
- 引用方法：M-L2-01 Extract Function
- 具体操作：在 `_load_module()` 的模块清理列表中加入 `page_repair_runtime`
- 退出信号：全量 characterization tests 在单进程内反复重载模块仍稳定
- 验证责任：AI 自证
- 回滚：移除 helper 中新增的模块名

## 4. 风险与看点

- 页面修补链内部函数互相调用密集，`bind_runtime()` 和 `_runtime_value()` 漏一处就会让 patch 点失效
- `input_adapter_runtime.load_pages()` 仍是输入适配与页面修补的连接点，默认 fallback 必须继续可用
- 这轮不改任何修补策略阈值和匹配规则，行为等价由 characterization tests 兜底
