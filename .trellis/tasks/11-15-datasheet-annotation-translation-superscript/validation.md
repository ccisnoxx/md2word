# 实施与同源验收记录

2026-11-15，基线为 `main@ea16ebddd0739a67d3d7b5a56c59c80ecfcaab68`。实现复用 TR-401 的按源下标抽取和回填规则，接入当前批次、源 IR 合同及渲染证据。工作区实现待评审。

## 代码验证

合并回归 304 项通过。随后对两个更新用例定向复跑均通过，其中一个是合并回归启动后新增的占位表用例，合计覆盖 305 个不同用例。验证四种语言的正式应用入口、已绑定 Profile 和 Prompt、direct 的注释原文及零翻译调用、历史源范围恢复、完整性与拆分、表级和单元格上下文、审核权限和证据、表转图、续表、Word 新旧公式报告及 B1。四方向使用确定性 Provider 校验应用链路。

```bash
.venv/bin/python -m unittest \
  tests.test_document_ir_translation tests.test_translation_table_context \
  tests.test_document_job_execution_stages tests.test_translation_integrity_execution \
  tests.test_formula_translation_boundary tests.test_translation_batch_workflow \
  tests.test_document_job_review_blocks_api tests.test_document_job_review_hints \
  tests.test_formula_rendering tests.test_formula_rendering_compatibility \
  tests.test_image_group_rendering tests.test_b1_preview_rollback \
  tests.test_document_ir_word_renderer_layout tests.test_document_ir_mineru_converter_layout tests.test_formal_mineru_render_evidence \
  tests.test_conversion_sandbox_dev_tools.LocalTranslationIntegrityTests \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_debug_full_text_is_admin_only
```

独立复核实际复现同代旧 attempt 迟到时覆盖调试对照。本版从译后 IR 的档案绑定读取已采用译文及术语证据，对应正式 API 回归通过。新增的同译文独立位置、占位表正文别名、图表原始来源和历史图注报告用例也通过定向验证。历史 RS2G04 主件通过实物及已登记 IR 的 SHA-256 核对，旧 `text_fallback` 公式报告可正常重读。

额外探查的 `test_document_job_uses_bound_profile_prompt_without_public_or_audit_leak` 在建应用时遇到模板 `default@2` seed 注册冲突。在干净的 `git archive ea16ebdd` 中使用同一运行时复现同一错误，发生于翻译前。该历史用例保留原状。Python 变更通过语法解析，Trellis 上下文及 `git diff --check` 通过。

## RS2G04 Rev A.4 第 6 页

以 [扩展样本清单](../11-11-datasheet-quality-baseline-contracts/extended-sample-manifest.json) 中登记的第 6 页为准。PDF、MinerU ZIP 和 content list v2 三份字节指纹均匹配。使用隔离的 FastAPI 应用、eager Worker、SQLite 和本地对象存储，注入同一份已保存的 MinerU ZIP。英译中使用现有版本化资源及 `deepseek-v4-flash`，真实 Provider 调用 1 次，共 87 项，应用重试 0 次。随后按同一有序编码请求和 Prompt 内容摘要重放已取得的响应，分别验证当前工作区的原始表头稿和同源校核稿。模板均为 `default@2`。

| 样本产物 | 注释、公式与结构 | DOCX SHA-256 |
| --- | --- | --- |
| [direct](../../../tests/tmp/datasheet-annotation-20261115/direct-final/RS2G04-p6.docx) | 注释原文与翻译源一致，零 Provider 调用和零批次。上标及签发下载通过。原始 ESD 表 4×4、两处合并，MinerU 缺首行表头语义。 | `462eddcfeb9666a4ce9557e5d67b5229bdf96317d428445e1033a5fe19563f12` |
| [原始输入实译](../../../tests/tmp/datasheet-annotation-20261115/live-original/RS2G04-p6.docx) | 8 组注释实译和恢复摘要通过。上标、签发下载和持久化读取通过。 | `20a7076554ea1125ac498061ee3f24213c80207f5f87c3f3f9020949ff952c28` |
| [最终代码复用实译响应](../../../tests/tmp/datasheet-annotation-20261115/live-recorded-original-final/RS2G04-p6.docx) | 8 组原译文、8 个对应批次绑定及 8 个 QA 单元通过。仅首行表头与独立标注有差异。 | `e88c28a348fc36a4c03cc8640e408d2e7e732ce37b3f12a6491920358d7e29db` |
| [同源表头校核稿](../../../tests/tmp/datasheet-annotation-20261115/live-header-reviewed-final/RS2G04-p6.docx) | 与上行的八条译文相同。4×4 原生表、首行表头、两处合并和标注的三个数值均通过。 | `1e29bc39ae1a8a5496a919a1f88cbbbfec1dbb718df9641c63e0653315bea9bb` |

源 PDF 文本独立核对额定值的风险、负电压例外、参考条件、JESD-51、最大功耗以及 ESD 使用限制、JEP155 和 JEP157。逐条对照八组源 IR、译后 IR 与审核返回，五条额定值脚注和两条 JEDEC 脚注保留限定条件，8.2 使用说明只出现一次。注释中的 19 个 Codec 占位通过批次完整性验证，ESD 标注的三个表格数值保留。

温度条件后的 `block_0003_context_0001.text` 对应公式报告为 `semantic_runs`。实物锚点内是文本为 `(1)(2)` 且带 `w:vertAlign w:val="superscript"` 的 Word run。此处无公式降级提示。源、目标、审核和输出对照通过。

LibreOffice 26.2.4.2 预览显示第一处上标及注释落在预期位置。当前模板的部分中文字形在该环境中显示为空白或方框，译文内容在 OOXML 与审核接口可读。Microsoft Word 的人工核对结果见下节。实译始终复用保存的解析包，未触发新的 MinerU 解析。其他三个方向的证据为确定性回归。

### Microsoft Word 人工验收

2026-11-15，用户在 Microsoft Word 中核对了 [RS2G04 第 6 页同源表头校核稿](../../../tests/tmp/datasheet-annotation-20261115/live-header-reviewed-final/RS2G04-p6.docx)，确认 **10/10 通过**。验收绑定的 DOCX SHA-256 为 `1e29bc39ae1a8a5496a919a1f88cbbbfec1dbb718df9641c63e0653315bea9bb`。

| 清单项 | 人工结果 |
| --- | --- |
| 1–5 · 8.1 绝对最大额定值表下五条脚注 | 5/5 通过 |
| 6 · 8.2 标题与 ESD 表之间的使用说明 | 1/1 通过 |
| 7–8 · ESD 表下 JEP155 和 JEP157 两条 JEDEC 脚注 | 2/2 通过 |
| 9 · 8.1 表前温度条件句末的 `(1)(2)` 原生上标 | 1/1 通过 |
| 10 · 8.2 ESD 额定值表首行的重复表头 | 1/1 通过 |

### 温度范围译词差异

位置为 8.1 绝对最大额定值标题与表格之间的温度条件句，`block_0003_context_0001.text`，紧邻 `(1)(2)` 上标。源 PDF 为 `over operating free-air temperature range (unless otherwise noted)`，校核稿为「在全程环境温度范围内（除非另有说明）」。源文包含工作状态和自由空气条件的限定，当前译词待单独复核。本项独立于上表的 10 项人工验收，验收稿保留原字节。
