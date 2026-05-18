---
doc_type: refactor-design
refactor: 2026-05-16-input-adapter-split
status: approved
scope: 在不改 CLI、数据模型和主模块导出面的前提下，将输入适配链从 `mineru_to_docx.py` 拆出到独立模块
summary: 先抽输入适配模块，再让主文件保留兼容导出，最后同步修共享 test helper 的模块重载入口
---

# input-adapter-split refactor design

## 1. 本次范围

- 从 scan 勾选了 #1 #2 #3
- 明确不做的：CLI 行为、配置解析、文本渲染、页面编排、表格渲染
- 预估总工作量 / 总风险档位：中等工作量 / 中风险

## 2. 前置依赖

- 继续使用现有 characterization tests，不新增测试文件
- 共享 helper 里的 `tempfile.tempdir` 已就位，本轮重点是补模块缓存清理

## 3. 执行顺序

- 步骤 1：抽出输入适配运行时模块
- 引用方法：M-L2-04 Move Function
- 具体操作：新建 `input_adapter_runtime.py`，迁移输入物料化、页装载、块解析、资产路径解析、middle 回填相关函数
- 退出信号：输入链函数不再在主文件中本地定义
- 验证责任：AI 自证
- 回滚：删除新模块并恢复主文件原实现

- 步骤 2：主文件保留兼容导出与运行时绑定
- 引用方法：M-L1-01 Parallel Change
- 具体操作：`mineru_to_docx.py` 继续暴露 `materialize_input`、`load_pages`、`parse_v2_block` 等同名入口，并为输入模块绑定主模块运行时符号
- 退出信号：现有 characterization tests 能继续从 `mineru_to_docx` 调用或 patch 输入链函数
- 验证责任：AI 自证
- 回滚：恢复主文件本地实现

- 步骤 3：共享测试 helper 同步清理输入适配子模块
- 引用方法：M-L2-01 Extract Function
- 具体操作：在 `_load_module()` 的模块清理列表中加入 `input_adapter_runtime`
- 退出信号：全量 characterization tests 在同一进程内多次重载模块仍稳定
- 验证责任：AI 自证
- 回滚：移除 helper 中新增的模块名

## 4. 风险与看点

- 输入适配链内部函数互相调用很多，运行时绑定漏一处就会让 patch 点失效
- 主文件要把 `input_adapter_runtime.bind_runtime(sys.modules[__name__])` 放在顶层导入后立即执行，避免测试初始化时绑定为空
- 这轮不改任何输入协议和解析规则，characterization tests 是行为等价的主要证据
