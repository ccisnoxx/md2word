---
doc_type: feature-evidence
feature: 2026-06-03-golden-sample-live-regression-scale-up
slug: failure-classification
status: completed
created_at: 2026-06-03
tags: [golden-sample, failure-classification, pipeline-parity-gap, document-ir, renderer]
---

# failure-classification

## 结论

本轮 4 个 runnable Golden Sample 没有真实链路失败：上传、document job、Worker、MinerU、DocumentIR 保存、Word 渲染、下载和 DOCX openable 检查均通过。

P0 人工质量未通过的主要原因归为：

```text
pipeline-parity-gap
```

定义：`md2word_main` / `app/conversion/runtime` 里已有或已验证过的 heading、list、formula、caption、table 和 layout 策略，没有接入当前线上 API 的 `document_jobs -> DocumentIR -> app/services/renderer` 链路。

这不是单纯“线上镜像没更新”：hostdzire 容器内关键代码 hash 与当前本地 `md2word` 一致。问题在于线上 document job 使用的是 `DocumentIRWordRenderer`，不是 legacy conversion runtime 的完整渲染路径。

## 证据摘要

### 真实回归证据

| 项目 | 结果 |
|---|---|
| 回归批次 | `20260603T070724Z` |
| 运行环境 | hostdzire 真实 API / Worker / MinerU |
| runnable 样本 | `gs-003`、`gs-004`、`gs-006`、`gs-008` |
| 主链路成功 | 4 |
| 主链路失败 | 0 |
| DOCX openable | 4 true |
| 质量记录 | `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md` |

### 线上 API 链路证据

`app/domains/document_jobs/execution.py` 的 `_render_and_save_word` 从已保存的 DocumentIR 读取内容，然后调用 `self.word_renderer.render_to_bytes(...)`。当前 `word_renderer` 是 `app/services/renderer/DocumentIRWordRenderer`。

`DocumentIRWordRenderer` 当前 list 和 formula 行为仍较基础：

- list block 使用 `_fill_paragraph(..., prefix="• ")`，也就是手写项目符号，不是真实 Word numbering。
- formula block 直接写 `block.latex or block.text`，没有走 legacy runtime 的公式规整。

### legacy runtime 证据

`app/conversion/runtime/text_rendering.py` 已有可迁移策略：

- `render_heading` 使用 `PartNumber` / `Heading N` 样式。
- `fill_list_paragraph` 会调用 `apply_bullet_numbering`，生成真实 Word numbering。
- `normalize_formula_text` / `fill_rich_text` 支持把常见 TeX 片段转成更自然的 Word run。

`md2word_main/out` 当前可观察到的 3 个 standalone 输出也说明 sandbox 链路明显优于线上 DocumentIR renderer：

| sandbox output | styles / numbering / formula | 结论 |
|---|---|---|
| `OPA228_P2_standalone.docx` | `Heading 1/2` 存在，`numbering=14`，`latex_hits=0` | heading/list/formula 质量优于线上 |
| `OPA228_P6_standalone.docx` | `Caption/TableNote/TableContent` 存在，`latex_hits=0` | caption/table/formula 质量优于线上 |
| `OPA228_P7_standalone.docx` | `Heading 2/TableContent` 存在，`latex_hits=0` | heading/table/formula 质量优于线上 |

限制：当前未在 `md2word_main/out` 找到 `OPA228_P1_standalone.docx`。既有 `docs/testing/pdf-to-word-gs-003-quality-triage.md` 记录显示 P1 的 `md2word_main` 基线“比线上 smoke 更好”，但也明确仍有双栏、Device Information caption/list/figure 结构问题。因此本轮不能声称 P1 已完全修复。

## 分类表

| 类别 | 当前结论 | 后续路由 |
|---|---|---|
| environment | hostdzire 本轮可执行；API/Worker/MinerU 均可用。远端容器原本没有 Golden Sample manifest/PDF，需要运行前同步。 | docs-and-roadmap-backfill 记录运行注意事项；不进入修复 feature |
| sample-sourcing | 12 个 manifest 样本中仍有 8 个 `missing_pdf`，但不影响本轮 4 个 runnable 样本分类。 | sample-sourcing / 后续样本扩容，不进入 renderer 修复 |
| upload/download/API | 4 个 runnable 样本均成功，没有上传、任务创建、下载授权或 DOCX 包损坏问题。 | 无需新 issue |
| mineru-live-parse | 4 个 runnable 样本均完成 MinerU 主链路；未观察到 MinerU stage failure。 | 不作为当前 P0 阻塞 |
| document-ir-layout-risk | 双栏 block 分组、宽表分页/页面方向、caption 与表格/figure 的相对位置仍有风险。 | `document-ir-layout-risk-pass` |
| word-renderer-editable-output | heading/list/formula/caption/table 样式策略没有同步到 API DocumentIR renderer。 | `word-renderer-editable-output-pass` |
| pipeline-parity-gap | legacy runtime / md2word_main 已有部分修复，但线上 API DocumentIR renderer 未接入。 | 两个后续 feature 的共同前置判断 |

## 逐样本路由

| sample_id | 人工质量问题 | failure_bucket | next_feature |
|---|---|---|---|
| `gs-003` | heading 全为 `Normal`，list 非 Word numbering，LaTeX 残留，双栏退化为表格近似，Description 跨整页，Device Information caption 在表格下方，figure 绑定不稳定。 | `pipeline-parity-gap` + `document-ir-layout-risk` + `word-renderer-editable-output` | 先在 `document-ir-layout-risk-pass` 判断 IR/layout 输入是否足以表达列、caption、figure 关系；再在 `word-renderer-editable-output-pass` 接入 heading/list/formula/caption 策略 |
| `gs-004` | TOC/Revision 标题全为 `Normal`，revision 列表不是 Word numbering，TOC leader/缩进/页码对齐漂移。 | `pipeline-parity-gap` + `word-renderer-editable-output` | 主要进入 `word-renderer-editable-output-pass`；优先迁移 legacy heading/list 策略并加 document_jobs 回归 |
| `gs-006` | Thermal table caption 在表格下方，第三张表分页 continuation 弱，表头/合并语义扁平化，LaTeX 符号残留。 | `pipeline-parity-gap` + `document-ir-layout-risk` + `word-renderer-editable-output` | `document-ir-layout-risk-pass` 先判断 caption/footnote/table 关系是否在 IR 中完整；renderer 侧迁移 caption-before-table、table style 和公式规整 |
| `gs-008` | 宽表被 A4 portrait 压缩，末行孤立到第 2 页，表头合并语义扁平化，公式/符号残留。 | `pipeline-parity-gap` + `document-ir-layout-risk` + `word-renderer-editable-output` | `document-ir-layout-risk-pass` 先判断页面方向/宽表信号；renderer 侧迁移宽表布局、table style 和公式规整 |

## 对下一轮 feature 的约束

### document-ir-layout-risk-pass

不要从零重写布局算法。第一步应做 parity 判断：

1. 对比当前 live job 保存的 DocumentIR 与 `md2word_main/mineru_result/*` legacy pages/blocks，确认哪些布局事实已经在 IR 里，哪些丢在 MinerU -> DocumentIR 转换阶段。
2. 盘点 `app/conversion/runtime/page_layout_runtime.py`、`page_repair_runtime.py`、`input_adapter_runtime.py` 中可迁移的策略：
   - page orientation / landscape 判断
   - two-column page/body block 分组
   - visual block caption/footnote 绑定
   - long/wide table continuation 信号
3. 只在 IR 缺字段或字段表达不足时改 DocumentIR；能由 renderer 消费现有字段解决的，不扩大 IR。

退出标准应是：列出“可直接迁移到 DocumentIR renderer 的 legacy 策略”和“必须补到 DocumentIR 的布局事实”。

### word-renderer-editable-output-pass

第一目标不是重新发明 renderer，而是把 `app/conversion/runtime` 的成熟策略同步到 `app/services/renderer`，并覆盖 API document_jobs 链路。

优先迁移范围：

1. heading：把 DocumentIR heading 渲染成真实 Word heading / configured named style，不再全部落成 `Normal`。
2. list：把 `fill_list_paragraph` / `apply_bullet_numbering` 的真实 numbering 策略迁移到 `DocumentIRWordRenderer`，禁止手写 `• ` prefix 作为最终语义。
3. formula/rich text：复用 `normalize_formula_text` / `fill_rich_text` 的 TeX 清理、上下标、`√Hz`、`θ/ψ/µ/±/°C` 等处理。
4. caption/table：迁移 caption-before-table、keep-with-next、TableContent/TableNote/Caption 等样式策略。
5. wide/long table：复用 table width、repeat/continuation 和 page orientation 策略；特别覆盖 `gs-006`、`gs-008`。

测试要求：

- 必须新增或更新 document_jobs / DocumentIR renderer 回归测试，不能只测 `md2word_main` sandbox 或 `app/conversion/runtime` 单元。
- 至少覆盖 `gs-004` 的 heading + Word numbering、`gs-006` 的 caption-before-table + formula clean、`gs-008` 的 wide table + formula clean。
- 验证产物要检查 OOXML 语义：paragraph style、`w:numPr`、LaTeX 残留、caption/table 顺序，而不是只看 DOCX 可打开。

## 当前 feature 后续动作

`failure-classification` 已满足退出信号：每个失败或质量不通过项都已路由到 environment、sample-sourcing、document-ir-layout-risk-pass 或 word-renderer-editable-output-pass。

下一步按 checklist 进入 `docs-and-roadmap-backfill`，回填 Golden Sample 验收报告和 roadmap notes，使后续 `document-ir-layout-risk-pass` design 可以直接读取本分类表。

