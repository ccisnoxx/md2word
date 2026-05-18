---
doc_type: refactor-scan
refactor: 2026-05-16-config-runtime-split
status: user-reviewed
scope: "`mineru_to_docx.py` 中的配置解析链，以及 characterization tests 的 tempfile 沙箱兼容入口"
summary: 发现 3 条优化点，结构 2 / 可维护性 1 / 性能 0
---

# config-runtime-split scan

## 总览

- 扫描范围：`mineru_to_docx.py`、`render_config_runtime.py`、`tests/test_render_table_from_html_characterization.py`、`tests/test_input_adapter_characterization.py`、`tests/test_render_config_characterization.py`
- 发现 3 条优化点：结构 2 / 可维护性 1 / 性能 0
- 按风险：低 2 / 中 1 / 高 0
- 建议先做：#1 #2 #3
- 建议慎做 / 后做：无
- 前置检查 7 条全过：✓

## 条目

### #1 把配置解析链抽到独立模块 ✓

- **位置**：`mineru_to_docx.py:1430-1560`
- **分类**：结构
- **现状**：`find_*_config_path`、`load_render_config`、`load_section_layout`、`load_paragraph_styles` 与主控制流仍混在主文件中
- **问题**：主文件同时承担 CLI、输入适配、页面编排、文本渲染和配置解析 5 类职责；配置链约 130 行，可独立成段
- **建议**：新建配置运行时模块，承接配置路径查找和 YAML 到运行时对象的装配逻辑
- **建议映射的方法**：M-L2-04
- **风险**：中（现有测试会 patch `mineru_to_docx` 顶层符号，必须保留兼容面）
- **验证**：AI 自证（跑配置解析 tests 与全量 characterization tests）
- **范围**：约 2 文件 / 130 行迁移

### #2 保留主模块的配置 patch 点与构造入口 ✓

- **位置**：`tests/test_render_config_characterization.py:103-162`、`mineru_to_docx.py:1430-1560`
- **分类**：结构
- **现状**：测试通过 patch `mineru_to_docx.find_layout_config_path`、`load_section_layout`、`load_paragraph_styles`、`TerminologyReplacer` 来刻画现状
- **问题**：如果主文件直接删除这些符号，拆分后测试和外部调用面会失效
- **建议**：主文件保留薄包装和同名导出，内部再委托到新模块
- **建议映射的方法**：M-L1-01
- **风险**：低（不改签名，只改实现位置）
- **验证**：AI 自证（跑 `test_render_config_characterization.py`）
- **范围**：约 1 文件 / 40 行

### #3 在测试引导里统一设置 sandbox 可写临时目录 ✓

- **位置**：`tests/test_render_table_from_html_characterization.py:1-120`
- **分类**：可维护性
- **现状**：多组 characterization tests 依赖 `tempfile.TemporaryDirectory()`，但沙箱环境默认临时目录不可写
- **问题**：`test_input_adapter_characterization.py` 有 11 个用例会在测试启动前失败，导致无法回归输入适配链
- **建议**：在共享测试 helper 中统一设置 `tempfile.tempdir` 到 `tests/.tmp`，并在模块重载时一并清理新拆分模块缓存
- **建议映射的方法**：M-L2-01
- **风险**：低（仅影响测试进程）
- **验证**：AI 自证（跑全量 characterization tests）
- **范围**：约 1 文件 / 10 行
