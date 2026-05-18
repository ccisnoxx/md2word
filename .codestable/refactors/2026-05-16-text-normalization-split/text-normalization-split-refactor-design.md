---
doc_type: refactor-design
refactor: 2026-05-16-text-normalization-split
status: approved
scope: 在不改 CLI、数据模型和外部导入面的前提下，将 `mineru_to_docx.py` 的文本规范化与段落渲染职责拆出为独立模块
summary: 先用 characterization tests 固化配置解析与文本渲染现状，再抽出文本模块，最后让主文件只保留编排层调用
---

# text-normalization-split refactor design

## 1. 本次范围

- 从 scan 勾选了 #1 #2 #3
- 明确不做的：输入适配、页面修补、表格渲染、CLI 入口、配置数据结构
- 预估总工作量 / 总风险档位：中等工作量 / 中风险

## 2. 前置依赖

- 已补 characterization tests：配置解析链、文本规范化与段落渲染链
- 不额外补端到端测试：本次不改主控制流和数据结构

## 3. 执行顺序

- 步骤 1：补齐并验证文本链 characterization tests
- 引用方法：M-L1-04 Characterization Test
- 具体操作：新增 `tests/test_render_config_characterization.py` 与 `tests/test_text_render_characterization.py`，固化配置解析、术语替换、样式应用、标题/正文/列表段落填充现状
- 退出信号：新增测试在当前环境下通过
- 验证责任：AI 自证
- 回滚：删除新增测试文件

- 步骤 2：抽出文本渲染模块
- 引用方法：M-L2-04 Move Function
- 具体操作：新建独立文本模块，承接公式归一化、TOC/标题/正文/列表填充、样式与 run 默认值 helper；保留函数签名与返回行为
- 退出信号：新模块可被主文件导入，文本链函数不再在主文件内定义
- 验证责任：AI 自证
- 回滚：删除新模块并恢复主文件原实现

- 步骤 3：让主文件回填同名导入并清理本地实现
- 引用方法：M-L1-01 Parallel Change
- 具体操作：`mineru_to_docx.py` 改为从新模块导入文本链符号，继续通过主模块对外暴露；更新 refactor 记录
- 退出信号：现有测试仍可从 `mineru_to_docx` 模块 patch / 调用这些函数
- 验证责任：AI 自证
- 回滚：恢复主文件本地实现并移除导入

## 4. 风险与看点

- `table_render_runtime.py` 和 `table_long_renderer.py` 通过主文件回调使用文本链函数；导入名必须保持不变
- `fill_title_paragraph` 当前有“无样式配置时字号落到 `BODY_FONT`”的现状，characterization tests 已按现状固化，不在本次顺手修
- 全量 characterization 集合里仍有 11 个老测试会被沙箱的 `tempfile.TemporaryDirectory()` 阻断；本次以新增测试和不依赖临时目录的相关测试作为主要验证依据
