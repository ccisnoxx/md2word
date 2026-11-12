# 拆分超大 Renderer 与 Evidence 模块

父任务：`11-11-structure-refactor`（对应用户需求第 4 项）。不依赖其他子任务，可以并行推进。

## 目标

按职责拆分 `app/services/renderer/evidence.py` 和 `DocumentIRWordRenderer` 的超大模块和超长方法，使"证据构建 / 证据校验 / 事件摘要投影"、"渲染准备 / 操作分发 / 结果冻结"、"段落文本 / 公式 / 编号"、"标准表格 / 原生网格表格"各有独立模块，同时生成的 DOCX 保持字节级一致。

## 现状

- `evidence.py` 1208 行，混合了三类职责：证据构建（`build_renderer_metadata`、`build_renderer_aggregate_evidence`、`formula_source_inventory`、`build_renderer_evidence`）、证据校验（`ensure_renderer_integrity`、`validate_render_result`、`validate_persisted_*`、`_validate_render_evidence` 约 220 行、legacy docx quality 恢复）、事件/报告的安全投影（`controlled_quality_flags`、`build_renderer_event_summary` 约 170 行、MinerU 报告清洗、`is_valid_table_rendering_evidence`）。共有 31 个导入方（应用代码 13 个，测试和脚本 18 个）。
- `DocumentIRWordRenderer` 由 `WordTextRendererMixin`（683 行）、`WordTableRendererMixin`（767 行）、`WordImageRendererMixin` 组合而成；`render_to_result` 单方法 138 行，串联了计划构建、Word 对象构建、操作分发、证据冻结。
- `.trellis/spec/backend/word-generation-rules.md` 按文件路径登记了规则 owner（`word_renderer.py` 14 处、`text_renderer.py` 6 处、`table_renderer.py` 5 处、`evidence.py` 3 处）。

## 需求

1. 把 `evidence.py` 拆成证据构建、证据校验、事件摘要投影三个模块，删除 `evidence.py`，所有导入方直接从新模块导入（不保留再导出壳）。
2. 把 `render_to_result` 拆成：渲染准备（计划与表格输入，返回不可变的准备结果）、单个操作的分发、结果冻结；主方法只负责串联这三步。
3. 页面设置/页眉页脚/分节列的 helper 从 `word_renderer.py` 移到独立模块。
4. 公式写入（`_append_formula`、`_render_mixed_math`、`_set_formula_source`、`_add_complex_field`）和列表编号 helper 从 `text_renderer.py` 拆出；原生网格表格（`NativeCellPart`、native grid/unit 相关方法）从 `table_renderer.py` 拆出。
5. 继续使用 Mixin 组合方式；测试直接调用的私有方法（9 个）在 `DocumentIRWordRenderer` 上的名字保持不变。
6. 同步更新 `word-generation-rules.md` 中的文件路径 owner。`docs/implementation/` 下是历史任务提示词，不修改。

## 约束

- 渲染输出零变化：DOCX 解压后每个 part 字节一致；异常类型、错误码、失败上下文不变。
- 拆分时注意延迟导入（`word_renderer.py` 和 `content_contract.py` 中有函数内导入 evidence），新模块之间不能产生循环导入。
- 不把 Mixin 改为组合对象：那样会改动所有 `self._xxx` 的互相调用，风险和收益不成比例（见 design §4）。

## 验收标准

- [x] `app/services/renderer/` 下没有超过约 550 行的模块；`render_to_result` 不超过约 50 行。
- [x] `evidence.py` 已删除，`rg "renderer\.evidence\b|renderer import evidence" app tests scripts` 结果为 0。
- [x] 渲染等价性：用第 0 步建立的 fixture 集合，在重构前后分别生成 DOCX，逐个 part 对比，结果完全一致。
- [x] 定向测试通过：`test_document_ir_word_renderer_layout`、`test_document_ir_mineru_converter_layout`、`test_formula_rendering`、`test_formula_rendering_compatibility`、`test_formula_literal_support`、`test_image_group_rendering`、`test_two_column_reading_order`、`test_parameter_paragraph_line_breaks`、`test_render_failure_context`、`test_render_page_degradation`、`test_document_ir_layout_contract`、`test_mineru_artifact_validator`、`test_document_job_result_persistence`、`test_document_job_execution_stages`、`test_document_job_delivery_state`、`test_rnd503_dependency_integration`、`test_component_pdf_sample_governance`、`test_conversion_sandbox_dev_tools`。
- [x] `word-generation-rules.md` 中引用的 renderer 文件路径都存在，且指向实际 owner。
