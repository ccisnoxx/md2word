---
doc_type: dev-guide
slug: local-conversion-sandbox
component: conversion-runtime
status: current
summary: 在正式项目中用 PyCharm 运行本地 MinerU 转 DOCX 调试。
tags: [conversion, mineru, sandbox, regression, pycharm]
last_reviewed: 2026-10-21
---

# 本地 MinerU 转 DOCX 调试入口

## 当前决定

`/Users/sc/PycharmProjects/md2word` 是唯一长期维护的转换代码源。所有本地 MinerU 结果包转 DOCX 调试，都在正式项目中通过 `scripts.dev.formal_mineru_conversion` 进入正式 DocumentIR 转换与 Word renderer 核心。

排版行为修复必须落到正式核心：`app/services/document_ir/*`、`app/services/renderer/*` 或共享规则 `app/conversion/docx_rules/*`。本地脚本只做路径、离线翻译响应和报告适配，不写独立排版逻辑。

`/Users/sc/PycharmProjects/PythonProject/md2word_main` 不再作为运行入口。它只保留历史样例资产和输出资产，例如：

- `test_pdf/`
- `mineru_result/`
- `out/`

不要再从 `md2word_main/mineru_to_docx.py` 运行转换。该入口已废弃，直接运行只会提示迁移到正式项目。

## PyCharm 推荐运行方式

在 PyCharm 中打开正式项目：

```text
/Users/sc/PycharmProjects/md2word
```

仓库已提供三个可共享 Run Configuration：

- `Local MinerU Direct`
- `Local MinerU En2Zh`
- `Local MinerU Ru2Zh`

如果 PyCharm 没有自动识别 `.run/` 下的配置，可以手动新建 Python Run Configuration：

- Script path: `scripts/dev/run_local_mineru_debug_config.py`
- Working directory: `/Users/sc/PycharmProjects/md2word`
- Python interpreter: 选择正式项目的 Python 3.11 解释器，例如 `.venv/bin/python`
- Parameters:
  - direct：`--config scripts/dev/local_mineru_debug_direct_config.json`
  - en2zh：`--config scripts/dev/local_mineru_debug_en2zh_config.json`
  - ru2zh：`--config scripts/dev/local_mineru_debug_ru2zh_config.json`

默认直接运行脚本时使用 direct 配置兼容文件：

```text
scripts/dev/local_mineru_debug_config.json
```

点击运行后，脚本会读取该 JSON 配置，解析路径，然后调用：

```python
scripts.dev.formal_mineru_conversion.run_conversion(...)
```

## 配置文件

默认配置示例：

```json
{
  "input_path": "mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4",
  "output_path": "tests/tmp/local_mineru_debug/direct/OPA228_P1.docx",
  "document_language": "en",
  "translation_mode": "direct",
  "template_path": "resources/templates/default/datasheet_template.docx",
  "layout_config_path": "resources/template_configs/datasheet_template_v2.yaml",
  "subscript_config": "resources/term_rules/subscripts_dictionary.yaml",
  "no_template": false,
  "use_mineru_header_footer": false,
  "translation_trace_output": "",
  "log_level": "INFO"
}
```

路径规则：

- 相对路径从正式项目根目录 `/Users/sc/PycharmProjects/md2word` 解析。
- 新样例优先放在正式项目根目录的 `mineru_result/`。
- 历史样例可以先复制或同步到正式项目 `mineru_result/` 后再运行；不要从 `md2word_main` 启动转换。
- 输出建议写入 `tests/tmp/`，不要提交生成的 DOCX、PNG、PDF 或调试 trace。

常用字段：

| 字段 | 用途 |
|---|---|
| `input_path` | MinerU 结果目录或 zip，必填 |
| `output_path` | 输出 DOCX 路径 |
| `document_language` | `auto` / `zh` / `en` / `ru` |
| `translation_mode` | `direct` / `none` / `en2zh` / `ru2zh` / `llm_en_to_zh` / `llm_ru_to_zh` |
| `template_path` | Word 模板 |
| `layout_config_path` | 版式 YAML |
| `subscript_config` | 术语/上下标 YAML |
| `no_template` | 是否禁用模板 |
| `use_mineru_header_footer` | 兼容字段；正式 renderer 行为以模板配置和 DocumentIR 布局事实为准 |
| `translation_request_output` | 写出 LLM 请求 JSON |
| `translation_response` | 读取 LLM 响应 JSON |
| `translation_trace_output` | 写出翻译 trace JSON |
| `translation_model` | 翻译模型名 |
| `translation_api_key` | 翻译 API key；不要提交真实密钥 |
| `translation_base_url` | OpenAI-compatible base URL |
| `translation_max_pages` | 翻译批次页数软限制 |
| `translation_max_chars` | 实际编码 items 文本字符硬限制；不是完整 Prompt 的 tokenizer 上限 |
| `log_level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

如果需要使用另一个配置文件，可以在 PyCharm Parameters 中传入：

```text
--config scripts/dev/local_mineru_debug_en2zh_config.json
```

命令行等价验证：

```bash
.venv/bin/python scripts/dev/run_local_mineru_debug_config.py
.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_direct_config.json
.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_en2zh_config.json
.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_ru2zh_config.json
```

## direct、en2zh 与 ru2zh 配置

`scripts/dev/local_mineru_debug_direct_config.json` 用于原排版直出：

- `translation_mode=direct`
- `document_language=en`
- 输出到 `tests/tmp/local_mineru_debug/direct/`
- `translation_request_output` / `translation_response` / `translation_trace_output` 留空

`scripts/dev/local_mineru_debug_en2zh_config.json` 用于英文转中文后出 Word：

- `translation_mode=en2zh`
- `document_language=auto`，转换后默认按中文排版覆盖处理
- `translation_request_output` 写到 `tests/tmp/local_mineru_debug/en2zh/`
- `translation_trace_output` 只在翻译响应成功应用后生成
- `translation_api_key` 和 `translation_base_url` 默认留空，真实值从 `.env`、环境变量或 PyCharm 环境变量读取

`scripts/dev/local_mineru_debug_ru2zh_config.json` 用于俄文转中文后出 Word：

- `translation_mode=ru2zh`
- `document_language=auto`，转换后默认按中文排版覆盖处理
- 输入样本固定为 `mineru_result/диод анод сверху.pdf-5a23152f-e597-40a4-98e8-585b78811b63`
- `translation_request_output` 写到 `tests/tmp/local_mineru_debug/ru2zh/`
- `translation_trace_output` 只在翻译响应成功应用后生成
- `translation_response` 默认留空；离线调试时填入未提交的本地响应 JSON

如果没有 `OPENAI_API_KEY` 且没有配置 `translation_response`，en2zh/ru2zh 会明确失败并提示缺少 key；这是预期行为，不会自动回退为 direct。需要离线调试时，先让脚本写出 `translation_request_output`，再把本地未提交的响应 JSON 填到 `translation_response`。

## TR-403 本地翻译请求 v2 与严格响应

`translation_request_output` 使用 `document-ir-local-translation-request/v2`，导出共享正式计划实际发送的编码 items，而不是 v1 的原始技术文本。每个实际 batch 独立生成占位符；既有 `char_count` 表示原文字符数，`encoded_char_count` 表示编码文本字符数。术语/Prompt/预算和完整性规则由正式 translator 拥有，本地 adapter 不维护第二套计划或自动修复。

离线响应只返回约定字段，例如：

```json
{"items":[{"id":"原请求中的完整 ID","text":"自然语言译文 {{MD2W_PT_v1_0_1}}"}]}
```

多批也可返回 `{"batches":[{"batch_id":"实际批次 ID","items":[...]}]}`；每批仅允许 `items` 和可选 `batch_id`。不要把请求的 schema、页码或字符计数复制进响应。全部 item/batch 必须与实际请求的数量、顺序和 ID 一致，完整 envelope 在翻译和回填前核对；不能以字典覆盖、过滤额外项或重排来修正响应。

所有占位符须在原 item 中恰好一次、字符完全一致；允许同 item 内移动，不允许跨 item 转移。响应不能在保留占位符之外新增裸数字、单位、型号、地址、位字段或公式。任一失败不回填、不生成目标 DOCX/成功 trace，不静默回退源文。无技术 Token 的合法文字响应仍可用。

原 v1 导出文件保持不变；技术文本响应必须重新导出 v2 并按真实编码请求提供，不把旧原文响应自动转换成占位响应。请求仍可能包含未保护自然语言；占位不是全文匿名化，显式导出文件和成功全文 trace 只留本地受控目录，不提交仓库或作为普通审计输出。direct 不导出/读取翻译资源，也不调用 Provider。

## 命令行临时入口

仍然保留 CLI 参数型入口，用于一次性命令行验证：

```bash
.venv/bin/python scripts/dev/run_local_mineru_conversion.py \
  mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \
  --output tests/tmp/local_conversion/direct/OPA228_P1.docx \
  --document-language en \
  --translation-mode direct
```

PyCharm 日常调试优先使用配置文件入口，避免每次手写参数。

## DOCX 标准视觉验收

DOCX 版式验收优先使用标准渲染链，不再使用 macOS Quick Look 缩略图作为最终判断。Quick Look / `qlmanage` 只适合在标准链不可用时做临时预览；它不是 Word 或 LibreOffice 排版引擎，页眉、浮动图片、锚定对象、文本环绕和字体度量可能出现误判。

标准链路：

```text
DOCX --soffice--> PDF --pdf2image + Poppler--> PNG
```

本机依赖：

- Python 虚拟环境：`pdf2image`、`Pillow`
- macOS 系统工具：LibreOffice 提供 `soffice`
- macOS 系统工具：Poppler 提供 `pdfinfo` 和 `pdftoppm`

首次配置：

```bash
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install pdf2image
brew install poppler
brew install --cask libreoffice
```

确认依赖：

```bash
.venv/bin/python -c "import pdf2image, PIL; print('pdf2image ok', PIL.__version__)"
command -v soffice
command -v pdfinfo
command -v pdftoppm
```

渲染 direct：

```bash
env TMPDIR=/private/tmp .venv/bin/python \
  /Users/sc/.codex/plugins/cache/openai-primary-runtime/documents/26.622.11653/skills/documents/render_docx.py \
  tests/tmp/local_mineru_debug/direct/OPA228_P1.docx \
  --output_dir tests/tmp/local_mineru_debug/visual_qa/standard_render/direct \
  --emit_pdf
```

渲染 en2zh：

```bash
env TMPDIR=/private/tmp .venv/bin/python \
  /Users/sc/.codex/plugins/cache/openai-primary-runtime/documents/26.622.11653/skills/documents/render_docx.py \
  tests/tmp/local_mineru_debug/en2zh/OPA228_P1.zh.docx \
  --output_dir tests/tmp/local_mineru_debug/visual_qa/standard_render/en2zh \
  --emit_pdf
```

Codex 桌面沙箱注意点：

- 在 Codex 受限沙箱内直接运行 LibreOffice 可能出现 `Abort trap: 6`。
- 同一条 `render_docx.py` 命令在非沙箱权限下可以正常完成。
- 因此通过 Codex 执行标准渲染时，需要用非沙箱权限运行；在本机终端或 PyCharm 正常运行时，按上面的命令即可。

视觉检查以 `page-*.png` 和可选的中间 PDF 为准。检查首页顶部 logo、页眉标题、产品标题、正文起始区域、表格边框、图片缩放、页脚页码和分页；如果 Word 实际打开结果与 Quick Look 不一致，以 Word 或标准 LibreOffice 渲染为准。

## 第二阶段质量矩阵

本地 MinerU 质量硬化使用专用矩阵 runner，覆盖 OPA228 P0 canonical suite 和 RS2G04 观察样本：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --mode direct \
  --sample-set phase2-core
```

矩阵包含：

- P0：`OPA228_P1`、`OPA228_P2`、`OPA228_P6`、`OPA228_P7`
- P1 观察：`RS2G04`

输出目录默认是 `tests/tmp/local_mineru_quality/<run_id>/`，包括：

- `docx/<mode>/<sample>.docx`
- `report.json`
- `report.md`
- `manual-signoff-template.yaml`

报告会记录 MinerU 页数、block 类型统计、图片数、DOCX hash、DOCX 可打开性、`docx_quality_flags`、P0/P1/P2 issue 分类，以及每个样本的标准渲染命令。runner 不会自动执行 LibreOffice 渲染；人工验收前按报告中的 `render_docx.py` 命令生成 PNG/PDF 证据。

en2zh 可以单独运行：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --mode en2zh \
  --sample-id OPA228_P1 \
  --translation-response-dir tests/tmp/local_mineru_debug/en2zh_responses
```

ru2zh 验收样本可以单独运行：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --sample-set ru2zh-acceptance \
  --mode ru2zh \
  --translation-response-dir tests/tmp/local_mineru_debug/ru2zh_responses
```

如果没有本地 `translation_response` 且没有 `OPENAI_API_KEY`，en2zh/ru2zh 条目会被标记为 `blocked` / `translation_api_key_missing`，不会静默回退到 direct。

## md2word_main 的状态

`md2word_main/mineru_to_docx.py` 已 deprecated：

- 不再代理调用 `scripts.dev.run_local_mineru_conversion`。
- 不再执行转换。
- 只输出迁移提示并以非零状态退出。

`md2word_main` 可以继续作为历史样例资产来源：

- 从 `test_pdf/` 识别 PDF。
- 从 `mineru_result/` 选择 MinerU 结果包。
- 必要时参考 `out/` 中的历史输出。

如果某个本地样例需要长期回归，应沉淀到：

[component-pdf-regression-governance.md](/Users/sc/PycharmProjects/md2word/docs/dev/component-pdf-regression-governance.md)

## Sandbox 审计

检查 `md2word_main` 是否仍存在活动复制代码：

```bash
.venv/bin/python scripts/dev/audit_conversion_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main \
  thin
```

盘点历史样例资产：

```bash
.venv/bin/python scripts/dev/audit_conversion_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main \
  samples --json
```

不要通过复制 `md2word_main/app/conversion` 来解决差异。转换行为修复必须进入正式项目的 DocumentIR/renderer 核心，并配套测试或样例回归。

## 验证

本地入口或 sandbox 工具变更后运行：

```bash
.venv/bin/python -m unittest tests.test_conversion_sandbox_dev_tools
.venv/bin/python -m unittest tests.test_local_mineru_quality_matrix
```

电子元器件样例治理变更后运行：

```bash
.venv/bin/python -m unittest tests.test_component_pdf_sample_governance
```

转换行为变更才需要额外运行相关 characterization tests；本入口治理任务不应改渲染策略。

## 风险和约束

- `md2word_main/resources/term_rules/term_rules.v2.yaml` 可能包含历史本地规则，但不能整包复制进正式项目；需要走术语规则流程。
- 正式项目根目录的 `mineru_result/` 是本地 staging，已被 `.gitignore` 忽略。
- 专有或客户 PDF 不应提交到正式项目；使用 manifest 指针或私有证据存储。
- 如果本地历史输出看起来更好，要把最小行为差异沉淀到 `app/services/document_ir/*`、`app/services/renderer/*` 或共享规则 `app/conversion/docx_rules/*` 并补测试，不能恢复 `md2word_main` 作为第二代码源。

完整第一阶段计划和后续扩展路线见：

[local-component-pdf-debugging-implementation-plan.md](/Users/sc/PycharmProjects/md2word/docs/dev/local-component-pdf-debugging-implementation-plan.md)
