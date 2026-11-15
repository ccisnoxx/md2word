# 实施计划：目录合并区域约束与列表项级账本

前置：PRD 待确认项 Q1–Q3 得到答复，`task.py start` 之后才动代码。

## 步骤

### S1 清理重复定义（R8）

- `app/conversion/docx_rules/mineru_content.py`：删除第 563-603 行重复的 `select_mineru_list_source` 与 `mineru_list_items`，保留第 157/176 行的版本。两份内容逐字相同，行为不变。
- 检查：`rg -n "def (select_mineru_list_source|mineru_list_items)"` 只剩一处。

### S2 目录区域（R1，G1）

- `app/services/renderer/render_plan.py`
  - `select_text_policy` 增加 `allow_toc: bool = True`。
  - 新增 `toc_region_block_ids(document_ir, operations)`，按 design §2.1 的状态机实现。
  - `build_render_plan` 的文本策略循环（约第 520-535 行）对区域外块传 `allow_toc=False`。
- 不改 `_plan_toc_formula_paragraphs`、`text_renderer.py`、`page_mapping.py`：它们只消费计划中的 mode。

### S3 列表项账本生成（R2）

- `mineru_content.py` 新增 `mineru_list_item_ledger(block)`（design §3.2）。
- `app/services/document_ir/mineru_converter.py`：主列表块写入 `metadata["list_item_ledger"]`；源项数不平衡时抛 `DocumentIntegrityError`。

### S4 账本对账（R3）

- `app/services/document_ir/integrity.py::build_source_integrity`：按 design §3.3 增加检查。只有在 IR 带账本时才新增 `list_item_ledger` 键。

### S5 生成期去向校验（R4）

- `app/services/renderer/render_evidence_validation.py::validate_render_result`：调用 `toc_region_block_ids` 独立重算区域，区域外出现目录类 mode 即阻断。

### S6 阻断码登记（R6）

- `app/domains/document_jobs/review.py::_SAFE_FLAGS`
- `app/services/renderer/render_event_summary.py::FIXED_FLAGS`

### S7 Spec（R7）

- `.trellis/spec/backend/word-generation-rules.md`
  - FIELD-001：写明区域规则、区域外禁止目录类 mode、新阻断码、自动验证用例名。
  - INPUT-004：写明 `list-item-ledger/v1` 的字段、平衡式与对账边界。

## 测试（新增，均为定向用例）

| 文件 | 用例 | 覆盖 |
|---|---|---|
| `tests/test_document_ir_word_renderer_layout.py` | 目录标题 + 目录列表 + 正文标题 + 带页码的修订列表：修订项全部可见，TOC 字段 1 个 | AC1、AC3 |
| 同上 | 人工把区域外块的策略改为 `coalesced` 后调用 `validate_render_result`，报 `ir_docx_integrity:toc_coalesced_outside_region` | AC6 |
| `tests/test_document_ir_layout_contract.py` | 带账本 IR 删除一项后，`build_source_integrity` 报 `list_item_count_mismatch`；无账本 IR 输出结构与现状一致 | AC4、AC7 |
| `tests/test_mineru_artifact_validator.py` 或转换器布局测试 | `content_list_v2` 含空项：账本 `empty_item_count == 1`，转换成功 | AC5 |
| `tests/test_fastapi_jobs_backend.py` 中已有的 flag 投影用例附近 | 新码按固定码投影 | AC8 |

## 验证命令

```bash
.venv/bin/python -m unittest tests.test_document_ir_word_renderer_layout tests.test_document_ir_layout_contract
```

```bash
.venv/bin/python -m unittest tests.test_mineru_artifact_validator tests.test_document_ir_mineru_converter_layout tests.test_page_degradation
```

另用本地 OPA228 P2、RS2G04、OPA228 P1 产物做一次只读渲染核对（临时目录，不入库）：

- P2：Revision B→C 14 项、A→B 段落可见；TOC 字段 1 个。
- RS2G04：目录项仍并入字段，正文无新增的静态点线目录。

只在 S2/S5 触及的共享合同出现失败时，才扩大到 `tests.test_fastapi_jobs_backend` 中与渲染证据、base quality 相关的用例。不跑全仓回归。

## 文档与注释

- 新增函数用中文 docstring，只说明区域状态机、平衡式和历史兼容这类不明显的约束。
- 新增异常与阻断码保持英文机器码；异常说明用中文。
