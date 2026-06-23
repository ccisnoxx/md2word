---
doc_type: dev-guide
slug: component-pdf-regression-governance
component: conversion-runtime
status: current
summary: 电子元器件 PDF 的品牌/分类样例治理与本地回归流程。
tags: [conversion, mineru, regression, samples, datasheet]
last_reviewed: 2026-06-23
---

# 电子元器件 PDF 样例回归治理

## 目的

当本地电子元器件 PDF 暴露出转换排版问题，并且这个问题后续不应再回归时，使用这套流程沉淀样例和验收记录。正式转换代码源始终是 `app/conversion`；`md2word_main` 只作为本地调试薄壳和样例来源。

这套样例体系独立于：

- `tests/fixtures/golden_samples/` 下的 P0 Golden Samples
- `tests/fixtures/p1_translation_samples/` 下的 P1 翻译样例

## 样例目录结构

电子元器件样例放在：

```text
tests/fixtures/component_pdf_samples/
  manifest.yaml
  acceptance-record-template.md
  samples/<brand>/<category>/<sample-id>/mineru/
```

`brand`、`category` 和 `sample-id` 使用小写 kebab-case。`manifest.yaml` 统一维护样例元数据，包括产品型号、标题、源 PDF 引用、MinerU 结果包路径、标签和人工验收关注点。

## 添加新的本地 MinerU 样例

从本地 MinerU 结果目录开始添加样例。这个目录通常来自 `md2word_main/mineru_result/`。

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/manage_component_pdf_samples.py \
  add-mineru-sample \
  --sample-id ti-opamp-opa228-p7-wide-table \
  --brand texas-instruments \
  --category op-amp \
  --product OPA228 \
  --title "OPA228 电气特性宽表" \
  --source-pdf "md2word_main:test_pdf/OPA228_P7.pdf" \
  --mineru-package /Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_result/OPA228_P7.pdf-d457d448-c495-41ea-8bcf-41a3f18c00fb \
  --tag datasheet \
  --tag wide_table \
  --tag electrical_characteristics \
  --acceptance-focus "电气特性宽表在 Word 中保持可编辑" \
  --acceptance-focus "单位和符号保持可读" \
  --apply
```

添加后运行 manifest 校验：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/manage_component_pdf_samples.py validate
```

## 本地回归闭环

推荐的日常流程是：

1. 在 `md2word_main` 或 worktree 调试环境中发现本地问题。
2. 将最小化后的 MinerU 样例加入 `tests/fixtures/component_pdf_samples/`。
3. 只在 `app/conversion` 中修复转换行为。
4. 运行电子元器件样例回归：

   ```bash
   /Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_component_pdf_regression.py
   ```

5. 人工检查生成的 DOCX。
6. 使用 `tests/fixtures/component_pdf_samples/acceptance-record-template.md` 记录人工验收结果。

默认情况下，生成的 DOCX 和报告会写入 `tests/tmp/component_pdf_regression/`。不要提交生成的 DOCX、渲染 PNG/PDF，或任何专有/客户 PDF。

## 针对性验证

修改样例治理结构、manifest 或脚本时运行：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_component_pdf_sample_governance
```

某个电子元器件样例暴露转换问题并完成修复后，运行对应样例回归：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_component_pdf_regression.py \
  --sample-id <sample-id>
```

交付前再运行相关的 conversion characterization tests，确保修复没有破坏既有转换行为。
