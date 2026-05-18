---
doc_type: refactor-design
refactor: 2026-05-16-config-runtime-split
status: approved
scope: 在不改 CLI、运行时配置结构和主模块导出面的前提下，拆出配置解析链并修复 characterization tests 的沙箱临时目录兼容性
summary: 先抽配置运行时模块，再保留主模块薄包装，最后修复共享测试 helper 的 tempfile 和模块重载入口
---

# config-runtime-split refactor design

## 1. 本次范围

- 从 scan 勾选了 #1 #2 #3
- 明确不做的：输入适配逻辑、页面编排逻辑、文本渲染逻辑、CLI 行为修改
- 预估总工作量 / 总风险档位：中等工作量 / 中风险

## 2. 前置依赖

- 继续复用上一轮补齐的配置/文本 characterization tests
- 不新增端到端测试；本轮以全量 characterization tests 为主验证面

## 3. 执行顺序

- 步骤 1：抽出配置运行时模块
- 引用方法：M-L2-04 Move Function
- 具体操作：新建 `render_config_runtime.py`，迁移 `TerminologyReplacer`、配置路径查找、布局与段落样式解析逻辑
- 退出信号：配置链实现不再在主文件中展开定义
- 验证责任：AI 自证
- 回滚：删除新模块并恢复主文件原实现

- 步骤 2：主文件保留薄包装与兼容导出
- 引用方法：M-L1-01 Parallel Change
- 具体操作：`mineru_to_docx.py` 保留 `find_layout_config_path`、`load_render_config`、`load_section_layout`、`load_paragraph_styles` 的同名入口，内部委托给新模块
- 退出信号：现有测试能继续 patch `mineru_to_docx` 顶层符号
- 验证责任：AI 自证
- 回滚：恢复主文件本地实现

- 步骤 3：修复测试临时目录与子模块重载
- 引用方法：M-L2-01 Extract Function
- 具体操作：在共享测试 helper 中固定 `tempfile.tempdir` 到 `tests/.tmp`，并在 `_load_module()` 里同时清理 `text_rendering` 与 `render_config_runtime`
- 退出信号：`test_input_adapter_characterization.py` 在沙箱内可执行
- 验证责任：AI 自证
- 回滚：移除 helper 中的 tempdir / 模块清理逻辑

## 4. 风险与看点

- 配置运行时模块如果不保留主模块兼容面，会再次触发 monkeypatch 打不中的问题
- `tempfile.tempdir` 是进程级全局；必须放在共享 helper，而不是每个测试各自设置，避免执行顺序差异
- 测试 helper 需要一起清理 `text_rendering` 和 `render_config_runtime`，否则 stub 依赖会被缓存污染
