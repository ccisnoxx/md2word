---
doc_type: dev-guide
slug: component-pdf-regression-governance
component: conversion-runtime
status: current
summary: Brand/category sample governance and local regression workflow for electronic component PDFs.
tags: [conversion, mineru, regression, samples, datasheet]
last_reviewed: 2026-06-23
---

# Component PDF Regression Governance

## Purpose

Use this workflow when a local electronic component PDF exposes a conversion
layout issue that should not regress. The official conversion code remains
`app/conversion`; `md2word_main` is only a thin local shell and sample source.

This suite is separate from:

- P0 Golden Samples under `tests/fixtures/golden_samples/`
- P1 translation samples under `tests/fixtures/p1_translation_samples/`

## Sample Layout

Component samples live under:

```text
tests/fixtures/component_pdf_samples/
  manifest.yaml
  acceptance-record-template.md
  samples/<brand>/<category>/<sample-id>/mineru/
```

`brand`, `category`, and `sample-id` use lowercase kebab-case. The manifest owns
the review metadata: product, title, source PDF reference, MinerU package path,
tags, and acceptance focus.

## Add A New Local MinerU Sample

Start from a local MinerU result directory, usually discovered through
`md2word_main/mineru_result/`.

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/manage_component_pdf_samples.py \
  add-mineru-sample \
  --sample-id ti-opamp-opa228-p7-wide-table \
  --brand texas-instruments \
  --category op-amp \
  --product OPA228 \
  --title "OPA228 electrical characteristics wide table" \
  --source-pdf "md2word_main:test_pdf/OPA228_P7.pdf" \
  --mineru-package /Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_result/OPA228_P7.pdf-d457d448-c495-41ea-8bcf-41a3f18c00fb \
  --tag datasheet \
  --tag wide_table \
  --tag electrical_characteristics \
  --acceptance-focus "Wide electrical characteristics table remains editable" \
  --acceptance-focus "Units and symbols stay readable" \
  --apply
```

Run validation after adding:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/manage_component_pdf_samples.py validate
```

## Local Regression Loop

The intended loop is:

1. Discover a local issue in `md2word_main` or a worktree sandbox.
2. Add a minimized MinerU sample to `tests/fixtures/component_pdf_samples/`.
3. Fix behavior in `app/conversion`.
4. Run component regression:

   ```bash
   /Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_component_pdf_regression.py
   ```

5. Review the generated DOCX manually.
6. Record manual results using
   `tests/fixtures/component_pdf_samples/acceptance-record-template.md`.

Generated DOCX and reports are written under
`tests/tmp/component_pdf_regression/` by default. Do not commit generated DOCX,
rendered PNG/PDF files, or proprietary customer PDFs.

## Targeted Validation

For sample-governance changes:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_component_pdf_sample_governance
```

For conversion behavior changes caused by a component sample:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_component_pdf_regression.py \
  --sample-id <sample-id>
```

Then run the relevant conversion characterization tests before handoff.

