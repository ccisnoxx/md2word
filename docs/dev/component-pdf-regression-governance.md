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

当本地电子元器件 PDF 暴露出转换排版问题，并且这个问题后续不应再回归时，使用这套流程沉淀样例和验收记录。正式转换代码源始终是 `app/conversion`；`md2word_main` 只作为历史样例资产来源，不再作为运行入口。

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

从本地 MinerU 结果目录开始添加样例。新样例优先放在正式项目根目录 `mineru_result/`，转换调试应在正式项目中通过 `scripts/dev/run_local_mineru_debug_config.py` 运行。

```bash
.venv/bin/python scripts/dev/manage_component_pdf_samples.py \
  add-mineru-sample \
  --sample-id ti-opamp-opa228-p7-wide-table \
  --brand texas-instruments \
  --category op-amp \
  --product OPA228 \
  --title "OPA228 电气特性宽表" \
  --source-pdf "local:mineru_result/OPA228_P7.pdf-d457d448-c495-41ea-8bcf-41a3f18c00fb/bb850108-9783-4a28-8523-9b115319bd47_origin.pdf" \
  --mineru-package mineru_result/OPA228_P7.pdf-d457d448-c495-41ea-8bcf-41a3f18c00fb \
  --tag datasheet \
  --tag wide_table \
  --tag electrical_characteristics \
  --acceptance-focus "电气特性宽表在 Word 中保持可编辑" \
  --acceptance-focus "单位和符号保持可读" \
  --apply
```

添加后运行 manifest 校验：

```bash
.venv/bin/python scripts/dev/manage_component_pdf_samples.py validate
```

## 本地回归闭环

推荐的日常流程是：

1. 在正式项目 PyCharm 配置入口或 worktree 调试环境中发现本地问题，输入路径优先指向正式项目内 `mineru_result/`。
2. 将最小化后的 MinerU 样例加入 `tests/fixtures/component_pdf_samples/`。
3. 只在 `app/conversion` 中修复转换行为。
4. 运行电子元器件样例回归：

   ```bash
   .venv/bin/python scripts/dev/run_component_pdf_regression.py
   ```

5. 人工检查生成的 DOCX。
6. 使用 `tests/fixtures/component_pdf_samples/acceptance-record-template.md` 记录人工验收结果。

默认情况下，生成的 DOCX 和报告会写入 `tests/tmp/component_pdf_regression/`。不要提交生成的 DOCX、渲染 PNG/PDF，或任何专有/客户 PDF。

## 第二阶段样本矩阵与长期样例的边界

第二阶段质量硬化先使用本地矩阵 runner 覆盖 `mineru_result/` 中的当前样本：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core
```

该矩阵用于快速扩大观察面和生成 QA 报告，不要求所有样本都进入 `tests/fixtures/component_pdf_samples/`。只有满足以下条件的样本才沉淀为长期 fixture：

- 来源公开，或已经最小化为不包含专有内容的 MinerU 包。
- 暴露出一个明确且后续需要防回归的版式风险。
- Manifest 能写清品牌、分类、产品型号、源 PDF 引用、标签和人工验收关注点。
- 样本体积可控，优先单页或最小页组，不提交完整客户资料。

新增样本优先补齐一个风险类型，例如长表、宽表、pinout/diagram、ordering info、复杂页眉页脚、中文技术手册或多页图文混排。不要一次把大量 PDF 加进 fixture；先在本地矩阵中观察并完成 P0/P1/P2 分级。

## P0 / P1 / P2 分级

- P0：DOCX 无法生成或打开、正文为空、疑似整页截图、OPA228 P0 任一核心焦点失败、关键表格不可读、关键图片缺失、direct/en2zh 结构顺序被破坏、en2zh 静默降级或泄露 key/trace。
- P1：RS2G04 或新增观察样本出现明显版式偏差但不破坏 OPA228 P0；双栏、分页、宽表在边界样本中可读但明显不接近 PDF；自动 quality flags 需要人工解释放行。
- P2：小范围 spacing、颜色、字号、caption 位置偏差；复杂双栏平衡和局部美观问题；报告 metadata、文档说明或样本治理改进。

## 针对性验证

修改样例治理结构、manifest 或脚本时运行：

```bash
.venv/bin/python -m unittest tests.test_component_pdf_sample_governance
.venv/bin/python -m unittest tests.test_local_mineru_quality_matrix
```

某个电子元器件样例暴露转换问题并完成修复后，运行对应样例回归：

```bash
.venv/bin/python scripts/dev/run_component_pdf_regression.py \
  --sample-id <sample-id>
```

交付前再运行相关的 conversion characterization tests，确保修复没有破坏既有转换行为。
