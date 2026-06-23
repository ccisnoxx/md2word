---
doc_type: dev-guide
slug: local-conversion-sandbox
component: conversion-runtime
status: current
summary: 在正式项目中用 PyCharm 运行本地 MinerU 转 DOCX 调试。
tags: [conversion, mineru, sandbox, regression, pycharm]
last_reviewed: 2026-06-23
---

# 本地 MinerU 转 DOCX 调试入口

## 当前决定

`/Users/sc/PycharmProjects/md2word` 是唯一长期维护的转换代码源。所有本地 MinerU 结果包转 DOCX 调试，都在正式项目中运行 `app/conversion`。

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

新建或更新一个 Python Run Configuration：

- Script path: `scripts/dev/run_local_mineru_debug_config.py`
- Working directory: `/Users/sc/PycharmProjects/md2word`
- Python interpreter: 选择正式项目的 Python 3.11 解释器，例如 `.venv/bin/python`
- Parameters: 留空

默认配置文件：

```text
scripts/dev/local_mineru_debug_config.json
```

点击运行后，脚本会读取该 JSON 配置，解析路径，然后调用：

```python
app.conversion.runtime_runner.run_conversion(...)
```

## 配置文件

默认配置示例：

```json
{
  "input_path": "/Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4",
  "output_path": "tests/tmp/local_mineru_debug/OPA228_P1.docx",
  "document_language": "en",
  "translation_mode": "direct",
  "template_path": "resources/templates/default/datasheet_template.docx",
  "layout_config_path": "resources/template_configs/datasheet_template.yaml",
  "subscript_config": "resources/term_rules/subscripts_dictionary.yaml",
  "no_template": false,
  "use_mineru_header_footer": false,
  "translation_trace_output": "",
  "log_level": "INFO"
}
```

路径规则：

- 相对路径从正式项目根目录 `/Users/sc/PycharmProjects/md2word` 解析。
- 绝对路径可以指向 `md2word_main/mineru_result` 下的历史 MinerU 结果包。
- 输出建议写入 `tests/tmp/`，不要提交生成的 DOCX、PNG、PDF 或调试 trace。

常用字段：

| 字段 | 用途 |
|---|---|
| `input_path` | MinerU 结果目录或 zip，必填 |
| `output_path` | 输出 DOCX 路径 |
| `document_language` | `auto` / `zh` / `en` |
| `translation_mode` | `direct` / `none` / `en2zh` / `llm_en_to_zh` |
| `template_path` | Word 模板 |
| `layout_config_path` | 版式 YAML |
| `subscript_config` | 术语/上下标 YAML |
| `no_template` | 是否禁用模板 |
| `use_mineru_header_footer` | 是否使用 MinerU 识别的页眉页脚 |
| `translation_request_output` | 写出 LLM 请求 JSON |
| `translation_response` | 读取 LLM 响应 JSON |
| `translation_trace_output` | 写出翻译 trace JSON |
| `translation_model` | 翻译模型名 |
| `translation_api_key` | 翻译 API key；不要提交真实密钥 |
| `translation_base_url` | OpenAI-compatible base URL |
| `translation_max_pages` | 翻译批次页数软限制 |
| `translation_max_chars` | 翻译批次字符硬限制 |
| `log_level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

如果需要使用另一个配置文件，可以在 PyCharm Parameters 中传入：

```text
--config scripts/dev/local_mineru_debug_config.json
```

命令行等价验证：

```bash
.venv/bin/python scripts/dev/run_local_mineru_debug_config.py
```

## 命令行临时入口

仍然保留 CLI 参数型入口，用于一次性命令行验证：

```bash
.venv/bin/python scripts/dev/run_local_mineru_conversion.py \
  /Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \
  --output tests/tmp/local_conversion/OPA228_P1.docx \
  --document-language en \
  --translation-mode direct
```

PyCharm 日常调试优先使用配置文件入口，避免每次手写参数。

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

不要通过复制 `md2word_main/app/conversion` 来解决差异。转换行为修复必须进入正式项目 `app/conversion`，并配套测试或样例回归。

## 验证

本地入口或 sandbox 工具变更后运行：

```bash
.venv/bin/python -m unittest tests.test_conversion_sandbox_dev_tools
```

电子元器件样例治理变更后运行：

```bash
.venv/bin/python -m unittest tests.test_component_pdf_sample_governance
```

转换行为变更才需要额外运行相关 characterization tests；本入口治理任务不应改渲染策略。

## 风险和约束

- `md2word_main/resources/term_rules/term_rules.v2.yaml` 可能包含历史本地规则，但不能整包复制进正式项目；需要走术语规则流程。
- 专有或客户 PDF 不应提交到正式项目；使用 manifest 指针或私有证据存储。
- 如果本地历史输出看起来更好，要把最小行为差异沉淀到 `app/conversion` 并补测试，不能恢复 `md2word_main` 作为第二代码源。
