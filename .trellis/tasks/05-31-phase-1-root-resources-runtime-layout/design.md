---
doc_type: design
task: 05-31-phase-1-root-resources-runtime-layout
status: approved
parent: 05-31-project-directory-restructure
scope: root entrypoints, conversion runtime config, resources, runtime var root, fixtures, docs, and deploy layout
---

# Phase 1 root resources runtime layout design

## 1. Scope

This phase removes root-level layout noise and clarifies file ownership before
any domain-first application migration starts. It changes paths and imports, not
product behavior.

In scope:

- local development entrypoints
- conversion runtime config module location
- versioned resource tree
- mutable runtime state root
- test fixture/scratch layout
- docs archive/runbook layout
- deploy/docker ownership cleanup
- path references in code, tests, docs, examples, and ignore files

Out of scope:

- `app/domains/`
- repository/persistence architecture split
- moving `app/core/*_models.py`
- deleting `app/schemas/`
- changing HTTP contracts, conversion behavior, or worker semantics

## 2. Target root layout for this phase

```text
.
├── app/
├── deploy/
│   ├── env/
│   ├── hosts/
│   └── nginx/
├── docker/
│   ├── dev/
│   └── prod/
├── docs/
│   ├── api/
│   ├── archive/
│   │   └── planning/
│   ├── deploy/
│   ├── dev/
│   ├── runbooks/
│   └── testing/
├── resources/
│   ├── prompts/
│   │   └── translation_en2zh.md
│   ├── template_configs/
│   │   ├── datasheet_template.yaml
│   │   ├── md2docx.yaml
│   │   └── templates_manifest.yaml
│   ├── templates/
│   │   └── default/
│   │       └── datasheet_template.docx
│   └── term_rules/
│       ├── subscripts_dictionary.yaml
│       ├── subscripts_dictionary_bak.yaml
│       ├── term_rules.v2.yaml
│       └── translation_terms.csv
├── scripts/
│   ├── dev/
│   │   ├── run_api.py
│   │   ├── run_document_worker.py
│   │   └── run_stage_worker.py
│   └── ops/
├── tests/
│   ├── fixtures/
│   │   ├── golden_samples/
│   │   └── p1_translation_samples/
│   └── tmp/
└── var/
```

Tool convention directories such as `.claude/`, `.cursor/`, `.codestable/`,
`.trellis/`, `.idea/`, and project metadata files stay at root.

## 3. Path decisions

### Development entrypoints

Move root entrypoints directly:

- `run_api.py` -> `scripts/dev/run_api.py`
- `run_worker.py` -> `scripts/dev/run_stage_worker.py`
- `run_document_worker.py` -> `scripts/dev/run_document_worker.py`

These files remain direct-run scripts with `main()` where applicable and no
required CLI arguments.

### Conversion runtime config

Move root `config.py` to `app/conversion/runtime_config.py`.

Update imports:

- `from config import APP_CONFIG` -> `from app.conversion.runtime_config import APP_CONFIG`
- `from config import APP_CONFIG, ROOT_DIR` -> `from app.conversion.runtime_config import APP_CONFIG, ROOT_DIR`

`ROOT_DIR` should continue to resolve to repository root, not the conversion
package directory.

### Versioned resources

Move root resource directories into `resources/`.

Code defaults should point to:

- `resources/templates/default/datasheet_template.docx`
- `resources/template_configs/datasheet_template.yaml`
- `resources/template_configs/templates_manifest.yaml`
- `resources/term_rules/term_rules.v2.yaml`
- `resources/term_rules/translation_terms.csv`
- `resources/term_rules/subscripts_dictionary.yaml`
- `resources/prompts/translation_en2zh.md`

No old `template/`, `template_configs/`, or `prompt/` fallback path should
remain in active code.

### Runtime state

Change the default mutable runtime root from `data` to `var`.

Default runtime paths should become:

- `var/metadata.sqlite3`
- `var/object_artifacts`
- `var/config/templates`
- `var/config/template_state.json`
- `var/config/term_rules_store.json`
- `var/config/runtime_subscripts_dictionary.yaml`

`var/` should be ignored. Existing local `data/` contents are not migrated by
this phase because they are local runtime state, not versioned project assets.

### Test fixtures

Move:

- `tests/golden_samples/` -> `tests/fixtures/golden_samples/`
- `tests/p1_translation_samples/` -> `tests/fixtures/p1_translation_samples/`
- `tests/.tmp/` -> `tests/tmp/`

Update manifests and scripts to use the new fixture paths.

### Docs and deploy

Move:

- `docs/runbook.md` -> `docs/runbooks/backend.md`
- `docs/planning/` -> `docs/archive/planning/`
- `deploy/p0.env.example` -> `deploy/env/p0.env.example`

Host-specific deployment notes may move to `deploy/hosts/` if they are
machine/provider specific. Current user-facing deployment docs can remain under
`docs/deploy/`.

## 4. Verification strategy

Run targeted tests for each path family:

- conversion config and prompt/resource loading
- render config and template discovery
- fixture manifest parsing
- backend settings/path derivation
- OpenAPI export importability if path changes touch docs/api generation

Use `rg` as the final stale-reference check. Old paths should not remain in
active code or current docs. Old paths may remain only inside historical archive
docs when preserving history is more valuable than rewriting past notes.

## 5. Risks

- Path strings appear in tests, docs, deployment examples, manifests, and
  scripts; missing one can leave a broken local workflow.
- `ROOT_DIR` in moved conversion config must still point at repository root.
- `data/` may still exist locally but is ignored; implementation must not
  delete local runtime contents.
- Moving docs can break relative references.
