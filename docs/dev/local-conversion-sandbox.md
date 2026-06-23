---
doc_type: dev-guide
slug: local-conversion-sandbox
component: conversion-runtime
status: current
summary: Local MinerU conversion sandbox workflow with md2word as the single source of conversion code.
tags: [conversion, mineru, sandbox, regression]
last_reviewed: 2026-06-23
---

# Local Conversion Sandbox

## Decision

`/Users/sc/PycharmProjects/md2word` is the only long-lived source of conversion
code. Local experiments that start from MinerU result directories must use the
official `app/conversion` runtime through a thin developer entrypoint, not a
copied conversion tree in another project.

`/Users/sc/PycharmProjects/PythonProject/md2word_main` is treated as a legacy
local sandbox and sample-asset source. It may still contain useful `test_pdf/`
and `mineru_result/` assets, but its `app/conversion/` copy is not authoritative.

## Phase 1 Workflow

Run one local MinerU package through the official runtime:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_local_mineru_conversion.py \
  /Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \
  --output tests/tmp/local_conversion/OPA228_P1.docx \
  --document-language en \
  --translation-mode direct
```

The same command can be used from PyCharm. The script is intentionally thin: it
validates CLI options, configures local logging, and calls
`app.conversion.runtime_runner.run_conversion`.

If the input path is inconvenient to pass in a PyCharm run configuration, set:

```bash
export MD2WORD_LOCAL_MINERU_INPUT=/absolute/path/to/mineru_result/package
```

Then run:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_local_mineru_conversion.py \
  --output tests/tmp/local_conversion/output.docx
```

## Sandbox Drift Audit

Check whether the legacy sandbox copy has drifted from the official conversion
source:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/audit_conversion_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main \
  drift
```

By default, this compares:

- `app/conversion`
- `resources`

The command exits with status 1 when drift exists. That is deliberate: drift is
evidence to inspect, not a synchronization success. Use `--allow-drift` when the
goal is only to capture a report:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/audit_conversion_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main \
  drift --json --allow-drift
```

Do not resolve drift by copying the whole sandbox tree over the official repo.
Promote individual behavior changes through normal code review, focused tests,
and sample evidence.

## Sample Asset Inventory

Inventory local PDFs and MinerU result packages before migrating them into a
versioned regression suite:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/audit_conversion_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main \
  samples --json
```

The inventory reports:

- PDFs under `test_pdf/`
- MinerU package directories under `mineru_result/`
- likely source PDF names inferred from `*.pdf-<id>` package names
- presence of `*_content_list_v2.json`, legacy `*_content_list.json`, model,
  layout, block list, markdown, and images

Use this output to decide which assets should become formal regression samples.
Generated DOCX, rendered PNG/PDF, and ad hoc output directories should remain in
`tests/tmp/` or external artifacts, not in `resources/`.

## Phase 2 Thin-Shell Migration

Convert `md2word_main` from a copied conversion implementation into a local
debug shell only after reviewing the dry-run output:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/migrate_md2word_main_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main
```

The dry run reports the active duplicate directories that would be archived and
the thin-shell files that would be written. Apply the migration only with
explicit approval because it moves directories inside `md2word_main`:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/migrate_md2word_main_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main \
  --apply
```

The apply step moves active duplicate code into `_legacy_duplicate_core/` rather
than deleting it. The active sandbox root should then keep only:

- `mineru_to_docx.py`
- `config.py`
- `sandbox_config.json`
- `README.md`
- `test_pdf/`
- `mineru_result/`
- `out/`
- `tests/test_thin_shell.py`

Validate the resulting shell from the official repository:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/audit_conversion_sandbox.py \
  --sandbox-root /Users/sc/PycharmProjects/PythonProject/md2word_main \
  thin
```

Then validate the shell from inside `md2word_main`:

```bash
cd /Users/sc/PycharmProjects/PythonProject/md2word_main
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_thin_shell
/Users/sc/miniconda3/envs/md2word/bin/python mineru_to_docx.py
/Users/sc/miniconda3/envs/md2word/bin/python mineru_to_docx.py \
  mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \
  --output out/smoke.docx \
  --document-language en \
  --translation-mode direct
```

## Recommended Worktree Shape

For repeated local work, create a second working tree from the official repo:

```bash
git -C /Users/sc/PycharmProjects/md2word worktree add \
  /Users/sc/PycharmProjects/PythonProject/md2word_sandbox \
  -b local/pdf-regression
```

Use that worktree for PyCharm runs and local sample iterations. It still uses the
same Git history and makes drift visible through normal Git status and tests.
The legacy `md2word_main` directory can then be kept read-only until its useful
sample assets are migrated.

## Validation

After changing local conversion tooling, run:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_conversion_sandbox_dev_tools
```

When changing conversion behavior, also run the focused characterization tests:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_text_render_characterization \
  tests.test_page_layout_characterization \
  tests.test_render_table_from_html_characterization \
  tests.test_render_config_characterization \
  tests.test_input_adapter_characterization
```

Run `scripts/ops/check_release.py` before release-oriented handoff. Do not start
real MySQL, Redis/Celery, MinerU, OpenAI, or browser smoke tests as part of the
ordinary local sandbox loop unless a release gate explicitly asks for it.

## Risks And Manual Decisions

- `md2word_main/resources/term_rules/term_rules.v2.yaml` may contain useful local
  rules, but it must be reviewed and imported through the term-rule workflow
  rather than copied wholesale.
- Proprietary or customer PDFs should not be committed to this repo. Add a
  manifest pointer or private artifact reference instead.
- If a local sandbox output looks better, promote the smallest behavior change
  into `app/conversion` and cover it with a characterization test or a formal
  regression sample before declaring it stable.
